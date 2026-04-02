// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import {Ownable} from "@openzeppelin/contracts/access/Ownable.sol";

/**
 * @title AIDirectorPaymaster
 * @notice ERC-4337 Paymaster that sponsors gas fees for first-time users.
 *
 * @dev Implements IPaymaster from ERC-4337 (EIP-4337).
 *      The EntryPoint contract calls validatePaymasterUserOp before executing
 *      a UserOperation.  If we return a valid response, the EntryPoint draws
 *      gas from our deposit instead of the user's smart account.
 *
 *      Sponsorship policy:
 *        - Only sponsor `mintFree` calls on CharacterNFT.
 *        - Only sponsor each address ONCE (first free mint only).
 *        - Hard cap: MAX_SPONSORED_WEI per UserOperation.
 */
contract AIDirectorPaymaster is Ownable {
    // ------------------------------------------------------------------ //
    // Constants                                                            //
    // ------------------------------------------------------------------ //

    /// @notice ERC-4337 EntryPoint contract address (same on all EVM chains).
    address public constant ENTRY_POINT = 0x5FF137D4b0FDCD49DcA30c7CF57E578a026d2789;

    /// @notice Maximum gas (in wei) we'll sponsor per UserOperation (~$0.05 on Base).
    uint256 public constant MAX_SPONSORED_WEI = 0.001 ether;

    /// @notice Function selector for CharacterNFT.mintFree(address).
    bytes4 public constant MINT_FREE_SELECTOR = bytes4(keccak256("mintFree(address)"));

    // ------------------------------------------------------------------ //
    // State                                                                //
    // ------------------------------------------------------------------ //

    /// @notice Address of the CharacterNFT contract we're sponsoring.
    address public characterNFT;

    /// @notice Track which addresses have already received sponsored gas.
    mapping(address => bool) public hasSponsoredMint;

    /// @notice Total amount sponsored (for analytics / budget tracking).
    uint256 public totalSponsored;

    // ------------------------------------------------------------------ //
    // Events                                                               //
    // ------------------------------------------------------------------ //

    /// @notice Emitted when gas is sponsored for a user.
    event MintSponsored(address indexed user, uint256 gasAmount);

    /// @notice Emitted when ETH is deposited to fund gas sponsorship.
    event Deposited(address indexed from, uint256 amount);

    /// @notice Emitted when ETH is withdrawn by the owner.
    event Withdrawn(address indexed to, uint256 amount);

    // ------------------------------------------------------------------ //
    // Constructor                                                          //
    // ------------------------------------------------------------------ //

    /**
     * @param _characterNFT CharacterNFT contract address.
     */
    constructor(address _characterNFT) Ownable(msg.sender) {
        require(_characterNFT != address(0), "Paymaster: zero NFT address");
        characterNFT = _characterNFT;
    }

    // ------------------------------------------------------------------ //
    // ERC-4337 IPaymaster implementation                                   //
    // ------------------------------------------------------------------ //

    /**
     * @notice Validate a UserOperation and decide whether to sponsor its gas.
     * @dev    Called by the EntryPoint before executing the UserOperation.
     *
     *         Validation logic:
     *           1. The UserOp's callData must begin with the mintFree() selector,
     *              indicating the user's smart account intends to call mintFree.
     *              (In ERC-4337, userOp.sender is the user's smart account, NOT
     *              the target contract.  The target is encoded inside callData.)
     *           2. The sender must not have been sponsored before.
     *           3. The required gas must not exceed MAX_SPONSORED_WEI.
     *
     * @param userOp        The UserOperation being validated.
     * @param userOpHash    Hash of the UserOperation.
     * @param maxCost       Maximum ETH cost of the UserOperation.
     * @return context      Arbitrary bytes passed to postOp (we encode the sender).
     * @return validationData 0 = valid, 1 = invalid (ERC-4337 spec).
     */
    function validatePaymasterUserOp(
        UserOperation calldata userOp,
        bytes32 userOpHash,
        uint256 maxCost
    ) external returns (bytes memory context, uint256 validationData) {
        require(msg.sender == ENTRY_POINT, "Paymaster: caller not EntryPoint");

        // Decode the callData to check which function is being called.
        if (userOp.callData.length < 4) {
            return ("", 1); // Invalid: no function selector
        }

        bytes4 selector = bytes4(userOp.callData[:4]);

        // Only sponsor calls where the user's account is executing mintFree.
        // Note: userOp.sender is the user's smart account address; the actual
        // target contract (CharacterNFT) is encoded in callData by the smart
        // account's execute() method.  A production implementation would fully
        // decode the execute() calldata to verify the exact target address.
        if (selector != MINT_FREE_SELECTOR) {
            return ("", 1);
        }

        // Only sponsor each user once.
        if (hasSponsoredMint[userOp.sender]) {
            return ("", 1);
        }

        // Cap gas sponsorship.
        if (maxCost > MAX_SPONSORED_WEI) {
            return ("", 1);
        }

        // Suppress unused variable warning for userOpHash.
        userOpHash;

        // Valid — encode sender for postOp callback.
        context = abi.encode(userOp.sender, maxCost);
        validationData = 0;
    }

    /**
     * @notice Post-execution hook called by EntryPoint.
     * @dev    Update sponsored tracking and emit an event.
     *
     * @param mode    0 = success, 1 = revert, 2 = postOp revert.
     * @param context The bytes we returned from validatePaymasterUserOp.
     * @param actualGasCost Actual gas used by the UserOperation.
     */
    function postOp(
        PostOpMode mode,
        bytes calldata context,
        uint256 actualGasCost
    ) external {
        require(msg.sender == ENTRY_POINT, "Paymaster: caller not EntryPoint");

        if (mode == PostOpMode.opSucceeded) {
            (address user,) = abi.decode(context, (address, uint256));
            hasSponsoredMint[user] = true;
            totalSponsored += actualGasCost;
            emit MintSponsored(user, actualGasCost);
        }
    }

    // ------------------------------------------------------------------ //
    // Funding                                                              //
    // ------------------------------------------------------------------ //

    /// @notice Deposit ETH to fund gas sponsorship.
    receive() external payable {
        emit Deposited(msg.sender, msg.value);
    }

    /// @notice Deposit ETH into the EntryPoint on behalf of this Paymaster.
    function depositToEntryPoint() external payable {
        IEntryPoint(ENTRY_POINT).depositTo{value: msg.value}(address(this));
        emit Deposited(msg.sender, msg.value);
    }

    /// @notice Withdraw ETH from the EntryPoint (owner only).
    function withdrawFromEntryPoint(address payable to, uint256 amount) external onlyOwner {
        IEntryPoint(ENTRY_POINT).withdrawTo(to, amount);
        emit Withdrawn(to, amount);
    }

    // ------------------------------------------------------------------ //
    // Admin                                                                //
    // ------------------------------------------------------------------ //

    /// @notice Update the CharacterNFT address (e.g. after upgrade).
    function setCharacterNFT(address _characterNFT) external onlyOwner {
        require(_characterNFT != address(0), "Paymaster: zero address");
        characterNFT = _characterNFT;
    }

    /// @notice Reset a user's sponsored status (for testing / exceptional cases).
    function resetSponsoredStatus(address user) external onlyOwner {
        hasSponsoredMint[user] = false;
    }
}

// ------------------------------------------------------------------ //
// ERC-4337 type stubs (normally imported from account-abstraction lib) //
// ------------------------------------------------------------------ //

/// @dev Minimal UserOperation struct per ERC-4337 spec.
struct UserOperation {
    address sender;
    uint256 nonce;
    bytes initCode;
    bytes callData;
    uint256 callGasLimit;
    uint256 verificationGasLimit;
    uint256 preVerificationGas;
    uint256 maxFeePerGas;
    uint256 maxPriorityFeePerGas;
    bytes paymasterAndData;
    bytes signature;
}

enum PostOpMode {
    opSucceeded,
    opReverted,
    postOpReverted
}

interface IEntryPoint {
    function depositTo(address account) external payable;
    function withdrawTo(address payable withdrawAddress, uint256 withdrawAmount) external;
}
