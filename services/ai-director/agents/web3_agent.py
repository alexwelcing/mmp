"""
web3_agent.py — On-chain operations via Base L2 and ERC-4337.

Handles:
  - Gasless NFT minting (ERC-4337 UserOperation via paymaster)
  - 0xSplits clone creation for royalty distribution
  - Royalty distribution triggering (keeper-bot friendly)

Key concepts:
  - ERC-4337 "account abstraction" lets us sponsor gas for new users.
  - The AI Director operational wallet submits signed UserOperations to
    a bundler (e.g. Pimlico), which submits them on-chain.
  - 0xSplits immutable splits automatically route royalties to all
    stakeholders when ``distribute()`` is called.
"""

from __future__ import annotations

import json
import logging
from typing import Any

import httpx
from eth_account import Account
from eth_account.messages import encode_defunct
from web3 import AsyncWeb3
from web3.types import TxReceipt

from config import Settings

logger = logging.getLogger(__name__)

# Minimal ABI snippets — only the functions we call.
_CHARACTER_NFT_ABI = json.loads("""[
  {
    "name": "mintFree",
    "type": "function",
    "inputs": [{"name": "to", "type": "address"}],
    "outputs": [{"name": "tokenId", "type": "uint256"}]
  },
  {
    "name": "mintRandom",
    "type": "function",
    "inputs": [{"name": "to", "type": "address"}],
    "outputs": [{"name": "tokenId", "type": "uint256"}]
  },
  {
    "name": "mintCustom",
    "type": "function",
    "inputs": [
      {"name": "to", "type": "address"},
      {"name": "traits", "type": "tuple",
       "components": [
         {"name": "role", "type": "uint8"},
         {"name": "aesthetic", "type": "uint8"},
         {"name": "rarity", "type": "uint8"}
       ]}
    ],
    "outputs": [{"name": "tokenId", "type": "uint256"}]
  },
  {
    "name": "setTokenURI",
    "type": "function",
    "inputs": [
      {"name": "tokenId", "type": "uint256"},
      {"name": "uri", "type": "string"}
    ],
    "outputs": []
  }
]""")

_SPLITS_ABI = json.loads("""[
  {
    "name": "createSplit",
    "type": "function",
    "inputs": [
      {"name": "accounts", "type": "address[]"},
      {"name": "percentAllocations", "type": "uint32[]"},
      {"name": "distributorFee", "type": "uint32"},
      {"name": "controller", "type": "address"}
    ],
    "outputs": [{"name": "split", "type": "address"}]
  },
  {
    "name": "distributeETH",
    "type": "function",
    "inputs": [
      {"name": "split", "type": "address"},
      {"name": "accounts", "type": "address[]"},
      {"name": "percentAllocations", "type": "uint32[]"},
      {"name": "distributorFee", "type": "uint32"},
      {"name": "distributorAddress", "type": "address"}
    ],
    "outputs": []
  }
]""")

# Canonical ERC-4337 v0.6 EntryPoint — used to compute the proper UserOp hash.
_ENTRYPOINT_ADDRESS = "0x5FF137D4b0FDCD49DcA30c7CF57E578a026d2789"

_ENTRYPOINT_ABI = json.loads("""[
  {
    "inputs": [
      {
        "components": [
          {"name": "sender", "type": "address"},
          {"name": "nonce", "type": "uint256"},
          {"name": "initCode", "type": "bytes"},
          {"name": "callData", "type": "bytes"},
          {"name": "callGasLimit", "type": "uint256"},
          {"name": "verificationGasLimit", "type": "uint256"},
          {"name": "preVerificationGas", "type": "uint256"},
          {"name": "maxFeePerGas", "type": "uint256"},
          {"name": "maxPriorityFeePerGas", "type": "uint256"},
          {"name": "paymasterAndData", "type": "bytes"},
          {"name": "signature", "type": "bytes"}
        ],
        "name": "userOp",
        "type": "tuple"
      }
    ],
    "name": "getUserOpHash",
    "outputs": [{"name": "", "type": "bytes32"}],
    "stateMutability": "view",
    "type": "function"
  }
]""")


