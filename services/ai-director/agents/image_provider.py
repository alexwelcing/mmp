"""image_provider.py — Pluggable image generation providers.

Supports multiple backends:
- comfyui: Self-hosted ComfyUI (GPU-intensive, full control)
- huggingface: Hugging Face Inference API (cheap, serverless)
- mock: For testing (no external calls)

Set via IMAGE_PROVIDER environment variable or config.
"""

from __future__ import annotations

import os
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Literal, Protocol


class ImageProvider(Protocol):
    """Protocol for image generation providers."""
    
    async def generate_drafts(
        self,
        prompt: str,
        count: int = 4,
        **kwargs
    ) -> list[bytes]:
        """Generate draft images."""
        ...
    
    async def upscale(self, image_bytes: bytes, scale: int = 4) -> bytes:
        """Upscale an image."""
        ...
    
    async def generate_3d(self, image_bytes: bytes) -> bytes:
        """Generate 3D asset from 2D image."""
        ...


class ComfyUIImageProvider:
    """Provider using self-hosted ComfyUI (GPU required)."""
    
    def __init__(self, endpoint: str = "http://comfyui-service.comfyui.svc.cluster.local:8188"):
        self.endpoint = endpoint
        self._client = None
    
    async def generate_drafts(self, prompt: str, count: int = 4, **kwargs) -> list[bytes]:
        """Generate using ComfyUI workflows."""
        # Import existing ImageAgent logic
        from .image_agent import ImageAgent
        agent = ImageAgent()
        return await agent.generate_drafts(prompt, count)
    
    async def upscale(self, image_bytes: bytes, scale: int = 4) -> bytes:
        from .image_agent import ImageAgent
        agent = ImageAgent()
        return await agent.upscale(image_bytes)
    
    async def generate_3d(self, image_bytes: bytes) -> bytes:
        from .image_agent import ImageAgent
        agent = ImageAgent()
        return await agent.generate_mesh(image_bytes)


class HuggingFaceImageProvider:
    """Provider using Hugging Face Inference API (serverless)."""
    
    def __init__(self, token: str | None = None):
        self.token = token or os.environ.get("HF_TOKEN")
        if not self.token:
            raise RuntimeError(
                "HF_TOKEN required for HuggingFaceImageProvider. "
                "Get token at: https://huggingface.co/settings/tokens"
            )
        self.base_url = "https://api-inference.huggingface.co/models"
        self.headers = {"Authorization": f"Bearer {self.token}"}
    
    async def generate_drafts(
        self,
        prompt: str,
        count: int = 4,
        negative_prompt: str = "blurry, low quality, distorted",
        **kwargs
    ) -> list[bytes]:
        """Generate using Hugging Face Inference API."""
        import httpx
        
        images = []
        variations = [
            f"{prompt}, highly detailed, masterpiece",
            f"{prompt}, cinematic lighting, professional",
            f"{prompt}, vibrant colors, artistic",
            f"{prompt}, concept art, trending",
        ]
        
        model = os.environ.get("HF_MODEL_SD", "stabilityai/stable-diffusion-xl-base-1.0")
        
        async with httpx.AsyncClient(timeout=60.0) as client:
            for i in range(min(count, len(variations))):
                payload = {
                    "inputs": variations[i],
                    "parameters": {
                        "negative_prompt": negative_prompt,
                        "num_inference_steps": 30,
                        "guidance_scale": 7.5,
                        "width": 512,
                        "height": 512,
                    },
                }
                
                response = await client.post(
                    f"{self.base_url}/{model}",
                    headers=self.headers,
                    json=payload,
                )
                response.raise_for_status()
                images.append(response.content)
        
        return images
    
    async def upscale(self, image_bytes: bytes, scale: int = 4) -> bytes:
        """Upscale using HF upscaler model."""
        import base64
        import httpx
        
        model = os.environ.get("HF_MODEL_UPSCALER", "stabilityai/stable-diffusion-x4-upscaler")
        image_b64 = base64.b64encode(image_bytes).decode()
        
        async with httpx.AsyncClient(timeout=60.0) as client:
            payload = {
                "inputs": {
                    "image": f"data:image/png;base64,{image_b64}",
                    "prompt": "high quality, detailed",
                },
            }
            
            response = await client.post(
                f"{self.base_url}/{model}",
                headers=self.headers,
                json=payload,
            )
            response.raise_for_status()
            return response.content
    
    async def generate_3d(self, image_bytes: bytes) -> bytes:
        """HF doesn't support 3D generation - use fallback or raise."""
        raise NotImplementedError(
            "3D generation not available with Hugging Face provider. "
            "Use ComfyUI provider or mock provider for testing."
        )


class MockImageProvider:
    """Mock provider for testing (no external calls)."""
    
    async def generate_drafts(self, prompt: str, count: int = 4, **kwargs) -> list[bytes]:
        """Return mock data."""
        return [b"mock_image_" + str(i).encode() for i in range(count)]
    
    async def upscale(self, image_bytes: bytes, scale: int = 4) -> bytes:
        return b"mock_upscaled"
    
    async def generate_3d(self, image_bytes: bytes) -> bytes:
        return b"mock_3d_mesh"


def get_image_provider(
    provider: Literal["comfyui", "huggingface", "mock"] | None = None
) -> ImageProvider:
    """Factory function to get configured image provider.
    
    Args:
        provider: Explicit provider name, or None to read from IMAGE_PROVIDER env var
        
    Returns:
        Configured ImageProvider instance
        
    Raises:
        RuntimeError: If provider is unknown or missing required config
    """
    if provider is None:
        provider = os.environ.get("IMAGE_PROVIDER", "comfyui")
    
    match provider.lower():
        case "comfyui":
            return ComfyUIImageProvider()
        
        case "huggingface" | "hf":
            return HuggingFaceImageProvider()
        
        case "mock":
            return MockImageProvider()
        
        case _:
            raise RuntimeError(
                f"Unknown image provider: {provider}. "
                f"Use: comfyui, huggingface, or mock"
            )


# Backward compatibility - default to ComfyUI
default_provider = get_image_provider("comfyui")
