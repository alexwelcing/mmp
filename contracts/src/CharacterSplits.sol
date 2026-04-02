// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import {Ownable} from "@openzeppelin/contracts/access/Ownable.sol";
import {ReentrancyGuard} from "@openzeppelin/contracts/utils/ReentrancyGuard.sol";

/**
 * @title CharacterSplits
 * @notice 0xSplits-compatible immutable royalty distribution contract.
 *
 * @dev Manages proportional ETH/ERC-20 distribution to multiple recipients.
 *      Inspired by 0xSplits (https://splits.org) but simplified for tutorial
 *      clarity.  Use the official 0xSplits contracts in production for
 *      gas efficiency and audited security.
 *
 *      Key design decisions:
 *        - Allocations are IMMUTABLE once set (trustless for recipients).
 *        - A 1% distributor fee incentivises keeper bots to call distribute().
 *        - The factory pattern allows cheap clone deployment per character.
 */
contract CharacterSplits is Ownable, ReentrancyGuard {
    // ------------------------------------------------------------------ //
    // Types                                                                //
    // ------------------------------------------------------------------ //

    /// @notice A single split recipient with their allocation in basis points.
    struct Recipient {
        address account;
        uint32  allocation; // Basis points (1e4 = 100%). Sum must equal 1e6.
    }

    // ------------------------------------------------------------------ //
    // Constants                                                            //
    // ------------------------------------------------------------------ //

    /// @notice Allocation scale (1e6 = 100%).
    uint32 public constant ALLOCATION_SCALE = 1_000_000;

    /// @notice Distributor fee: 1% of distributed amount.
    uint32 public constant DISTRIBUTOR_FEE = 10_000;  // 1% of ALLOCATION_SCALE

    // ------------------------------------------------------------------ //
    // State                                                                //
    // ------------------------------------------------------------------ //

    /// @notice Immutable list of recipients set at deployment.
    Recipient[] public recipients;

    /// @notice Whether this split has been initialised (clone-safe).
    bool public initialised;

    // ------------------------------------------------------------------ //
    // Events                                                               //
    // ------------------------------------------------------------------ //

    /// @notice Emitted when a split is initialised.
    event SplitCreated(address[] accounts, uint32[] allocations);

    /// @notice Emitted when ETH is distributed.
    event Distributed(
        address indexed distributor,
        uint256 totalAmount,
        uint256 distributorFee,
        uint256 recipientAmount
    );

    /// @notice Emitted when an individual recipient receives their share.
    event RecipientPaid(address indexed recipient, uint256 amount);

    // ------------------------------------------------------------------ //
    // Initialiser (used by factory clone pattern)                          //
    // ------------------------------------------------------------------ //

    /**
     * @notice Initialise the split with recipients and allocations.
     * @dev    Can only be called once.  Allocations must sum to ALLOCATION_SCALE
     *         minus DISTRIBUTOR_FEE (1% reserved for the distributor).
     *
     * @param accounts    Ordered list of recipient addresses.
     * @param allocations Corresponding allocations in basis points (sum = 990_000).
     */
    function initialise(
        address[] calldata accounts,
        uint32[]  calldata allocations
    ) external {
        require(!initialised, "CharacterSplits: already initialised");
        require(accounts.length > 0,                    "CharacterSplits: no recipients");
        require(accounts.length == allocations.length,  "CharacterSplits: length mismatch");

        uint32 total = 0;
        for (uint256 i = 0; i < accounts.length; i++) {
            require(accounts[i] != address(0), "CharacterSplits: zero address");
            require(allocations[i] > 0,        "CharacterSplits: zero allocation");
            recipients.push(Recipient({account: accounts[i], allocation: allocations[i]}));
            total += allocations[i];
        }

        // Total recipient allocations + distributor fee must equal ALLOCATION_SCALE.
        require(
            total == ALLOCATION_SCALE - DISTRIBUTOR_FEE,
            "CharacterSplits: allocations must sum to 990000"
        );

        initialised = true;
        emit SplitCreated(accounts, allocations);
    }

    // ------------------------------------------------------------------ //
    // Distribution                                                         //
    // ------------------------------------------------------------------ //

    /**
     * @notice Distribute the contract's entire ETH balance to all recipients.
     * @dev    Callable by anyone — the caller earns the 1% distributor fee.
     *         This incentivises keeper bots to call distribute() regularly,
     *         ensuring recipients receive their funds promptly.
     *
     *         Gas note: iterating over recipients is O(n).  Keep n small
     *         (≤10) to avoid block gas limit issues.
     */
    function distribute() external nonReentrant {
        require(initialised, "CharacterSplits: not initialised");

        uint256 balance = address(this).balance;
        require(balance > 0, "CharacterSplits: nothing to distribute");

        // 1% to the distributor (keeper bot incentive).
        uint256 distributorShare = (balance * DISTRIBUTOR_FEE) / ALLOCATION_SCALE;
        uint256 remaining = balance - distributorShare;

        // Distribute remaining proportionally to recipients.
        for (uint256 i = 0; i < recipients.length; i++) {
            Recipient memory r = recipients[i];
            uint256 share = (remaining * r.allocation) / (ALLOCATION_SCALE - DISTRIBUTOR_FEE);
            if (share > 0) {
                (bool ok,) = payable(r.account).call{value: share}("");
                require(ok, "CharacterSplits: transfer failed");
                emit RecipientPaid(r.account, share);
            }
        }

        // Pay the distributor last (checks-effects-interactions pattern).
        (bool ok,) = payable(msg.sender).call{value: distributorShare}("");
        require(ok, "CharacterSplits: distributor transfer failed");

        emit Distributed(msg.sender, balance, distributorShare, remaining);
    }

    // ------------------------------------------------------------------ //
    // Views                                                                //
    // ------------------------------------------------------------------ //

    /// @notice Return all recipients.
    function getRecipients() external view returns (Recipient[] memory) {
        return recipients;
    }

    /// @notice Return the number of recipients.
    function recipientCount() external view returns (uint256) {
        return recipients.length;
    }

    // ------------------------------------------------------------------ //
    // Receive                                                              //
    // ------------------------------------------------------------------ //

    /// @notice Accept ETH deposits (e.g. royalty payments from marketplaces).
    receive() external payable {}
}

