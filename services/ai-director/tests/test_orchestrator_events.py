from __future__ import annotations

import uuid

import pytest

from agents.orchestrator import GenerationJob, JobStage, OrchestratorAgent
from config import Settings


@pytest.mark.asyncio
async def test_run_pipeline_emits_stage_and_completion_events(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = Settings(
        environment="local",
        pubsub_status_topic="asset-generation-status-local",
    )
    agent = OrchestratorAgent(settings)
    job = GenerationJob(
        job_id=str(uuid.uuid4()),
        user_id="user-123",
        preferences={"role": "mage"},
    )

    events: list[tuple[str, str]] = []
    monkeypatch.setattr(
        agent,
        "_publish_job_event",
        lambda current_job, event_type: events.append((event_type, current_job.stage.value)),
    )

    async def _generate_2d_drafts(
        preferences: dict[str, str],
        count: int,
        job_id: str,
    ) -> list[str]:
        assert preferences["role"] == "mage"
        assert count == settings.comfyui_draft_count
        assert job_id == job.job_id
        return ["draft-a.png", "draft-b.png"]

    async def _select_best_draft(draft_urls: list[str]) -> str:
        assert draft_urls == ["draft-a.png", "draft-b.png"]
        return "draft-b.png"

    async def _upscale_draft(selected_draft_url: str, job_id: str) -> str:
        assert selected_draft_url == "draft-b.png"
        assert job_id == job.job_id
        return "upscaled.png"

    async def _generate_3dgs(upscaled_url: str, job_id: str) -> str:
        assert upscaled_url == "upscaled.png"
        assert job_id == job.job_id
        return "character.ply"

    async def _generate_soundscape(character_role: str) -> str:
        assert character_role == "mage"
        return "soundscape.wav"

    monkeypatch.setattr(agent._image_agent, "generate_2d_drafts", _generate_2d_drafts)
    monkeypatch.setattr(agent._evaluator, "select_best_draft", _select_best_draft)
    monkeypatch.setattr(agent._image_agent, "upscale_draft", _upscale_draft)
    monkeypatch.setattr(agent._image_agent, "generate_3dgs", _generate_3dgs)
    monkeypatch.setattr(agent._audio_agent, "generate_soundscape", _generate_soundscape)

    await agent._run_pipeline(job)

    assert job.stage is JobStage.COMPLETE
    assert events == [
        ("stage_changed", "drafting"),
        ("stage_changed", "evaluating"),
        ("stage_changed", "upscaling"),
        ("stage_changed", "generating_3dgs"),
        ("stage_changed", "generating_audio"),
        ("job_completed", "complete"),
    ]


@pytest.mark.asyncio
async def test_run_pipeline_emits_failure_event(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = Settings(
        environment="local",
        pubsub_status_topic="asset-generation-status-local",
    )
    agent = OrchestratorAgent(settings)
    job = GenerationJob(
        job_id=str(uuid.uuid4()),
        user_id="user-456",
        preferences={},
    )

    events: list[tuple[str, str]] = []
    monkeypatch.setattr(
        agent,
        "_publish_job_event",
        lambda current_job, event_type: events.append((event_type, current_job.stage.value)),
    )

    async def _boom(*_args: object, **_kwargs: object) -> list[str]:
        raise RuntimeError("draft generation failed")

    monkeypatch.setattr(agent._image_agent, "generate_2d_drafts", _boom)

    with pytest.raises(RuntimeError, match="draft generation failed"):
        await agent._run_pipeline(job)

    assert job.stage is JobStage.FAILED
    assert job.error == "draft generation failed"
    assert events == [
        ("stage_changed", "drafting"),
        ("job_failed", "failed"),
    ]
