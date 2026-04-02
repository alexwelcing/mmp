"""
config.py — Centralised configuration for the AI Director service.

Uses pydantic-settings so every value can be supplied via environment
variable or a .env file (for local development).  Production deployments
should inject secrets via GCP Secret Manager → Kubernetes secrets.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field, HttpUrl
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """All runtime configuration for the AI Director."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # ------------------------------------------------------------------ #
    # GCP                                                                  #
    # ------------------------------------------------------------------ #
    gcp_project_id: str = Field(..., description="GCP project ID")
    gcp_region: str = Field("us-central1", description="GCP region")

    # ------------------------------------------------------------------ #
    # Pub/Sub                                                              #
    # ------------------------------------------------------------------ #
    pubsub_topic: str = Field(
        "asset-generation-requests",
        description="Pub/Sub topic for incoming generation requests",
    )
    pubsub_subscription: str = Field(
        "asset-generation-requests-sub",
        description="Pub/Sub pull subscription consumed by this service",
    )
    pubsub_max_messages: int = Field(
        10,
        description="Max messages to pull per batch",
    )

    # ------------------------------------------------------------------ #
    # Filestore / Shared Storage                                           #
    # ------------------------------------------------------------------ #
    filestore_mount_path: str = Field(
        "/mnt/filestore",
        description="NFS mount point for shared ComfyUI models & outputs",
    )
    output_base_path: str = Field(
        "/mnt/filestore/outputs",
        description="Directory where completed assets are written",
    )

    # ------------------------------------------------------------------ #
    # ComfyUI                                                              #
    # ------------------------------------------------------------------ #
    comfyui_endpoint: HttpUrl = Field(
        "http://comfyui-service.comfyui.svc.cluster.local:8188",
        description="Internal K8s service URL for the ComfyUI API",
    )
    comfyui_timeout_seconds: int = Field(
        120,
        description="Max seconds to wait for a ComfyUI prompt to complete",
    )
    comfyui_draft_count: int = Field(
        4,
        description="Number of 2D draft images to generate before selection",
    )

    # ------------------------------------------------------------------ #
    # Audio                                                                #
    # ------------------------------------------------------------------ #
    audio_model: Literal["moshi", "vibevoice"] = Field(
        "moshi",
        description="Which audio generation backend to use",
    )
    audio_endpoint: HttpUrl = Field(
        "http://audio-service.ai-director.svc.cluster.local:9000",
        description="Internal audio inference service URL",
    )

    # ------------------------------------------------------------------ #
    # Web3 / Base L2                                                       #
    # ------------------------------------------------------------------ #
    base_rpc_url: HttpUrl = Field(
        "https://sepolia.base.org",
        description="Base L2 JSON-RPC endpoint (use mainnet for production)",
    )
    bundler_url: HttpUrl = Field(
        "https://api.pimlico.io/v2/base-sepolia/rpc",
        description="ERC-4337 bundler endpoint (Pimlico, Stackup, etc.)",
    )
    character_nft_address: str = Field(
        "0x0000000000000000000000000000000000000000",
        description="Deployed CharacterNFT contract address",
    )
    paymaster_address: str = Field(
        "0x0000000000000000000000000000000000000000",
        description="Deployed AIDirectorPaymaster contract address",
    )
    splits_factory_address: str = Field(
        "0x0000000000000000000000000000000000000000",
        description="Deployed CharacterSplits factory address",
    )
    # Private key for the AI Director's operational wallet.
    # REQUIRED in staging/production: set AI_DIRECTOR_PRIVATE_KEY env var,
    # ideally sourced from GCP Secret Manager via Secret Manager sidecar or
    # Workload Identity + Secret Manager API.  Never hardcode in source.
    ai_director_private_key: str = Field(
        ...,
        description="Private key for the AI Director operational wallet (required)",
    )

    # ------------------------------------------------------------------ #
    # Service                                                              #
    # ------------------------------------------------------------------ #
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    environment: Literal["local", "staging", "production"] = "local"
    max_concurrent_jobs: int = Field(
        20,
        description="Max concurrent generation pipelines in this instance",
    )
    # CORS: set to a comma-separated list of allowed origins in production.
    # e.g. "https://yourgame.com,https://www.yourgame.com"
    cors_allow_origins: str = Field(
        "*",
        description="Comma-separated allowed CORS origins; use '*' for local dev only",
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return a cached Settings singleton.

    Using lru_cache means we only parse env vars once per process,
    which is important for performance and test isolation.
    """
    return Settings()  # type: ignore[call-arg]