// ─────────────────────────────────────────────────────────────────────── //

/**
 * @title CharacterSplitsFactory
 * @notice Deploys cheap CharacterSplits clones for each new character.
 *
 * @dev Uses EIP-1167 minimal proxy (clone) pattern to reduce deployment cost
 *      by ~10× compared to full contract deployment.
 */
contract CharacterSplitsFactory is Ownable {
    /// @notice The implementation contract all clones delegate to.
    address public immutable implementation;

    /// @notice Emitted when a new split contract is deployed.
    event SplitDeployed(
        address indexed splitAddress,
        address[] accounts,
        uint32[]  allocations
    );

    constructor() Ownable(msg.sender) {
        implementation = address(new CharacterSplits());
    }

    /**
     * @notice Deploy a new immutable split contract.
     *
     * @param accounts    Recipient addresses.
     * @param allocations Corresponding allocations (sum = 990_000).
     * @return split      Address of the new CharacterSplits contract.
     */
    function createSplit(
        address[] calldata accounts,
        uint32[]  calldata allocations
    ) external returns (address split) {
        split = _clone(implementation);
        CharacterSplits(payable(split)).initialise(accounts, allocations);
        emit SplitDeployed(split, accounts, allocations);
    }

    /// @dev EIP-1167 minimal proxy clone.
    function _clone(address impl) internal returns (address instance) {
        assembly {
            let ptr := mload(0x40)
            mstore(ptr, 0x3d602d80600a3d3981f3363d3d373d3d3d363d73000000000000000000000000)
            mstore(add(ptr, 0x14), shl(0x60, impl))
            mstore(add(ptr, 0x28), 0x5af43d82803e903d91602b57fd5bf30000000000000000000000000000000000)
            instance := create(0, ptr, 0x37)
        }
        require(instance != address(0), "CharacterSplitsFactory: clone failed");
    }
}
