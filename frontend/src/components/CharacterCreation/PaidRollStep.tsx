/**
 * PaidRollStep.tsx — Step 4 of the onboarding funnel.
 *
 * Lets the user choose between a $1 random roll and a $9.99 custom character.
 * Payment is handled via a Stripe-style credit card form (crypto is hidden).
 * In production: integrate Stripe.js + server-side USDC conversion.
 */

import type { FormEvent, CSSProperties } from "react";
import { useState } from "react";
import type { MintTier, CharacterTraits, Role, Aesthetic } from "../../types/character";

interface PaidRollStepProps {
  onSubmit: (tier: MintTier, preferences: Partial<CharacterTraits>) => Promise<void>;
  isLoading: boolean;
}

type ActiveTab = "random" | "custom";

export function PaidRollStep({ onSubmit, isLoading }: PaidRollStepProps) {
  const [activeTab, setActiveTab] = useState<ActiveTab>("random");
  const [selectedRole, setSelectedRole] = useState<Role>("Warrior");
  const [selectedAesthetic, setSelectedAesthetic] = useState<Aesthetic>("Fantasy");

  // Mock payment state (replace with Stripe Elements in production).
  const [cardNumber, setCardNumber] = useState("");
  const [expiry, setExpiry] = useState("");
  const [cvv, setCvv] = useState("");
  const [paymentError, setPaymentError] = useState<string | null>(null);

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setPaymentError(null);

    // Mock payment validation.
    if (cardNumber.replace(/\s/g, "").length < 16) {
      setPaymentError("Please enter a valid card number.");
      return;
    }

    const preferences: Partial<CharacterTraits> =
      activeTab === "custom"
        ? { role: selectedRole, aesthetic: selectedAesthetic }
        : {};

    await onSubmit(activeTab === "random" ? "random" : "custom", preferences);
  };

  const price = activeTab === "random" ? "$1.00" : "$9.99";

  return (
    <div>
      <h2 style={{ textAlign: "center", margin: "0 0 0.25rem" }}>
        Get Your Character
      </h2>
      <p style={{ color: "#94a3b8", textAlign: "center", margin: "0 0 1.5rem", fontSize: "0.875rem" }}>
        Yours forever. Trade, earn, collect.
      </p>

      {/* Tab selector */}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "1fr 1fr",
          gap: "0.5rem",
          marginBottom: "1.5rem",
          background: "rgba(0,0,0,0.3)",
          borderRadius: "12px",
          padding: "0.375rem",
        }}
      >
        <TabButton
          label="🎲 Lucky Roll — $1"
          active={activeTab === "random"}
          onClick={() => setActiveTab("random")}
        />
        <TabButton
          label="✨ Custom — $9.99"
          active={activeTab === "custom"}
          onClick={() => setActiveTab("custom")}
        />
      </div>

      {/* Custom trait selectors (only shown for custom tier) */}
      {activeTab === "custom" && (
        <div style={{ marginBottom: "1.5rem" }}>
          <TraitSelector
            label="Role"
            options={["Warrior", "Mage", "Scout", "Healer", "Assassin", "Berserker", "Paladin"]}
            value={selectedRole}
            onChange={(v) => setSelectedRole(v as Role)}
          />
          <TraitSelector
            label="Aesthetic"
            options={["Fantasy", "SciFi", "Cyberpunk", "Steampunk", "Mythological"]}
            value={selectedAesthetic}
            onChange={(v) => setSelectedAesthetic(v as Aesthetic)}
          />
          <p style={{ color: "#64748b", fontSize: "0.8rem", margin: "0.5rem 0 0" }}>
            * Rarity is always random — even for custom characters.
          </p>
        </div>
      )}

      {/* Payment form */}
      <form onSubmit={handleSubmit}>
        <div style={{ display: "flex", flexDirection: "column", gap: "0.75rem", marginBottom: "1rem" }}>
          <input
            type="text"
            placeholder="Card number"
            value={cardNumber}
            onChange={(e) => setCardNumber(formatCardNumber(e.target.value))}
            maxLength={19}
            style={inputStyle}
          />
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "0.75rem" }}>
            <input
              type="text"
              placeholder="MM / YY"
              value={expiry}
              onChange={(e) => setExpiry(formatExpiry(e.target.value))}
              maxLength={7}
              style={inputStyle}
            />
            <input
              type="text"
              placeholder="CVV"
              value={cvv}
              onChange={(e) => setCvv(e.target.value.replace(/\D/g, "").slice(0, 4))}
              style={inputStyle}
            />
          </div>
        </div>

        {paymentError && (
          <p style={{ color: "#ef4444", fontSize: "0.875rem", margin: "0 0 0.75rem" }}>
            {paymentError}
          </p>
        )}

        <button
          type="submit"
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
          }}
        >
          {isLoading ? "Processing..." : `Pay ${price}`}
        </button>

        <p style={{ color: "#475569", fontSize: "0.75rem", textAlign: "center", margin: "0.75rem 0 0" }}>
          🔒 Secure payment · Cancel anytime
        </p>
      </form>
    </div>
  );
}

