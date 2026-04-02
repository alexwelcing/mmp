import { expect } from "chai";
import { ethers } from "hardhat";

describe("Deploy smoke", () => {
  it("deploys core contracts and wires references", async () => {
    const [deployer] = await ethers.getSigners();

    const MockUSDC = await ethers.getContractFactory("MockERC20");
    const usdc = await MockUSDC.deploy("USD Coin", "USDC", 6);

    const SplitsFactory = await ethers.getContractFactory("CharacterSplitsFactory");
    const splitsFactory = await SplitsFactory.deploy();

    const CharacterNFT = await ethers.getContractFactory("CharacterNFT");
    const nft = await CharacterNFT.deploy(
      await usdc.getAddress(),
      deployer.address,
      deployer.address
    );

    const Paymaster = await ethers.getContractFactory("AIDirectorPaymaster");
    const paymaster = await Paymaster.deploy(await nft.getAddress());

    await nft.setPaymaster(await paymaster.getAddress());
    await splitsFactory.createSplit(
      [deployer.address, deployer.address],
      [495_000, 495_000]
    );

    expect(await nft.paymaster()).to.equal(await paymaster.getAddress());
    expect(await splitsFactory.implementation()).to.not.equal(
      "0x0000000000000000000000000000000000000000"
    );
  });
});
