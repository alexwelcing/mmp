"""
infer.py — HTTP inference service wrapper around ReSplat.

Supports two modes:
  1. POST /infer           — expects an existing COLMAP dataset.
  2. POST /infer-from-image — full pipeline: single image → multi-view
n                              → COLMAP → ReSplat → .ply
"""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
import sys
import tempfile
import uuid
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import urlopen

import uvicorn
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger(__name__)

app = FastAPI(title="ReSplat Worker", version="0.2.0")

# ReSplat model preset (maps to a pretrained checkpoint inside the repo).
DEFAULT_MODEL_PRESET = os.environ.get("RESPLAT_MODEL_PRESET", "dl3dv_8v_512x960")
PRETRAINED_DIR = Path("/app/resplat/pretrained")
OUTPUT_DIR = Path("/app/resplat/outputs")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# ------------------------------------------------------------------ #
# Request / Response models                                          #
# ------------------------------------------------------------------ #


class InferRequest(BaseModel):
    colmap_dir: str = Field(..., description="Path to COLMAP dataset directory")
    output_name: str = Field("character", description="Base name for the output .ply file")
    scene_name: str = Field("scene", description="Scene subfolder inside the COLMAP dataset")


class InferFromImageRequest(BaseModel):
    image_path: str = Field(..., description="Path to the single upscaled 2D portrait")
    output_name: str = Field("character", description="Base name for the output .ply file")
    use_zero123: bool = Field(
        True, description="Use Stable Zero123 for true novel views; otherwise simple rotation fallback"
    )
    num_inference_steps: int = Field(50, ge=1, le=100, description="Zero123 sampling steps")


class InferResponse(BaseModel):
    ply_url: str = Field(..., description="URL/path to the generated .ply file")
    model: str = Field(..., description="ReSplat checkpoint used")


# ------------------------------------------------------------------ #
# Endpoints                                                          #
# ------------------------------------------------------------------ #


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "model_preset": DEFAULT_MODEL_PRESET, "model_dir": str(PRETRAINED_DIR)}


@app.post("/infer", response_model=InferResponse)
async def infer(request: InferRequest) -> InferResponse:
    """Run ReSplat inference on an existing COLMAP dataset."""
    return await _run_resplat(
        colmap_dir=request.colmap_dir,
        scene_name=request.scene_name,
        output_name=request.output_name,
    )


def _download_if_url(path_or_url: str, dest_dir: Path) -> Path:
    """Download remote images so the worker can ingest them locally."""
    parsed = urlparse(path_or_url)
    if parsed.scheme in ("http", "https"):
        filename = Path(parsed.path).name or "input_image.png"
        dest = dest_dir / filename
        logger.info("Downloading image from %s to %s", path_or_url, dest)
        with urlopen(path_or_url, timeout=60) as resp:
            dest.write_bytes(resp.read())
        return dest
    return Path(path_or_url)


@app.post("/infer-from-image", response_model=InferResponse)
async def infer_from_image(request: InferFromImageRequest) -> InferResponse:
    """
    Full pipeline: single image → multi-view → COLMAP → ReSplat.

    A temporary workspace is created for the intermediate files and
    cleaned up after ReSplat finishes.
    """
    work_dir = Path(tempfile.gettempdir()) / f"resplat_job_{uuid.uuid4().hex}"
    scene_dir = work_dir / "scene"
    images_dir = scene_dir / "images"
    images_dir.mkdir(parents=True, exist_ok=True)

    try:
        image_path = _download_if_url(request.image_path, work_dir)
        if not image_path.is_file():
            raise HTTPException(
                status_code=400,
                detail=f"Input image not found: {request.image_path}",
            )

        # ── Step 1: Multi-view synthesis ───────────────────────────────
        logger.info("Generating multi-view images for %s", image_path)
        if request.use_zero123:
            try:
                from viewgen import generate_views

                await _run_sync(
                    generate_views,
                    str(image_path),
                    str(images_dir),
                    request.num_inference_steps,
                )
            except Exception as exc:
                logger.warning(
                    "Stable Zero123 failed (%s); falling back to simple rotation", exc
                )
                from viewgen import generate_views_simple

                await _run_sync(generate_views_simple, str(image_path), str(images_dir))
        else:
            from viewgen import generate_views_simple

            await _run_sync(generate_views_simple, str(image_path), str(images_dir))

        # ── Step 2: COLMAP sparse reconstruction ───────────────────────
        logger.info("Running COLMAP on generated views...")
        await _run_colmap(str(scene_dir))

        # ── Step 3: ReSplat inference ──────────────────────────────────
        logger.info("Running ReSplat on COLMAP dataset...")
        result = await _run_resplat(
            colmap_dir=str(work_dir),
            scene_name="scene",
            output_name=request.output_name,
        )

        return result

    finally:
        # Best-effort cleanup of temp workspace.
        shutil.rmtree(work_dir, ignore_errors=True)


