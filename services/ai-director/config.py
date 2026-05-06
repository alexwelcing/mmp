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
    gcp_project_id: str = Field(
        "local-dev",
        description="GCP project ID (set to 'local-dev' for local development)",
    )
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
    pubsub_status_topic: str = Field(
        "",
        description=(
            "Optional Pub/Sub topic for job lifecycle events "
            "(leave empty to disable event publishing)"
        ),
    )
    pubsub_max_messages: int = Field(
        10,
        description="Max messages to pull per batch",
    )
    ai_k8s_namespaces: str = Field(
        "ai-director,comfyui,resplat,audio",
        description="Comma-separated Kubernetes namespaces exposed through MCP tools",
    )

    # ------------------------------------------------------------------ #
    # Asset Storage (GCS for persistent assets, Filestore for ComfyUI)     #
    # ------------------------------------------------------------------ #
    filestore_mount_path: str = Field(
        "/mnt/filestore",
        description="NFS mount point for shared ComfyUI models & outputs",
    )
    output_base_path: str = Field(
        "/mnt/filestore/outputs",
        description="Directory where completed assets are written",
    )
    gcs_bucket: str = Field(
        "",
        description="GCS bucket for persistent asset storage (e.g., 'my-project-assets')",
    )

    # ------------------------------------------------------------------ #
    # Image Generation Provider                                            #
    # ------------------------------------------------------------------ #
    image_provider: Literal["comfyui", "huggingface"] = Field(
        "comfyui",
        description="Image generation backend: 'comfyui' (GCP GPU) or 'huggingface' (API)",
    )
    huggingface_token: str = Field(
        "",
        description="Hugging Face API token (required if image_provider='huggingface')",
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
    # ReSplat (experimental 3DGS worker)                                   #
    # ------------------------------------------------------------------ #
    use_resplat_for_3d: bool = Field(
        False,
        description="Route 3D generation through the ReSplat worker instead of ComfyUI",
    )
    resplat_endpoint: HttpUrl = Field(
        "http://resplat-worker.ai-director.svc.cluster.local:9001",
        description="Internal K8s service URL for the ReSplat inference service",
    )
    resplat_timeout_seconds: int = Field(
        600,
        description="Max seconds to wait for ReSplat inference",
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
        "0x" + "00" * 32,
        description="Private key for the AI Director operational wallet (required in prod)",
    )

    # ------------------------------------------------------------------ #
    # Service                                                              #
    # ------------------------------------------------------------------ #
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    environment: Literal["local", "dev", "staging", "production"] = "local"
    max_concurrent_jobs: int = Field(
        20,
        description="Max concurrent generation pipelines in this instance",
    )
    enable_mcp_server: bool = Field(
        True,
        description="Expose MCP-compatible AI Director tools over HTTP",
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
