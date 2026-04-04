"""
orchestrator.py — The central AI Director that coordinates all sub-agents.

Responsibilities:
  1. Pull generation requests from GCP Pub/Sub.
  2. Manage per-job state machines (draft → upscale → 3DGS → audio → mint).
  3. Delegate work to specialised sub-agents.
  4. Handle retries, dead-letter routing, and partial failures gracefully.

Design notes:
  - One asyncio task per active Pub/Sub message keeps the concurrency model
    simple while staying within the max_concurrent_jobs budget.
  - Job state is stored in an in-process dict for this tutorial; in
    production you would persist to Cloud Spanner or Firestore.
"""

from __future__ import annotations

import asyncio
import json
import logging
import random
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from google.cloud import pubsub_v1

from config import Settings
from .audio_agent import AudioAgent
from .evaluator_agent import EvaluatorAgent
from .image_agent import ImageAgent
from .resplat_agent import ResplatAgent
from .web3_agent import Web3Agent

logger = logging.getLogger(__name__)


class JobStage(str, Enum):
    """Ordered pipeline stages for an asset-generation job."""

    QUEUED = "queued"
    DRAFTING = "drafting"
    EVALUATING = "evaluating"
    UPSCALING = "upscaling"
    GENERATING_3DGS = "generating_3dgs"
    GENERATING_AUDIO = "generating_audio"
    MINTING = "minting"
    COMPLETE = "complete"
    FAILED = "failed"


@dataclass
class GenerationJob:
    """Runtime state for a single character-generation pipeline."""

    job_id: str
    user_id: str
    preferences: dict[str, Any]
    stage: JobStage = JobStage.QUEUED
    draft_urls: list[str] = field(default_factory=list)
    selected_draft_url: str = ""
    upscaled_url: str = ""
    threedgs_url: str = ""
    audio_url: str = ""
    nft_token_id: int | None = None
    error: str | None = None
    traits: dict[str, str] = field(default_factory=dict)


