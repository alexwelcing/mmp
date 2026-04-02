import { expect } from "chai";
import { ethers } from "hardhat";
import { loadFixture } from "@nomicfoundation/hardhat-toolbox/network-helpers";
import type { CharacterNFT, AIDirectorPaymaster } from "../typechain-types";

/**
 * CharacterNFT test suite.
 *
 * Covers:
 *   - Free mint (one per address, paymaster-gated)
 *   - Paid random mint (USDC payment)
 *   - Premium custom mint (USDC payment + trait override)
 *   - Paymaster validation logic
 *   - Access control
 */
describe("CharacterNFT", () => {
  // ── Fixture ──────────────────────────────────────────────────────────
  async function deployFixture() {
    const [owner, user1, user2, user3] = await ethers.getSigners();

    // Deploy a mock ERC-20 for USDC (18 decimals for testing simplicity;
    // real USDC on Base has 6 decimals).
    const MockUSDC = await ethers.getContractFactory("MockERC20");
    const usdc = await MockUSDC.deploy("USD Coin", "USDC", 6);
    const usdcAddress = await usdc.getAddress();

    // Mint 100 USDC to user1 and user2 for testing paid mints.
    await usdc.mint(user1.address, ethers.parseUnits("100", 6));
    await usdc.mint(user2.address, ethers.parseUnits("100", 6));

    // Deploy CharacterNFT with owner as temporary paymaster.
    const CharacterNFT = await ethers.getContractFactory("CharacterNFT");
    const nft = (await CharacterNFT.deploy(
      usdcAddress,
      owner.address, // payment recipient
      owner.address, // paymaster (temporary)
    )) as CharacterNFT;

    // Deploy AIDirectorPaymaster.
    const Paymaster = await ethers.getContractFactory("AIDirectorPaymaster");
    const paymaster = (await Paymaster.deploy(await nft.getAddress())) as AIDirectorPaymaster;

    // Update NFT to use real paymaster.
    await nft.setPaymaster(await paymaster.getAddress());

    return { nft, usdc, paymaster, owner, user1, user2, user3 };
  }

  // ── Free Mint ─────────────────────────────────────────────────────────
  describe("mintFree", () => {
    it("should allow the owner to mint a free character for a user", async () => {
      const { nft, owner, user1 } = await loadFixture(deployFixture);

      // Owner acts as paymaster substitute for testing.
      await nft.setPaymaster(owner.address);
      const tx = await nft.mintFree(user1.address);
      const receipt = await tx.wait();

      expect(receipt).to.not.be.null;

      // Token 0 should be owned by user1.
      expect(await nft.ownerOf(0)).to.equal(user1.address);
    });

    it("should mark the address as having used its free mint", async () => {
      const { nft, owner, user1 } = await loadFixture(deployFixture);
      await nft.setPaymaster(owner.address);

      expect(await nft.hasFreeMint(user1.address)).to.be.false;
      await nft.mintFree(user1.address);
      expect(await nft.hasFreeMint(user1.address)).to.be.true;
    });

    it("should revert if the same address tries to claim a second free mint", async () => {
      const { nft, owner, user1 } = await loadFixture(deployFixture);
      await nft.setPaymaster(owner.address);

      await nft.mintFree(user1.address);
      await expect(nft.mintFree(user1.address))
        .to.be.revertedWith("CharacterNFT: free mint already claimed");
    });

    it("should revert if called by an address other than the paymaster", async () => {
      const { nft, user1, user2 } = await loadFixture(deployFixture);

      // user2 is not the paymaster.
      await expect(nft.connect(user2).mintFree(user1.address))
        .to.be.revertedWith("CharacterNFT: caller not paymaster");
    });

    it("should emit a CharacterMinted event with isFree=true", async () => {
      const { nft, owner, user1 } = await loadFixture(deployFixture);
      await nft.setPaymaster(owner.address);

      await expect(nft.mintFree(user1.address))
        .to.emit(nft, "CharacterMinted")
        .withArgs(
          user1.address,
          0,                 // tokenId
          (v: bigint) => v >= 0n && v <= 6n,  // role
          (v: bigint) => v >= 0n && v <= 4n,  // aesthetic
          (v: bigint) => v >= 0n && v <= 4n,  // rarity
          true,              // isFree
        );
    });
  });

  // ── Paid Random Mint ─────────────────────────────────────────────────
  describe("mintRandom", () => {
    it("should mint a random character when USDC is approved", async () => {
      const { nft, usdc, user1 } = await loadFixture(deployFixture);
      const nftAddress = await nft.getAddress();
      const price = await nft.RANDOM_ROLL_PRICE();

      await usdc.connect(user1).approve(nftAddress, price);
      await nft.connect(user1).mintRandom(user1.address);

      expect(await nft.ownerOf(0)).to.equal(user1.address);
    });

    it("should transfer USDC from the caller to the payment recipient", async () => {
      const { nft, usdc, owner, user1 } = await loadFixture(deployFixture);
      const nftAddress = await nft.getAddress();
      const price = await nft.RANDOM_ROLL_PRICE();

      const ownerBalanceBefore = await usdc.balanceOf(owner.address);
      await usdc.connect(user1).approve(nftAddress, price);
      await nft.connect(user1).mintRandom(user1.address);

      expect(await usdc.balanceOf(owner.address)).to.equal(ownerBalanceBefore + price);
    });

    it("should revert when USDC allowance is insufficient", async () => {
      const { nft, user1 } = await loadFixture(deployFixture);

      // No approval.
      await expect(nft.connect(user1).mintRandom(user1.address))
        .to.be.reverted;
    });

    it("should allow minting to a different address (gifting)", async () => {
      const { nft, usdc, user1, user2 } = await loadFixture(deployFixture);
      const price = await nft.RANDOM_ROLL_PRICE();

      await usdc.connect(user1).approve(await nft.getAddress(), price);
      await nft.connect(user1).mintRandom(user2.address);

      expect(await nft.ownerOf(0)).to.equal(user2.address);
    });
  });

  // ── Premium Custom Mint ───────────────────────────────────────────────
  describe("mintCustom", () => {
    it("should mint with the specified role and aesthetic", async () => {
      const { nft, usdc, user1 } = await loadFixture(deployFixture);
      const price = await nft.CUSTOM_MINT_PRICE();

      await usdc.connect(user1).approve(await nft.getAddress(), price);

      // Role.Mage (1), Aesthetic.Cyberpunk (2), Rarity will be overridden.
      const traits = { role: 1, aesthetic: 2, rarity: 0 };
      await nft.connect(user1).mintCustom(user1.address, traits);

      const storedTraits = await nft.getTraits(0);
      expect(storedTraits.role).to.equal(1);
      expect(storedTraits.aesthetic).to.equal(2);
      // Rarity is randomised — just check it's a valid enum value.
      expect(storedTraits.rarity).to.be.within(0, 4);
    });

    it("should charge the CUSTOM_MINT_PRICE", async () => {
      const { nft, usdc, owner, user1 } = await loadFixture(deployFixture);
      const price = await nft.CUSTOM_MINT_PRICE();

      const ownerBefore = await usdc.balanceOf(owner.address);
      await usdc.connect(user1).approve(await nft.getAddress(), price);
      await nft.connect(user1).mintCustom(user1.address, { role: 0, aesthetic: 0, rarity: 0 });

      expect(await usdc.balanceOf(owner.address)).to.equal(ownerBefore + price);
    });
  });

  // ── Paymaster ─────────────────────────────────────────────────────────
  describe("AIDirectorPaymaster", () => {
    it("should be deployed with the correct CharacterNFT reference", async () => {
      const { nft, paymaster } = await loadFixture(deployFixture);
      expect(await paymaster.characterNFT()).to.equal(await nft.getAddress());
    });

    it("should allow the owner to reset a user's sponsored status", async () => {
      const { paymaster, owner, user1 } = await loadFixture(deployFixture);

      // Simulate sponsored state.
      // (In production this is set by postOp; we call reset directly here.)
      await paymaster.connect(owner).resetSponsoredStatus(user1.address);
      expect(await paymaster.hasSponsoredMint(user1.address)).to.be.false;
    });

    it("should revert resetSponsoredStatus for non-owners", async () => {
      const { paymaster, user1, user2 } = await loadFixture(deployFixture);
      await expect(paymaster.connect(user2).resetSponsoredStatus(user1.address))
        .to.be.reverted;
    });
  });

  // ── Traits ────────────────────────────────────────────────────────────
  describe("getTraits", () => {
    it("should revert for non-existent tokens", async () => {
      const { nft } = await loadFixture(deployFixture);
      await expect(nft.getTraits(999)).to.be.revertedWith(
        "CharacterNFT: token does not exist"
      );
    });
  });
});

// ── Mock ERC-20 contract (compiled inline by Hardhat) ──────────────────
// In a real project this would live in contracts/src/mocks/MockERC20.sol.
// We declare it here as a string so hardhat-toolbox can compile it.
