/**
 * CharacterCard.tsx — Displays a fully generated character.
 *
 * Shows the character's image, attributes, 3D viewer placeholder,
 * and provides sharing / on-chain ownership CTAs.
 */

import { useState } from "react";
import type { Character } from "../../types/character";

interface CharacterCardProps {
  character: Character;
}

const RARITY_COLORS: Record<string, string> = {
  Common:    "#94a3b8",
  Uncommon:  "#4ade80",
  Rare:      "#60a5fa",
  Epic:      "#a78bfa",
  Legendary: "#f59e0b",
};

export function CharacterCard({ character }: CharacterCardProps) {
  const [viewMode, setViewMode] = useState<"2d" | "3d">("2d");
  const [copied, setCopied] = useState(false);

  const rarityColor = RARITY_COLORS[character.traits.rarity] ?? "#fff";

  const handleShare = async () => {
    const shareText = `I just created ${character.name} — a ${character.traits.rarity} ${character.traits.role} on MMP! Get yours free: ${window.location.href}`;

    if (navigator.share) {
      try {
        await navigator.share({ text: shareText, url: window.location.href });
      } catch {
        // User cancelled share sheet.
      }
    } else {
      await navigator.clipboard.writeText(shareText);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  return (
    <div>
      {/* Character name + rarity badge */}
      <div style={{ textAlign: "center", marginBottom: "1.25rem" }}>
        <h2 style={{ margin: "0 0 0.375rem", fontSize: "1.75rem" }}>
          {character.name}
        </h2>
        <span
          style={{
            display: "inline-block",
            padding: "0.25rem 0.75rem",
            borderRadius: "20px",
            border: `1px solid ${rarityColor}`,
            color: rarityColor,
            fontSize: "0.8125rem",
            fontWeight: 700,
            letterSpacing: "0.05em",
            textTransform: "uppercase",
          }}
        >
          {character.traits.rarity}
        </span>
      </div>

      {/* View mode toggle */}
      <div
        style={{
          display: "flex",
          justifyContent: "center",
          gap: "0.5rem",
          marginBottom: "1rem",
        }}
      >
        <ViewToggle label="2D Art" active={viewMode === "2d"} onClick={() => setViewMode("2d")} />
        <ViewToggle label="3D View" active={viewMode === "3d"} onClick={() => setViewMode("3d")} />
      </div>

      {/* Asset display */}
      <div
        style={{
          borderRadius: "16px",
          overflow: "hidden",
          marginBottom: "1.25rem",
          border: `1px solid ${rarityColor}33`,
          minHeight: "280px",
          background: "rgba(0,0,0,0.3)",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
        }}
      >
        {viewMode === "2d" ? (
          character.imageUrl ? (
            <img
              src={character.imageUrl}
              alt={character.name}
              style={{ width: "100%", display: "block" }}
            />
          ) : (
            <PlaceholderArt role={character.traits.role} />
          )
        ) : (
          <ThreeDViewer threedgsUrl={character.threedgsUrl} name={character.name} />
        )}
      </div>

      {/* Trait pills */}
      <div
        style={{
          display: "flex",
          flexWrap: "wrap",
          gap: "0.5rem",
          marginBottom: "1.25rem",
          justifyContent: "center",
        }}
      >
        <TraitPill label="Role" value={character.traits.role} />
        <TraitPill label="Aesthetic" value={character.traits.aesthetic} />
        <TraitPill label="Rarity" value={character.traits.rarity} color={rarityColor} />
        {character.tokenId !== undefined && (
          <TraitPill label="Token" value={`#${character.tokenId}`} />
        )}
      </div>

      {/* Action buttons */}
      <div style={{ display: "flex", gap: "0.75rem" }}>
        <button
          onClick={handleShare}
          style={{
            flex: 1,
            background: "rgba(255,255,255,0.05)",
            border: "1px solid rgba(255,255,255,0.1)",
            borderRadius: "12px",
            padding: "0.75rem",
            color: "#fff",
            cursor: "pointer",
            fontWeight: 600,
            fontSize: "0.9375rem",
          }}
        >
          {copied ? "✅ Copied!" : "📤 Share"}
        </button>

        {character.tokenId === undefined && (
          <button
            style={{
              flex: 1,
              background: "linear-gradient(135deg, #7c3aed, #a78bfa)",
              border: "none",
              borderRadius: "12px",
              padding: "0.75rem",
              color: "#fff",
              cursor: "pointer",
              fontWeight: 700,
              fontSize: "0.9375rem",
            }}
          >
            🔗 Own On-Chain
          </button>
        )}
      </div>

      {/* On-chain ownership hint */}
      {character.tokenId !== undefined && (
        <p style={{ color: "#4ade80", textAlign: "center", margin: "1rem 0 0", fontSize: "0.875rem" }}>
          ✅ Secured on Base L2 · Token #{character.tokenId}
        </p>
      )}
    </div>
  );
}

// ── Sub-components ────────────────────────────────────────────────────

interface ViewToggleProps {
  label: string;
  active: boolean;
  onClick: () => void;
}

function ViewToggle({ label, active, onClick }: ViewToggleProps) {
  return (
    <button
      onClick={onClick}
      style={{
        padding: "0.375rem 1rem",
        borderRadius: "20px",
        border: "1px solid",
        borderColor: active ? "#a78bfa" : "rgba(255,255,255,0.1)",
        background: active ? "rgba(167, 139, 250, 0.2)" : "transparent",
        color: active ? "#a78bfa" : "#94a3b8",
        cursor: "pointer",
        fontSize: "0.875rem",
        fontWeight: active ? 700 : 400,
        transition: "all 0.2s",
      }}
    >
      {label}
    </button>
  );
}

interface TraitPillProps {
  label: string;
  value: string;
  color?: string;
}

function TraitPill({ label, value, color }: TraitPillProps) {
  return (
    <div
      style={{
        background: "rgba(255,255,255,0.05)",
        border: "1px solid rgba(255,255,255,0.1)",
        borderRadius: "8px",
        padding: "0.375rem 0.625rem",
        fontSize: "0.8rem",
      }}
    >
      <span style={{ color: "#64748b" }}>{label}: </span>
      <span style={{ color: color ?? "#e2e8f0", fontWeight: 600 }}>{value}</span>
    </div>
  );
}

function PlaceholderArt({ role }: { role: string }) {
  const roleEmoji: Record<string, string> = {
    Warrior: "⚔️", Mage: "🔮", Scout: "🏹", Healer: "💊",
    Assassin: "🗡️", Berserker: "🪓", Paladin: "🛡️",
  };
  return (
    <div style={{ textAlign: "center", padding: "3rem" }}>
      <div style={{ fontSize: "5rem", marginBottom: "0.5rem" }}>
        {roleEmoji[role] ?? "🧙"}
      </div>
      <p style={{ color: "#475569", margin: 0 }}>Character art loading...</p>
    </div>
  );
}

function ThreeDViewer({ threedgsUrl, name }: { threedgsUrl: string; name: string }) {
  if (!threedgsUrl) {
    return (
      <div style={{ textAlign: "center", padding: "3rem" }}>
        <div style={{ fontSize: "3rem", marginBottom: "0.5rem" }}>🌐</div>
        <p style={{ color: "#475569", margin: 0, fontSize: "0.875rem" }}>
          3D model generating...
        </p>
      </div>
    );
  }

  // In production: use a WebGL-based 3DGS viewer (e.g. gaussian-splats-3d library).
  return (
    <div style={{ textAlign: "center", padding: "2rem" }}>
      <div style={{ fontSize: "3rem", marginBottom: "0.5rem" }}>🌐</div>
      <p style={{ color: "#a78bfa", fontWeight: 600, margin: "0 0 0.25rem" }}>{name}</p>
      <p style={{ color: "#475569", margin: 0, fontSize: "0.8rem" }}>
        3D viewer coming soon
        <br />
        <a
          href={threedgsUrl}
          target="_blank"
          rel="noreferrer"
          style={{ color: "#60a5fa" }}
        >
          Download .ply file
        </a>
      </p>
    </div>
  );
}
