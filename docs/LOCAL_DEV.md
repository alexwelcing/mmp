# Local Development Guide

This guide explains how to run the entire MMP stack on your local machine **without GCP**. The goal is a fast, iterative development experience.

## 🏆 Recommended Setup: Hybrid Mode

For the best developer experience, we recommend a **hybrid approach**:

| Component | How to Run | Why |
|-----------|-----------|-----|
| **ComfyUI Worker** | Docker | Heavy Python/CUDA dependencies; easiest to containerise |
| **Audio Worker** | Docker | AudioGen model cached via HF Hub volume |
| **AI Director** | Native Python (`uvicorn`) | Fast hot-reload; easy debugging |
| **Frontend** | Native Node (`vite`) | Fast HMR; instant feedback |
| **Smart Contracts** | Native Hardhat node | Direct control over local EVM state |

## ⚡ Quick Start (One Command)

```bash
# 1. Install dependencies once
make install

# 2. Start ComfyUI + AudioGen in Docker
make dev-native

# 3. In a second terminal — deploy local contracts
make contracts-local
# This creates `.env.contracts` — source it into your shell:
export $(cat .env.contracts | xargs)

# 4. In a third terminal — start the AI Director
cd services/ai-director
source .venv/bin/activate
uvicorn main:app --reload --port 8080

# 5. In a fourth terminal — start the frontend
cd frontend
npm run dev
# Open http://localhost:5173
```

That's it! You now have:
- **Frontend** at http://localhost:5173
- **AI Director API** at http://localhost:8080
- **ComfyUI** at http://localhost:8188
- **AudioGen** at http://localhost:9000
- **Hardhat node** at http://localhost:8545

## 🔧 Environment Variables

Copy the example env file and source the contract addresses after deploying:

```bash
cp .env.example .env
# After `make contracts-local`:
export $(cat .env.contracts | xargs)
```

The `.env.example` already contains sensible defaults for local development.

## 🐳 Docker-Only Mode

If you prefer everything in containers (e.g. for demos or CI):

```bash
make dev-docker
```

This starts:
- ComfyUI worker
- AI Director
- Hardhat local node

All inside Docker Compose with a shared bridge network.

### Container Networking Notes
- The **ComfyUI webhook** calls `http://host.docker.internal:8080/webhook/comfyui` to reach the AI Director running on your host.
- When the AI Director runs inside Docker, it talks to ComfyUI via `http://comfyui:8188` and Audio via `http://audio:9000`.

## 🎮 Local Web3 Behavior

When `ENVIRONMENT=local`, the AI Director automatically switches to **direct EOA transactions** instead of ERC-4337 UserOperations. This means:

- No bundler (Pimlico) is required
- No paymaster deposits are needed
- The local deploy script sets the AI Director's wallet as the paymaster, so `mintFree()` works with direct transactions

## 🖼️ ComfyUI Workflows

The local ComfyUI container mounts a Docker volume for model caching (`comfyui-models`). The first cold start will download models on demand, or you can pre-populate the volume:

```bash
# Check the model cache location
docker volume inspect mmp_comfyui-models
```

The included workflows are:
- `lightning_2d_draft.json` — fast SDXL-Lightning character portraits
- `mesh_generation.json` — 3D mesh generation via TripoSR (renamed from the misleading `3dgs_generation.json`)

## 🔊 Audio Worker

The local stack includes a **Facebook AudioGen** container (`services/audio-worker/`) that downloads the medium model from the Hugging Face Hub on first startup (~1.3 GB). The model cache is stored in a named Docker volume (`huggingface-cache`), so subsequent restarts are instant.

The `AudioAgent` calls `http://localhost:9000/generate` to produce real soundscapes. If the container is not running, it falls back to a mock URL so the pipeline never blocks.

### Hugging Face Cache

```bash
# Check the cached model size
docker volume inspect mmp_huggingface-cache
```

## 🧪 Testing

```bash
# AI Director (Python)
cd services/ai-director
pytest

# Frontend (TypeScript)
cd frontend
npm run type-check

# Smart Contracts (Solidity)
cd contracts
npx hardhat test
```

## 🧹 Cleanup

```bash
make stop    # Stop Docker containers
make clean   # Stop containers AND delete model volumes
```

## 🚨 Troubleshooting

### ComfyUI or Audio fails to start
- **GPU not available?** Remove the `deploy.resources.reservations.devices` section from `docker-compose.yml` to run on CPU (slower but works for testing).
- **Port 8188 or 9000 in use?** Change the host port mapping in `docker-compose.yml`.

### AI Director can't reach ComfyUI or Audio
- In **hybrid mode**, ensure `COMFYUI_ENDPOINT=http://localhost:8188` and `AUDIO_ENDPOINT=http://localhost:9000` in your `.env`.
- In **Docker mode**, the AI Director uses `COMFYUI_ENDPOINT=http://comfyui:8188` and `AUDIO_ENDPOINT=http://audio:9000` automatically.

### Web3 minting fails locally
- Did you run `make contracts-local` and `export $(cat .env.contracts | xargs)`?
- Is the Hardhat node still running on port 8545?
- Check that `AI_DIRECTOR_PRIVATE_KEY` matches the second Hardhat account (the local deploy script uses it as the paymaster).

### Frontend can't connect to AI Director
- The Vite dev server proxies `/api` to `localhost:8080` automatically.
- If you changed the AI Director port, update `vite.config.ts`.

## 📁 Useful Files

| File | Purpose |
|------|---------|
| `docker-compose.yml` | Local container orchestration |
| `Makefile` | One-command shortcuts |
| `.env.example` | Template for all environment variables |
| `contracts/scripts/deploy-local.ts` | Local contract deployment |
| `services/audio-worker/` | Facebook AudioGen local inference |
| `services/ai-director/config.py` | Local-friendly defaults |

## 🧩 Optional: ReSplat 3D Gaussian Splatting

ReSplat is now **fully wired up** locally, but it requires an NVIDIA GPU with **CUDA 12.8** support because the worker runs on PyTorch 2.7.0.

To enable it:

```bash
# 1. Start the stack with ReSplat
make dev-resplat

# 2. Enable ReSplat routing in your .env
USE_RESPLAT_FOR_3D=true
RESPLAT_ENDPOINT=http://localhost:9001
```

The pipeline is:
1. **Stable Zero123** inside the ReSplat worker generates ~8 novel views from the 2D portrait.
2. **COLMAP** reconstructs sparse camera poses from those views.
3. **ReSplat** converts the COLMAP dataset into a `.ply` Gaussian Splatting file.

If you don't have a compatible GPU, leave `USE_RESPLAT_FOR_3D=false` (default) and the pipeline will use the ComfyUI-based mesh generation instead.

### Hugging Face Cache

Both AudioGen and Stable Zero123 share the same Hugging Face model cache volume:

```bash
# Check cached model size
docker volume inspect mmp_huggingface-cache
```
