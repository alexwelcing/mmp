/// <reference types="vite/client" />

// Vite exposes environment variables prefixed with VITE_ on import.meta.env.
interface ImportMetaEnv {
  readonly VITE_AI_DIRECTOR_URL: string;
  readonly VITE_CHARACTER_NFT_ADDRESS: string;
  readonly VITE_PAYMASTER_ADDRESS: string;
  readonly VITE_CHAIN_ID: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
