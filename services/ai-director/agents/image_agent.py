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
from pathlib import Path
from typing import Any

import httpx

from config import Settings

logger = logging.getLogger(__name__)

# Paths to the ComfyUI workflow JSON templates.
# The workflow files live in services/comfyui-worker/workflows/ and are
# mounted into the ComfyUI worker container at /workflows/.  When running
# the AI Director locally (outside Docker), we fall back to the sibling
# directory relative to the repository root.
_WORKFLOW_DIR = Path(__file__).resolve().parents[3] / "services" / "comfyui-worker" / "workflows"
_LIGHTNING_2D_WORKFLOW = _WORKFLOW_DIR / "lightning_2d_draft.json"
_3DGS_WORKFLOW = _WORKFLOW_DIR / "3dgs_generation.json"


def _load_workflow(path: Path) -> dict[str, Any]:
    """Load a ComfyUI workflow JSON file."""
    with open(path) as fh:
        return json.load(fh)


class ImageAgent:
    """
    Generates 2D character drafts, upscales them, and produces
    3D Gaussian Splatting (3DGS) assets via ComfyUI.
    """

    def __init__(self, settings: Settings) -> None:
        self._endpoint = str(settings.comfyui_endpoint).rstrip("/")
        self._timeout = settings.comfyui_timeout_seconds
        self._output_base = settings.output_base_path

    # ------------------------------------------------------------------ #
    # Public methods                                                       #
    # ------------------------------------------------------------------ #

    async def generate_2d_drafts(
        self,
        preferences: dict[str, Any],
        count: int = 4,
    ) -> list[str]:
        """
        Generate `count` 2D character drafts using the SDXL-Lightning workflow.

        Returns a list of file URLs / paths to the generated images.
        Each draft is generated concurrently for speed.
        """
        tasks = [
            self._run_comfyui_workflow(
                workflow_path=_LIGHTNING_2D_WORKFLOW,
                parameters=self._build_2d_params(preferences, seed=i * 1000),
            )
            for i in range(count)
        ]
        results = await asyncio.gather(*tasks)
        logger.info("Generated %d 2D drafts", len(results))
        return list(results)

    async def upscale_draft(self, draft_url: str) -> str:
        """
        Upscale a selected draft using the ComfyUI clarity upscaler node.

        The clarity upscaler (4× tile-based) preserves fine details while
        dramatically increasing resolution for print / 3D use.
        """
        params = {"input_image": draft_url, "upscale_factor": 4}
        upscaled = await self._run_comfyui_workflow(
            workflow_path=_LIGHTNING_2D_WORKFLOW,  # reuses same template w/ upscale node
            parameters={**params, "mode": "upscale"},
        )
        logger.info("Upscaled draft: %s → %s", draft_url, upscaled)
        return upscaled

    async def generate_3dgs(self, upscaled_url: str) -> str:
        """
        Convert a 2D upscaled image to a 3D Gaussian Splatting scene.

        Uses the SHARP (Score-based HARmonic Prior) model loaded inside
        ComfyUI via the comfyui-3dgs custom node pack.
        """
        params = {"input_image": upscaled_url}
        threedgs_path = await self._run_comfyui_workflow(
            workflow_path=_3DGS_WORKFLOW,
            parameters=params,
        )
        logger.info("3DGS generation complete: %s", threedgs_path)
        return threedgs_path

    # ------------------------------------------------------------------ #
    # Private helpers                                                      #
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
            "steps": 6,       # SDXL-Lightning uses very few steps
            "cfg_scale": 1.5,
            "width": 1024,
            "height": 1024,
        }

    async def _run_comfyui_workflow(
        self,
        workflow_path: Path,
        parameters: dict[str, Any],
    ) -> str:
        """
        Submit a parameterised workflow to ComfyUI and wait for completion.

        ComfyUI's /prompt endpoint accepts a graph; we patch selected nodes
        with our runtime parameters then poll /history until done.

        In a real deployment the ComfyUI webhook (POST /webhook/comfyui)
        replaces the polling loop for lower latency.
        """
        workflow = _load_workflow(workflow_path)
        workflow = self._patch_workflow(workflow, parameters)

        client_id = str(uuid.uuid4())
        prompt_payload = {"prompt": workflow, "client_id": client_id}

        async with httpx.AsyncClient(timeout=self._timeout) as client:
            # Submit the prompt.
            resp = await client.post(
                f"{self._endpoint}/prompt",
                json=prompt_payload,
            )
            resp.raise_for_status()
            prompt_id: str = resp.json()["prompt_id"]

            # Poll /history until the job is done.
            output_path = await self._poll_for_completion(client, prompt_id)

        return output_path

    async def _poll_for_completion(
        self, client: httpx.AsyncClient, prompt_id: str
    ) -> str:
        """Poll ComfyUI /history endpoint until a prompt completes."""
        for attempt in range(self._timeout // 2):
            await asyncio.sleep(2)
            resp = await client.get(f"{self._endpoint}/history/{prompt_id}")
            resp.raise_for_status()
            history = resp.json()

            if prompt_id not in history:
                continue  # not finished yet

            outputs = history[prompt_id].get("outputs", {})
            for node_id, node_output in outputs.items():
                images = node_output.get("images", [])
                if images:
                    img = images[0]
                    filename: str = img["filename"]
                    subfolder: str = img.get("subfolder", "")
                    url = (
                        f"{self._endpoint}/view"
                        f"?filename={filename}&subfolder={subfolder}"
                    )
                    return url

            raise RuntimeError(f"ComfyUI prompt {prompt_id} finished with no image output")

        raise TimeoutError(f"ComfyUI prompt {prompt_id} did not complete within {self._timeout}s")

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
