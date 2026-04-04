"""
audio-worker/main.py — Local audio generation via Facebook AudioGen.

The model is loaded lazily on the first request so the service can start
quickly and respond to /health even if Hugging Face is temporarily
unreachable.  The model cache is persisted to ``/root/.cache/huggingface``
via a Docker volume so restarts are fast.

API:
  GET  /health
  POST /generate          — Moshi-compatible endpoint
  POST /vibevoice/generate — VibeVoice-compatible endpoint
"""

from __future__ import annotations

import asyncio
import logging
import sys
import uuid
from pathlib import Path

import soundfile as sf
import torch
import uvicorn
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger(__name__)

# ------------------------------------------------------------------ #
# Output directory                                                   #
# ------------------------------------------------------------------ #
OUTPUT_DIR = Path("/mnt/filestore/outputs/audio")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# ------------------------------------------------------------------ #
# Lazy model loading                                                 #
# ------------------------------------------------------------------ #
_MODEL_NAME = "facebook/audiogen-medium"
_model = None
_model_lock = asyncio.Lock()
_device = "cuda" if torch.cuda.is_available() else "cpu"


async def _get_model():
    """Lazy-load AudioGen so /health is always responsive."""
    global _model
    if _model is not None:
        return _model
    async with _model_lock:
        if _model is not None:
            return _model
        logger.info("Loading AudioGen model from Hugging Face Hub...")
        logger.info("(First startup may take a few minutes while the model downloads)")
        # audiocraft imports torch and can be heavy — run in a thread.
        loop = asyncio.get_running_loop()

        def _load():
            from audiocraft.models import AudioGen

            m = AudioGen.get_pretrained(_MODEL_NAME)
            return m.to(_device)

        _model = await loop.run_in_executor(None, _load)
        logger.info("AudioGen loaded on %s", _device.upper())
    return _model


# ------------------------------------------------------------------ #
# FastAPI app                                                        #
# ------------------------------------------------------------------ #
app = FastAPI(title="MMP Audio Worker", version="0.1.0")


class GenerateRequest(BaseModel):
    text: str = Field(..., description="Text prompt describing the desired sound")
    duration_seconds: int = Field(10, ge=1, le=30, description="Audio length in seconds")
    sample_rate: int = Field(32000, description="Target sample rate (info only)")
    format: str = Field("wav", description="Output audio format")


class GenerateResponse(BaseModel):
    audio_url: str = Field(..., description="URL/path to the generated audio file")
    model: str = Field(_MODEL_NAME, description="Model used for generation")
    device: str = Field(_device, description="Compute device")


class VibeVoiceRequest(BaseModel):
    style_prompt: str = Field(..., description="Style prompt for the soundscape")
    duration: int = Field(10, ge=1, le=30)
    temperature: float = Field(0.8, ge=0.1, le=1.5)


class VibeVoiceResponse(BaseModel):
    output_url: str = Field(..., description="URL/path to the generated audio file")
    model: str = Field(_MODEL_NAME)


# ------------------------------------------------------------------ #
# Endpoints                                                          #
# ------------------------------------------------------------------ #

@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "model": _MODEL_NAME, "device": _device}


@app.post("/generate", response_model=GenerateResponse)
async def generate(req: GenerateRequest) -> GenerateResponse:
    result = await _do_generate(req.text, req.duration_seconds, req.format)
    return result


@app.post("/vibevoice/generate", response_model=VibeVoiceResponse)
async def vibevoice_generate(req: VibeVoiceRequest) -> VibeVoiceResponse:
    result = await _do_generate(req.style_prompt, req.duration, "wav")
    return VibeVoiceResponse(
        output_url=result.audio_url,
        model=_MODEL_NAME,
    )


# ------------------------------------------------------------------ #
# Generation helper                                                  #
# ------------------------------------------------------------------ #

async def _do_generate(prompt: str, duration: int, fmt: str) -> GenerateResponse:
    model = await _get_model()
    logger.info("Generating audio: prompt='%s' duration=%ds device=%s", prompt, duration, _device)

    loop = asyncio.get_running_loop()

    def _generate():
        try:
            model.set_generation_params(duration=duration)
            wav = model.generate([prompt])
            return wav
        except Exception:
            logger.exception("AudioGen generation failed")
            raise

    try:
        wav = await loop.run_in_executor(None, _generate)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    # wav shape: (1, channels, samples) — squeeze batch dim
    audio = wav[0].cpu().numpy().T  # shape: (samples, channels)
    if audio.ndim == 1:
        audio = audio.reshape(-1, 1)

    filename = f"audio_{uuid.uuid4().hex}.{fmt}"
    filepath = OUTPUT_DIR / filename

    def _write():
        # AudioGen outputs at 32 kHz
        sf.write(filepath, audio, samplerate=32000, format="WAV")

    await loop.run_in_executor(None, _write)
    logger.info("Audio saved: %s", filepath)

    return GenerateResponse(
        audio_url=str(filepath),
        model=_MODEL_NAME,
        device=_device,
    )


# ------------------------------------------------------------------ #
# Entrypoint                                                         #
# ------------------------------------------------------------------ #
if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=9000, log_level="info")
