/**
 * character.ts — TypeScript types for the character generation domain.
 *
 * These types are shared across components and hooks.  They mirror the
 * structures defined in the Python AI Director service and Solidity contracts.
 */

// ── Enums ──────────────────────────────────────────────────────────────

/** Character role archetypes. Must match CharacterNFT.sol `Role` enum. */
export type Role =
  | "Warrior"
  | "Mage"
  | "Scout"
  | "Healer"
  | "Assassin"
  | "Berserker"
  | "Paladin";

/** Visual aesthetic styles. Must match CharacterNFT.sol `Aesthetic` enum. */
export type Aesthetic =
  | "Fantasy"
  | "SciFi"
  | "Cyberpunk"
  | "Steampunk"
  | "Mythological";

/** Rarity tiers — higher index is rarer. */
export type Rarity = "Common" | "Uncommon" | "Rare" | "Epic" | "Legendary";

// ── Core domain types ─────────────────────────────────────────────────

/** On-chain and display traits for a character. */
export interface CharacterTraits {
  role: Role;
  aesthetic: Aesthetic;
  rarity: Rarity;
}

/** A fully generated character with all asset URLs. */
export interface Character {
  /** Unique identifier (matches the backend job ID). */
  id: string;

  /** Display name — AI-generated or user-chosen. */
  name: string;

  /** Character traits. */
  traits: CharacterTraits;

  /** URL of the 2D character image (upscaled). */
  imageUrl: string;

  /** URL of the 3DGS scene file (for 3D viewer). */
  threedgsUrl: string;

  /** URL of the character audio soundscape. */
  audioUrl: string;

  /** On-chain token ID (undefined until minted). */
  tokenId?: number;

  /** EVM wallet address that owns the NFT (undefined until minted). */
  ownerAddress?: string;
}

// ── API request / response types ──────────────────────────────────────

/** Request body for POST /generate. */
export interface GenerationRequest {
  userId: string;
  preferences: {
    role?: Role;
    aesthetic?: Aesthetic;
    /** Override the AI-generated prompt (premium custom mints). */
    promptOverride?: string;
  };
  /** Trigger on-chain mint after generation (requires walletAddress). */
  mintOnChain?: boolean;
  walletAddress?: string;
}

/** Stage names matching JobStage enum in orchestrator.py. */
export type GenerationStage =
  | "queued"
  | "drafting"
  | "evaluating"
  | "upscaling"
  | "generating_3dgs"
  | "generating_audio"
  | "minting"
  | "complete"
  | "failed";

/** Response body from GET /status/{jobId}. */
export interface GenerationStatus {
  jobId: string;
  stage: GenerationStage;
  draftUrls: string[];
  selectedDraftUrl: string;
  upscaledUrl: string;
  threedgsUrl: string;
  audioUrl: string;
  nftTokenId: number | null;
  error: string | null;
}

// ── UI flow types ─────────────────────────────────────────────────────

/** The steps in the onboarding funnel. */
export type OnboardingStep =
  | "free-roll"
  | "generating"
  | "reveal"
  | "upsell"
  | "paid-roll"
  | "minting"
  | "complete";

/** Mint tier selected by the user. */
export type MintTier = "free" | "random" | "custom";
