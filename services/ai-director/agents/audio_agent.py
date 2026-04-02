"""
audio_agent.py — Generates environmental audio / soundscapes for characters.

Supports two backends:
  - Moshi  (Kyutai's real-time audio LLM)
  - VibeVoice-1.5B (lightweight voice/ambient model)

Both backends are called via an internal HTTP inference service.  The
backend to use is configured via ``Settings.audio_model``.
"""

from __future__ import annotations

import logging

import httpx

from config import Settings

logger = logging.getLogger(__name__)

# Map character roles to descriptive audio prompts.
_ROLE_AUDIO_PROMPTS: dict[str, str] = {
    "warrior": "epic battle drums, steel clashing, low brass fanfare",
    "mage": "mystical ambience, choral ethereal voices, arcane hum",
    "scout": "forest ambience, light percussion, wind through leaves",
    "healer": "gentle harp arpeggios, soft choir, warm ambient pads",
    "assassin": "dark cinematic tension, subtle percussion, shadow ambience",
    "berserker": "intense tribal drums, roaring crowd, heavy metal undertones",
    "paladin": "sacred choir, church organ, triumphant brass fanfare",
}

_DEFAULT_PROMPT = "neutral adventure ambience, orchestral underscore"


class AudioAgent:
    """Generates character soundscapes using an external audio inference API."""

    def __init__(self, settings: Settings) -> None:
        self._endpoint = str(settings.audio_endpoint).rstrip("/")
        self._model = settings.audio_model
        self._output_base = settings.output_base_path

    async def generate_soundscape(self, character_role: str) -> str:
        """
        Generate a short audio clip (8–16 seconds) matching a character role.

        Args:
            character_role: The character's class/role (e.g. "warrior").

        Returns:
            URL / file path of the generated audio file.
        """
        prompt = _ROLE_AUDIO_PROMPTS.get(character_role.lower(), _DEFAULT_PROMPT)
        logger.info(
            "Generating soundscape for role=%s using model=%s",
            character_role,
            self._model,
        )

        if self._model == "moshi":
            return await self._call_moshi(prompt)
        return await self._call_vibevoice(prompt)

    # ------------------------------------------------------------------ #
    # Backend implementations                                              #
    # ------------------------------------------------------------------ #

    async def _call_moshi(self, prompt: str) -> str:
        """
        Call the Moshi inference service.

        Moshi accepts a text description and returns a streaming audio
        response.  We collect the full response and save to Filestore.

        API reference: https://github.com/kyutai-labs/moshi
        """
        payload = {
            "text": prompt,
            "duration_seconds": 12,
            "sample_rate": 24000,
            "format": "wav",
        }
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(
                f"{self._endpoint}/generate",
                json=payload,
            )
            resp.raise_for_status()
            data = resp.json()

        audio_url: str = data["audio_url"]
        logger.info("Moshi soundscape generated: %s", audio_url)
        return audio_url

    async def _call_vibevoice(self, prompt: str) -> str:
        """
        Call the VibeVoice-1.5B inference service.

        VibeVoice is lighter weight and suitable for lower-cost deployments.
        It accepts a style prompt and optional reference audio.
        """
        payload = {
            "style_prompt": prompt,
            "duration": 10,
            "temperature": 0.8,
        }
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(
                f"{self._endpoint}/vibevoice/generate",
                json=payload,
            )
            resp.raise_for_status()
            data = resp.json()

        audio_url: str = data["output_url"]
        logger.info("VibeVoice soundscape generated: %s", audio_url)
        return audio_url
