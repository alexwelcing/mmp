# MMP Audio Worker

Local audio generation service powered by **Facebook AudioGen** via the [AudioCraft](https://github.com/facebookresearch/audiocraft) library.

## What It Does

Converts text prompts like *"epic battle drums, steel clashing, low brass fanfare"* into short soundscape audio clips (WAV format).

## Model

- **Model**: `facebook/audiogen-medium`
- **Source**: Hugging Face Hub
- **Cache**: `/root/.cache/huggingface` (persisted via Docker volume)

## API

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/health` | Liveness probe |
| `POST` | `/generate` | Moshi-compatible generation endpoint |
| `POST` | `/vibevoice/generate` | VibeVoice-compatible generation endpoint |

## Local Development

The audio worker is automatically started by `docker-compose.yml` when you run:

```bash
make dev-native
```

Or manually:

```bash
docker compose up --build audio
```

The first startup will download the AudioGen medium model (~1.3 GB) from Hugging Face. Subsequent restarts are instant because the model cache is stored in a named Docker volume (`huggingface-cache`).

## Performance Notes

- **CPU**: A 10-second clip takes ~30–60 seconds on a modern CPU.
- **GPU**: If you have an NVIDIA GPU and the CUDA runtime available, generation drops to ~5–10 seconds.

For pure local development, the container stays running and caches the model, so you only pay the generation cost per request.
