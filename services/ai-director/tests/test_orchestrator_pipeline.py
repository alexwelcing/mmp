from __future__ import annotations

import asyncio
import tempfile
from pathlib import Path
from typing import Any, cast

import pytest

from agents.orchestrator import JobStage, OrchestratorAgent
from config import Settings


def build_settings(state_path: str) -> Settings:
    return Settings(
        gcp_project_id="local-project",
        gcp_region="us-central1",
        pubsub_topic="asset-generation-requests",
        pubsub_subscription="asset-generation-requests-sub",
        pubsub_max_messages=10,
        filestore_mount_path="/tmp/filestore",
        output_base_path="/tmp/filestore/outputs",
        comfyui_timeout_seconds=120,
        comfyui_draft_count=4,
        audio_model="moshi",
        character_nft_address="0x0000000000000000000000000000000000000001",
        paymaster_address="0x0000000000000000000000000000000000000002",
        splits_factory_address="0x0000000000000000000000000000000000000003",
        max_concurrent_jobs=4,
        cors_allow_origins="*",
        ai_director_private_key="0x" + "1" * 64,
        execution_mode="mock",
        job_state_store_path=state_path,
        environment="local",
        base_rpc_url=cast(Any, "https://sepolia.base.org/"),
        bundler_url=cast(Any, "https://example.invalid/rpc/"),
        comfyui_endpoint=cast(Any, "http://localhost:8188/"),
        audio_endpoint=cast(Any, "http://localhost:9000/"),
    )


@pytest.mark.asyncio
async def test_pipeline_reaches_complete_and_persists_state() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        state_path = str(Path(tmpdir) / "jobs.json")
        orchestrator = OrchestratorAgent(build_settings(state_path))

        job_id = await orchestrator.enqueue(user_id="u1", preferences={})

        for _ in range(50):
            job = orchestrator.get_job(job_id)
            assert job is not None
            if job.stage in {JobStage.COMPLETE, JobStage.FAILED}:
                break
            await asyncio.sleep(0.02)

        final_job = orchestrator.get_job(job_id)
        assert final_job is not None
        assert final_job.stage == JobStage.COMPLETE
        assert final_job.upscaled_url.startswith("mock://upscaled/")
        assert final_job.threedgs_url.startswith("mock://3dgs/")
        assert final_job.audio_url.startswith("mock://audio/")

        reloaded = OrchestratorAgent(build_settings(state_path))
        reloaded_job = reloaded.get_job(job_id)
        assert reloaded_job is not None
        assert reloaded_job.stage == JobStage.COMPLETE


@pytest.mark.asyncio
async def test_pipeline_can_mint_in_mock_mode() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        state_path = str(Path(tmpdir) / "jobs.json")
        orchestrator = OrchestratorAgent(build_settings(state_path))

        job_id = await orchestrator.enqueue(
            user_id="u2",
            preferences={
                "mint_on_chain": True,
                "wallet_address": "0x1111111111111111111111111111111111111111",
            },
        )

        for _ in range(50):
            job = orchestrator.get_job(job_id)
            assert job is not None
            if job.stage in {JobStage.COMPLETE, JobStage.FAILED}:
                break
            await asyncio.sleep(0.02)

        final_job = orchestrator.get_job(job_id)
        assert final_job is not None
        assert final_job.stage == JobStage.COMPLETE
        assert isinstance(final_job.nft_token_id, int)
