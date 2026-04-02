"""
orchestrator.py — The central AI Director that coordinates all sub-agents.

Responsibilities:
  1. Pull generation requests from GCP Pub/Sub.
  2. Manage per-job state machines (draft → upscale → 3DGS → audio → mint).
  3. Delegate work to specialised sub-agents.
  4. Handle retries, dead-letter routing, and partial failures gracefully.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any

from google.cloud import pubsub_v1

from config import Settings
from state_store import JsonStateStore

from .audio_agent import AudioAgent
from .evaluator_agent import EvaluatorAgent
from .image_agent import ImageAgent
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
    stage_started_at_ms: int = 0
    stage_durations_ms: dict[str, int] = field(default_factory=dict)
    created_at_ms: int = field(default_factory=lambda: int(time.time() * 1000))
    updated_at_ms: int = field(default_factory=lambda: int(time.time() * 1000))
    mode: str = "mock"


class OrchestratorAgent:
    """Coordinates the full asset generation pipeline."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._jobs: dict[str, GenerationJob] = {}
        self._semaphore = asyncio.Semaphore(settings.max_concurrent_jobs)
        self._store = JsonStateStore(settings.job_state_store_path)

        self._image_agent = ImageAgent(settings)
        self._evaluator = EvaluatorAgent()
        self._audio_agent = AudioAgent(settings)
        self._web3_agent = Web3Agent(settings)

        self._subscriber: pubsub_v1.SubscriberClient | None = None
        self._subscription_path = ""
        if settings.environment != "local":
            self._subscriber = pubsub_v1.SubscriberClient()
            self._subscription_path = self._subscriber.subscription_path(
                settings.gcp_project_id, settings.pubsub_subscription
            )
        self._load_jobs()

    async def start(self) -> None:
        logger.info(
            "OrchestratorAgent starting; subscription=%s",
            self._subscription_path,
        )
        await self._pull_loop()

    async def enqueue(self, user_id: str, preferences: dict[str, Any]) -> str:
        job_id = str(uuid.uuid4())
        job = GenerationJob(
            job_id=job_id,
            user_id=user_id,
            preferences=preferences,
            mode=self._settings.execution_mode,
        )
        self._jobs[job_id] = job
        self._persist_jobs()
        asyncio.create_task(self._run_pipeline(job))
        return job_id

    def get_job(self, job_id: str) -> GenerationJob | None:
        return self._jobs.get(job_id)

    async def _pull_loop(self) -> None:
        if self._subscriber is None:
            raise RuntimeError("Pub/Sub subscriber is not initialized in local mode")
        loop = asyncio.get_running_loop()
        while True:
            try:
                response = await loop.run_in_executor(
                    None,
                    lambda: self._subscriber.pull(  # type: ignore[union-attr]
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
                        mode=self._settings.execution_mode,
                    )
                    self._jobs[job.job_id] = job
                    self._persist_jobs()
                    asyncio.create_task(
                        self._run_pipeline_with_ack(job=job, ack_id=received.ack_id)
                    )
            except Exception:
                logger.exception("Error in Pub/Sub pull loop; retrying in 5s")
                await asyncio.sleep(5)
            await asyncio.sleep(0.5)

    async def _run_pipeline_with_ack(self, job: GenerationJob, ack_id: str) -> None:
        if self._subscriber is None:
            raise RuntimeError("Pub/Sub subscriber is not initialized in local mode")
        loop = asyncio.get_running_loop()
        try:
            await self._run_pipeline(job)
            await loop.run_in_executor(
                None,
                lambda: self._subscriber.acknowledge(  # type: ignore[union-attr]
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

    async def _run_pipeline(self, job: GenerationJob) -> None:
        logger.info(
            "Starting pipeline for job %s (user=%s, mode=%s)",
            job.job_id,
            job.user_id,
            job.mode,
        )
        try:
            self._set_stage(job, JobStage.DRAFTING)
            job.draft_urls = await self._image_agent.generate_2d_drafts(
                job.preferences,
                count=self._settings.comfyui_draft_count,
            )
            self._persist_jobs()

            self._set_stage(job, JobStage.EVALUATING)
            job.selected_draft_url = await self._evaluator.select_best_draft(job.draft_urls)
            self._persist_jobs()

            self._set_stage(job, JobStage.UPSCALING)
            job.upscaled_url = await self._image_agent.upscale_draft(job.selected_draft_url)
            self._persist_jobs()

            self._set_stage(job, JobStage.GENERATING_3DGS)
            job.threedgs_url = await self._image_agent.generate_3dgs(job.upscaled_url)
            self._persist_jobs()

            self._set_stage(job, JobStage.GENERATING_AUDIO)
            character_role = str(job.preferences.get("role", "warrior"))
            job.audio_url = await self._audio_agent.generate_soundscape(character_role)
            self._persist_jobs()

            if job.preferences.get("mint_on_chain", False):
                self._set_stage(job, JobStage.MINTING)
                job.nft_token_id = await self._web3_agent.mint_character(
                    to_address=str(job.preferences["wallet_address"]),
                    metadata_uri=job.threedgs_url,
                )
                self._persist_jobs()

            self._set_stage(job, JobStage.COMPLETE)
            logger.info(
                "Pipeline complete for job %s; token_id=%s",
                job.job_id,
                job.nft_token_id,
            )
            self._persist_jobs()
        except Exception as exc:
            job.stage = JobStage.FAILED
            job.error = str(exc)
            job.updated_at_ms = int(time.time() * 1000)
            logger.exception("Pipeline failed for job %s", job.job_id)
            self._persist_jobs()
            raise

    def _set_stage(self, job: GenerationJob, next_stage: JobStage) -> None:
        now_ms = int(time.time() * 1000)
        if job.stage_started_at_ms > 0:
            previous_stage = job.stage.value
            previous_duration = max(0, now_ms - job.stage_started_at_ms)
            job.stage_durations_ms[previous_stage] = previous_duration
        job.stage = next_stage
        job.stage_started_at_ms = now_ms
        job.updated_at_ms = now_ms
        logger.info("job=%s stage=%s", job.job_id, next_stage.value)

    def _persist_jobs(self) -> None:
        payload = {job_id: asdict(job) for job_id, job in self._jobs.items()}
        self._store.save(payload)

    def _load_jobs(self) -> None:
        payload = self._store.load()
        for job_id, raw in payload.items():
            try:
                stage_value = str(raw.get("stage", JobStage.FAILED.value))
                job = GenerationJob(
                    job_id=str(raw["job_id"]),
                    user_id=str(raw["user_id"]),
                    preferences=dict(raw.get("preferences", {})),
                    stage=JobStage(stage_value),
                    draft_urls=list(raw.get("draft_urls", [])),
                    selected_draft_url=str(raw.get("selected_draft_url", "")),
                    upscaled_url=str(raw.get("upscaled_url", "")),
                    threedgs_url=str(raw.get("threedgs_url", "")),
                    audio_url=str(raw.get("audio_url", "")),
                    nft_token_id=raw.get("nft_token_id"),
                    error=raw.get("error"),
                    stage_started_at_ms=int(raw.get("stage_started_at_ms", 0)),
                    stage_durations_ms=dict(raw.get("stage_durations_ms", {})),
                    created_at_ms=int(raw.get("created_at_ms", int(time.time() * 1000))),
                    updated_at_ms=int(raw.get("updated_at_ms", int(time.time() * 1000))),
                    mode=str(raw.get("mode", self._settings.execution_mode)),
                )
                self._jobs[job_id] = job
            except Exception:
                logger.exception("Failed to load persisted job %s", job_id)
