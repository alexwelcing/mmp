"""
resplat_agent.py — Foundation agent for ReSplat 3D Gaussian Splatting.

ReSplat (https://github.com/cvg/resplat) is a feed-forward recurrent model
that iteratively refines Gaussians.  Unlike the current ComfyUI-based mesh
pipeline, ReSplat requires a COLMAP-format dataset (multiple views + poses).

This agent is a scaffold for the future integration:
  1. Accept the upscaled character portrait.
  2. (Future) Generate multi-view images + synthetic poses.
  3. (Future) Run COLMAP sparse reconstruction.
  4. Call the ReSplat worker HTTP service to produce a .ply file.
  5. Return the public URL of the .ply.
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

from config import Settings

logger = logging.getLogger(__name__)


class ResplatAgent:
    """
    Scaffold agent for ReSplat-based 3D Gaussian Splatting generation.

    When ``use_resplat_for_3d`` is enabled in Settings, the Orchestrator
    routes 3D generation through this agent instead of ``ImageAgent``.
    """

    def __init__(self, settings: Settings) -> None:
        self._endpoint = str(settings.resplat_endpoint).rstrip("/")
        self._timeout = settings.resplat_timeout_seconds
        # Persistent client for connection pooling.
        self._client = httpx.AsyncClient(timeout=self._timeout)

    async def generate_3dgs(
        self,
        upscaled_url: str,
        job_id: str = "",
    ) -> str:
        """
        Generate a 3D Gaussian Splatting .ply from an upscaled 2D portrait.

        The full pipeline is delegated to the ReSplat worker:
          1. Multi-view synthesis (Stable Zero123)
          2. COLMAP sparse reconstruction
          3. ReSplat inference
        """
        logger.info(
            "ResplatAgent.generate_3dgs called for job=%s (image=%s)",
            job_id,
            upscaled_url,
        )

        # Pass the ComfyUI view URL directly to the worker.
        # The worker will download the image if it receives an HTTP URL,
        # which is essential when the AI Director runs natively on the host
        # while the ReSplat worker lives inside a Docker container.
        return await self._call_worker_from_image(upscaled_url, output_name=job_id)



    async def _call_worker_from_image(self, image_path: str, output_name: str) -> str:
        """POST to the ReSplat worker /infer-from-image endpoint."""
        payload: dict[str, Any] = {
            "image_path": image_path,
            "output_name": output_name,
            "use_zero123": True,
            "num_inference_steps": 50,
        }
        resp = await self._client.post(
            f"{self._endpoint}/infer-from-image",
            json=payload,
        )
        resp.raise_for_status()
        result = resp.json()

        ply_url: str = result["ply_url"]
        logger.info("ReSplat worker returned ply: %s", ply_url)
        return ply_url
