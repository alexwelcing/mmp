import { ethers } from "hardhat";

/**
 * Deployment script for all MMP smart contracts.
 *
 * Deployment order matters:
 *   1. CharacterSplitsFactory (no dependencies)
 *   2. CharacterNFT (needs USDC address + payment recipient + paymaster placeholder)
 *   3. AIDirectorPaymaster (needs CharacterNFT address)
 *   4. Update CharacterNFT paymaster reference to real Paymaster address
 *   5. Deploy a default CharacterSplits via the factory
 *   6. Update CharacterNFT payment recipient to the splits contract
 *
 * Run:
 *   npx hardhat run scripts/deploy.ts --network base-sepolia
 */
async function main(): Promise<void> {
  const [deployer] = await ethers.getSigners();
  console.log(`\nDeploying contracts with account: ${deployer.address}`);
  console.log(`Account balance: ${ethers.formatEther(await ethers.provider.getBalance(deployer.address))} ETH\n`);

  // ── 1. CharacterSplitsFactory ────────────────────────────────────────
  console.log("Deploying CharacterSplitsFactory...");
  const SplitsFactory = await ethers.getContractFactory("CharacterSplitsFactory");
  const splitsFactory = await SplitsFactory.deploy();
  await splitsFactory.waitForDeployment();
  const splitsFactoryAddress = await splitsFactory.getAddress();
  console.log(`  CharacterSplitsFactory deployed to: ${splitsFactoryAddress}`);

  // ── 2. CharacterNFT (with placeholder paymaster) ─────────────────────
  console.log("\nDeploying CharacterNFT...");

  // USDC on Base Sepolia testnet.
  // Mainnet: 0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913
  const USDC_BASE_SEPOLIA = "0x036CbD53842c5426634e7929541eC2318f3dCF7e";
  const usdcAddress = process.env.USDC_ADDRESS ?? USDC_BASE_SEPOLIA;

  // Temporary payment recipient (deployer) — will be updated to splits contract.
  const CharacterNFT = await ethers.getContractFactory("CharacterNFT");
  const characterNFT = await CharacterNFT.deploy(
    usdcAddress,
    deployer.address,     // temporary recipient
    deployer.address,     // temporary paymaster
  );
  await characterNFT.waitForDeployment();
  const nftAddress = await characterNFT.getAddress();
  console.log(`  CharacterNFT deployed to: ${nftAddress}`);

  // ── 3. AIDirectorPaymaster ────────────────────────────────────────────
  console.log("\nDeploying AIDirectorPaymaster...");
  const Paymaster = await ethers.getContractFactory("AIDirectorPaymaster");
  const paymaster = await Paymaster.deploy(nftAddress);
  await paymaster.waitForDeployment();
  const paymasterAddress = await paymaster.getAddress();
  console.log(`  AIDirectorPaymaster deployed to: ${paymasterAddress}`);

  // ── 4. Update CharacterNFT paymaster ──────────────────────────────────
  console.log("\nUpdating CharacterNFT paymaster reference...");
  const setPaymasterTx = await characterNFT.setPaymaster(paymasterAddress);
  await setPaymasterTx.wait();
  console.log(`  Paymaster updated to: ${paymasterAddress}`);

  // ── 5. Deploy default royalty split ───────────────────────────────────
  console.log("\nDeploying default CharacterSplits via factory...");

  // 79% to dev wallet, 20% to AI ops wallet, 1% to distributor (auto-deducted).
  // Allocations sum to 990_000 (ALLOCATION_SCALE - DISTRIBUTOR_FEE = 1_000_000 - 10_000).
  const devWallet = process.env.DEV_WALLET ?? deployer.address;
  const aiOpsWallet = process.env.AI_OPS_WALLET ?? deployer.address;

  // Allocations are in units of 1e6 and must sum to ALLOCATION_SCALE - DISTRIBUTOR_FEE = 990_000.
  // At distribution: dev gets 79% of balance, AI ops gets 20%, keeper bot gets 1%.
  const createSplitTx = await splitsFactory.createSplit(
    [devWallet, aiOpsWallet],
    [790_000, 200_000],  // 790_000 + 200_000 = 990_000 ✓
  );
  const receipt = await createSplitTx.wait();

  // Parse the SplitDeployed event to get the split address.
  const splitDeployedEvent = receipt?.logs
    .map(log => {
      try { return splitsFactory.interface.parseLog(log); } catch { return null; }
    })
    .find(e => e?.name === "SplitDeployed");

  const splitAddress = splitDeployedEvent?.args[0] as string ?? "unknown";
  console.log(`  CharacterSplits deployed to: ${splitAddress}`);

  // ── 6. Update CharacterNFT payment recipient to splits ─────────────────
  console.log("\nUpdating CharacterNFT payment recipient to splits contract...");
  const setRecipientTx = await characterNFT.setPaymentRecipient(splitAddress);
  await setRecipientTx.wait();
  console.log(`  Payment recipient updated to: ${splitAddress}`);

  // ── Summary ────────────────────────────────────────────────────────────
  console.log("\n" + "=".repeat(60));
  console.log("Deployment complete! Save these addresses:");
  console.log("=".repeat(60));
  console.log(`CHARACTER_NFT_ADDRESS=${nftAddress}`);
  console.log(`PAYMASTER_ADDRESS=${paymasterAddress}`);
  console.log(`SPLITS_FACTORY_ADDRESS=${splitsFactoryAddress}`);
  console.log(`DEFAULT_SPLIT_ADDRESS=${splitAddress}`);
  console.log("=".repeat(60));
  console.log("\nNext steps:");
  console.log("  1. Fund the Paymaster via depositToEntryPoint() with ~0.1 ETH");
  console.log("  2. Verify contracts on BaseScan with: npx hardhat verify");
  console.log("  3. Update .env / GCP Secret Manager with the above addresses\n");
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