class OrchestratorAgent:
    """
    Coordinates the full asset generation pipeline.

    Usage::

        orchestrator = OrchestratorAgent(settings)
        await orchestrator.start()   # blocks; pulls from Pub/Sub indefinitely
    """

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._jobs: dict[str, GenerationJob] = {}
        self._semaphore = asyncio.Semaphore(settings.max_concurrent_jobs)

        # Sub-agents are instantiated once and reused across jobs.
        self._image_agent = ImageAgent(settings)
        self._evaluator = EvaluatorAgent()
        self._audio_agent = AudioAgent(settings)
        self._web3_agent = Web3Agent(settings)
        self._resplat_agent = ResplatAgent(settings) if settings.use_resplat_for_3d else None

        # Pub/Sub subscriber client is lazy-initialised so local dev
        # (where GOOGLE_APPLICATION_CREDENTIALS may be missing) doesn't crash.
        self._subscriber: pubsub_v1.SubscriberClient | None = None
        self._subscription_path: str | None = None

    # ------------------------------------------------------------------ #
    # Public API                                                           #
    # ------------------------------------------------------------------ #

    async def start(self) -> None:
        """Begin processing messages from Pub/Sub indefinitely."""
        self._ensure_subscriber()
        logger.info(
            "OrchestratorAgent starting; subscription=%s",
            self._subscription_path,
        )
        await self._pull_loop()

    async def enqueue(self, user_id: str, preferences: dict[str, Any]) -> str:
        """
        Directly enqueue a job (bypasses Pub/Sub; used by the FastAPI layer
        for low-latency local testing and the /generate endpoint).

        Returns the new job_id.
        """
        job_id = str(uuid.uuid4())
        job = GenerationJob(
            job_id=job_id,
            user_id=user_id,
            preferences=preferences,
        )
        self._jobs[job_id] = job
        self._trim_jobs()
        self._spawn_task(self._run_pipeline(job))
        return job_id

    def get_job(self, job_id: str) -> GenerationJob | None:
        """Return the current state of a job, or None if not found."""
        return self._jobs.get(job_id)

    # ------------------------------------------------------------------ #
    # Internal helpers                                                     #
    # ------------------------------------------------------------------ #

    def _trim_jobs(self) -> None:
        """Evict oldest jobs to prevent unbounded memory growth."""
        max_jobs = max(self._settings.max_concurrent_jobs * 10, 1000)
        while len(self._jobs) > max_jobs:
            oldest = next(iter(self._jobs))
            self._jobs.pop(oldest, None)

    def _ensure_subscriber(self) -> None:
        """Lazy-create the Pub/Sub subscriber client."""
        if self._subscriber is None:
            self._subscriber = pubsub_v1.SubscriberClient()
            self._subscription_path = self._subscriber.subscription_path(
                self._settings.gcp_project_id, self._settings.pubsub_subscription
            )

    @staticmethod
    def _spawn_task(coro) -> asyncio.Task:
        """Create a background task and log any unhandled exceptions."""
        task = asyncio.create_task(coro)

        def _log_exception(t: asyncio.Task) -> None:
            if not t.cancelled() and t.exception():
                logger.exception("Unhandled exception in background task: %s", t.exception())

        task.add_done_callback(_log_exception)
        return task

    # ------------------------------------------------------------------ #
    # Pub/Sub pull loop                                                    #
    # ------------------------------------------------------------------ #

    async def _pull_loop(self) -> None:
        """Pull messages in batches and dispatch pipeline tasks."""
        loop = asyncio.get_running_loop()

        while True:
            try:
                self._ensure_subscriber()
                response = await loop.run_in_executor(
                    None,
                    lambda: self._subscriber.pull(
                        request={
                            "subscription": self._subscription_path,
                            "max_messages": self._settings.pubsub_max_messages,
                        }
                    ),
                )
                for received in response.received_messages:
                    await self._semaphore.acquire()
                    msg_data = json.loads(received.message.data.decode())
                    job = GenerationJob(
                        job_id=msg_data.get("job_id", str(uuid.uuid4())),
                        user_id=msg_data["user_id"],
                        preferences=msg_data.get("preferences", {}),
                    )
                    self._jobs[job.job_id] = job
                    self._trim_jobs()
                    self._spawn_task(
                        self._run_pipeline_with_ack(
                            job,
                            ack_id=received.ack_id,
                        )
                    )
            except Exception:
                logger.exception("Error in Pub/Sub pull loop; retrying in 5s")
                await asyncio.sleep(5)

            # Slight back-off to avoid tight empty-queue polling.
            await asyncio.sleep(0.5)

    async def _run_pipeline_with_ack(
        self, job: GenerationJob, ack_id: str
    ) -> None:
        """Run pipeline, then ack the Pub/Sub message on success."""
        loop = asyncio.get_running_loop()
        try:
            await self._run_pipeline(job)
            self._ensure_subscriber()
            await loop.run_in_executor(
                None,
                lambda: self._subscriber.acknowledge(
                    request={
                        "subscription": self._subscription_path,
                        "ack_ids": [ack_id],
                    }
                ),
            )
        except Exception:
            logger.exception("Pipeline failed for job %s; message not acked", job.job_id)
        finally:
            self._semaphore.release()

    # ------------------------------------------------------------------ #
    # Pipeline                                                             #
    # ------------------------------------------------------------------ #

    async def _run_pipeline(self, job: GenerationJob) -> None:
        """Execute all pipeline stages in sequence."""
        logger.info("Starting pipeline for job %s (user=%s)", job.job_id, job.user_id)
        try:
            # Stage 1: Generate multiple 2D drafts in parallel.
            job.stage = JobStage.DRAFTING
            job.draft_urls = await self._image_agent.generate_2d_drafts(
                job.preferences,
                count=self._settings.comfyui_draft_count,
                job_id=job.job_id,
            )

            # Stage 2: Pick the best draft using the evaluator.
            job.stage = JobStage.EVALUATING
            job.selected_draft_url = await self._evaluator.select_best_draft(
                job.draft_urls
            )

            # Stage 3: Upscale the selected draft.
            job.stage = JobStage.UPSCALING
            job.upscaled_url = await self._image_agent.upscale_draft(
                job.selected_draft_url,
                job_id=job.job_id,
            )

            # Assign traits deterministically from the job id so they survive
            # re-runs and match what the contract will mint.
            job.traits = _generate_traits(job.job_id, job.preferences)

            # Stage 4: Generate 3D representation (ComfyUI mesh or ReSplat).
            job.stage = JobStage.GENERATING_3DGS
            if self._resplat_agent:
                job.threedgs_url = await self._resplat_agent.generate_3dgs(
                    job.upscaled_url,
                    job_id=job.job_id,
                )
            else:
                job.threedgs_url = await self._image_agent.generate_3dgs(
                    job.upscaled_url,
                    job_id=job.job_id,
                )

            # Stage 5: Generate audio soundscape.
            job.stage = JobStage.GENERATING_AUDIO
            character_role = job.preferences.get("role", "warrior")
            job.audio_url = await self._audio_agent.generate_soundscape(
                character_role
            )

            # Stage 6: Gasless on-chain mint (only if user opted in).
            if job.preferences.get("mint_on_chain", False):
                job.stage = JobStage.MINTING
                traits_indices: dict[str, int] | None = None
                if job.traits:
                    traits_indices = {
                        "role": _ROLES.index(job.traits["role"]),
                        "aesthetic": _AESTHETICS.index(job.traits["aesthetic"]),
                        "rarity": _RARITIES.index(job.traits["rarity"]),
                    }
                job.nft_token_id = await self._web3_agent.mint_character(
                    to_address=job.preferences["wallet_address"],
                    metadata_uri=job.threedgs_url,
                    traits=traits_indices,
                    tier=job.preferences.get("mint_tier", "free"),
                )

            job.stage = JobStage.COMPLETE
            logger.info("Pipeline complete for job %s; token_id=%s", job.job_id, job.nft_token_id)

        except Exception as exc:
            job.stage = JobStage.FAILED
            job.error = str(exc)
            logger.exception("Pipeline failed for job %s", job.job_id)
            raise

