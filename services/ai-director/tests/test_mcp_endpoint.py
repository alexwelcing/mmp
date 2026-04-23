from __future__ import annotations

from fastapi.testclient import TestClient

import main
from agents.orchestrator import GenerationJob, JobStage
from k8s_ai_service import KubernetesAIService
from mcp_server import MCPServer


class FakeOrchestrator:
    def __init__(self) -> None:
        self.jobs: dict[str, GenerationJob] = {
            "job-123": GenerationJob(
                job_id="job-123",
                user_id="user-123",
                preferences={"role": "mage"},
                stage=JobStage.COMPLETE,
                draft_urls=["draft-a.png"],
                selected_draft_url="draft-a.png",
                upscaled_url="upscaled.png",
                threedgs_url="character.ply",
                audio_url="soundscape.wav",
                traits={"role": "Mage", "aesthetic": "Fantasy", "rarity": "Rare"},
            )
        }

    async def enqueue(self, user_id: str, preferences: dict[str, object]) -> str:
        self.jobs["job-new"] = GenerationJob(
            job_id="job-new",
            user_id=user_id,
            preferences=preferences,
        )
        return "job-new"

    def get_job(self, job_id: str) -> GenerationJob | None:
        return self.jobs.get(job_id)


class FakeKubernetesAIService(KubernetesAIService):
    def __init__(self) -> None:
        pass

    def list_ai_workloads(self) -> dict[str, object]:
        return {
            "config_source": "test",
            "namespaces": ["ai-director", "comfyui"],
            "workloads": [
                {
                    "namespace": "comfyui",
                    "deployments": [{"name": "comfyui-api", "ready_replicas": 1}],
                    "services": [{"name": "comfyui-service"}],
                    "jobs": [{"name": "comfyui-job-1", "active": 1}],
                }
            ],
        }

    def get_ai_workload(self, namespace: str, kind: str, name: str) -> dict[str, object]:
        return {
            "config_source": "test",
            "namespace": namespace,
            "kind": kind,
            "resource": {"name": name},
        }


def test_mcp_tools_list(monkeypatch) -> None:
    fake_orchestrator = FakeOrchestrator()
    fake_k8s_service = FakeKubernetesAIService()
    monkeypatch.setattr(main, "mcp_server", MCPServer(fake_orchestrator, fake_k8s_service))

    with TestClient(main.app) as client:
        response = client.post(
            "/mcp",
            json={"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}},
        )

    assert response.status_code == 200
    tool_names = [tool["name"] for tool in response.json()["result"]["tools"]]
    assert tool_names == [
        "submit_generation_job",
        "get_generation_job_status",
        "list_ai_k8s_resources",
        "get_ai_k8s_resource",
    ]


def test_mcp_submit_and_k8s_calls(monkeypatch) -> None:
    fake_orchestrator = FakeOrchestrator()
    fake_k8s_service = FakeKubernetesAIService()
    monkeypatch.setattr(main, "mcp_server", MCPServer(fake_orchestrator, fake_k8s_service))

    with TestClient(main.app) as client:
        submit_response = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/call",
                "params": {
                    "name": "submit_generation_job",
                    "arguments": {"user_id": "agent-user", "preferences": {"role": "scout"}},
                },
            },
        )
        k8s_response = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {"name": "list_ai_k8s_resources", "arguments": {}},
            },
        )
        status_response = client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "id": 4,
                "method": "tools/call",
                "params": {
                    "name": "get_generation_job_status",
                    "arguments": {"job_id": "job-123"},
                },
            },
        )

    assert submit_response.status_code == 200
    assert submit_response.json()["result"]["structuredContent"] == {
        "job_id": "job-new",
        "status": "queued",
    }

    assert k8s_response.status_code == 200
    assert k8s_response.json()["result"]["structuredContent"]["workloads"][0]["namespace"] == "comfyui"

    assert status_response.status_code == 200
    assert status_response.json()["result"]["structuredContent"]["stage"] == "complete"
    assert status_response.json()["result"]["structuredContent"]["traits"]["role"] == "Mage"
