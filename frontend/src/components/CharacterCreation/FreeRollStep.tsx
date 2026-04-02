/**
 * FreeRollStep.tsx — Step 1 of the onboarding funnel.
 *
 * Design principle: zero friction, zero crypto.  The user just needs to
 * click a button to start.  Social login is mocked here; integrate with
 * Firebase Auth or Auth0 for production.
 */

import { useState } from "react";

interface FreeRollStepProps {
  onSubmit: () => Promise<void>;
  isLoading: boolean;
}

export function FreeRollStep({ onSubmit, isLoading }: FreeRollStepProps) {
  const [loginMethod, setLoginMethod] = useState<"none" | "google" | "steam">("none");

  const handleSocialLogin = async (method: "google" | "steam") => {
    setLoginMethod(method);
    // In production: call Firebase Auth or Auth0 here, then invoke onSubmit.
    // For the tutorial we mock this with a brief delay.
    await onSubmit();
  };

  const handleGuestClaim = async () => {
    setLoginMethod("none");
    await onSubmit();
  };

  return (
    <div style={{ textAlign: "center" }}>
      {/* Hero section */}
      <div style={{ marginBottom: "2rem" }}>
        <div style={{ fontSize: "4rem", marginBottom: "0.75rem" }}>⚔️</div>
        <h1
          style={{
            margin: "0 0 0.5rem",
            fontSize: "1.875rem",
            fontWeight: 800,
            background: "linear-gradient(135deg, #a78bfa, #60a5fa)",
            WebkitBackgroundClip: "text",
            WebkitTextFillColor: "transparent",
          }}
        >
          Claim Your Free Character
        </h1>
        <p style={{ color: "#94a3b8", margin: 0, lineHeight: 1.6 }}>
          The AI will craft a unique character just for you.
          <br />
          No credit card, no wallet required.
        </p>
      </div>

      {/* Social login buttons */}
      <div style={{ display: "flex", flexDirection: "column", gap: "0.75rem", marginBottom: "1rem" }}>
        <SocialButton
          icon="🔵"
          label="Continue with Google"
          disabled={isLoading}
          onClick={() => handleSocialLogin("google")}
          loading={isLoading && loginMethod === "google"}
        />
        <SocialButton
          icon="🎮"
          label="Continue with Steam"
          disabled={isLoading}
          onClick={() => handleSocialLogin("steam")}
          loading={isLoading && loginMethod === "steam"}
        />
      </div>

      <div style={{ color: "#475569", fontSize: "0.875rem", margin: "1rem 0" }}>
        — or —
      </div>

      {/* Guest claim */}
      <button
        onClick={handleGuestClaim}
        disabled={isLoading}
        style={{
          width: "100%",
          background: "linear-gradient(135deg, #7c3aed, #a78bfa)",
          color: "#fff",
          border: "none",
          borderRadius: "12px",
          padding: "0.875rem",
          fontSize: "1rem",
          fontWeight: 700,
          cursor: isLoading ? "not-allowed" : "pointer",
          opacity: isLoading ? 0.7 : 1,
          transition: "opacity 0.2s",
        }}
      >
        {isLoading ? "✨ Generating..." : "✨ Generate My Character"}
      </button>

      {/* Trust signals */}
      <div
        style={{
          display: "flex",
          justifyContent: "center",
          gap: "1.5rem",
          marginTop: "1.5rem",
          color: "#475569",
          fontSize: "0.8rem",
        }}
      >
        <span>🔒 Free forever</span>
        <span>⚡ Ready in ~30s</span>
        <span>🎨 Truly unique</span>
      </div>
    </div>
  );
}

// ── Sub-components ────────────────────────────────────────────────────

interface SocialButtonProps {
  icon: string;
  label: string;
  disabled: boolean;
  loading: boolean;
  onClick: () => void;
}

function SocialButton({ icon, label, disabled, loading, onClick }: SocialButtonProps) {
  return (
    <button
      onClick={onClick}
      disabled={disabled}
      style={{
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        gap: "0.5rem",
        width: "100%",
        background: "rgba(255,255,255,0.05)",
        color: "#e2e8f0",
        border: "1px solid rgba(255,255,255,0.1)",
        borderRadius: "12px",
        padding: "0.75rem",
        fontSize: "0.9375rem",
        cursor: disabled ? "not-allowed" : "pointer",
        opacity: disabled ? 0.6 : 1,
        transition: "all 0.2s",
      }}
    >
      <span style={{ fontSize: "1.25rem" }}>{icon}</span>
      <span>{loading ? "Connecting..." : label}</span>
    </button>
  );
}
