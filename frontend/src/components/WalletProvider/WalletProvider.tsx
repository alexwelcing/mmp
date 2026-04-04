/**
 * WalletProvider.tsx — Context provider for wallet state.
 *
 * Wrap your app (or just the pages that need Web3) with this provider to
 * give all child components access to the wallet state and actions via
 * the useWalletContext() hook.
 */

import type { ReactNode } from "react";
import { createContext, useContext } from "react";
import { useWallet, type UseWalletReturn } from "../../hooks/useWallet";

const WalletContext = createContext<UseWalletReturn | null>(null);

interface WalletProviderProps {
  children: ReactNode;
}

/** Provides wallet connection state to all children. */
export function WalletProvider({ children }: WalletProviderProps) {
  const wallet = useWallet();
  return (
    <WalletContext.Provider value={wallet}>{children}</WalletContext.Provider>
  );
}

/**
 * Hook to consume the wallet context.
 * Must be used inside a <WalletProvider>.
 */
export function useWalletContext(): UseWalletReturn {
  const ctx = useContext(WalletContext);
  if (!ctx) {
    throw new Error("useWalletContext must be used inside <WalletProvider>");
  }
  return ctx;
}
