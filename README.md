# 🎮 Autonomous AI Director: GCP-Native Pipeline for Web3 Game Asset Generation

> **Tutorial Repository** — A production-quality reference implementation for building a real-time, AI-driven game asset pipeline with on-chain monetization on Base (Ethereum L2).

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![Solidity ^0.8.20](https://img.shields.io/badge/solidity-%5E0.8.20-red.svg)](https://soliditylang.org/)

---

## 📖 Overview

This project demonstrates a **Dual-Horizon Strategy** for Web3 game monetization:

| Horizon | Description | Revenue |
|---------|-------------|---------|
| **H1 (Now)** | Free-to-play with gasless onboarding | Viral growth |
| **H2 (Scale)** | On-chain character ownership + royalty splits | Sustainable revenue |

Players claim a free AI-generated character (no wallet required), then optionally mint it on-chain with full ownership. An autonomous AI Director orchestrates the entire pipeline — from Pub/Sub request to on-chain NFT — using GCP-native services.

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        FRONTEND (React/Vite)                    │
│  FreeRollStep → CharacterCard → PaidRollStep → WalletProvider   │
│                         ↑                                       │
│              GaussianSplatViewer (WebGL .ply)                   │
└──────────────────────────┬──────────────────────────────────────┘
                           │ REST API
┌──────────────────────────▼──────────────────────────────────────┐
│                    AI DIRECTOR SERVICE (FastAPI)                 │
│                                                                 │
│  OrchestratorAgent                                              │
│  ├── ImageAgent  ──────────► ComfyUI Worker (GKE + GPU)         │
│  │   (2D draft → upscale)        ▲                              │
│  ├── EvaluatorAgent              │ Webhook (AIDirectorWebhook)  │
│  ├── AudioAgent  ──────────► Audio Worker (AudioGen)            │
│  ├── ResplatAgent ─────────► ReSplat Worker (GPU)               │
│  │   (Stable Zero123 → COLMAP → 3DGS)                           │
│  └── Web3Agent   ──────────► Base L2 (ERC-4337)                 │
│                                       │                        │
└──────────────────────────┬────────────┼────────────────────────┘
                           │            │
┌──────────────────────────▼────────────▼────────────────────────┐
│                       GCP INFRASTRUCTURE                        │
│                                                                 │
│  Pub/Sub Topics          GKE Cluster          Filestore NFS     │
│  asset-generation  ───►  GPU Node Pool  ◄───  Model Cache       │
│  (requests/dlq)          (gVisor + CUDA)      (ReadWriteMany)   │
└─────────────────────────────────────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────────┐
│                    BASE L2 SMART CONTRACTS                      │
│                                                                 │
│  CharacterNFT (ERC-721)                                         │
│  ├── AIDirectorPaymaster (ERC-4337) ← Gasless for new users     │
│  └── CharacterSplits (0xSplits)    ← Royalty distribution       │
└─────────────────────────────────────────────────────────────────┘
```

---

## 📋 Prerequisites

| Tool | Version | Purpose |
|------|---------|---------|
| Python | 3.11+ | AI Director service |
| Node.js | 18+ | Contracts & frontend |
| Pulumi | 3.120+ | GCP infrastructure (Python) |
| kubectl | 1.28+ | Kubernetes management |
| Docker | 24+ | Container builds |
| Make | — | One-command local dev |
| GCP Account | — | Cloud infrastructure |

---

## 🚀 Quick Start (Local Dev)

The fastest way to run locally is **hybrid mode**: ComfyUI, AudioGen, and optional ReSplat run in Docker; the AI Director and Frontend run natively for fast hot-reload.

```bash
# 1. Install dependencies once
make install

# 2. Start ComfyUI + AudioGen containers
make dev-native

# 3. Deploy local contracts (creates .env.contracts)
make contracts-local
export $(cat .env.contracts | xargs)

# 4. Start the AI Director (in a second terminal)
cd services/ai-director
source .venv/bin/activate
uvicorn main:app --reload --port 8080

# 5. Start the frontend (in a third terminal)
cd frontend
npm run dev
# Open http://localhost:5173
```

### Optional: ReSplat 3D Mode

If you have an NVIDIA GPU with CUDA 12.8 support, start the full stack including ReSplat:

```bash
make dev-resplat
```

Then set `USE_RESPLAT_FOR_3D=true` in your `.env` to route 3D generation through ReSplat instead of ComfyUI.

---

## 🗂️ Component Breakdown

### `services/ai-director/`
The core orchestration service. Subscribes to GCP Pub/Sub, routes requests through a multi-agent pipeline, and coordinates asset delivery.

```
agents/
├── orchestrator.py    # Main pipeline coordinator
├── image_agent.py     # 2D draft + upscale (ComfyUI)
├── evaluator_agent.py # Aesthetic scoring & selection
├── audio_agent.py     # Soundscape generation (AudioGen)
├── resplat_agent.py   # 3D Gaussian Splatting (ReSplat)
└── web3_agent.py      # ERC-4337 gasless minting + splits
```

### `services/comfyui-worker/`
Containerized ComfyUI with custom workflows and the `AIDirectorWebhook` custom node for push notifications:
- `lightning_2d_draft.json` — Fast SDXL-Lightning draft generation
- `mesh_generation.json` — 3D mesh generation fallback

### `services/audio-worker/`
Facebook AudioGen inference service via Hugging Face Hub. Generates character soundscapes on CPU.

### `services/resplat-worker/`
Full 3D Gaussian Splatting pipeline: Stable Zero123 multi-view synthesis → COLMAP sparse reconstruction → ReSplat inference → `.ply` output.

### `infrastructure/pulumi/`
GCP infrastructure as code using Python Component Resources:
- **MMPCluster**: VPC, GKE, system/GPU node pools, Workload Identity
- **FilestoreCache**: NFS-backed shared model cache (ReadWriteMany)
- **PubSubPipeline**: Request queue with dead-letter topic
- **ComfyUIWorkerPool**, **AIDirectorService**, **ResplatWorker**, **AudioWorker**: Kubernetes deployments via `pulumi_kubernetes`

### `infrastructure/kubernetes/`
Reference Kubernetes manifests (deprecated in favour of Pulumi, but useful for debugging).

### `contracts/src/`
Base L2 (Ethereum) contracts:
- **CharacterNFT**: ERC-721 with free/paid/custom mint tiers
- **AIDirectorPaymaster**: ERC-4337 paymaster sponsoring first-time gas
- **CharacterSplits**: 0xSplits-compatible royalty distribution

### `frontend/src/`
React + TypeScript progressive onboarding UI:
- No crypto jargon for new users
- Social login → character reveal → optional Web3 upgrade
- Integrated `@mkkellogg/gaussian-splats-3d` WebGL viewer for `.ply` files

---

## 🌩️ GCP Deployment

### ⚠️ Cost Warning

| Tier | Idle Cost | Active Cost | Best For |
|------|-----------|-------------|----------|
| **Max Mini (dev)** | ~$50-70/mo | ~$100-200/mo | Solo dev, 2D only |
| **Standard Dev** | ~$150/mo | ~$300-500/mo | Team dev, full pipeline |
| **Production** | ~$285/mo | ~$1,500-9,000/mo | Live users, high availability |

> **Note:** First deployment takes 15-20 minutes. Ensure you have [GPU quota](#prerequisites) before deploying.

### Quick Deploy (Makefile)

```bash
# 1. Check prerequisites
make check

# 2. Set your project
export GCP_PROJECT_ID=your-project-id

# 3. Deploy (choose one)
make deploy-dev      # Max Mini tier (~$50/mo idle)
make deploy-staging  # Standard Dev tier (~$150/mo idle)
make deploy-prod     # Production tier (~$285/mo idle)

# 4. Test the API
make test-api
```

### Manual Deploy

```bash
# 1. Setup gcloud
export GCP_PROJECT_ID=your-project-id
./infrastructure/scripts/gcloud-setup.sh

# 2. Build images
make build-images

# 3. Deploy with Pulumi
cd infrastructure/pulumi
pulumi stack init dev
pulumi config set project_id $GCP_PROJECT_ID
pulumi config set environment dev
pulumi up

# 4. Get the load balancer IP
make get-ip
```

### Required GCP Quotas

Before deploying, ensure your project has these quotas:

| Resource | Minimum | Request Increase |
|----------|---------|------------------|
| CPUS | 50 | [GCP Console](https://console.cloud.google.com/iam-admin/quotas) |
| NVIDIA_T4_GPUS | 4 | [GCP Console](https://console.cloud.google.com/iam-admin/quotas) |
| IN_USE_ADDRESSES | 20 | Usually automatic |
| FILESTORE_INSTANCES | 2 | Usually automatic |

### 2. Build & Push Docker Images

```bash
export REGION=us-central1
export PROJECT_ID=YOUR_PROJECT
export REGISTRY=${REGION}-docker.pkg.dev/${PROJECT_ID}/mmp-images

# AI Director
docker build -t ${REGISTRY}/ai-director:latest services/ai-director/
docker push ${REGISTRY}/ai-director:latest

# ComfyUI Worker
docker build -t ${REGISTRY}/comfyui-worker:latest services/comfyui-worker/
docker push ${REGISTRY}/comfyui-worker:latest

# Audio Worker
docker build -t ${REGISTRY}/audio-worker:latest services/audio-worker/
docker push ${REGISTRY}/audio-worker:latest

# ReSplat Worker (optional)
docker build -t ${REGISTRY}/resplat-worker:latest services/resplat-worker/
docker push ${REGISTRY}/resplat-worker:latest
```

### 3. Deploy Contracts

```bash
cd contracts
npx hardhat run scripts/deploy.ts --network base-sepolia
```

---

## 🔑 Environment Variables

| Variable | Description |
|----------|-------------|
| `GCP_PROJECT_ID` | Your GCP project ID |
| `PUBSUB_TOPIC` | Pub/Sub topic for generation requests |
| `PUBSUB_SUBSCRIPTION` | Pull subscription consumed by the AI Director |
| `COMFYUI_ENDPOINT` | ComfyUI service URL |
| `AUDIO_ENDPOINT` | Audio worker URL |
| `USE_RESPLAT_FOR_3D` | Route 3D generation through ReSplat (`true` / `false`) |
| `RESPLAT_ENDPOINT` | ReSplat worker URL |
| `BASE_RPC_URL` | Base L2 RPC endpoint |
| `BUNDLER_URL` | ERC-4337 bundler endpoint |
| `CHARACTER_NFT_ADDRESS` | Deployed CharacterNFT contract |
| `PAYMASTER_ADDRESS` | Deployed AIDirectorPaymaster contract |
| `SPLITS_ADDRESS` | Deployed CharacterSplits contract |
| `AI_DIRECTOR_PRIVATE_KEY` | Operational wallet private key (required in prod) |

---

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Follow the code style (Black for Python, ESLint for TS, Solhint for Solidity)
4. Add tests for new functionality
5. Submit a pull request

---

## 📄 License

MIT — see [LICENSE](LICENSE) for details.