# ------------------------------------------------------------------ #
# Trait generation helpers                                           #
# ------------------------------------------------------------------ #

_ROLES = ["Warrior", "Mage", "Scout", "Healer", "Assassin", "Berserker", "Paladin"]
_AESTHETICS = ["Fantasy", "SciFi", "Cyberpunk", "Steampunk", "Mythological"]
_RARITIES = ["Common", "Uncommon", "Rare", "Epic", "Legendary"]


def _generate_traits(job_id: str, preferences: dict[str, Any]) -> dict[str, str]:
    """
    Generate character traits that mirror the on-chain probabilities in
    CharacterNFT.sol.  If the user specified role or aesthetic in
    preferences we respect those; rarity is always random.
    """
    # Use the job_id as a stable seed so traits never change for a job.
    seed = int(uuid.UUID(job_id))
    rng = random.Random(seed)

    role_pref = preferences.get("role")
    aesthetic_pref = preferences.get("aesthetic")

    role = role_pref.capitalize() if isinstance(role_pref, str) else rng.choice(_ROLES)
    aesthetic = (
        aesthetic_pref.capitalize()
        if isinstance(aesthetic_pref, str)
        else rng.choice(_AESTHETICS)
    )
    rarity = _roll_rarity(rng)

    return {"role": role, "aesthetic": aesthetic, "rarity": rarity}


def _roll_rarity(rng: random.Random) -> str:
    """Weighted rarity roll matching CharacterNFT.sol probabilities."""
    roll = rng.randint(0, 99)
    if roll < 50:
        return "Common"
    if roll < 80:
        return "Uncommon"
    if roll < 95:
        return "Rare"
    if roll < 99:
        return "Epic"
    return "Legendary"
