# Architecture Overview

## System Design Philosophy

This project follows an **event-driven, microservices architecture** running on GCP. Each component is independently scalable, and the pipeline is designed for low-latency asset generation (target: <30 seconds draft-to-reveal).

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
    │       │                │
    │       │         AIDirectorWebhook
    │       │                │
    │   dead-letter topic (failed jobs → alerting)
    │       ▲
    │       │ (webhook callback)
    │
    ├─► Audio Worker (AudioGen, CPU)
    │
    ├─► ReSplat Worker (GPU, optional)
    │       Stable Zero123 → COLMAP → ReSplat → .ply
    │
    └─► Base L2 RPC (via ERC-4337 Bundler, or direct EOA in local mode)
            │
            ├── CharacterNFT.sol
            ├── AIDirectorPaymaster.sol
            └── CharacterSplits.sol
```

---

## Pipeline Stages

| Stage | Agent | Duration (p50) | Infrastructure |
|-------|-------|----------------|----------------|
| Request intake | Orchestrator | ~50ms | Pub/Sub publish |
| 2D draft generation (×4) | ImageAgent | ~8s | ComfyUI on GKE GPU |
| Draft selection | EvaluatorAgent | ~200ms | In-process |
| Upscale selected draft | ImageAgent | ~5s | ComfyUI on GKE GPU |
| 3DGS generation | ImageAgent / ResplatAgent | ~12–60s | ComfyUI GPU / ReSplat GPU |
| Audio generation | AudioAgent | ~4s | AudioGen CPU worker |
| On-chain mint | Web3Agent | ~3s | Base L2 ERC-4337 |
| **Total** | | **~32s** | |

> **Note:** When `USE_RESPLAT_FOR_3D=true`, 3D generation is routed to the ReSplat worker for higher-quality Gaussian Splatting `.ply` output. Otherwise, the faster ComfyUI-based mesh path is used.

---

## Scaling Strategy

### KEDA ScaledJobs
KEDA watches the `asset-generation-requests` Pub/Sub subscription. For each undelivered message, it creates a Kubernetes Job. This provides:
- **True zero-to-N scaling** — no idle GPU costs
- **Per-request isolation** — one Job per asset, failures don't cascade
- **Automatic cleanup** — completed Jobs are garbage-collected

### Filestore NFS Model Cache
ComfyUI and ReSplat models (SDXL, ControlNet, Zero123, etc.) are large (~10GB+). Downloading on every cold start is unacceptable. Filestore provides:
- **ReadWriteMany** — all GPU pods share one NFS mount
- **Pre-warmed cache** — a separate init Job pre-downloads models on deploy
- **gVisor + CUDA snapshots** — fast pod restore from checkpoint

## Google Cloud NEXT '26 Upgrade Path

The current tutorial architecture still holds up well, but three NEXT '26 sessions sharpen where it should evolve next:

| NEXT '26 signal | Current MMP state | Recommended tutorial upgrade |
|---|---|---|
| [`Google MCP Services: Connect AI agents to cloud infrastructure in minutes`](https://www.googlecloudevents.com/next-vegas/session/3912288/google-mcp-services-connect-ai-agents-to-cloud-infrastructure-in-minutes) | The AI Director already behaves like a control-plane agent, but cloud integrations are still described as direct service-specific calls. | Add an MCP tool layer for cloud operations so the AI Director can inspect GKE, query analytics, and trigger future support workflows with IAM-backed access instead of custom glue code. |
| [`What's new for AI on GKE: Training, serving, and agents`](https://www.googlecloudevents.com/next-vegas/session/3912907/what's-new-for-ai-on-gke-training-serving-and-agents) | GPU work is already isolated behind GKE workers, KEDA scaling, and a shared model cache. | Document the workers as an AI serving plane, with separate operational guidance for batch generation, interactive inference, and agent-triggered workloads. |
| [`What's new in streaming: Real-time data for agentic AI`](https://www.googlecloudevents.com/next-vegas/session/3912220/what's-new-in-streaming-real-time-data-for-agentic-ai) | Pub/Sub currently handles request intake and dead-letter recovery. | This refresh adds a dedicated status topic so the AI Director now emits job lifecycle events; moderation and analytics streams are the next logical extensions. |

In short: NEXT '26 does not require a rewrite of MMP. It validates the existing direction, and this refresh already makes one of those ideas concrete by **emitting generation lifecycle events onto Pub/Sub for downstream consumers**.

---

## Security Architecture

### Workload Identity
GKE pods authenticate to GCP APIs (Pub/Sub, Filestore) via Workload Identity — no service account keys stored in the cluster.

That same IAM-first posture lines up with the MCP direction highlighted at NEXT '26: agents should inherit scoped cloud permissions instead of shipping API keys inside application code.

### ERC-4337 Account Abstraction
Users never touch private keys directly. The flow:
1. Frontend generates a session keypair in-browser
2. AIDirectorPaymaster sponsors gas for first-time mints
3. User operations are submitted through a bundler (or direct EOA transactions in local dev mode)

### Smart Contract Access Control
- `CharacterNFT`: `mintFree` enforced one-per-address via mapping
- `AIDirectorPaymaster`: Only whitelisted EntryPoint can call `validatePaymasterUserOp`
- `CharacterSplits`: Immutable split allocations set at deployment

---

## Data Flow: Character Generation Request

```
1. User clicks "Claim Free Character"
2. Frontend: POST /generate {userId, preferences}
3. AI Director: Creates job record, publishes to Pub/Sub (or runs inline locally)
4. KEDA: Detects message, spawns ComfyUI Job
5. ComfyUI: Generates 4 drafts, POSTs to /webhook/comfyui via AIDirectorWebhook node
6. EvaluatorAgent: Scores drafts, selects best
7. ImageAgent: Upscales selected draft
8. ImageAgent / ResplatAgent: Generates 3D asset (ComfyUI mesh or ReSplat .ply)
9. AudioAgent: Generates soundscape for character type
10. AI Director: Bundles assets, updates job status, and emits lifecycle events to `PUBSUB_STATUS_TOPIC` when configured
11. Frontend: Polls /status/{job_id}, reveals character
12. (Optional) Web3Agent: ERC-4337 gasless mint on Base
```

---

## Infrastructure as Code (Pulumi)

The canonical deployment path uses **Pulumi Python Component Resources**:

| Component | Responsibility |
|-----------|---------------|
| `MMPCluster` | VPC, GKE cluster, system/GPU node pools, Workload Identity |
| `FilestoreCache` | NFS-backed shared model & output storage |
| `PubSubPipeline` | Topic, subscription, and dead-letter topic |
| `ComfyUIWorkerPool` | KEDA ScaledJob + ConfigMap for ComfyUI |
| `AIDirectorService` | FastAPI Deployment, HPA, Ingress |
| `AudioWorker` | AudioGen CPU Deployment + Service |
| `ResplatWorker` | ReSplat GPU Deployment + Service |

Raw Kubernetes YAML manifests still exist in `infrastructure/kubernetes/` as reference material, but they are no longer the primary deployment mechanism.
