// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import {ERC721} from "@openzeppelin/contracts/token/ERC721/ERC721.sol";
import {ERC721URIStorage} from "@openzeppelin/contracts/token/ERC721/extensions/ERC721URIStorage.sol";
import {Ownable} from "@openzeppelin/contracts/access/Ownable.sol";
import {ReentrancyGuard} from "@openzeppelin/contracts/utils/ReentrancyGuard.sol";
import {IERC20} from "@openzeppelin/contracts/token/ERC20/IERC20.sol";

/**
 * @title CharacterNFT
 * @notice ERC-721 contract for AI-generated game characters with three mint tiers:
 *         1. Free mint (one per address, gasless via Paymaster)
 *         2. Random paid mint ($1 USDC on Base)
 *         3. Custom premium mint ($9.99 USDC, user-specified traits)
 *
 * @dev Integrates with Story Protocol for IP asset registration (stubbed).
 *      Random trait generation uses block entropy — not suitable for high-value
 *      randomness; upgrade to Chainlink VRF for production.
 */
contract CharacterNFT is ERC721URIStorage, Ownable, ReentrancyGuard {
    // ------------------------------------------------------------------ //
    // Types                                                                //
    // ------------------------------------------------------------------ //

    /// @notice Character role archetypes.
    enum Role {
        Warrior,   // 0
        Mage,      // 1
        Scout,     // 2
        Healer,    // 3
        Assassin,  // 4
        Berserker, // 5
        Paladin    // 6
    }

    /// @notice Visual aesthetic styles.
    enum Aesthetic {
        Fantasy,     // 0
        SciFi,       // 1
        Cyberpunk,   // 2
        Steampunk,   // 3
        Mythological // 4
    }

    /// @notice Rarity tiers — higher is rarer.
    enum Rarity {
        Common,    // 0 — 50% probability
        Uncommon,  // 1 — 30%
        Rare,      // 2 — 15%
        Epic,      // 3 — 4%
        Legendary  // 4 — 1%
    }

    /// @notice Packed character traits stored on-chain.
    struct CharacterTraits {
        Role      role;
        Aesthetic aesthetic;
        Rarity    rarity;
    }

    // ------------------------------------------------------------------ //
    // State                                                                //
    // ------------------------------------------------------------------ //

    /// @notice Price for a random paid roll (1 USDC = 1e6).
    uint256 public constant RANDOM_ROLL_PRICE = 1e6;

    /// @notice Price for a custom character (9.99 USDC ≈ 9_990_000).
    uint256 public constant CUSTOM_MINT_PRICE = 9_990_000;

    /// @notice USDC token contract on Base.
    IERC20 public immutable usdc;

    /// @notice Address that receives USDC payments.
    address public paymentRecipient;

    /// @notice Running token ID counter.
    uint256 private _nextTokenId;

    /// @notice Traits for each minted token.
    mapping(uint256 => CharacterTraits) public tokenTraits;

    /// @notice Track which addresses have claimed their free mint.
    mapping(address => bool) public hasFreeMint;

    /// @notice Only the paymaster contract can call mintFree.
    address public paymaster;

    // ------------------------------------------------------------------ //
    // Events                                                               //
    // ------------------------------------------------------------------ //

    /// @notice Emitted when a new character is minted.
    event CharacterMinted(
        address indexed to,
        uint256 indexed tokenId,
        Role role,
        Aesthetic aesthetic,
        Rarity rarity,
        bool isFree
    );

    /// @notice Emitted when the paymaster address is updated.
    event PaymasterUpdated(address indexed newPaymaster);

    /// @notice Emitted when payment recipient is updated.
    event PaymentRecipientUpdated(address indexed newRecipient);

    // ------------------------------------------------------------------ //
    // Constructor                                                          //
    // ------------------------------------------------------------------ //

    /**
     * @param _usdc             USDC token address on Base.
     * @param _paymentRecipient Wallet that receives mint revenue.
     * @param _paymaster        AIDirectorPaymaster contract address.
     */
    constructor(
        address _usdc,
        address _paymentRecipient,
        address _paymaster
    ) ERC721("MMP Character", "MMPC") Ownable(msg.sender) {
        require(_usdc != address(0), "CharacterNFT: zero USDC address");
        require(_paymentRecipient != address(0), "CharacterNFT: zero recipient");
        usdc = IERC20(_usdc);
        paymentRecipient = _paymentRecipient;
        paymaster = _paymaster;
    }

    // ------------------------------------------------------------------ //
    // Minting                                                              //
    // ------------------------------------------------------------------ //

    /**
     * @notice Mint one free character to `to`.
     * @dev    One free mint per address, enforced via `hasFreeMint`.
     *         Only callable by the Paymaster contract (which sponsors gas).
     *         The AI Director calls this via an ERC-4337 UserOperation.
     *
     * @param to Recipient address.
     * @return tokenId The newly minted token ID.
     */
    function mintFree(address to) external nonReentrant returns (uint256 tokenId) {
        require(
            msg.sender == paymaster || msg.sender == owner(),
            "CharacterNFT: caller not paymaster"
        );
        require(!hasFreeMint[to], "CharacterNFT: free mint already claimed");

        hasFreeMint[to] = true;
        tokenId = _mintCharacter(to, _randomTraits(to, 0), true);
    }

    /**
     * @notice Mint a random character for RANDOM_ROLL_PRICE USDC.
     * @dev    Caller must have approved this contract to spend USDC.
     *
     * @param to Recipient address (may differ from msg.sender for gifting).
     * @return tokenId The newly minted token ID.
     */
    function mintRandom(address to) external nonReentrant returns (uint256 tokenId) {
        require(to != address(0), "CharacterNFT: zero recipient");
        usdc.transferFrom(msg.sender, paymentRecipient, RANDOM_ROLL_PRICE);
        tokenId = _mintCharacter(to, _randomTraits(to, _nextTokenId), false);
    }

    /**
     * @notice Mint a custom character with specified traits for CUSTOM_MINT_PRICE USDC.
     * @dev    Allows players to choose their role and aesthetic; rarity is still random.
     *
     * @param to     Recipient address.
     * @param traits Desired traits (rarity is overridden by random selection).
     * @return tokenId The newly minted token ID.
     */
    function mintCustom(
        address to,
        CharacterTraits memory traits
    ) external nonReentrant returns (uint256 tokenId) {
        require(to != address(0), "CharacterNFT: zero recipient");
        usdc.transferFrom(msg.sender, paymentRecipient, CUSTOM_MINT_PRICE);

        // Rarity is random even for custom mints — preserves game balance.
        traits.rarity = _randomRarity(to, _nextTokenId);
        tokenId = _mintCharacter(to, traits, false);
    }

    // ------------------------------------------------------------------ //
    // Views                                                                //
    // ------------------------------------------------------------------ //

    /**
     * @notice Return all traits for a given token.
     * @param tokenId Token to query.
     */
    function getTraits(uint256 tokenId) external view returns (CharacterTraits memory) {
        require(_ownerOf(tokenId) != address(0), "CharacterNFT: token does not exist");
        return tokenTraits[tokenId];
    }

    // ------------------------------------------------------------------ //
    // Admin                                                                //
    // ------------------------------------------------------------------ //

    /// @notice Update the paymaster address (e.g. after redeployment).
    function setPaymaster(address _paymaster) external onlyOwner {
        require(_paymaster != address(0), "CharacterNFT: zero paymaster");
        paymaster = _paymaster;
        emit PaymasterUpdated(_paymaster);
    }

    /// @notice Update the payment recipient (e.g. to point at CharacterSplits).
    function setPaymentRecipient(address _recipient) external onlyOwner {
        require(_recipient != address(0), "CharacterNFT: zero recipient");
        paymentRecipient = _recipient;
        emit PaymentRecipientUpdated(_recipient);
    }

    /**
     * @notice Set the token URI for a minted token (called by AI Director after
     *         off-chain asset generation completes).
     * @param tokenId Token to update.
     * @param uri     IPFS or HTTPS URI for the character metadata JSON.
     */
    function setTokenURI(uint256 tokenId, string calldata uri) external {
        require(
            msg.sender == owner() || msg.sender == paymaster,
            "CharacterNFT: not authorised"
        );
        _setTokenURI(tokenId, uri);
    }

    // ------------------------------------------------------------------ //
    // Internal                                                             //
    // ------------------------------------------------------------------ //

    /// @dev Core mint logic — shared by all three public mint functions.
    function _mintCharacter(
        address to,
        CharacterTraits memory traits,
        bool isFree
    ) internal returns (uint256 tokenId) {
        tokenId = _nextTokenId++;
        _safeMint(to, tokenId);
        tokenTraits[tokenId] = traits;

        emit CharacterMinted(to, tokenId, traits.role, traits.aesthetic, traits.rarity, isFree);
    }

    /**
     * @dev Generate pseudo-random traits from block entropy and address.
     *
     *      ⚠️  SECURITY WARNING: block.prevrandao and block.timestamp are
     *      influenceable by validators and must NOT be used for high-value
     *      randomness.  For production games where NFT rarity has real monetary
     *      value, replace this with Chainlink VRF v2+ or a commit-reveal scheme.
     *      This implementation is acceptable only for low-stakes tutorials.
     */
    function _randomTraits(
        address to,
        uint256 salt
    ) internal view returns (CharacterTraits memory) {
        uint256 seed = uint256(
            keccak256(abi.encodePacked(block.prevrandao, block.timestamp, to, salt))
        );
        return CharacterTraits({
            role:      Role(seed % 7),
            aesthetic: Aesthetic((seed >> 8) % 5),
            rarity:    _randomRarity(to, salt)
        });
    }

    /// @dev Weighted rarity roll: 50% Common, 30% Uncommon, 15% Rare, 4% Epic, 1% Legendary.
    function _randomRarity(address to, uint256 salt) internal view returns (Rarity) {
        uint256 roll = uint256(
            keccak256(abi.encodePacked(block.prevrandao, block.timestamp, to, salt, "rarity"))
        ) % 100;

        if (roll < 50) return Rarity.Common;
        if (roll < 80) return Rarity.Uncommon;
        if (roll < 95) return Rarity.Rare;
        if (roll < 99) return Rarity.Epic;
        return Rarity.Legendary;
    }
}
