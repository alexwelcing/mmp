# AGENTS.md — MMP (Autonomous AI Director)

## 1. Background & Goal

This is a **tutorial / reference repository** for a GCP-native, AI-driven Web3 game asset pipeline.  
The high-level flow:

1. A player visits the React frontend and requests a free AI-generated character.
2. The **AI Director** (FastAPI service) orchestrates a multi-agent pipeline (image generation, evaluation, audio, Web3).
3. Heavy image/3D work is off-loaded to **ComfyUI workers** running on GKE with GPU nodes.
4. Players can optionally mint their character on **Base L2** via ERC-721 contracts with gasless onboarding (ERC-4337 paymaster).

When modifying code, keep the tutorial / educational nature in mind: changes should be readable, well-commented, and not introduce hidden complexity.

## 2. Tech Stack

| Layer | Tech |
|-------|------|
| Frontend | React 18 + TypeScript + Vite |
| AI Director | Python 3.11 + FastAPI + Pydantic |
| Messaging | GCP Pub/Sub |
| GPU Workers | ComfyUI + AudioGen (containerised) on GKE |
| Infra (IaC) | Pulumi (Python) + Kubernetes (KEDA) |
| Smart Contracts | Solidity ^0.8.20 + Hardhat + TypeScript |
| Web3 Libs | web3.py, eth-account, ERC-4337 patterns |

## 3. Directory Structure

```
/workspaces/mmp/
├── frontend/               # Vite React app
│   src/
│   ├── components/CharacterCreation/
│   ├── components/WalletProvider/
│   ├── hooks/
│   └── types/
├── services/
│   ├── ai-director/        # FastAPI orchestrator
│   │   ├── main.py
│   │   ├── config.py
│   │   └── agents/
│   │       ├── orchestrator.py
│   │       ├── image_agent.py
│   │       ├── evaluator_agent.py
│   │       ├── audio_agent.py
│   │       ├── resplat_agent.py
│   │       └── web3_agent.py
│   ├── comfyui-worker/     # Dockerised ComfyUI + workflows
│   ├── audio-worker/       # Facebook AudioGen inference worker
│   └── resplat-worker/     # ReSplat 3DGS (Zero123 → COLMAP → ReSplat)
├── infrastructure/
│   ├── pulumi/             # Pulumi Python program (GCP + K8s)
│   └── kubernetes/         # KEDA operator, fallback raw manifests
├── contracts/
│   ├── src/                # Solidity contracts
│   ├── test/               # Hardhat TS tests
│   └── scripts/            # Deployment scripts
└── docs/                   # Additional documentation
```

## 4. Build & Run Commands

### AI Director (local)
```bash
cd services/ai-director
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload --port 8080
```

### Frontend (local)
```bash
cd frontend
npm install
npm run dev        # http://localhost:5173
npm run build      # tsc && vite build
```

### Smart Contracts (local)
```bash
cd contracts
npm install
npx hardhat test
npx hardhat compile
```

### Infra (deploy)
```bash
cd infrastructure/pulumi
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
pulumi stack init staging
pulumi config set project_id YOUR_PROJECT
pulumi preview
pulumi up
```

## 9. Agent Guidelines & Conventions

- **Python**: Follow PEP 8. Use type hints. The project uses `ruff` for linting/formatting and `mypy` for type checking.
- **TypeScript / React**: Functional components, explicit return types on exported functions, and hooks co-located in `src/hooks/`.
- **Solidity**: OpenZeppelin contracts are the standard library. Use `solhint` for linting. Keep external calls safe and document access control.
- **Minimal changes**: Prefer the smallest diff that achieves the goal. Avoid refactoring unrelated code.
- **No secrets in source**: Environment variables live in `.env` (gitignored). Never hard-code keys, RPC URLs, or private data.
- **Tests**: If you add or change logic, run the relevant tests (`pytest`, `hardhat test`, etc.) and ensure they pass before finishing.
