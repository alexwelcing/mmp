"""
main.py — FastAPI application entry point for the AI Director service.

Exposes three HTTP endpoints:
  POST /generate          — Trigger a character generation pipeline.
  GET  /status/{job_id}  — Poll for job progress and results.
  POST /webhook/comfyui  — ComfyUI completion webhook (called by the worker).

The OrchestratorAgent runs in the background, consuming messages from
GCP Pub/Sub.  Direct /generate calls bypass Pub/Sub for low-latency
local testing.
"""

from __future__ import annotations

import logging
import sys
from contextlib import asynccontextmanager
from typing import Any

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from agents.orchestrator import OrchestratorAgent, JobStage, _ROLES, _AESTHETICS, _RARITIES
from config import get_settings

# -------------------------------------------------------------------- #
# Logging setup                                                          #
# -------------------------------------------------------------------- #
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger(__name__)

# -------------------------------------------------------------------- #
# Application lifespan                                                   #
# -------------------------------------------------------------------- #
settings = get_settings()
orchestrator = OrchestratorAgent(settings)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """Start the Pub/Sub pull loop in the background when the app boots."""
    import asyncio

    logger.info("AI Director starting up (env=%s)", settings.environment)
    # Only start Pub/Sub polling when not in local dev mode.
    if settings.environment != "local":
        asyncio.create_task(orchestrator.start())
    yield
    logger.info("AI Director shutting down")


# -------------------------------------------------------------------- #
# FastAPI app                                                            #
# -------------------------------------------------------------------- #
app = FastAPI(
    title="AI Director",
    description="Autonomous AI pipeline for Web3 game asset generation",
    version="1.0.0",
    lifespan=lifespan,
)

# Serve generated images statically
import os
os.makedirs("/tmp/outputs", exist_ok=True)
app.mount("/images", StaticFiles(directory="/tmp/outputs"), name="images")

# In production, set CORS_ALLOW_ORIGINS to a comma-separated list of
# allowed origins (e.g. "https://yourgame.com,https://www.yourgame.com").
# The wildcard is only permitted in local development.
if settings.cors_allow_origins == "*":
    _cors_origins: list[str] = ["*"] if settings.environment == "local" else []
else:
    _cors_origins = [o.strip() for o in settings.cors_allow_origins.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "Authorization"],
)


# -------------------------------------------------------------------- #
# Request / Response models                                              #
# -------------------------------------------------------------------- #

class GenerateRequest(BaseModel):
    user_id: str = Field(..., description="Unique user identifier")
    preferences: dict[str, Any] = Field(
        default_factory=dict,
        description="Optional generation preferences (role, aesthetic, etc.)",
    )
    mint_on_chain: bool = Field(
        False,
        description="Whether to mint the result as an NFT after generation",
    )
    wallet_address: str | None = Field(
        None,
        description="Recipient wallet address (required if mint_on_chain=True)",
    )


class GenerateResponse(BaseModel):
    job_id: str
    status: str
    message: str


class StatusResponse(BaseModel):
    job_id: str
    stage: str
    draft_urls: list[str]
    selected_draft_url: str
    upscaled_url: str
    threedgs_url: str
    audio_url: str
    nft_token_id: int | None
    error: str | None
    traits: dict[str, Any] = Field(default_factory=dict)


class MintRequest(BaseModel):
    wallet_address: str = Field(..., description="Recipient wallet address")
    tier: str = Field("free", description="Mint tier: free | random | custom")


class ComfyUIWebhookPayload(BaseModel):
    client_id: str
    job_id: str
    node_type: str = "image"  # "image" | "3dgs"


# -------------------------------------------------------------------- #
# Endpoints                                                              #
# -------------------------------------------------------------------- #

@app.post("/generate", response_model=GenerateResponse, status_code=202)
async def generate_character(request: GenerateRequest) -> GenerateResponse:
    """
    Trigger a new character generation pipeline.

    The job runs asynchronously.  Use GET /status/{job_id} to poll for
    results.  In production, prefer the Pub/Sub path for better backpressure.
    """
    if request.mint_on_chain and not request.wallet_address:
        raise HTTPException(
            status_code=400,
            detail="wallet_address is required when mint_on_chain is True",
        )

    prefs = dict(request.preferences)
    if request.mint_on_chain:
        prefs["mint_on_chain"] = True
        prefs["wallet_address"] = request.wallet_address

    job_id = await orchestrator.enqueue(
        user_id=request.user_id,
        preferences=prefs,
    )

    logger.info("Generation job %s created for user %s", job_id, request.user_id)
    return GenerateResponse(
        job_id=job_id,
        status="queued",
        message="Character generation started. Poll /status/{job_id} for updates.",
    )


