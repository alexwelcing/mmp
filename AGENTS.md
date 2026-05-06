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

#### Prerequisites
```bash
# Set your GCP project ID
export GCP_PROJECT_ID=your-project-id
export GCP_BILLING_ACCOUNT=XXXXXX-XXXXXX-XXXXXX  # Optional, for budget alerts

# Run automated setup
./infrastructure/scripts/gcloud-setup.sh
```

#### Build and Push Images
```bash
./infrastructure/scripts/build-images.sh
```

#### Deploy with Pulumi
```bash
cd infrastructure/pulumi
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt

# Create stack
pulumi stack init staging
pulumi config set project_id YOUR_PROJECT
pulumi config set billing_account XXXXXX-XXXXXX-XXXXXX  # Optional
pulumi config set api_domain api.yourdomain.com
pulumi config set filestore_tier BASIC_HDD  # or BASIC_SSD for production

# Preview and deploy
pulumi preview
pulumi up
```

## 9. Cost Optimization & Security Considerations

### Cost Optimization
- **Spot instances**: GPU pool uses Spot VMs by default (~60-90% savings). Jobs must be fault-tolerant.
- **KEDA scaling**: ComfyUI workers scale to zero when idle. No GPU costs during quiet periods.
- **Filestore tier**: Use `BASIC_HDD` for staging ($80/TB), `BASIC_SSD` for production ($200/TB). Avoid `ENTERPRISE` unless <10ms latency is critical.
- **GPU time-sharing**: T4 GPUs are shared among 4 concurrent jobs to maximize utilization.
- **Budget alerts**: Set up billing alerts at 50%, 80%, and 100% thresholds to avoid surprises.

### Security Best Practices
- **Workload Identity**: No service account keys in the cluster. Pods authenticate via GKE Workload Identity.
- **gVisor sandbox**: GPU workloads run in gVisor for additional isolation.
- **Cloud Armor WAF**: Automatically deployed with OWASP rules, rate limiting (100 req/min per IP).
- **Filestore security**: Uses `ROOT_SQUASH` with anon UID/GID mapping (not `NO_ROOT_SQUASH`).
- **Audit logging**: Cloud Audit Logs enabled for Admin, Data Read, and Data Write operations.
- **No wildcard CORS**: Production deployments must set explicit `api_domain`, not `*`.

See `docs/GCP_DEPLOYMENT_READINESS.md` for detailed cost analysis and security architecture.

## 10. Agent Guidelines & Conventions

- **Python**: Follow PEP 8. Use type hints. The project uses `ruff` for linting/formatting and `mypy` for type checking.
- **TypeScript / React**: Functional components, explicit return types on exported functions, and hooks co-located in `src/hooks/`.
- **Solidity**: OpenZeppelin contracts are the standard library. Use `solhint` for linting. Keep external calls safe and document access control.
- **Minimal changes**: Prefer the smallest diff that achieves the goal. Avoid refactoring unrelated code.
- **No secrets in source**: Environment variables live in `.env` (gitignored). Never hard-code keys, RPC URLs, or private data.
- **Tests**: If you add or change logic, run the relevant tests (`pytest`, `hardhat test`, etc.) and ensure they pass before finishing.
