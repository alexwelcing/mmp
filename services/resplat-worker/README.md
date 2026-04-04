# ReSplat Worker

Foundation scaffold for integrating [ReSplat](https://github.com/cvg/resplat) into the MMP pipeline.

## What is ReSplat?

ReSplat is a feed-forward recurrent model for 3D Gaussian Splatting that iteratively refines Gaussians using rendering error as a gradient-free feedback signal.

## Why a separate worker?

ReSplat requires **PyTorch 2.7.0 + CUDA 12.8**, which conflicts with the ComfyUI worker's PyTorch 2.4.0 / CUDA 12.1 base image. Running it as a standalone service keeps both containers simple and upgradeable independently.

## Expected Pipeline (future)

```
Upscaled 2D portrait
       ↓
Multi-view synthesis (Zero123 / MVAdapter)
       ↓
COLMAP sparse reconstruction
       ↓
ReSplat worker inference  ←  this container
       ↓
.ply file on Filestore
```

## Model Weights

Download the pretrained ReSplat checkpoints and place them in your shared Filestore:

```
/mnt/filestore/resplat/pretrained/
  └── resplat_re10k.pt
```

The Dockerfile symlinks `/app/resplat/pretrained` to this path at runtime.

## Local Dev

```bash
cd services/resplat-worker
docker build -t resplat-worker:latest .
docker run --gpus all -p 9001:9001 \
  -v /path/to/filestore/resplat:/mnt/filestore/resplat \
  resplat-worker:latest
```

## HTTP API

- `GET /health` — liveness probe
- `POST /infer` — run inference on a COLMAP dataset

## Pipeline

The ReSplat worker now supports a complete end-to-end pipeline via the `/infer-from-image` endpoint:

```
Single 2D portrait
       ↓
Stable Zero123 (8 novel views)
       ↓
COLMAP sparse reconstruction
       ↓
ReSplat inference
       ↓
.ply file
```

## Status

✅ **End-to-end pipeline implemented** — image → multi-view → COLMAP → ReSplat.
🚧 **Requires CUDA 12.8 GPU** for reasonable inference times.
