/**
 * CharacterCreationFlow.tsx — Top-level multi-step wizard.
 *
 * Manages the onboarding funnel state machine:
 *
 *   free-roll → generating → reveal → upsell → paid-roll → complete
 *
 * Key design decision: blockchain terminology is hidden until the user
 * has already received their character and is ready to commit.
 */

import React, { useState, useCallback } from "react";
import { FreeRollStep } from "./FreeRollStep";
import { PaidRollStep } from "./PaidRollStep";
import { CharacterCard } from "./CharacterCard";
import { useCharacterMint } from "../../hooks/useCharacterMint";
import type { Character, OnboardingStep, MintTier, CharacterTraits } from "../../types/character";

// ── Inline styles (replace with CSS modules / Tailwind in production) ──

const styles = {
  container: {
    minHeight: "100vh",
    background: "linear-gradient(135deg, #0f0c29, #302b63, #24243e)",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    padding: "2rem",
    fontFamily: "'Segoe UI', system-ui, sans-serif",
    color: "#fff",
  } as React.CSSProperties,

  card: {
    background: "rgba(255,255,255,0.07)",
    backdropFilter: "blur(20px)",
    borderRadius: "24px",
    padding: "2.5rem",
    maxWidth: "480px",
    width: "100%",
    boxShadow: "0 8px 32px rgba(0,0,0,0.4)",
    border: "1px solid rgba(255,255,255,0.1)",
  } as React.CSSProperties,
};

export function CharacterCreationFlow() {
  const [step, setStep] = useState<OnboardingStep>("free-roll");
  const [userId] = useState(() => `user_${Math.random().toString(36).slice(2)}`);

  const { character, isLoading, stage, error, mintFree, mintPaid } =
    useCharacterMint();

  // ── Handlers ────────────────────────────────────────────────────────

  const handleFreeRollSubmit = useCallback(async () => {
    setStep("generating");
    await mintFree(userId);
    // mintFree resolves when character is ready.
    setStep("reveal");
  }, [mintFree, userId]);

  const handleUpsellDecision = useCallback(
    (choice: "random" | "custom" | "skip") => {
      if (choice === "skip") {
        setStep("complete");
      } else {
        setStep("paid-roll");
      }
    },
    []
  );

  const handlePaidRollSubmit = useCallback(
    async (tier: MintTier, preferences: Partial<CharacterTraits>) => {
      setStep("generating");
      await mintPaid(userId, tier, preferences);
      setStep("complete");
    },
    [mintPaid, userId]
  );

  // ── Render ───────────────────────────────────────────────────────────

  return (
    <div style={styles.container}>
      <div style={styles.card}>
        {step === "free-roll" && (
          <FreeRollStep onSubmit={handleFreeRollSubmit} isLoading={isLoading} />
        )}

        {step === "generating" && (
          <GeneratingView stage={stage} />
        )}

        {step === "reveal" && character && (
          <RevealView
            character={character}
            onContinue={() => setStep("upsell")}
          />
        )}

        {step === "upsell" && character && (
          <UpsellView character={character} onDecision={handleUpsellDecision} />
        )}

        {step === "paid-roll" && (
          <PaidRollStep onSubmit={handlePaidRollSubmit} isLoading={isLoading} />
        )}

        {step === "complete" && character && (
          <CharacterCard character={character} />
        )}

        {error && (
          <div style={{ color: "#ff6b6b", marginTop: "1rem", textAlign: "center" }}>
            {error}{" "}
            <button
              onClick={() => setStep("free-roll")}
              style={{ color: "#a78bfa", background: "none", border: "none", cursor: "pointer" }}
            >
              Try again
            </button>
          </div>
        )}
      </div>
    </div>
  );
}

// ── Sub-views (small enough to live in this file) ─────────────────────

interface GeneratingViewProps {
  stage: string | null;
}

function GeneratingView({ stage }: GeneratingViewProps) {
  const stageLabels: Record<string, string> = {
    queued:           "Preparing your character...",
    drafting:         "The AI is sketching concepts...",
    evaluating:       "Selecting the best design...",
    upscaling:        "Enhancing the artwork...",
    generating_3dgs:  "Creating 3D model...",
    generating_audio: "Composing your soundscape...",
    minting:          "Securing on-chain ownership...",
  };

  return (
    <div style={{ textAlign: "center", padding: "2rem 0" }}>
      <div style={{ fontSize: "3rem", marginBottom: "1rem" }}>✨</div>
      <h2 style={{ margin: "0 0 0.5rem" }}>Crafting your character</h2>
      <p style={{ color: "#a78bfa", margin: "0 0 1.5rem" }}>
        {stage ? stageLabels[stage] ?? stage : "Starting..."}
      </p>
      <LoadingSpinner />
    </div>
  );
}

