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
└──────────────────────────┬──────────────────────────────────────┘
                           │ REST API
┌──────────────────────────▼──────────────────────────────────────┐
│                    AI DIRECTOR SERVICE (FastAPI)                 │
│                                                                 │
│  OrchestratorAgent                                              │
│  ├── ImageAgent  ──────────► ComfyUI Worker (GKE + GPU)         │
│  │   (2D draft → upscale → 3DGS)      ▲                        │
│  ├── EvaluatorAgent                   │ KEDA ScaledJob          │
│  ├── AudioAgent  ──────────► Moshi/VibeVoice                   │
│  └── Web3Agent   ──────────► Base L2 (ERC-4337)                │
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
| Terraform | 1.6+ | GCP infrastructure |
| kubectl | 1.28+ | Kubernetes management |
| Docker | 24+ | Container builds |
| GCP Account | — | Cloud infrastructure |

---

## 🚀 Quick Start (Local Dev)

### 1. Clone & Configure

```bash
git clone https://github.com/your-org/mmp.git
cd mmp
cp .env.example .env  # Fill in your GCP project, RPC URLs, etc.
```

### 2. Start the AI Director

```bash
cd services/ai-director
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload --port 8080
```

### 3. Start the Frontend

```bash
cd frontend
npm install
npm run dev
# Open http://localhost:5173
```

### 4. Run Contract Tests

```bash
cd contracts
npm install
npx hardhat test
```

---

## 🗂️ Component Breakdown

### `services/ai-director/`
The core orchestration service. Subscribes to GCP Pub/Sub, routes requests through a multi-agent pipeline, and coordinates asset delivery.

```
agents/
├── orchestrator.py    # Main pipeline coordinator
├── image_agent.py     # 2D → Upscale → 3DGS generation
├── evaluator_agent.py # Aesthetic scoring & selection
├── audio_agent.py     # Soundscape generation
└── web3_agent.py      # ERC-4337 gasless minting
```

### `services/comfyui-worker/`
Containerized ComfyUI with custom workflows for game asset generation:
- `lightning_2d_draft.json` — Fast SDXL-Lightning draft generation
- `3dgs_generation.json` — 3D Gaussian Splatting from 2D images

### `infrastructure/terraform/`
GCP infrastructure as code:
- **GKE**: GPU node pool with gVisor sandboxing for CUDA checkpoints
- **Filestore**: NFS-backed shared model cache (ReadWriteMany)
- **Pub/Sub**: Request queue with dead-letter topic

### `infrastructure/kubernetes/`
- **KEDA ScaledJob**: Scale ComfyUI workers from 0→15 based on queue depth
- **Pod Snapshots**: gVisor + CUDA checkpoint for fast cold starts

### `contracts/src/`
Base L2 (Ethereum) contracts:
- **CharacterNFT**: ERC-721 with free/paid/custom mint tiers
- **AIDirectorPaymaster**: ERC-4337 paymaster sponsoring first-time gas
- **CharacterSplits**: 0xSplits-compatible royalty distribution

### `frontend/src/`
React + TypeScript progressive onboarding UI:
- No crypto jargon for new users
- Social login → character reveal → optional Web3 upgrade

---

## 🌩️ GCP Deployment

### 1. Provision Infrastructure

```bash
cd infrastructure/terraform
terraform init
terraform plan -var="project_id=YOUR_PROJECT" -var="region=us-central1"
terraform apply
```

### 2. Build & Push Docker Images

```bash
# AI Director
docker build -t gcr.io/YOUR_PROJECT/ai-director:latest services/ai-director/
docker push gcr.io/YOUR_PROJECT/ai-director:latest

# ComfyUI Worker
docker build -t gcr.io/YOUR_PROJECT/comfyui-worker:latest services/comfyui-worker/
docker push gcr.io/YOUR_PROJECT/comfyui-worker:latest
```

### 3. Deploy to Kubernetes

```bash
cd infrastructure/kubernetes
kubectl apply -f namespaces.yaml
kubectl apply -f filestore/persistent-volume.yaml
kubectl apply -f keda/keda-operator.yaml
kubectl apply -f keda/comfyui-scaled-job.yaml
```

### 4. Deploy Contracts

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
| `COMFYUI_ENDPOINT` | ComfyUI service URL |
| `BASE_RPC_URL` | Base L2 RPC endpoint |
| `CHARACTER_NFT_ADDRESS` | Deployed CharacterNFT contract |
| `PAYMASTER_ADDRESS` | Deployed AIDirectorPaymaster contract |
| `SPLITS_ADDRESS` | Deployed CharacterSplits contract |

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
