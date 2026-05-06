"""
Character Attribute System for AI-Generated NFT Characters.

This module defines the trait system that makes each character unique.
Traits affect both the visual generation (prompts) and on-chain metadata.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Any


# --------------------------------------------------------------------------- #
# Character Roles (Determines base archetype and abilities)
# --------------------------------------------------------------------------- #

ROLES = {
    "cyberpunk_hacker": {
        "description": "A digital infiltrator who manipulates systems and extracts secrets",
        "visual_traits": ["neon tattoos", "holographic visor", "cybernetic implants", "glowing circuits"],
        "aesthetic_bias": "neon_noir",
        "base_prompt": "cyberpunk hacker with {visual}, digital rain background, dystopian cityscape",
    },
    "mystic_knight": {
        "description": "An armored warrior wielding weapons forged from starlight and void",
        "visual_traits": ["crystalline armor", "starlight sword", "cosmic cape", "celestial halo"],
        "aesthetic_bias": "ethereal_fantasy",
        "base_prompt": "mystic knight with {visual}, ancient ruins, magical particles, ethereal glow",
    },
    "forest_druid": {
        "description": "A guardian of nature who commands the living world",
        "visual_traits": ["bark armor", "living vines", "antler crown", "nature magic aura"],
        "aesthetic_bias": "nature_magic",
        "base_prompt": "forest druid with {visual}, enchanted forest, bioluminescent plants, nature spirits",
    },
    "shadow_assassin": {
        "description": "A phantom killer who strikes from the darkness unseen",
        "visual_traits": ["smoke-wrapped cloak", "shadow daggers", "mask of void", "phantom limbs"],
        "aesthetic_bias": "shadow_forged",
        "base_prompt": "shadow assassin with {visual}, dark alleyway, smoke effects, ominous atmosphere",
    },
    "tech_mage": {
        "description": "A spellcaster who channels arcane power through technology",
        "visual_traits": ["circuit robes", "holo-spellbook", "arcane implants", "energy gauntlets"],
        "aesthetic_bias": "arcane_cybernetics",
        "base_prompt": "tech mage with {visual}, futuristic laboratory, holographic spells, neon magic",
    },
    "desert_wanderer": {
        "description": "A survivor who thrives in the harshest wastelands",
        "visual_traits": ["tattered robes", "sand-scarred tech", "goggles", "weathered cloak"],
        "aesthetic_bias": "post_apocalyptic",
        "base_prompt": "desert wanderer with {visual}, post-apocalyptic wasteland, dust storm, ruined structures",
    },
    "celestial_guardian": {
        "description": "A holy warrior blessed with divine light and wings",
        "visual_traits": ["golden wings", "crystalline armor", "divine halo", "light weapons"],
        "aesthetic_bias": "divine_light",
        "base_prompt": "celestial guardian with {visual}, heavenly clouds, divine radiance, angelic architecture",
    },
    "necrotic_sorcerer": {
        "description": "A master of death magic who commands the departed",
        "visual_traits": ["bone accessories", "glowing eyes", "death shroud", "soul fragments"],
        "aesthetic_bias": "dark_fantasy",
        "base_prompt": "necrotic sorcerer with {visual}, dark crypt, necrotic energy, undead minions",
    },
    "steam_captain": {
        "description": "A swashbuckling commander of airships and mechanical marvels",
        "visual_traits": ["steampunk coat", "mechanical limbs", "brass gadgets", "captain's hat"],
        "aesthetic_bias": "steampunk_ocean",
        "base_prompt": "steampunk captain with {visual}, airship deck, gears and steam, Victorian sci-fi",
    },
    "quantum_ranger": {
        "description": "A gunslinger who manipulates time and probability",
        "visual_traits": ["phase-shift coat", "quantum revolver", "holographic badge", "time echoes"],
        "aesthetic_bias": "sci_fi_western",
        "base_prompt": "quantum ranger with {visual}, futuristic wild west, time distortion effects, neon desert",
    },
}


# --------------------------------------------------------------------------- #
# Aesthetic Styles (Determines visual style and color palette)
# --------------------------------------------------------------------------- #

AESTHETICS = {
    "neon_noir": {
        "colors": ["electric blue", "hot pink", "acid green", "deep purple"],
        "lighting": "high contrast neon against dark shadows",
        "mood": "gritty, high-tech, mysterious",
    },
    "ethereal_fantasy": {
        "colors": ["moonlight silver", "starlight gold", "void black", "cosmic blue"],
        "lighting": "soft magical glow with particle effects",
        "mood": "mystical, otherworldly, majestic",
    },
    "nature_magic": {
        "colors": ["forest green", "earth brown", "flower pink", "sky blue"],
        "lighting": "dappled sunlight through leaves, bioluminescence",
        "mood": "organic, alive, harmonious",
    },
    "shadow_forged": {
        "colors": ["void black", "smoke grey", "blood red", "poison green"],
        "lighting": "deep shadows with minimal accent lighting",
        "mood": "ominous, dangerous, stealthy",
    },
    "arcane_cybernetics": {
        "colors": ["circuit blue", "magic purple", "tech orange", "data green"],
        "lighting": "holographic glow mixed with arcane radiance",
        "mood": "futuristic, magical, innovative",
    },
    "post_apocalyptic": {
        "colors": ["dust brown", "rust orange", "sun-bleached white", "toxic yellow"],
        "lighting": "harsh sunlight, dust particles, decay",
        "mood": "survivalist, rugged, desperate",
    },
    "divine_light": {
        "colors": ["pure gold", "holy white", "sapphire blue", "crimson red"],
        "lighting": "radiant divine glow, heavenly beams",
        "mood": "righteous, noble, transcendent",
    },
    "dark_fantasy": {
        "colors": ["bone white", "necrotic green", "soul blue", "ash grey"],
        "lighting": "eerie glow, flickering torchlight, dark magic",
        "mood": "macabre, powerful, forbidden",
    },
    "steampunk_ocean": {
        "colors": ["brass gold", "ocean teal", "copper brown", "steam white"],
        "lighting": "warm industrial light, steam effects, sunset",
        "mood": "adventurous, mechanical, nautical",
    },
    "sci_fi_western": {
        "colors": ["desert orange", "laser red", "hologram cyan", "dust brown"],
        "lighting": "harsh desert sun mixed with neon tech glow",
        "mood": "frontier spirit, high-tech outlaw, isolation",
    },
}


# --------------------------------------------------------------------------- #
# Rarity Tiers (Affects trait quality and special features)
# --------------------------------------------------------------------------- #

RARITY_TIERS = {
    "Common": {
        "weight": 50,
        "visual_bonus": [],
        "description": "A capable adventurer with standard equipment",
    },
    "Uncommon": {
        "weight": 30,
        "visual_bonus": ["weathered equipment", "minor scars", "personal touches"],
        "description": "An experienced character with customized gear",
    },
    "Rare": {
        "weight": 15,
        "visual_bonus": ["ornate details", "magical glow", "unique accessories"],
        "description": "A distinguished hero with exceptional equipment",
    },
    "Epic": {
        "weight": 4,
        "visual_bonus": ["legendary artifacts", "aura of power", "dramatic pose"],
        "description": "A legendary figure wielding world-altering power",
    },
    "Legendary": {
        "weight": 1,
        "visual_bonus": ["godlike presence", "reality-warping effects", "mythical companions"],
        "description": "A mythic being whose name echoes through history",
    },
}


# --------------------------------------------------------------------------- #
# Special Traits (Unique modifiers that add flavor)
# --------------------------------------------------------------------------- #

SPECIAL_TRAITS = [
    "one-eyed", "scarred face", "tattooed arms", "mechanical eye",
    "hooded", "masked", "crowned", "horned",
    "ethereal wings", "shadow tendrils", "holographic aura",
    "ancient armor", "experimental tech", "cursed artifact",
    "pet companion", "floating items", "energy manifestation",
]


@dataclass
class CharacterAttributes:
    """Complete attribute set for a generated character."""
    
    role: str
    role_description: str
    aesthetic: str
    rarity: str
    visual_traits: list[str]
    special_trait: str | None
    colors: list[str]
    lighting: str
    mood: str
    generation_prompt: str
    
    def to_metadata(self) -> dict[str, Any]:
        """Convert to NFT metadata format."""
        return {
            "role": self.role,
            "description": self.role_description,
            "aesthetic": self.aesthetic,
            "rarity": self.rarity,
            "visual_traits": self.visual_traits,
            "special_trait": self.special_trait,
            "colors": self.colors,
            "lighting": self.lighting,
            "mood": self.mood,
        }


def generate_character_attributes(user_id: str = "") -> CharacterAttributes:
    """
    Generate unique character attributes based on user_id for determinism.
    
    Args:
        user_id: Used as seed for deterministic generation
        
    Returns:
        CharacterAttributes with unique traits
    """
    # Use user_id as seed for deterministic but unique generation
    seed = hash(user_id) % (2**32) if user_id else random.randint(0, 2**32)
    rng = random.Random(seed)
    
    # Select role
    role_key = rng.choice(list(ROLES.keys()))
    role_data = ROLES[role_key]
    
    # Select aesthetic (biased toward role's preferred aesthetic)
    if rng.random() < 0.7:  # 70% chance to use role's preferred aesthetic
        aesthetic_key = role_data["aesthetic_bias"]
    else:
        aesthetic_key = rng.choice(list(AESTHETICS.keys()))
    aesthetic_data = AESTHETICS[aesthetic_key]
    
    # Select rarity based on weights
    rarity = rng.choices(
        list(RARITY_TIERS.keys()),
        weights=[t["weight"] for t in RARITY_TIERS.values()]
    )[0]
    rarity_data = RARITY_TIERS[rarity]
    
    # Build visual traits
    base_traits = rng.sample(role_data["visual_traits"], k=min(2, len(role_data["visual_traits"])))
    bonus_traits = rng.sample(rarity_data["visual_bonus"], k=min(1, len(rarity_data["visual_bonus"])))
    visual_traits = base_traits + bonus_traits
    
    # Maybe add special trait for rare+ characters
    special_trait = None
    if rarity in ["Rare", "Epic", "Legendary"] and rng.random() < 0.5:
        special_trait = rng.choice(SPECIAL_TRAITS)
    
    # Build generation prompt
    visual_description = ", ".join(visual_traits)
    if special_trait:
        visual_description = f"{special_trait}, {visual_description}"
    
    color_scheme = ", ".join(rng.sample(aesthetic_data["colors"], k=2))
    
    prompt_parts = [
        role_data["base_prompt"].format(visual=visual_description),
        f"color scheme: {color_scheme}",
        aesthetic_data["lighting"],
        f"mood: {aesthetic_data['mood']}",
        "highly detailed, professional digital art, 8k, masterpiece",
    ]
    
    # Add rarity-specific quality modifiers
    if rarity == "Legendary":
        prompt_parts.append("ethereal godlike presence, reality bending effects, maximum detail")
    elif rarity == "Epic":
        prompt_parts.append("dramatic lighting, powerful stance, legendary quality")
    elif rarity == "Rare":
        prompt_parts.append("ornate details, exceptional quality")
    
    generation_prompt = ", ".join(prompt_parts)
    
    return CharacterAttributes(
        role=role_key,
        role_description=role_data["description"],
        aesthetic=aesthetic_key,
        rarity=rarity,
        visual_traits=visual_traits,
        special_trait=special_trait,
        colors=aesthetic_data["colors"],
        lighting=aesthetic_data["lighting"],
        mood=aesthetic_data["mood"],
        generation_prompt=generation_prompt,
    )


def get_trait_rarity_description(rarity: str) -> str:
    """Get the description for a rarity tier."""
    return RARITY_TIERS[rarity]["description"]


def format_traits_for_display(attrs: CharacterAttributes) -> str:
    """Format attributes for human-readable display."""
    lines = [
        f"Role: {attrs.role.replace('_', ' ').title()}",
        f"Rarity: {attrs.rarity}",
        f"Aesthetic: {attrs.aesthetic.replace('_', ' ').title()}",
        "",
        f"Visual Traits: {', '.join(attrs.visual_traits)}",
    ]
    if attrs.special_trait:
        lines.append(f"Special: {attrs.special_trait}")
    lines.extend([
        "",
        f"Description: {attrs.role_description}",
        f"Mood: {attrs.mood}",
    ])
    return "\n".join(lines)
