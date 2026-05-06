"""
image_agent.py — Handles all image-based asset generation steps.

Interacts with a ComfyUI instance (running as a GKE Job) via its
HTTP API.  The ComfyUI prompt format is a JSON graph where each node
is identified by a numeric key.  We load workflow templates from
the workflows/ directory and parameterise them at runtime.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import uuid
from functools import lru_cache
from pathlib import Path
from typing import Any

import httpx

from config import Settings
from .providers.image_provider import ImageProvider, GeneratedImage
from .character_attributes import (
    CharacterAttributes,
    generate_character_attributes,
    format_traits_for_display,
)

logger = logging.getLogger(__name__)

# Paths to the ComfyUI workflow JSON templates.
# The workflow files live in services/comfyui-worker/workflows/ and are
# mounted into the ComfyUI worker container at /workflows/.  When running
# the AI Director locally (outside Docker), we fall back to the sibling
# directory relative to the repository root.
def _get_workflow_dir() -> Path:
    """Resolve workflow directory for both Docker and local dev."""
    # First priority: explicit env var
    if env_dir := os.environ.get("COMFYUI_WORKFLOWS_DIR"):
        return Path(env_dir)
    
    # Second priority: check if running in Docker (/app/workflows exists)
    docker_path = Path("/app/workflows")
    if docker_path.exists():
        return docker_path
    
    # Third priority: local dev relative to repo root
    try:
        repo_root = Path(__file__).resolve().parents[3]
        local_path = repo_root / "services" / "comfyui-worker" / "workflows"
        if local_path.exists():
            return local_path
    except IndexError:
        pass
    
    # Fallback: return a default that will fail gracefully
    return Path("/app/workflows")

_WORKFLOW_DIR = _get_workflow_dir()
_LIGHTNING_2D_WORKFLOW = _WORKFLOW_DIR / "lightning_2d_draft.json"
_MESH_WORKFLOW = _WORKFLOW_DIR / "mesh_generation.json"


def _check_workflow_files() -> bool:
    """Validate workflow files exist and provide helpful error messages.
    
    Returns True if workflows are available, False otherwise.
    When using a provider like HuggingFace, workflows are not required.
    """
    if not _WORKFLOW_DIR.exists():
        logger.warning(
            f"Workflow directory not found: {_WORKFLOW_DIR}. "
            f"ComfyUI workflows will not be available. "
            f"Set COMFYUI_WORKFLOWS_DIR if using ComfyUI provider."
        )
        return False
    
    missing = []
    if not _LIGHTNING_2D_WORKFLOW.exists():
        missing.append(_LIGHTNING_2D_WORKFLOW.name)
    if not _MESH_WORKFLOW.exists():
        missing.append(_MESH_WORKFLOW.name)
    
    if missing:
        available = list(_WORKFLOW_DIR.glob("*.json")) if _WORKFLOW_DIR.exists() else []
        logger.warning(
            f"Missing workflow files in {_WORKFLOW_DIR}: {', '.join(missing)}. "
            f"Available files: {[f.name for f in available]}"
        )
        return False
    
    return True

# Check workflows on module load but don't fail - provider may not need them
_WORKFLOWS_AVAILABLE = _check_workflow_files()


@lru_cache(maxsize=8)
def _load_workflow(path: Path) -> dict[str, Any]:
    """Load a ComfyUI workflow JSON file (cached in memory)."""
    with open(path) as fh:
        return json.load(fh)


class ImageAgent:
    """
    Generates 2D character drafts, upscales them, and produces
    3D Gaussian Splatting (3DGS) assets via ComfyUI.

    Supports webhook-driven completion via the AIDirectorWebhook custom node.
    """

    # Shared class-level state for webhook notifications across all instances.
    _webhook_events: dict[str, asyncio.Event] = {}
    _client_to_prompt: dict[str, str] = {}

    def __init__(self, settings: Settings, provider: ImageProvider | None = None) -> None:
        self._endpoint = str(settings.comfyui_endpoint).rstrip("/")
        self._timeout = settings.comfyui_timeout_seconds
        self._output_base = settings.output_base_path
        self._provider = provider
        # Reuse a single httpx client for connection pooling across all
        # ComfyUI requests (prompt submission + polling).
        self._client = httpx.AsyncClient(timeout=self._timeout)

    # ------------------------------------------------------------------ #
    # Public methods                                                       #
    # ------------------------------------------------------------------ #

    async def generate_2d_drafts(
        self,
        preferences: dict[str, Any],
        count: int = 4,
        job_id: str = "",
    ) -> tuple[list[str], CharacterAttributes]:
        """
        Generate `count` 2D character drafts using the configured provider.

        Returns a tuple of (image_urls, character_attributes).
        Each draft is generated concurrently for speed.
        """
        # Generate unique character attributes based on job_id
        attrs = generate_character_attributes(user_id=job_id)
        logger.info("Generated character attributes for %s:\n%s", job_id, format_traits_for_display(attrs))
        
        if self._provider:
            # Use pluggable provider (Hugging Face, etc.) with rich prompt
            prompt = attrs.generation_prompt
            tasks = [
                self._provider.generate_image(prompt, seed=i * 1000)
                for i in range(count)
            ]
            results = await asyncio.gather(*tasks)
            logger.info("Generated %d 2D drafts via provider", len(results))
            return [r.url for r in results], attrs
        
        # Fallback to ComfyUI workflow
        tasks = [
            self._run_comfyui_workflow(
                workflow_path=_LIGHTNING_2D_WORKFLOW,
                parameters=self._build_2d_params(preferences, seed=i * 1000),
                job_id=job_id,
                node_type="image",
            )
            for i in range(count)
        ]
        results = await asyncio.gather(*tasks)
        logger.info("Generated %d 2D drafts", len(results))
        return list(results), attrs

    async def upscale_draft(
        self, draft_url: str, job_id: str = ""
    ) -> str:
        """
        Upscale a selected draft.
        
        Uses HF provider if available, otherwise falls back to ComfyUI.
        """
        if self._provider:
            # Use HF provider for upscaling
            result = await self._provider.upscale_image(draft_url)
            return result.url
        
        # Fallback to ComfyUI workflow
        params = {"input_image": draft_url, "upscale_factor": 4}
        upscaled = await self._run_comfyui_workflow(
            workflow_path=_LIGHTNING_2D_WORKFLOW,
            parameters={**params, "mode": "upscale"},
            job_id=job_id,
            node_type="image",
        )
        logger.info("Upscaled draft: %s → %s", draft_url, upscaled)
        return upscaled

    async def generate_3dgs(
        self, upscaled_url: str, job_id: str = ""
    ) -> str:
        """
        Convert a 2D upscaled image to a 3D Gaussian Splatting scene.

        Uses the SHARP (Score-based HARmonic Prior) model loaded inside
        ComfyUI via the comfyui-3dgs custom node pack.
        """
        params = {"input_image": upscaled_url}
        threedgs_path = await self._run_comfyui_workflow(
            workflow_path=_MESH_WORKFLOW,
            parameters=params,
            job_id=job_id,
            node_type="3dgs",
        )
        logger.info("3DGS generation complete: %s", threedgs_path)
        return threedgs_path

    @classmethod
    def handle_webhook(cls, client_id: str) -> None:
        """
        Signal that a ComfyUI prompt has completed.

        Called by the FastAPI webhook endpoint when the AIDirectorWebhook
        node POSTs its notification.
        """
        event = cls._webhook_events.get(client_id)
        if event and not event.is_set():
            event.set()
            logger.debug("Webhook received for client_id=%s", client_id)

    # ------------------------------------------------------------------ #
    # Private helpers                                                    #
    # ------------------------------------------------------------------ #

    @staticmethod
    def _build_2d_params(
        preferences: dict[str, Any], seed: int = 0
    ) -> dict[str, Any]:
        """Build ComfyUI node parameters from user preferences."""
        role = preferences.get("role", "warrior")
        aesthetic = preferences.get("aesthetic", "fantasy")
        custom_prompt = preferences.get("prompt_override", "")

        base_prompt = (
            f"game character portrait, {role}, {aesthetic} aesthetic, "
            "detailed illustration, vibrant colors, dynamic pose, "
            "professional concept art, 8k resolution"
        )
        negative_prompt = (
            "blurry, low quality, deformed, ugly, watermark, signature"
        )
        return {
            "prompt": custom_prompt or base_prompt,
            "negative_prompt": negative_prompt,
            "seed": seed + hash(str(preferences)) % 100_000,
            "steps": 6,  # SDXL-Lightning uses very few steps
            "cfg_scale": 1.5,
            "width": 1024,
            "height": 1024,
        }

    @staticmethod
    def _build_prompt_from_preferences(preferences: dict[str, Any]) -> str:
        """Build a text prompt from user preferences for provider-based generation."""
        role = preferences.get("role", "warrior")
        aesthetic = preferences.get("aesthetic", "fantasy")
        custom_prompt = preferences.get("prompt_override", "")

        base_prompt = (
            f"game character portrait, {role}, {aesthetic} aesthetic, "
            "detailed illustration, vibrant colors, dynamic pose, "
            "professional concept art, 8k resolution"
        )
        return custom_prompt or base_prompt

    async def _run_comfyui_workflow(
        self,
        workflow_path: Path,
        parameters: dict[str, Any],
        job_id: str = "",
        node_type: str = "image",
    ) -> str:
        """
        Submit a parameterised workflow to ComfyUI and wait for completion.

        If ``job_id`` is provided we inject the AIDirectorWebhook custom node
        so ComfyUI can notify us when the prompt finishes, allowing us to
        exit the polling loop early.
        """
        workflow = _load_workflow(workflow_path)
        workflow = self._patch_workflow(workflow, parameters)

        client_id = str(uuid.uuid4())
        if job_id:
            workflow = self._inject_webhook_node(
                workflow, client_id=client_id, job_id=job_id, node_type=node_type
            )
            event = asyncio.Event()
            ImageAgent._webhook_events[client_id] = event

        prompt_payload = {"prompt": workflow, "client_id": client_id}

        try:
            resp = await self._client.post(
                f"{self._endpoint}/prompt",
                json=prompt_payload,
            )
            resp.raise_for_status()
            prompt_id: str = resp.json()["prompt_id"]

            if job_id:
                ImageAgent._client_to_prompt[client_id] = prompt_id

            # Poll /history until the job is done (or webhook signals us).
            output_path = await self._poll_for_completion(
                prompt_id, client_id=client_id if job_id else None
            )
        finally:
            # Clean up webhook state so the class-level registries don't grow
            # unbounded in long-running processes.
            if job_id:
                ImageAgent._webhook_events.pop(client_id, None)
                ImageAgent._client_to_prompt.pop(client_id, None)

        return output_path

    async def _poll_for_completion(
        self,
        prompt_id: str,
        client_id: str | None = None,
    ) -> str:
        """Poll ComfyUI /history endpoint until a prompt completes."""
        event = ImageAgent._webhook_events.get(client_id) if client_id else None

        for attempt in range(self._timeout // 2):
            if event and event.is_set():
                logger.debug("Prompt %s completed via webhook", prompt_id)
            else:
                # Exponential backoff capped at 8 s to reduce load.
                delay = min(2 * (2 ** attempt), 8)
                await asyncio.sleep(delay)

            resp = await self._client.get(f"{self._endpoint}/history/{prompt_id}")
            resp.raise_for_status()
            history = resp.json()

            if prompt_id not in history:
                if event and event.is_set():
                    # Webhook fired but history not yet visible — give it one more tick.
                    await asyncio.sleep(0.5)
                    continue
                continue  # not finished yet

            outputs = history[prompt_id].get("outputs", {})
            for node_id, node_output in outputs.items():
                if not isinstance(node_output, dict):
                    continue
                # ComfyUI nodes may emit files under keys like "images",
                # "gltf", "obj", "ply", etc.  We look for any list of dicts
                # that contain a "filename" key.
                for key, value in node_output.items():
                    if isinstance(value, list) and value:
                        first = value[0]
                        if isinstance(first, dict) and "filename" in first:
                            filename: str = first["filename"]
                            subfolder: str = first.get("subfolder", "")
                            file_type: str = first.get("type", "output")
                            url = (
                                f"{self._endpoint}/view"
                                f"?filename={filename}&subfolder={subfolder}&type={file_type}"
                            )
                            return url

            raise RuntimeError(
                f"ComfyUI prompt {prompt_id} finished with no output files"
            )

        raise TimeoutError(
            f"ComfyUI prompt {prompt_id} did not complete within {self._timeout}s"
        )

    @staticmethod
    def _patch_workflow(
        workflow: dict[str, Any],
        parameters: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Patch ComfyUI workflow node inputs with runtime parameters.

        The workflow JSON uses a convention where nodes named "PromptInput",
        "SeedInput", etc. can be overridden.  This is a simplified patcher;
        production code would use ComfyUI's dynamic prompt API.
        """
        for _node_id, node in workflow.items():
            if not isinstance(node, dict):
                continue
            inputs: dict = node.get("inputs", {})
            for key, value in parameters.items():
                if key in inputs:
                    inputs[key] = value
        return workflow

    @staticmethod
    def _inject_webhook_node(
        workflow: dict[str, Any],
        client_id: str,
        job_id: str,
        node_type: str,
    ) -> dict[str, Any]:
        """
        Append the AIDirectorWebhook custom node to the workflow graph.

        The node is wired to the final SaveImage / Save3DModel node so it
        executes after the generation is complete.
        """
        output_node_id: str | None = None
        for node_id, node in workflow.items():
            if not isinstance(node, dict):
                continue
            class_type = node.get("class_type", "")
            if class_type in ("SaveImage", "Save3DModel"):
                output_node_id = node_id
                break

        if output_node_id is None:
            logger.warning(
                "No SaveImage/Save3DModel node found; skipping webhook injection"
            )
            return workflow

        webhook_id = "9999"
        workflow[webhook_id] = {
            "inputs": {
                "images": [output_node_id, 0],
                "client_id": client_id,
                "job_id": job_id,
                "node_type": node_type,
            },
            "class_type": "AIDirectorWebhook",
        }
        return workflow
