# Architecture Overview

## System Design Philosophy

This project follows a **event-driven, microservices architecture** running on GCP. Each component is independently scalable, and the pipeline is designed for low-latency asset generation (target: <30 seconds draft-to-reveal).

---

## Component Interaction Diagram

```
User Browser
    │
    │ HTTP/REST
    ▼
AI Director (FastAPI, GKE)
    │
    ├─► GCP Pub/Sub ──► ComfyUI Workers (KEDA ScaledJobs, GPU nodes)
    │       │                │
    │       │         Filestore NFS (shared model cache)
    │       │
    │   dead-letter topic (failed jobs → alerting)
    │
    ├─► Moshi/VibeVoice (Audio, separate GKE deployment)
    │
    └─► Base L2 RPC (via ERC-4337 Bundler)
            │
            ├── CharacterNFT.sol
            ├── AIDirectorPaymaster.sol
            └── CharacterSplits.sol
```

---

## Pipeline Stages

| Stage | Agent | Duration (p50) | GCP Service |
|-------|-------|----------------|-------------|
| Request intake | Orchestrator | ~50ms | Pub/Sub publish |
| 2D draft generation (×4) | ImageAgent | ~8s | ComfyUI on GKE GPU |
| Draft selection | EvaluatorAgent | ~200ms | In-process |
| Upscale selected draft | ImageAgent | ~5s | ComfyUI on GKE GPU |
| 3DGS generation | ImageAgent | ~12s | ComfyUI on GKE GPU |
| Audio generation | AudioAgent | ~4s | Moshi inference |
| On-chain mint | Web3Agent | ~3s | Base L2 ERC-4337 |
| **Total** | | **~32s** | |

---

## Scaling Strategy

### KEDA ScaledJobs
KEDA watches the `asset-generation-requests` Pub/Sub subscription. For each undelivered message, it creates a Kubernetes Job. This provides:
- **True zero-to-N scaling** — no idle GPU costs
- **Per-request isolation** — one Job per asset, failures don't cascade
- **Automatic cleanup** — completed Jobs are garbage-collected

### Filestore NFS Model Cache
ComfyUI models (SDXL, ControlNet, etc.) are large (~10GB+). Downloading on every cold start is unacceptable. Filestore provides:
- **ReadWriteMany** — all GPU pods share one NFS mount
- **Pre-warmed cache** — a separate init Job pre-downloads models on deploy
- **gVisor + CUDA snapshots** — fast pod restore from checkpoint

---

## Security Architecture

### Workload Identity
GKE pods authenticate to GCP APIs (Pub/Sub, Filestore) via Workload Identity — no service account keys stored in the cluster.

### ERC-4337 Account Abstraction
Users never touch private keys directly. The flow:
1. Frontend generates a session keypair in-browser
2. AIDirectorPaymaster sponsors gas for first-time mints
3. User operations are submitted through a bundler

### Smart Contract Access Control
- `CharacterNFT`: `mintFree` enforced one-per-address via mapping
- `AIDirectorPaymaster`: Only whitelisted EntryPoint can call `validatePaymasterUserOp`
- `CharacterSplits`: Immutable split allocations set at deployment

---

## Data Flow: Character Generation Request

```
1. User clicks "Claim Free Character"
2. Frontend: POST /generate {userId, preferences}
3. AI Director: Creates job record, publishes to Pub/Sub
4. KEDA: Detects message, spawns ComfyUI Job
5. ComfyUI: Generates 4 drafts, POSTs to /webhook/comfyui
6. EvaluatorAgent: Scores drafts, selects best
7. ImageAgent: Upscales + generates 3DGS
8. AudioAgent: Generates soundscape for character type
9. AI Director: Bundles assets, updates job status
10. Frontend: Polls /status/{job_id}, reveals character
11. (Optional) Web3Agent: ERC-4337 gasless mint on Base
```
