import { HardhatUserConfig } from "hardhat/config";
import "@nomicfoundation/hardhat-toolbox";

// Load environment variables for RPC URLs and private keys.
// Never commit real private keys — use environment variables or a keystore.
const BASE_SEPOLIA_RPC = process.env.BASE_SEPOLIA_RPC ?? "https://sepolia.base.org";
const BASE_MAINNET_RPC = process.env.BASE_MAINNET_RPC ?? "https://mainnet.base.org";

// In CI/testing, use a dummy private key so compilation doesn't fail.
const DEPLOY_PRIVATE_KEY =
  process.env.DEPLOY_PRIVATE_KEY ?? "0x" + "a".repeat(64);

const config: HardhatUserConfig = {
  solidity: {
    // 0.8.24 is the highest patch that satisfies ^0.8.20 in all contracts.
    // Pinned here for reproducibility; update carefully and re-run tests.
    version: "0.8.24",
    settings: {
      optimizer: {
        enabled: true,
        runs: 200,
      },
      viaIR: true,
    },
  },

  networks: {
    // Local Hardhat network (default for `hardhat test`).
    hardhat: {
      chainId: 31337,
    },

    // Base Sepolia testnet.
    "base-sepolia": {
      url: BASE_SEPOLIA_RPC,
      chainId: 84532,
      accounts: [DEPLOY_PRIVATE_KEY],
    },

    // Base mainnet.
    "base-mainnet": {
      url: BASE_MAINNET_RPC,
      chainId: 8453,
      accounts: [DEPLOY_PRIVATE_KEY],
    },
  },

  // Etherscan API key for contract verification on BaseScan.
  etherscan: {
    apiKey: {
      "base-sepolia": process.env.BASESCAN_API_KEY ?? "",
      "base-mainnet": process.env.BASESCAN_API_KEY ?? "",
    },
    customChains: [
      {
        network: "base-sepolia",
        chainId: 84532,
        urls: {
          apiURL: "https://api-sepolia.basescan.org/api",
          browserURL: "https://sepolia.basescan.org",
        },
      },
      {
        network: "base-mainnet",
        chainId: 8453,
        urls: {
          apiURL: "https://api.basescan.org/api",
          browserURL: "https://basescan.org",
        },
      },
    ],
  },

  paths: {
    sources: "./src",
    tests: "./test",
    cache: "./cache",
    artifacts: "./artifacts",
  },

  gasReporter: {
    enabled: process.env.REPORT_GAS === "true",
    currency: "USD",
    coinmarketcap: process.env.COINMARKETCAP_API_KEY,
  },
};

export default config;
