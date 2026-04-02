"""
evaluator_agent.py — Scores generated drafts and selects the best one.

In production you would call a vision model (GPT-4o, Gemini Vision, or a
fine-tuned CLIP scorer) to evaluate aesthetic quality.  For this tutorial
we implement a deterministic mock that exercises the same interface.

Scoring criteria:
  - Aesthetic quality (composition, colour harmony)
  - Prompt adherence (does the character match the requested role/aesthetic)
  - Uniqueness (avoid near-duplicate outputs)
"""

from __future__ import annotations

import hashlib
import logging
import random

logger = logging.getLogger(__name__)


class EvaluatorAgent:
    """
    Evaluates a list of image draft URLs and returns the URL of the
    draft deemed highest quality.

    The evaluation is intentionally stateless so multiple instances
    can run concurrently without coordination.
    """

    async def select_best_draft(self, draft_urls: list[str]) -> str:
        """
        Score each draft and return the URL of the winner.

        Args:
            draft_urls: List of URLs/paths returned by ImageAgent.

        Returns:
            The URL of the highest-scoring draft.

        Raises:
            ValueError: If the list is empty.
        """
        if not draft_urls:
            raise ValueError("Cannot evaluate an empty list of drafts")

        scores = [
            (url, await self._score_draft(url))
            for url in draft_urls
        ]

        # Sort descending by score; pick the best.
        scores.sort(key=lambda t: t[1], reverse=True)
        best_url, best_score = scores[0]

        logger.info(
            "Draft evaluation complete — selected %s (score=%.3f)",
            best_url,
            best_score,
        )
        return best_url

    # ------------------------------------------------------------------ #
    # Private                                                              #
    # ------------------------------------------------------------------ #

    async def _score_draft(self, url: str) -> float:
        """
        Return an aesthetic quality score in [0, 1] for a draft image.

        Tutorial implementation: derives a deterministic pseudo-score from
        the URL hash so we can write reproducible tests.  Replace with a
        real vision-model call in production.

        In production (example with Google Vertex AI):

            response = await vision_client.analyze_image(
                image_url=url,
                features=["AESTHETICS", "SAFE_SEARCH"],
            )
            return response.aesthetics_score
        """
        url_hash = int(hashlib.sha256(url.encode()).hexdigest(), 16)
        # Deterministic but spread across [0.3, 1.0] to look realistic.
        base_score = (url_hash % 700) / 1000 + 0.3

        # Add a tiny random jitter so equal-hash URLs aren't always tied.
        jitter = random.uniform(-0.01, 0.01)
        return min(1.0, max(0.0, base_score + jitter))
