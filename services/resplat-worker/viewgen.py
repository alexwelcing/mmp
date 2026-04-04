"""
viewgen.py — Generate multi-view images from a single portrait using
Stable Zero123 via the diffusers library.

The generated views are saved to a COLMAP-compatible directory structure:
    dataset/
      scene/
        images/
          000.png
          001.png
          ...

Stable Zero123 is loaded from the Hugging Face Hub on first use.
The model cache is shared with the Hugging Face cache volume.
"""

from __future__ import annotations

import logging
from pathlib import Path

import numpy as np
from PIL import Image

logger = logging.getLogger(__name__)

# Number of views to generate around the object.
NUM_VIEWS = 8
AZIMUTHS = [0, 45, 90, 135, 180, 225, 270, 315]
ELEVATION = 15.0  # degrees above horizon
DEFAULT_STEPS = 50


def generate_views(
    input_image_path: str,
    output_dir: str,
    num_inference_steps: int = DEFAULT_STEPS,
) -> list[str]:
    """
    Generate `NUM_VIEWS` novel views of the input image using Stable Zero123.

    Args:
        input_image_path: Path to the source 2D portrait (PNG/JPG).
        output_dir:       Directory where the views will be written.
        num_inference_steps: Diffusion sampling steps (higher = slower/better).

    Returns:
        List of file paths to the generated view images.
    """
    import torch
    from diffusers import DiffusionPipeline

    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    logger.info("Loading Stable Zero123 from Hugging Face Hub...")
    pipe = DiffusionPipeline.from_pretrained(
        "stabilityai/stable-zero123",
        torch_dtype=torch.float16 if torch.cuda.is_available() else torch.float32,
    )
    device = "cuda" if torch.cuda.is_available() else "cpu"
    pipe = pipe.to(device)
    logger.info("Stable Zero123 loaded on %s", device.upper())

    input_image = Image.open(input_image_path).convert("RGB")
    view_paths: list[str] = []

    for idx, azimuth in enumerate(AZIMUTHS):
        logger.info(
            "Generating view %d/%d (azimuth=%d, elevation=%d)",
            idx + 1,
            len(AZIMUTHS),
            azimuth,
            ELEVATION,
        )

        # Zero123 expects elevation/azimuth in radians or degrees depending
        # on the diffusers version.  Modern diffusers accepts degrees via
        # the `elevation` and `azimuth` kwargs.
        result = pipe(
            image=input_image,
            elevation=ELEVATION,
            azimuth=azimuth,
            num_inference_steps=num_inference_steps,
        )
        view_img = result.images[0]

        view_file = out_path / f"{idx:03d}.png"
        view_img.save(view_file)
        view_paths.append(str(view_file))

    logger.info("Generated %d views in %s", len(view_paths), out_path)
    return view_paths


def generate_views_simple(
    input_image_path: str,
    output_dir: str,
) -> list[str]:
    """
    Fallback view generator that simply rotates the 2D image.

    This does NOT produce true 3D-consistent novel views, but it allows
    the ReSplat pipeline to proceed if Stable Zero123 fails to load or
    if you want a quick smoke-test without waiting for diffusion.
    COLMAP may struggle with pure planar rotations, so this is primarily
    for pipeline verification.
    """
    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    input_image = Image.open(input_image_path).convert("RGB")
    view_paths: list[str] = []

    for idx, angle in enumerate(AZIMUTHS):
        rotated = input_image.rotate(-angle, resample=Image.Resampling.BICUBIC)
        view_file = out_path / f"{idx:03d}.png"
        rotated.save(view_file)
        view_paths.append(str(view_file))

    logger.info("Generated %d simple rotated views in %s", len(view_paths), out_path)
    return view_paths