// ── Sub-components ────────────────────────────────────────────────────

interface TabButtonProps {
  label: string;
  active: boolean;
  onClick: () => void;
}

function TabButton({ label, active, onClick }: TabButtonProps) {
  return (
    <button
      type="button"
      onClick={onClick}
      style={{
        padding: "0.625rem 0.5rem",
        borderRadius: "8px",
        border: "none",
        cursor: "pointer",
        fontWeight: active ? 700 : 400,
        background: active ? "rgba(124, 58, 237, 0.5)" : "transparent",
        color: active ? "#fff" : "#64748b",
        fontSize: "0.875rem",
        transition: "all 0.2s",
      }}
    >
      {label}
    </button>
  );
}

interface TraitSelectorProps {
  label: string;
  options: string[];
  value: string;
  onChange: (v: string) => void;
}

function TraitSelector({ label, options, value, onChange }: TraitSelectorProps) {
  return (
    <div style={{ marginBottom: "0.75rem" }}>
      <label style={{ display: "block", color: "#94a3b8", fontSize: "0.875rem", marginBottom: "0.375rem" }}>
        {label}
      </label>
      <div style={{ display: "flex", flexWrap: "wrap", gap: "0.375rem" }}>
        {options.map((opt) => (
          <button
            key={opt}
            type="button"
            onClick={() => onChange(opt)}
            style={{
              padding: "0.375rem 0.75rem",
              borderRadius: "20px",
              border: "1px solid",
              borderColor: value === opt ? "#a78bfa" : "rgba(255,255,255,0.1)",
              background: value === opt ? "rgba(167, 139, 250, 0.2)" : "transparent",
              color: value === opt ? "#a78bfa" : "#94a3b8",
              fontSize: "0.8125rem",
              cursor: "pointer",
              transition: "all 0.2s",
            }}
          >
            {opt}
          </button>
        ))}
      </div>
    </div>
  );
}

// ── Helpers ───────────────────────────────────────────────────────────

const inputStyle: CSSProperties = {
  width: "100%",
  background: "rgba(255,255,255,0.05)",
  border: "1px solid rgba(255,255,255,0.1)",
  borderRadius: "10px",
  padding: "0.75rem 1rem",
  color: "#fff",
  fontSize: "0.9375rem",
  boxSizing: "border-box",
  outline: "none",
};

function formatCardNumber(value: string): string {
  return value
    .replace(/\D/g, "")
    .slice(0, 16)
    .replace(/(.{4})/g, "$1 ")
    .trim();
}

function formatExpiry(value: string): string {
  const digits = value.replace(/\D/g, "").slice(0, 4);
  if (digits.length >= 3) {
    return `${digits.slice(0, 2)} / ${digits.slice(2)}`;
  }
  return digits;
}
