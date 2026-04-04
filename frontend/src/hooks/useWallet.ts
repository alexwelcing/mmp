/**
 * useWallet.ts — Hook for managing wallet connection state.
 *
 * Abstracts the underlying wallet provider (EIP-1193 injected wallet,
 * WalletConnect, Coinbase Smart Wallet, etc.).  In this tutorial we
 * implement a simple injected wallet connector.
 *
 * For production, consider using wagmi + viem for a fully-featured
 * multi-wallet experience with type-safe contract interactions.
 */

import { useState, useCallback, useEffect } from "react";

export interface WalletState {
  address: string | null;
  chainId: number | null;
  isConnected: boolean;
  isConnecting: boolean;
  error: string | null;
}

export interface UseWalletReturn extends WalletState {
  connect: () => Promise<void>;
  disconnect: () => void;
  switchToBase: () => Promise<void>;
}

/** Base mainnet chain ID. */
const BASE_CHAIN_ID = 8453;

/** Base Sepolia testnet chain ID. */
const BASE_SEPOLIA_CHAIN_ID = 84532;

const TARGET_CHAIN_ID =
  import.meta.env.VITE_CHAIN_ID === "mainnet"
    ? BASE_CHAIN_ID
    : BASE_SEPOLIA_CHAIN_ID;

export function useWallet(): UseWalletReturn {
  const [state, setState] = useState<WalletState>({
    address: null,
    chainId: null,
    isConnected: false,
    isConnecting: false,
    error: null,
  });

  const syncChainId = useCallback(async (address: string) => {
    const provider = getProvider();
    if (!provider) return;
    const chainIdHex = (await provider.request({ method: "eth_chainId" })) as string;
    setState({
      address,
      chainId: parseInt(chainIdHex, 16),
      isConnected: true,
      isConnecting: false,
      error: null,
    });
  }, []);

  /** Read current account from the injected provider on mount. */
  useEffect(() => {
    const provider = getProvider();
    if (!provider) return;

    // Silently check if already connected (don't prompt the user).
    provider
      .request({ method: "eth_accounts" })
      .then((accounts) => {
        const accs = (accounts || []) as string[];
        if (accs.length > 0) {
          void syncChainId(accs[0]);
        }
      })
      .catch(() => {/* no wallet connected — ignore */});

    // Listen for account / chain changes.
    const handleAccountsChanged = (...args: unknown[]) => {
      const accounts = (args[0] || []) as string[];
      if (accounts.length === 0) {
        setState({ address: null, chainId: null, isConnected: false, isConnecting: false, error: null });
      } else {
        void syncChainId(accounts[0]);
      }
    };
    const handleChainChanged = () => window.location.reload();

    provider.on("accountsChanged", handleAccountsChanged);
    provider.on("chainChanged", handleChainChanged);
    return () => {
      provider.removeListener("accountsChanged", handleAccountsChanged);
      provider.removeListener("chainChanged", handleChainChanged);
    };
  }, [syncChainId]);

  /** Prompt the user to connect their wallet. */
  const connect = useCallback(async () => {
    const provider = getProvider();
    if (!provider) {
      setState((s) => ({
        ...s,
        error: "No wallet found. Please install MetaMask or a compatible wallet.",
      }));
      return;
    }

    setState((s) => ({ ...s, isConnecting: true, error: null }));
    try {
      const accounts = (await provider.request({
        method: "eth_requestAccounts",
      })) as string[];
      await syncChainId(accounts[0]);
    } catch (err) {
      const message = err instanceof Error ? err.message : "Connection rejected";
      setState((s) => ({ ...s, isConnecting: false, error: message }));
    }
  }, [syncChainId]);

  /** Disconnect wallet (clear local state — cannot revoke browser wallet access). */
  const disconnect = useCallback(() => {
    setState({ address: null, chainId: null, isConnected: false, isConnecting: false, error: null });
  }, []);

  /** Prompt the user to switch to the Base network. */
  const switchToBase = useCallback(async () => {
    const provider = getProvider();
    if (!provider) return;

    const chainIdHex = `0x${TARGET_CHAIN_ID.toString(16)}`;
    try {
      await provider.request({
        method: "wallet_switchEthereumChain",
        params: [{ chainId: chainIdHex }],
      });
    } catch (err: unknown) {
      // Error code 4902 = chain not added yet.
      if (isProviderError(err) && err.code === 4902) {
        await addBaseNetwork(provider, TARGET_CHAIN_ID);
      } else {
        throw err;
      }
    }
  }, []);

  return { ...state, connect, disconnect, switchToBase };
}

// ── Helpers ──────────────────────────────────────────────────────────────

interface EIP1193Provider {
  request: (args: { method: string; params?: unknown[] }) => Promise<unknown>;
  on: (event: string, listener: (...args: unknown[]) => void) => void;
  removeListener: (event: string, listener: (...args: unknown[]) => void) => void;
}

function getProvider(): EIP1193Provider | null {
  if (typeof window !== "undefined" && "ethereum" in window) {
    return (window as { ethereum: EIP1193Provider }).ethereum;
  }
  return null;
}

interface ProviderError {
  code: number;
  message: string;
}

function isProviderError(err: unknown): err is ProviderError {
  return typeof err === "object" && err !== null && "code" in err;
}

async function addBaseNetwork(
  provider: EIP1193Provider,
  chainId: number
): Promise<void> {
  const isMainnet = chainId === BASE_CHAIN_ID;
  await provider.request({
    method: "wallet_addEthereumChain",
    params: [
      {
        chainId: `0x${chainId.toString(16)}`,
        chainName: isMainnet ? "Base" : "Base Sepolia",
        nativeCurrency: { name: "Ether", symbol: "ETH", decimals: 18 },
        rpcUrls: [isMainnet ? "https://mainnet.base.org" : "https://sepolia.base.org"],
        blockExplorerUrls: [
          isMainnet ? "https://basescan.org" : "https://sepolia.basescan.org",
        ],
      },
    ],
  });
}
