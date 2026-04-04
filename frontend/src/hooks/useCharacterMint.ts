/**
 * useCharacterMint.ts — Hook for orchestrating character generation and minting.
 *
 * Responsibilities:
 *   - POST to /api/generate to trigger the AI Director pipeline.
 *   - Poll GET /api/status/{jobId} every 2.5 seconds until complete.
 *   - Expose the resulting Character and loading/error state.
 *   - Provide mintFree() and mintPaid() action functions.
 */

import { useState, useCallback, useRef } from "react";
import type {
  Character,
  CharacterTraits,
  GenerationRequest,
  GenerationStatus,
  MintTier,
} from "../types/character";

const AI_DIRECTOR_URL =
  import.meta.env.VITE_AI_DIRECTOR_URL ?? "http://localhost:8080";

const POLL_INTERVAL_MS = 2500;
const MAX_POLL_ATTEMPTS = 60; // 2.5s × 60 = 150s timeout

// ── Return type ─────────────────────────────────────────────────────────

export interface UseCharacterMintReturn {
  character: Character | null;
  isLoading: boolean;
  stage: GenerationStatus["stage"] | null;
  error: string | null;
  mintFree: (userId: string) => Promise<void>;
  mintPaid: (
    userId: string,
    tier: MintTier,
    preferences: Partial<CharacterTraits>
  ) => Promise<void>;
  mintOnChain: (jobId: string, walletAddress: string, tier?: MintTier) => Promise<void>;
  reset: () => void;
  /** The tier used to generate the current character (defaults to 'free'). */
  tier: MintTier;
}

// ── Hook ────────────────────────────────────────────────────────────────

export function useCharacterMint(): UseCharacterMintReturn {
  const [character, setCharacter] = useState<Character | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [stage, setStage] = useState<GenerationStatus["stage"] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [tier, setTier] = useState<MintTier>("free");

  // Ref to allow cancelling the poll loop on unmount or reset.
  const pollingRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const stopPolling = useCallback(() => {
    if (pollingRef.current !== null) {
      clearInterval(pollingRef.current);
      pollingRef.current = null;
    }
  }, []);

  const reset = useCallback(() => {
    stopPolling();
    setCharacter(null);
    setIsLoading(false);
    setStage(null);
    setError(null);
  }, [stopPolling]);

  /** Trigger a generation job and poll until complete. */
  const triggerGeneration = useCallback(
    async (request: GenerationRequest): Promise<void> => {
      setIsLoading(true);
      setError(null);
      setCharacter(null);

      try {
        // Step 1: Start the generation pipeline.
        const generateResp = await fetch(`${AI_DIRECTOR_URL}/generate`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            user_id: request.userId,
            preferences: {
              role: request.preferences.role?.toLowerCase(),
              aesthetic: request.preferences.aesthetic?.toLowerCase(),
              prompt_override: request.preferences.promptOverride,
            },
            mint_on_chain: request.mintOnChain ?? false,
            wallet_address: request.walletAddress,
          }),
        });

        if (!generateResp.ok) {
          const errBody = await generateResp.text();
          throw new Error(`Generation failed: ${errBody}`);
        }

        const { job_id: jobId } = (await generateResp.json()) as {
          job_id: string;
          status: string;
        };

        // Step 2: Poll for status.
        await pollForCompletion(jobId);
      } catch (err) {
        const message = err instanceof Error ? err.message : "Unknown error";
        setError(message);
        setIsLoading(false);
      }
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    []
  );

  /** Poll /status/{jobId} until stage === "complete" or "failed". */
  const pollForCompletion = useCallback(
    (jobId: string): Promise<void> => {
      return new Promise<void>((resolve, reject) => {
        let attempts = 0;

        const poll = async () => {
          try {
            const resp = await fetch(`${AI_DIRECTOR_URL}/status/${jobId}`);
            if (!resp.ok) {
              reject(new Error(`Status check failed: ${resp.status}`));
              stopPolling();
              return;
            }

            const status = (await resp.json()) as GenerationStatus;
            setStage(status.stage);

            if (status.stage === "complete") {
              stopPolling();
              setCharacter(buildCharacter(status, jobId));
              setIsLoading(false);
              resolve();
              return;
            }

            if (status.stage === "failed") {
              stopPolling();
              setError(status.error ?? "Generation failed");
              setIsLoading(false);
              reject(new Error(status.error ?? "Generation failed"));
              return;
            }

            attempts++;
            if (attempts >= MAX_POLL_ATTEMPTS) {
              stopPolling();
              setError("Generation timed out. Please try again.");
              setIsLoading(false);
              reject(new Error("Generation timed out"));
            }
          } catch (err) {
            stopPolling();
            const message = err instanceof Error ? err.message : "Network error";
            setError(message);
            setIsLoading(false);
            reject(err);
          }
        };

        pollingRef.current = setInterval(poll, POLL_INTERVAL_MS);
        poll(); // Immediate first check.
      });
    },
    [stopPolling]
  );

  /** Claim the free character (no wallet, no payment). */
  const mintFree = useCallback(
    async (userId: string): Promise<void> => {
      setTier("free");
      await triggerGeneration({ userId, preferences: {} });
    },
    [triggerGeneration]
  );

  /** Paid roll — either $1 random or $9.99 custom. */
  const mintPaid = useCallback(
    async (
      userId: string,
      paidTier: MintTier,
      preferences: Partial<CharacterTraits>
    ): Promise<void> => {
      setTier(paidTier);
      await triggerGeneration({
        userId,
        preferences: {
          role: preferences.role,
          aesthetic: preferences.aesthetic,
        },
        mintOnChain: paidTier !== "free",
      });
    },
    [triggerGeneration]
  );

  /** Mint an already-generated character on-chain. */
  const mintOnChain = useCallback(
    async (jobId: string, walletAddress: string, tier: MintTier = "free"): Promise<void> => {
      setIsLoading(true);
      setError(null);
      try {
        const resp = await fetch(`${AI_DIRECTOR_URL}/mint/${jobId}`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ wallet_address: walletAddress, tier }),
        });
        if (!resp.ok) {
          const errBody = await resp.text();
          throw new Error(`Mint failed: ${errBody}`);
        }
        const status = (await resp.json()) as GenerationStatus;
        setCharacter(buildCharacter(status, jobId));
      } catch (err) {
        const message = err instanceof Error ? err.message : "Unknown error";
        setError(message);
      } finally {
        setIsLoading(false);
      }
    },
    []
  );

  return { character, isLoading, stage, error, mintFree, mintPaid, mintOnChain, reset, tier };
}

// ── Helpers ─────────────────────────────────────────────────────────────

/** Convert a completed GenerationStatus into a displayable Character. */
function buildCharacter(status: GenerationStatus, jobId: string): Character {
  return {
    id: jobId,
    name: generateCharacterName(jobId),
    traits: status.traits,
    imageUrl: status.upscaledUrl || status.selectedDraftUrl,
    threedgsUrl: status.threedgsUrl,
    audioUrl: status.audioUrl,
    tokenId: status.nftTokenId ?? undefined,
  };
}

/** Generate a deterministic fantasy name from a job ID for display. */
function generateCharacterName(jobId: string): string {
  const prefixes = ["Zyr", "Aex", "Mor", "Val", "Thr", "Kal", "Syn"];
  const suffixes = ["axen", "idor", "alis", "orin", "ethos", "yxis"];
  const hash = jobId.split("").reduce((acc, c) => acc + c.charCodeAt(0), 0);
  return `${prefixes[hash % prefixes.length]}${suffixes[(hash >> 2) % suffixes.length]}`;
}