class Web3Agent:
    """
    Submits on-chain transactions for character minting and royalty splits.

    All mints use ERC-4337 UserOperations so new users never pay gas.
    """

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._w3 = AsyncWeb3(AsyncWeb3.AsyncHTTPProvider(str(settings.base_rpc_url)))
        self._account = Account.from_key(settings.ai_director_private_key)
        self._local_mode = settings.environment == "local"

        self._nft_contract = self._w3.eth.contract(
            address=settings.character_nft_address,
            abi=_CHARACTER_NFT_ABI,
        )
        self._splits_contract = self._w3.eth.contract(
            address=settings.splits_factory_address,
            abi=_SPLITS_ABI,
        )
        self._entrypoint = self._w3.eth.contract(
            address=_ENTRYPOINT_ADDRESS,
            abi=_ENTRYPOINT_ABI,
        )

    # ------------------------------------------------------------------ #
    # Minting                                                              #
    # ------------------------------------------------------------------ #

    async def mint_character(
        self,
        to_address: str,
        metadata_uri: str,
        traits: dict[str, int] | None = None,
        tier: str = "free",
    ) -> int:
        """
        Mint a CharacterNFT to `to_address` via a gasless ERC-4337 UserOp.

        Args:
            to_address:   Recipient wallet address (checksummed).
            metadata_uri: IPFS / Filestore URL for the character's metadata.
            traits:       Optional trait overrides for custom mints.
            tier:         "free", "random", or "custom".

        Returns:
            The newly minted token ID.
        """
        logger.info("Minting character NFT for %s (tier=%s)", to_address, tier)

        if tier == "custom" and traits:
            call_data = self._nft_contract.encodeABI(
                fn_name="mintCustom",
                args=[to_address, (traits["role"], traits["aesthetic"], traits["rarity"])],
            )
        elif tier == "random":
            call_data = self._nft_contract.encodeABI(
                fn_name="mintRandom",
                args=[to_address],
            )
        else:
            call_data = self._nft_contract.encodeABI(
                fn_name="mintFree",
                args=[to_address],
            )

        tx_hash = await self._submit_user_operation(
            target=self._settings.character_nft_address,
            call_data=call_data,
        )

        receipt = await self._wait_for_receipt(tx_hash)
        token_id = self._parse_token_id_from_receipt(receipt)

        # Attach metadata URI in a second transaction.
        if metadata_uri:
            set_uri_data = self._nft_contract.encodeABI(
                fn_name="setTokenURI",
                args=[token_id, metadata_uri],
            )
            uri_tx_hash = await self._submit_user_operation(
                target=self._settings.character_nft_address,
                call_data=set_uri_data,
            )
            await self._wait_for_receipt(uri_tx_hash)
            logger.info("Set token URI for token %d, tx=%s", token_id, uri_tx_hash)

        logger.info("Minted token %d, tx=%s", token_id, tx_hash)
        return token_id

    # ------------------------------------------------------------------ #
    # Splits                                                               #
    # ------------------------------------------------------------------ #

    async def setup_splits(
        self,
        dev_wallet: str,
        ai_ops_wallet: str,
        dev_pct: int = 80,
    ) -> str:
        """
        Create an immutable 0xSplits contract for royalty distribution.

        Args:
            dev_wallet:    Developer team wallet address.
            ai_ops_wallet: AI operational wallet (pays for inference costs).
            dev_pct:       Developer percentage (0–100); rest goes to ai_ops.

        Returns:
            The address of the newly created splits contract.
        """
        ops_pct = 100 - dev_pct
        # 0xSplits uses 1e6 scale for percentages.
        allocations = [dev_pct * 10_000, ops_pct * 10_000]
        # 1% distributor fee incentivises keeper bots to call distribute().
        distributor_fee = 10_000  # 1% in 1e6 scale

        call_data = self._splits_contract.encodeABI(
            fn_name="createSplit",
            args=[
                [dev_wallet, ai_ops_wallet],
                allocations,
                distributor_fee,
                "0x0000000000000000000000000000000000000000",  # immutable
            ],
        )

        tx_hash = await self._submit_user_operation(
            target=self._settings.splits_factory_address,
            call_data=call_data,
        )
        receipt = await self._wait_for_receipt(tx_hash)
        split_address = self._parse_split_address_from_receipt(receipt)
        logger.info("Created splits contract at %s", split_address)
        return split_address

    async def trigger_distribution(
        self,
        split_address: str,
        accounts: list[str],
        allocations: list[int],
    ) -> str:
        """
        Call distributeETH() on a splits contract.

        This is typically called by a keeper bot which earns the 1%
        distributor fee as an incentive.

        Returns:
            Transaction hash.
        """
        distributor_fee = 10_000  # must match createSplit value
        call_data = self._splits_contract.encodeABI(
            fn_name="distributeETH",
            args=[
                split_address,
                accounts,
                allocations,
                distributor_fee,
                self._account.address,
            ],
        )
        tx_hash = await self._submit_user_operation(
            target=self._settings.splits_factory_address,
            call_data=call_data,
        )
        logger.info("Distribution triggered; tx=%s", tx_hash)
        return tx_hash

    # ------------------------------------------------------------------ #
    # ERC-4337 helpers                                                     #
    # ------------------------------------------------------------------ #

    async def _submit_user_operation(
        self, target: str, call_data: bytes | str
    ) -> str:
        """
        Build, sign, and submit an ERC-4337 UserOperation via the bundler.

        In local development mode we bypass the bundler and send a direct
        EOA transaction instead — no EntryPoint or paymaster is required.

        Returns:
            The transaction hash once the bundler submits the UserOp.
        """
        if isinstance(call_data, bytes):
            call_data = call_data.hex()
        call_data_hex = call_data if call_data.startswith("0x") else f"0x{call_data}"

        if self._local_mode:
            return await self._send_direct_transaction(target, call_data_hex)

        nonce = await self._w3.eth.get_transaction_count(self._account.address)

        # Build the UserOp tuple exactly as EntryPoint expects.
        user_op: dict[str, Any] = {
            "sender": self._account.address,
            "nonce": nonce,
            "initCode": "0x",
            "callData": call_data_hex,
            "callGasLimit": 200_000,
            "verificationGasLimit": 150_000,
            "preVerificationGas": 21_000,
            "maxFeePerGas": await self._w3.eth.gas_price,
            "maxPriorityFeePerGas": 1_000_000_000,
            "paymasterAndData": (
                self._settings.paymaster_address
                if self._settings.paymaster_address
                else "0x"
            ),
            "signature": b"",
        }

        # Ask the EntryPoint for the canonical hash (includes chain ID).
        op_hash = await self._entrypoint.functions.getUserOpHash(user_op).call()
        logger.debug("UserOp hash: %s", op_hash.hex())

        # Sign the 32-byte hash directly (ERC-191 style via encode_defunct).
        signed = self._account.sign_message(encode_defunct(op_hash))
        user_op["signature"] = signed.signature

        # Hex-ify for JSON-RPC (bundler expects hex strings).
        user_op_hex: dict[str, Any] = {
            "sender": user_op["sender"],
            "nonce": hex(user_op["nonce"]),
            "initCode": user_op["initCode"],
            "callData": user_op["callData"],
            "callGasLimit": hex(user_op["callGasLimit"]),
            "verificationGasLimit": hex(user_op["verificationGasLimit"]),
            "preVerificationGas": hex(user_op["preVerificationGas"]),
            "maxFeePerGas": hex(user_op["maxFeePerGas"]),
            "maxPriorityFeePerGas": hex(user_op["maxPriorityFeePerGas"]),
            "paymasterAndData": user_op["paymasterAndData"],
            "signature": "0x" + user_op["signature"].hex(),
        }

        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                str(self._settings.bundler_url),
                json={
                    "jsonrpc": "2.0",
                    "method": "eth_sendUserOperation",
                    "params": [
                        user_op_hex,
                        _ENTRYPOINT_ADDRESS,
                    ],
                    "id": 1,
                },
            )
            resp.raise_for_status()
            result = resp.json()

        if "error" in result:
            raise RuntimeError(f"Bundler error: {result['error']}")

        return result["result"]

    async def _send_direct_transaction(self, target: str, call_data: str) -> str:
        """Send a direct EOA transaction (used in local dev mode)."""
        nonce = await self._w3.eth.get_transaction_count(self._account.address)
        gas_price = await self._w3.eth.gas_price

        tx = {
            "from": self._account.address,
            "to": target,
            "data": call_data,
            "nonce": nonce,
            "gas": 500_000,
            "maxFeePerGas": gas_price,
            "maxPriorityFeePerGas": 1_000_000_000,
            "chainId": await self._w3.eth.chain_id,
            "value": 0,
        }

        signed = self._account.sign_transaction(tx)
        tx_hash = await self._w3.eth.send_raw_transaction(signed.rawTransaction)
        return tx_hash.hex()

    async def _wait_for_receipt(self, tx_hash: str) -> TxReceipt:
        """Poll for a transaction receipt (30-second timeout)."""
        return await self._w3.eth.wait_for_transaction_receipt(
            tx_hash, timeout=30
        )

    @staticmethod
    def _parse_token_id_from_receipt(receipt: TxReceipt) -> int:
        """Extract the newly minted token ID from CharacterMinted event logs."""
        # CharacterMinted(address indexed to, uint256 indexed tokenId, ...)
        # has 3 topics: event signature, to, tokenId.
        for log in receipt.get("logs", []):
            topics = log.get("topics", [])
            if len(topics) >= 3:
                # topic[0] is the event signature hash.
                # topic[1] is indexed to, topic[2] is indexed tokenId.
                return int(topics[2].hex(), 16)
        return 0

    @staticmethod
    def _parse_split_address_from_receipt(receipt: TxReceipt) -> str:
        """Extract the new split contract address from CreateSplit event."""
        for log in receipt.get("logs", []):
            if len(log.get("topics", [])) >= 2:
                # CreateSplit(address split) — split address is the first topic.
                raw = log["topics"][1]
                return AsyncWeb3.to_checksum_address("0x" + raw.hex()[-40:])
        return "0x0000000000000000000000000000000000000000"
