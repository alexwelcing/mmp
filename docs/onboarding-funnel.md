# Onboarding Funnel Design

## Philosophy: Progressive Commitment

The single biggest mistake in Web3 games is leading with blockchain. We never mention crypto, wallets, or gas fees until the user has already fallen in love with their character.

---

## Funnel Stages

```
Stage 1: Hook        Stage 2: Reveal       Stage 3: Upsell       Stage 4: Ownership
───────────          ───────────────       ──────────────         ─────────────────
"Claim your          Character animation   "$1 to re-roll         "Your character,
 free character"     + attribute reveal    or customize"          forever on-chain"
    │                     │                    │                       │
No wallet            No mention           Credit card UX          Wallet creation
required             of blockchain        (abstracts crypto)      (optional, post-love)
```

---

## Stage 1: Free Roll (FreeRollStep)

**Goal**: Maximum conversion. Remove all friction.

**UI Elements**:
- Large CTA: "Claim Your Free Character"
- Social login: Google, Steam (players already have these)
- Loading animation: "The AI is crafting your character..." (30s)
- No mention of: blockchain, NFT, gas, wallet, crypto

**Backend**:
- Creates anonymous session
- Triggers AI Director pipeline
- Character stored in DB, not on-chain yet

**Conversion Target**: >60% of visitors click CTA

---

## Stage 2: Character Reveal

**Goal**: Create emotional attachment before any ask.

**UI Elements**:
- Dramatic reveal animation (3D card flip)
- Character name (AI-generated)
- Role badge (Warrior, Mage, Scout, etc.)
- Rarity indicator (Common → Legendary)
- Aesthetic tags
- Share button (viral loop)

**Copy Examples**:
- "Meet Zyraxen the Shadow Mage — your new companion"
- "Ultra Rare! Only 2% of characters have this trait combination"

**Conversion Target**: 40% share or continue

---

## Stage 3: Upsell (PaidRollStep entry)

**Goal**: Convert 10-15% to paid, while keeping others in the funnel.

**Dual Path Offer**:

```
┌─────────────────────┐    ┌──────────────────────────┐
│   🎲 Lucky Roll      │    │   ✨ Custom Character      │
│                     │    │                          │
│  $1.00              │    │  $9.99                   │
│                     │    │                          │
│  New random         │    │  Choose your:            │
│  character          │    │  - Role                  │
│  generation         │    │  - Aesthetic             │
│                     │    │  - Special traits        │
│  [Roll Now]         │    │  [Customize]             │
└─────────────────────┘    └──────────────────────────┘
```

**Payment UX**:
- Credit card form (Stripe-style)
- No mention of crypto until wallet creation step
- "Pay $1.00" button — familiar e-commerce UX

**What actually happens**: USDC payment on Base, abstracted by paymaster

---

## Stage 4: Ownership & On-Chain (Optional)

**Goal**: Convert engaged players to on-chain owners.

**Trigger**: After paid mint, or after playing for 7 days

**Value Proposition**:
- "Your character earns royalties when others use them in tournaments"
- "Trade or sell your character on any NFT marketplace"
- "Participate in governance of the game world"

**Wallet Creation**:
- "Create a free wallet to secure your character"
- Uses passkeys or social login (no seed phrase for new users)
- ERC-4337 smart wallet — first transaction gasless via Paymaster

---

## Metrics to Track

| Metric | Target | Notes |
|--------|--------|-------|
| CTA Click Rate | >60% | Stage 1 entry |
| Generation Completion | >95% | Pipeline reliability |
| Reveal → Share | >40% | Viral coefficient |
| Free → Paid Conversion | >10% | Core monetization |
| $1 Roll vs $9.99 Custom | 70/30 split | Volume vs value |
| Paid → On-chain | >50% | Long-term retention |
| On-chain → Governance | >20% | Community building |

---

## Copy Guidelines

### Never Say
- "NFT", "blockchain", "crypto", "gas fees", "wallet", "seed phrase"
- "Mint" (before Stage 4 reveal)
- "Smart contract", "on-chain", "L2"

### Always Say
- "Your character", "own forever", "earn royalties"
- "Secure", "trade", "collect"
- "Instant", "free to start", "no commitment"

---

## A/B Test Ideas

1. **Character name reveal timing**: Instant vs. letter-by-letter typewriter
2. **Rarity framing**: "Ultra Rare" vs. "Top 2% of characters"
3. **Upsell timing**: Immediate vs. after sharing
4. **Price anchoring**: Show $9.99 first to make $1 feel cheap
5. **Social proof**: "12,847 characters created today"