interface RevealViewProps {
  character: Character;
  onContinue: () => void;
}

function RevealView({ character, onContinue }: RevealViewProps) {
  return (
    <div style={{ textAlign: "center" }}>
      <div style={{ fontSize: "3rem", marginBottom: "0.5rem" }}>🎉</div>
      <h2 style={{ margin: "0 0 0.25rem" }}>
        Meet {character.name}!
      </h2>
      <p style={{ color: "#a78bfa", marginBottom: "1.5rem" }}>
        {character.traits.rarity} {character.traits.role} · {character.traits.aesthetic}
      </p>
      {character.imageUrl && (
        <img
          src={character.imageUrl}
          alt={character.name}
          style={{
            width: "100%",
            borderRadius: "16px",
            marginBottom: "1.5rem",
            border: "2px solid rgba(167, 139, 250, 0.3)",
          }}
        />
      )}
      <button onClick={onContinue} style={primaryButtonStyle}>
        Continue →
      </button>
    </div>
  );
}

interface UpsellViewProps {
  character: Character;
  onDecision: (choice: "random" | "custom" | "skip") => void;
}

function UpsellView({ character, onDecision }: UpsellViewProps) {
  return (
    <div>
      <h2 style={{ textAlign: "center", margin: "0 0 0.5rem" }}>
        Love {character.name}?
      </h2>
      <p style={{ color: "#94a3b8", textAlign: "center", margin: "0 0 1.5rem" }}>
        Own them forever — trade, use in tournaments, earn royalties.
      </p>

      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "1rem", marginBottom: "1rem" }}>
        <OfferCard
          emoji="🎲"
          title="Lucky Roll"
          price="$1.00"
          description="New random character"
          onClick={() => onDecision("random")}
        />
        <OfferCard
          emoji="✨"
          title="Custom"
          price="$9.99"
          description="Choose role & aesthetic"
          onClick={() => onDecision("custom")}
        />
      </div>

      <button
        onClick={() => onDecision("skip")}
        style={{
          width: "100%",
          background: "none",
          border: "none",
          color: "#64748b",
          cursor: "pointer",
          padding: "0.5rem",
          fontSize: "0.875rem",
        }}
      >
        Maybe later
      </button>
    </div>
  );
}

interface OfferCardProps {
  emoji: string;
  title: string;
  price: string;
  description: string;
  onClick: () => void;
}

function OfferCard({ emoji, title, price, description, onClick }: OfferCardProps) {
  return (
    <button
      onClick={onClick}
      style={{
        background: "rgba(167, 139, 250, 0.1)",
        border: "1px solid rgba(167, 139, 250, 0.3)",
        borderRadius: "12px",
        padding: "1.25rem 1rem",
        cursor: "pointer",
        color: "#fff",
        textAlign: "center",
        transition: "all 0.2s",
      }}
    >
      <div style={{ fontSize: "2rem", marginBottom: "0.5rem" }}>{emoji}</div>
      <div style={{ fontWeight: 700, marginBottom: "0.25rem" }}>{title}</div>
      <div style={{ color: "#a78bfa", fontSize: "1.25rem", fontWeight: 700, marginBottom: "0.25rem" }}>
        {price}
      </div>
      <div style={{ color: "#94a3b8", fontSize: "0.8rem" }}>{description}</div>
    </button>
  );
}

function LoadingSpinner() {
  return (
    <div
      style={{
        width: "48px",
        height: "48px",
        border: "4px solid rgba(167, 139, 250, 0.2)",
        borderTop: "4px solid #a78bfa",
        borderRadius: "50%",
        animation: "spin 1s linear infinite",
        margin: "0 auto",
      }}
    />
  );
}

const primaryButtonStyle: React.CSSProperties = {
  background: "linear-gradient(135deg, #7c3aed, #a78bfa)",
  color: "#fff",
  border: "none",
  borderRadius: "12px",
  padding: "0.875rem 2rem",
  fontSize: "1rem",
  fontWeight: 700,
  cursor: "pointer",
  width: "100%",
  transition: "opacity 0.2s",
};