@app.get("/status/{job_id}", response_model=StatusResponse)
async def get_status(job_id: str) -> StatusResponse:
    """
    Return the current pipeline state for a generation job.

    Poll this endpoint every 2–3 seconds.  When ``stage == "complete"``
    all asset URLs are populated and the character is ready to reveal.
    """
    job = orchestrator.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")

    return StatusResponse(
        job_id=job.job_id,
        stage=job.stage.value,
        draft_urls=job.draft_urls,
        selected_draft_url=job.selected_draft_url,
        upscaled_url=job.upscaled_url,
        threedgs_url=job.threedgs_url,
        audio_url=job.audio_url,
        nft_token_id=job.nft_token_id,
        error=job.error,
        traits=job.traits,
    )


@app.post("/mint/{job_id}", response_model=StatusResponse)
async def mint_job(job_id: str, request: MintRequest) -> StatusResponse:
    """
    Mint an already-completed character on-chain.

    The job must be in the ``complete`` stage and not already minted.
    """
    job = orchestrator.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
    if job.stage != JobStage.COMPLETE:
        raise HTTPException(
            status_code=400,
            detail=f"Job {job_id} is not complete (current stage: {job.stage.value})",
        )
    if job.nft_token_id is not None:
        raise HTTPException(
            status_code=400,
            detail=f"Job {job_id} is already minted (token {job.nft_token_id})",
        )

    traits: dict[str, int] | None = None
    if request.tier == "custom" and job.traits:
        traits = {
            "role": _ROLES.index(job.traits["role"]),
            "aesthetic": _AESTHETICS.index(job.traits["aesthetic"]),
            "rarity": _RARITIES.index(job.traits["rarity"]),
        }

    try:
        job.stage = JobStage.MINTING
        token_id = await orchestrator._web3_agent.mint_character(
            to_address=request.wallet_address,
            metadata_uri=job.threedgs_url or job.upscaled_url,
            traits=traits,
            tier=request.tier,
        )
        job.nft_token_id = token_id
        job.stage = JobStage.COMPLETE
        logger.info("Minted job %s as token %d", job_id, token_id)
    except Exception as exc:
        job.stage = JobStage.COMPLETE  # revert so user can retry
        raise HTTPException(status_code=500, detail=str(exc))

    return StatusResponse(
        job_id=job.job_id,
        stage=job.stage.value,
        draft_urls=job.draft_urls,
        selected_draft_url=job.selected_draft_url,
        upscaled_url=job.upscaled_url,
        threedgs_url=job.threedgs_url,
        audio_url=job.audio_url,
        nft_token_id=job.nft_token_id,
        error=job.error,
        traits=job.traits,
    )


@app.post("/webhook/comfyui", status_code=200)
async def comfyui_webhook(payload: ComfyUIWebhookPayload) -> dict[str, str]:
    """
    Receive completion notifications from ComfyUI workers.

    The AIDirectorWebhook custom node inside ComfyUI POSTs here when a
    prompt finishes.  We signal the waiting ``ImageAgent`` poll loop so
    it can fetch outputs immediately instead of waiting for the next poll.
    """
    logger.info(
        "ComfyUI webhook received: job=%s, client=%s, node_type=%s",
        payload.job_id,
        payload.client_id,
        payload.node_type,
    )

    from agents.image_agent import ImageAgent

    ImageAgent.handle_webhook(payload.client_id)
    return {"status": "acknowledged"}


@app.get("/health")
async def health() -> dict[str, str]:
    """Kubernetes liveness/readiness probe."""
    return {"status": "ok", "environment": settings.environment}


# -------------------------------------------------------------------- #
# Entrypoint                                                             #
# -------------------------------------------------------------------- #
if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8080,
        log_level=settings.log_level.lower(),
        reload=settings.environment == "local",
    )
