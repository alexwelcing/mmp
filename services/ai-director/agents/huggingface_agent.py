"""HuggingFaceAgent — Image generation via Hugging Face Inference API.

Uses HF Inference API instead of self-hosted ComfyUI for cost savings.
With HF Pro ($9/mo): Unlimited inference on most models.

Requires HF_TOKEN environment variable.
"""

from __future__ import annotations

import os
from io import BytesIO
from pathlib import Path
from typing import Literal

import httpx
from PIL import Image


class HuggingFaceAgent:
    """
    Generates images using Hugging Face Inference API.
    
    Models available (with HF Pro):
    - stabilityai/stable-diffusion-xl-base-1.0 (2D generation)
    - stabilityai/stable-diffusion-x4-upscaler (4x upscaling)
    - timbrooks/instruct-pix2pix (image editing)
    - facebook/audiogen-medium (audio generation)
    
    Cost: FREE with HF Pro ($9/mo), or $0.001-0.01 per call on free tier
    """

    def __init__(self) -> None:
        self.token = os.environ.get("HF_TOKEN")
        if not self.token:
            raise RuntimeError(
                "HF_TOKEN environment variable not set.\n"
                "Get token at: https://huggingface.co/settings/tokens\n"
                "Or run: export HF_TOKEN=hf_..."
            )
        
        self.base_url = "https://api-inference.huggingface.co/models"
        self.headers = {"Authorization": f"Bearer {self.token}"}

    async def generate_drafts(
        self,
        prompt: str,
        count: int = 4,
        negative_prompt: str = "blurry, low quality, distorted",
    ) -> list[bytes]:
        """Generate multiple draft images."""
        images = []
        
        # Add variety to prompts
        variations = [
            f"{prompt}, highly detailed, masterpiece",
            f"{prompt}, cinematic lighting, professional",
            f"{prompt}, vibrant colors, artistic",
            f"{prompt}, concept art, trending",
        ]
        
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
                    f"{self.base_url}/stabilityai/stable-diffusion-xl-base-1.0",
                    headers=self.headers,
                    json=payload,
                )
                response.raise_for_status()
                images.append(response.content)
        
        return images

    async def upscale(self, image_bytes: bytes, scale: int = 4) -> bytes:
        """Upscale image using stabilityai upscaler."""
        async with httpx.AsyncClient(timeout=60.0) as client:
            # Convert bytes to base64 for API
            import base64
            image_b64 = base64.b64encode(image_bytes).decode()
            
            payload = {
                "inputs": {
                    "image": f"data:image/png;base64,{image_b64}",
                    "prompt": "high quality, detailed",
                },
            }
            
            response = await client.post(
                f"{self_url}/stabilityai/stable-diffusion-x4-upscaler",
                headers=self.headers,
                json=payload,
            )
            response.raise_for_status()
            return response.content

    async def generate_audio(
        self,
        description: str,
        duration: float = 5.0,
    ) -> bytes:
        """Generate audio using AudioGen."""
        async with httpx.AsyncClient(timeout=30.0) as client:
            payload = {
                "inputs": description,
                "parameters": {
                    "max_new_tokens": int(duration * 50),  # ~50 tokens per second
                },
            }
            
            response = await client.post(
                f"{self.base_url}/facebook/audiogen-medium",
                headers=self.headers,
                json=payload,
            )
            response.raise_for_status()
            return response.content

    def save_image(self, image_bytes: bytes, path: Path) -> None:
        """Save image bytes to disk."""
        image = Image.open(BytesIO(image_bytes))
        image.save(path)


class MockHuggingFaceAgent:
    """Mock agent for testing without HF token."""
    
    async def generate_drafts(self, prompt: str, count: int = 4) -> list[bytes]:
        """Return placeholder data."""
        return [b"mock_image_data"] * count
    
    async def upscale(self, image_bytes: bytes, scale: int = 4) -> bytes:
        return b"mock_upscaled_data"
    
    async def generate_audio(self, description: str, duration: float = 5.0) -> bytes:
        return b"mock_audio_data"
    
    def save_image(self, image_bytes: bytes, path: Path) -> None:
        """Create empty file."""
        path.touch()


def get_hf_agent() -> HuggingFaceAgent | MockHuggingFaceAgent:
    """Factory function to get appropriate agent."""
    if os.environ.get("HF_TOKEN"):
        return HuggingFaceAgent()
    else:
        print("⚠️  HF_TOKEN not set, using mock agent")
        return MockHuggingFaceAgent()