# ------------------------------------------------------------------ #
# Helpers                                                            #
# ------------------------------------------------------------------ #


async def _run_sync(func, *args, **kwargs):
    """Run a synchronous function in the default executor."""
    import asyncio

    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, lambda: func(*args, **kwargs))


async def _run_colmap(scene_dir: str) -> None:
    """
    Run COLMAP feature_extractor → matcher → mapper → model_converter.

    Expects `scene_dir/images/` to exist and contain the source views.
    Produces `scene_dir/sparse/0/*.txt`.
    """
    scene = Path(scene_dir)
    images_dir = scene / "images"
    database_path = scene / "database.db"
    sparse_dir = scene / "sparse"
    raw_sparse_dir = sparse_dir / "0"

    if not images_dir.is_dir():
        raise HTTPException(
            status_code=400,
            detail=f"images/ directory not found in {scene_dir}",
        )

    cmds = [
        [
            "colmap",
            "feature_extractor",
            "--database_path", str(database_path),
            "--image_path", str(images_dir),
            "--ImageReader.camera_model", "SIMPLE_PINHOLE",
        ],
        [
            "colmap",
            "exhaustive_matcher",
            "--database_path", str(database_path),
        ],
        [
            "colmap",
            "mapper",
            "--database_path", str(database_path),
            "--image_path", str(images_dir),
            "--output_path", str(sparse_dir),
        ],
    ]

    for cmd in cmds:
        logger.debug("Running: %s", " ".join(cmd))
        proc = subprocess.run(cmd, capture_output=True, text=True)
        if proc.returncode != 0:
            logger.error("COLMAP command failed:\n%s", proc.stderr)
            raise HTTPException(
                status_code=500,
                detail=f"COLMAP failed: {' '.join(cmd)}\n{proc.stderr}",
            )

    # Convert binary model to TXT for ReSplat compatibility.
    if raw_sparse_dir.is_dir():
        convert_cmd = [
            "colmap",
            "model_converter",
            "--input_path", str(raw_sparse_dir),
            "--output_path", str(raw_sparse_dir),
            "--output_type", "TXT",
        ]
        proc = subprocess.run(convert_cmd, capture_output=True, text=True)
        if proc.returncode != 0:
            logger.error("COLMAP model_converter failed:\n%s", proc.stderr)
            raise HTTPException(
                status_code=500,
                detail=f"COLMAP model_converter failed:\n{proc.stderr}",
            )
    else:
        raise HTTPException(
            status_code=500,
            detail="COLMAP mapper did not produce a sparse reconstruction. "
            "The input views may lack sufficient parallax or texture.",
        )

    logger.info("COLMAP sparse reconstruction written to %s", raw_sparse_dir)


async def _run_resplat(colmap_dir: str, scene_name: str, output_name: str) -> InferResponse:
    """Run ReSplat inference and return the path to the generated .ply."""
    output_dir = OUTPUT_DIR / output_name
    output_dir.mkdir(parents=True, exist_ok=True)
    output_ply = output_dir / "gaussians.ply"

    # ReSplat inference command (mirrors scripts/infer_colmap.sh).
    cmd = [
        "python",
        "scripts/infer_colmap.py",
        f"--model_preset={DEFAULT_MODEL_PRESET}",
        f"--scene_path={colmap_dir}",
        f"--output_dir={output_dir}",
        "--save_ply",
    ]

    logger.info("Running ReSplat inference: %s", " ".join(cmd))
    try:
        result = subprocess.run(
            cmd,
            cwd="/app/resplat",
            capture_output=True,
            text=True,
            check=True,
            timeout=600,
        )
        logger.debug("ReSplat stdout:\n%s", result.stdout)
    except subprocess.CalledProcessError as exc:
        logger.error("ReSplat failed:\n%s", exc.stderr)
        raise HTTPException(status_code=500, detail=exc.stderr) from exc
    except subprocess.TimeoutExpired as exc:
        logger.error("ReSplat timed out after 600s")
        raise HTTPException(status_code=504, detail="Inference timed out") from exc

    if not output_ply.exists():
        raise HTTPException(
            status_code=500,
            detail="ReSplat finished but output .ply was not created",
        )

    return InferResponse(
        ply_url=str(output_ply),
        model=DEFAULT_MODEL_PRESET,
    )


# ------------------------------------------------------------------ #
# Entrypoint                                                         #
# ------------------------------------------------------------------ #

if __name__ == "__main__":
    uvicorn.run("infer:app", host="0.0.0.0", port=9001, log_level="info")
