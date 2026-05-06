"""
Pluggable provider pattern for image generation.

Supports:
- Hugging Face Inference API (HF_TOKEN required)
- ComfyUI workers (GCP GPU or local)
"""

from __future__ import annotations

import os
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import Any

import requests
from google.cloud import storage
from huggingface_hub import InferenceClient
from PIL import Image

from config import Settings
from agents.character_attributes import CharacterAttributes, generate_character_attributes


@dataclass
class GeneratedImage:
    """Result from an image generation request."""

    url: str  # Public URL to the generated image
    width: int = 1024
    height: int = 1024
    metadata: dict[str, Any] | None = None


class ImageProvider(ABC):
    """Abstract base class for image generation providers."""

    @abstractmethod
    async def generate_image(
        self, prompt: str, **kwargs: Any
    ) -> GeneratedImage:
        """
        Generate an image from a text prompt.

        Args:
            prompt: The text prompt describing the desired image
            **kwargs: Provider-specific parameters (seed, guidance_scale, etc.)

        Returns:
            GeneratedImage with public URL to the generated image
        """
        raise NotImplementedError

    @abstractmethod
    async def upscale_image(
        self, image_url: str, **kwargs: Any
    ) -> GeneratedImage:
        """
        Upscale an existing image.

        Args:
            image_url: URL or path to the image to upscale
            **kwargs: Provider-specific parameters

        Returns:
            GeneratedImage with public URL to the upscaled image
        """
        raise NotImplementedError


class HuggingFaceProvider(ImageProvider):
    """
    Hugging Face Inference API provider for image generation.

    Uses FLUX.1-schnell for fast generation. Images are uploaded to GCS
    for persistent storage and public access.
    
    Requires:
    - HF_TOKEN environment variable or huggingface_token in settings
    - GCS_BUCKET environment variable or gcs_bucket in settings
    """

    DEFAULT_MODEL = "black-forest-labs/FLUX.1-schnell"

    def __init__(self, settings: Settings) -> None:
        self.token = settings.huggingface_token or os.environ.get("HF_TOKEN")
        if not self.token:
            raise ValueError(
                "Hugging Face token required. Set HF_TOKEN environment variable "
                "or huggingface_token in settings."
            )
        
        # GCS configuration
        self.gcs_bucket = settings.gcs_bucket or os.environ.get("GCS_BUCKET")
        if not self.gcs_bucket:
            raise ValueError(
                "GCS bucket required. Set GCS_BUCKET environment variable "
                "or gcs_bucket in settings."
            )
        self.gcs_client = storage.Client()
        self.bucket = self.gcs_client.bucket(self.gcs_bucket)
        
        self.output_base = settings.output_base_path

    async def generate_image(
        self, prompt: str, **kwargs: Any
    ) -> GeneratedImage:
        """Generate image using Hugging Face Inference API and upload to GCS."""
        model = kwargs.get("model", self.DEFAULT_MODEL)
        guidance_scale = kwargs.get("guidance_scale", 7.5)
        num_inference_steps = kwargs.get("num_inference_steps", 28)
        seed = kwargs.get("seed")

        # Generate image using HF Inference API
        api_url = f"https://router.huggingface.co/hf-inference/models/{model}"
        headers = {"Authorization": f"Bearer {self.token}"}
        payload = {
            "inputs": prompt,
            "parameters": {
                "guidance_scale": guidance_scale,
                "num_inference_steps": num_inference_steps,
            }
        }
        response = requests.post(api_url, headers=headers, json=payload)
        response.raise_for_status()
        image = Image.open(BytesIO(response.content))

        # Upload to GCS and get public URL
        public_url = self._upload_to_gcs(image, prefix="draft")

        return GeneratedImage(
            url=public_url,
            width=image.width,
            height=image.height,
            metadata={
                "provider": "huggingface",
                "model": model,
                "prompt": prompt,
                "seed": seed,
                "gcs_bucket": self.gcs_bucket,
            },
        )

    async def upscale_image(
        self, image_url: str, **kwargs: Any
    ) -> GeneratedImage:
        """Upscale image using simple 2x resize and upload to GCS."""
        # Load the image from URL
        response = requests.get(image_url)
        response.raise_for_status()
        image = Image.open(BytesIO(response.content))

        # Simple 2x upscale using PIL
        new_size = (image.width * 2, image.height * 2)
        upscaled = image.resize(new_size, Image.Resampling.LANCZOS)

        # Upload to GCS and get public URL
        public_url = self._upload_to_gcs(upscaled, prefix="upscaled")

        return GeneratedImage(
            url=public_url,
            width=upscaled.width,
            height=upscaled.height,
            metadata={
                "provider": "huggingface",
                "method": "pil_resize",
                "original": image_url,
                "gcs_bucket": self.gcs_bucket,
            },
        )

    def _upload_to_gcs(self, image: Image.Image, prefix: str = "image") -> str:
        """Upload PIL image to GCS and return public URL."""
        filename = f"{prefix}_{uuid.uuid4().hex[:8]}.png"
        blob = self.bucket.blob(f"characters/{filename}")
        
        # Save to bytes buffer
        buffer = BytesIO()
        image.save(buffer, format="PNG")
        buffer.seek(0)
        
        # Upload to GCS
        blob.upload_from_file(buffer, content_type="image/png")
        
        # Make publicly readable
        blob.make_public()
        
        return blob.public_url


class ComfyUIProvider(ImageProvider):
    """
    ComfyUI-based image generation provider.

    Connects to a ComfyUI instance (local or GCP GPU worker) via HTTP API.
    """

    def __init__(self, settings: Settings) -> None:
        self.endpoint = str(settings.comfyui_endpoint).rstrip("/")
        self.timeout = settings.comfyui_timeout_seconds
        self.output_base = settings.output_base_path

    async def generate_image(
        self, prompt: str, **kwargs: Any
    ) -> GeneratedImage:
        """Generate image via ComfyUI API (to be implemented)."""
        # This would integrate with the existing ComfyUI workflow logic
        # For now, delegate to the existing ImageAgent methods
        raise NotImplementedError(
            "ComfyUIProvider.generate_image should be called via ImageAgent directly"
        )

    async def upscale_image(
        self, image_url: str, **kwargs: Any
    ) -> GeneratedImage:
        """Upscale image via ComfyUI API."""
        raise NotImplementedError(
            "ComfyUIProvider.upscale_image should be called via ImageAgent directly"
        )


class ImageProviderFactory:
    """Factory for creating the appropriate image provider."""

    @staticmethod
    def create(settings: Settings) -> ImageProvider:
        """
        Create an image provider based on configuration.

        Provider selection priority:
        1. settings.image_provider if explicitly set
        2. "huggingface" if settings.use_huggingface is True
        3. "comfyui" as default
        """
        provider_type = settings.image_provider.lower()

        if provider_type == "huggingface":
            return HuggingFaceProvider(settings)
        elif provider_type == "comfyui":
            return ComfyUIProvider(settings)
        else:
            raise ValueError(f"Unknown image provider: {provider_type}")
