"""
mcp_server.py — Minimal MCP-compatible tool surface for the AI Director.

The goal is not to replace FastAPI; it is to let other agents interact with the
AI Director through a standard tool protocol instead of custom one-off glue.
"""

from __future__ import annotations

import json
from typing import Any

from fastapi import HTTPException

from agents.orchestrator import OrchestratorAgent
from k8s_ai_service import KubernetesAIService

MCP_PROTOCOL_VERSION = "2025-03-26"


class MCPServer:
    """Minimal JSON-RPC/MCP handler for AI Director tools."""

    def __init__(
        self,
        orchestrator: OrchestratorAgent,
        k8s_ai_service: KubernetesAIService,
    ) -> None:
        self._orchestrator = orchestrator
        self._k8s_ai_service = k8s_ai_service

    async def handle(self, request_id: str | int | None, method: str, params: dict[str, Any]) -> dict[str, Any]:
        """Handle an MCP JSON-RPC request."""
        if method == "initialize":
            return self._success(
                request_id,
                {
                    "protocolVersion": MCP_PROTOCOL_VERSION,
                    "capabilities": {"tools": {}},
                    "serverInfo": {"name": "mmp-ai-director", "version": "1.0.0"},
                },
            )
        if method == "tools/list":
            return self._success(request_id, {"tools": self._tools()})
        if method == "tools/call":
            tool_name = params.get("name")
            tool_arguments = params.get("arguments", {})
            return self._success(request_id, await self._call_tool(tool_name, tool_arguments))

        return self._error(request_id, code=-32601, message=f"Unsupported MCP method: {method}")

    def _tools(self) -> list[dict[str, Any]]:
        return [
            {
                "name": "submit_generation_job",
                "description": "Queue a new character generation job in the AI Director.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "user_id": {"type": "string"},
                        "preferences": {"type": "object"},
                    },
                    "required": ["user_id"],
                },
            },
            {
                "name": "get_generation_job_status",
                "description": "Read the current status of a queued or completed generation job.",
                "inputSchema": {
                    "type": "object",
                    "properties": {"job_id": {"type": "string"}},
                    "required": ["job_id"],
                },
            },
            {
                "name": "list_ai_k8s_resources",
                "description": "Inspect the AI-serving Kubernetes namespaces managed by MMP.",
                "inputSchema": {"type": "object", "properties": {}},
            },
            {
                "name": "get_ai_k8s_resource",
                "description": "Fetch a single deployment, service, or job from the AI-serving plane.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "namespace": {"type": "string"},
                        "kind": {"type": "string"},
                        "name": {"type": "string"},
                    },
                    "required": ["namespace", "kind", "name"],
                },
            },
        ]

    async def _call_tool(self, tool_name: str | None, arguments: dict[str, Any]) -> dict[str, Any]:
        if tool_name == "submit_generation_job":
            user_id = arguments.get("user_id")
            if not isinstance(user_id, str) or not user_id:
                raise HTTPException(status_code=400, detail="submit_generation_job requires user_id")
            preferences = arguments.get("preferences", {})
            if not isinstance(preferences, dict):
                raise HTTPException(status_code=400, detail="preferences must be an object")
            job_id = await self._orchestrator.enqueue(user_id=user_id, preferences=preferences)
            payload = {"job_id": job_id, "status": "queued"}
            return self._tool_result(payload)

        if tool_name == "get_generation_job_status":
            job_id = arguments.get("job_id")
            if not isinstance(job_id, str) or not job_id:
                raise HTTPException(status_code=400, detail="get_generation_job_status requires job_id")
            job = self._orchestrator.get_job(job_id)
            if job is None:
                raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
            payload = {
                "job_id": job.job_id,
                "stage": job.stage.value,
                "draft_urls": job.draft_urls,
                "selected_draft_url": job.selected_draft_url,
                "upscaled_url": job.upscaled_url,
                "threedgs_url": job.threedgs_url,
                "audio_url": job.audio_url,
                "nft_token_id": job.nft_token_id,
                "error": job.error,
                "traits": job.traits,
            }
            return self._tool_result(payload)

        if tool_name == "list_ai_k8s_resources":
            return self._tool_result(self._k8s_ai_service.list_ai_workloads())

        if tool_name == "get_ai_k8s_resource":
            namespace = arguments.get("namespace")
            kind = arguments.get("kind")
            name = arguments.get("name")
            if not all(isinstance(value, str) and value for value in (namespace, kind, name)):
                raise HTTPException(
                    status_code=400,
                    detail="get_ai_k8s_resource requires namespace, kind, and name",
                )
            return self._tool_result(
                self._k8s_ai_service.get_ai_workload(
                    namespace=namespace,
                    kind=kind,
                    name=name,
                )
            )

        raise HTTPException(status_code=404, detail=f"Unknown MCP tool: {tool_name}")

    @staticmethod
    def _tool_result(payload: dict[str, Any]) -> dict[str, Any]:
        text = json.dumps(payload, indent=2, sort_keys=True)
        return {
            "content": [{"type": "text", "text": text}],
            "structuredContent": payload,
            "isError": False,
        }

    @staticmethod
    def _success(request_id: str | int | None, result: dict[str, Any]) -> dict[str, Any]:
        return {"jsonrpc": "2.0", "id": request_id, "result": result}

    @staticmethod
    def _error(request_id: str | int | None, code: int, message: str) -> dict[str, Any]:
        return {"jsonrpc": "2.0", "id": request_id, "error": {"code": code, "message": message}}
