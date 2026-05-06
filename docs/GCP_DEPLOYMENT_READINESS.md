# GCP Deployment Readiness Analysis

> **Prepared for:** MMP (Autonomous AI Director) Production Deployment  
> **Date:** 2026-04-12  
> **Objective:** Identify cost-value tradeoffs, security gaps, monitoring needs, and deployment prerequisites

---

## Executive Summary

The MMP architecture is **well-designed for cost efficiency** with several smart choices (Spot instances, KEDA-based scaling, shared Filestore). However, there are **critical gaps in monitoring, security hardening, and cost controls** that must be addressed before production deployment.

### Risk Rating: 🟡 MEDIUM-HIGH
- **Good foundation** but missing production guardrails
- **Cost surprises likely** without spending alerts and quotas
- **Security exposure** from missing WAF, audit logging, and secret management
- **Operational blindness** without structured observability

---

## 1. Current Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              GCP PROJECT                                      │
│  ┌───────────────────────────────────────────────────────────────────────┐   │
│  │                          GKE CLUSTER (Autopilot-like)                  │   │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐   │   │
│  │  │ System Pool │  │  GPU Pool   │  │  KEDA       │  │  Filestore  │   │   │
│  │  │ e2-standard-4│  │ n1-standard-4│  │  ScaledJobs │  │  NFS Cache  │   │   │
│  │  │ Spot (dev)  │  │ Spot + T4   │  │  (0-15 pods)│  │  1TB BASIC  │   │   │
│  │  │ 1-5 nodes   │  │ 0-10 nodes  │  │             │  │  HDD/ENT    │   │   │
│  │  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘   │   │
│  │         │                │                │                │          │   │
│  │         ▼                ▼                ▼                ▼          │   │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐   │   │
│  │  │ AI Director │  │ ComfyUI     │  │  ReSplat    │  │   Audio     │   │   │
│  │  │  (FastAPI)  │  │  Workers    │  │  Worker     │  │   Worker    │   │   │
│  │  │   HPA 1-5   │  │  (Jobs)     │  │  1 replica  │  │  1 replica  │   │   │
│  │  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘   │   │
│  └───────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
│  ┌───────────────────────────────────────────────────────────────────────┐   │
│  │                    MESSAGING & STORAGE                                 │   │
│  │  Pub/Sub Topic ──► Subscription ──► Dead Letter Queue                │   │
│  │  (asset-gen-requests)     (ack=600s)        (max_delivery=5)         │   │
│  └───────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
│  ┌───────────────────────────────────────────────────────────────────────┐   │
│  │                    SECURITY & IDENTITY                                 │   │
│  │  Workload Identity ──► Service Accounts ──► IAM Roles                  │   │
│  │  gVisor sandbox ──► GPU time-sharing ──► Spot instances                │   │
│  └───────────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Cost-Value Tradeoff Analysis

### ✅ GOOD Tradeoffs (Keep These)

| Decision | Cost Impact | Value | Rationale |
|----------|-------------|-------|-----------|
| **Spot instances for GPU pool** | -60-90% compute | High | GPU workloads are fault-tolerant (jobs restart on preemption) |
| **KEDA ScaledJobs (vs Deployment)** | $0 when idle | High | True serverless GPU scaling; no idle node costs |
| **Filestore BASIC_HDD (staging)** | ~$80/TB/month | Medium | NFS is required for RWX; HDD acceptable for non-prod |
| **GPU time-sharing (4 clients/GPU)** | -75% GPU count | Medium | T4 can handle 4 concurrent ComfyUI jobs |
| **n1-standard-4 for GPU nodes** | Balanced | High | Right-sized for T4 + ComfyUI memory needs |
| **Pub/Sub (vs HTTP polling)** | ~$40/TB | High | Decouples services; dead-letter for reliability |

### ⚠️ QUESTIONABLE Tradeoffs (Review Needed)

| Decision | Monthly Cost | Concern | Recommendation |
|----------|--------------|---------|----------------|
| **Filestore ENTERPRISE (prod)** | ~$460/TB/month | 5.7x cost vs BASIC_SSD | Use BASIC_SSD ($200/TB) unless <10ms latency required |
| **ReSplat worker: always 1 replica** | ~$730/month idle | GPU node stays warm 24/7 | Make ReSplat KEDA-scaled or move to ComfyUI path |
| **Audio worker: always 1 replica** | ~$100/month idle | CPU can cold-start fast | Add HPA minReplicas=0 or use Cloud Run |
| **No resource quotas/limits** | $$$ surprise | Burst spending risk | Add GKE ResourceQuotas + GCP budget alerts |
| **us-central1 only** | None yet | No DR, latency for global users | Document single-region risk; add Cloud CDN |

### 🚨 BAD Tradeoffs (Fix Before Deploy)

| Decision | Risk | Impact | Fix Priority |
|----------|------|--------|--------------|
| **No cost monitoring/alerts** | Bill shock | Unlimited | P0 - Set $500/day alert minimum |
| **No VPC egress controls** | Data exfiltration | Security breach | P0 - Cloud Armor + private Google Access |
| **No pod security policies** | Container escape | Cluster compromise | P1 - kyverno/gatekeeper + seccomp |
| **Filestore NO_ROOT_SQUASH** | Privilege escalation | Unauthorized access | P1 - Switch to ROOT_SQUASH + anon uid/gid |
| **Hardcoded RPC URLs** | Infra lock-in | Reliability issues | P1 - Use ConfigMap + health-checked endpoints |

---

## 3. Cost Estimation (Monthly)

### Staging Environment

| Component | Specs | Est. Monthly Cost |
|-----------|-------|-------------------|
| GKE cluster mgmt | Regional | $75 |
| System pool (e2-standard-4) | 1-5 nodes, Spot | $50-250 |
| GPU pool (n1-standard-4 + T4) | 0-10 nodes, Spot | $0-2,200 |
| Filestore BASIC_HDD | 1 TB | $80 |
| Pub/Sub | 1M messages/day | $30 |
| Load balancer | L7 | $20 |
| **Staging Total** | | **~$500-2,700** |

### Production Environment (Cost-Optimized)

| Component | Specs | Idle Cost | Active Cost |
|-----------|-------|-----------|-------------|
| GKE cluster mgmt | Regional | $75 | $75 |
| System pool (e2-standard-4) | 1 node, **Spot** | ~$50 | $200-500 |
| GPU pool (n1-standard-4 + T4) | **0 nodes** (KEDA) | **$0** | $0-8,000 |
| Filestore **BASIC_HDD** | 1 TB | ~$80 | ~$80 |
| Pub/Sub | 10M messages/day | ~$10 | ~$300 |
| Cloud Armor (WAF) | Standard | $0 | $100 |
| Cloud CDN | 100GB egress | $0 | $20 |
| Cloud Monitoring | Metrics/logs | $50 | $200 |
| Secret Manager | 50 secrets | $20 | $20 |
| **Production Total** | | **~$285** | **~$1,500-9,000** |

> **Idle cost: ~$285/month**  
> To reach **$100 idle target**, enable aggressive cost mode (see below)

### Cost Optimization Opportunities

#### Implemented (Already in Code)
```yaml
✅ ReSplat KEDA ScaledJob:                       Save $730/mo idle
✅ Audio worker scale-to-zero:                   Save $100/mo idle
✅ Filestore BASIC_HDD (all envs):               Save $120/mo per TB vs SSD
✅ Spot for system pool (optional):              Save $50/mo per node
```

#### To Reach $100/Month Idle Target
```yaml
Aggressive Cost Mode (add to Pulumi config):
  mmp:aggressive_cost_mode: "true"
  mmp:filestore_capacity_gb: "256"              # Save $60/mo (was 1TB)
  mmp:system_pool_machine_type: "e2-medium"     # Save $30/mo (was e2-standard-4)
  mmp:scheduled_shutdown: "0 20 * * *"          # Shutdown 8pm-8am UTC: Save $100/mo
  
Expected idle cost with aggressive mode: ~$95/mo
```

#### Long-term Optimizations
```yaml
  - Migrate Audio to Cloud Run (gen2):            Save $50/mo, instant scaling
  - Use Cloud Storage FUSE instead of Filestore:  Save $60/mo for models
  - GKE Autopilot for system workloads:           Reduce mgmt overhead
  - Tiered storage for old outputs:               Save $30-50/mo
```

---

## 4. Security Gaps & Recommendations

### P0 - Critical (Block Deployment)

| Gap | Risk | Mitigation |
|-----|------|------------|
| **No WAF/Cloud Armor** | DDoS, injection attacks | Add Cloud Armor with OWASP rules |
| **No audit logging** | Undetected compromise | Enable Cloud Audit Logs (Admin, Data Access) |
| **Secrets in ConfigMaps** | Credential leakage | Migrate to Secret Manager + CSI driver |
| **Wildcard CORS in prod** | CSRF, data theft | Strict origin allowlist |

### P1 - High (Fix in First Sprint)

| Gap | Risk | Mitigation |
|-----|------|------------|
| **No network policies** | Lateral movement | Default-deny + explicit allow |
| **Filestore NO_ROOT_SQUASH** | Host compromise | ROOT_SQUASH with mapped anon user |
| **No binary authorization** | Supply chain attacks | Enable BinAuthz + attestations |
| **Hardcoded service URLs** | MITM, failover gaps | Service mesh or DNS-based discovery |

### P2 - Medium (Post-Launch)

| Gap | Risk | Mitigation |
|-----|------|------------|
| **No pod security context** | Container escape | RunAsNonRoot, readOnlyRootFilesystem |
| **No encryption in transit for internal** | Side-channel | Istio/Linkerd mTLS |
| **No vulnerability scanning** | CVE exploitation | Container Analysis + GCR scanning |

---

## 5. Monitoring & Observability Gaps

### Current State
- ✅ Basic GKE logging enabled (SYSTEM_COMPONENTS, WORKLOADS)
- ✅ Basic GKE monitoring enabled (SYSTEM_COMPONENTS)
- ✅ Health check endpoints on all services
- ❌ No custom metrics or SLOs
- ❌ No alerting policies
- ❌ No distributed tracing
- ❌ No log-based metrics

### Required Monitoring Stack

```yaml
# Missing components to implement:

Metrics:
  - Custom metrics: Job duration, queue depth, generation latency
  - SLOs: 99th percentile <30s draft-to-reveal
  - Cost metrics: Per-workload spend attribution

Alerting:
  - Pub/Sub subscription lag > 5 minutes
  - GPU pool scaling failures
  - Job failure rate > 5%
  - Daily spend > $500
  - Filestore capacity > 80%

Dashboards:
  - Pipeline health: Jobs/sec, error rate, latency percentiles
  - Cost tracking: Per-service spend, forecast
  - Resource utilization: GPU/CPU/Memory efficiency

Tracing:
  - OpenTelemetry integration
  - End-to-end request tracing (frontend → AI Director → ComfyUI)
```

---

## 6. Deployment Readiness Checklist

### Phase 1: Prerequisites (You Provide)

- [ ] **GCP Project** with billing enabled
- [ ] **Service Account** for Pulumi deployment with roles:
  - `roles/compute.admin`
  - `roles/container.admin`
  - `roles/file.editor`
  - `roles/pubsub.admin`
  - `roles/resourcemanager.projectIamAdmin`
  - `roles/iam.serviceAccountAdmin`
  - `roles/artifactregistry.admin`
- [ ] **APIs Enabled**:
  - `compute.googleapis.com`
  - `container.googleapis.com`
  - `file.googleapis.com`
  - `pubsub.googleapis.com`
  - `artifactregistry.googleapis.com`
  - `monitoring.googleapis.com`
  - `logging.googleapis.com`
  - `cloudbuild.googleapis.com` (for CI/CD)

### Phase 2: gcloud Setup (We'll Execute)

```bash
# Authentication & project configuration
gcloud auth login
gcloud config set project YOUR_PROJECT_ID
gcloud auth application-default login

# Verify quotas (need at least):
gcloud compute project-info describe --project YOUR_PROJECT_ID | grep -i quota
# - CPUS: 100
# - NVIDIA_T4_GPUS: 10
# - IN_USE_ADDRESSES: 50
# - FILESTORE_INSTANCES: 5

# Enable required APIs
gcloud services enable compute.googleapis.com container.googleapis.com \
  file.googleapis.com pubsub.googleapis.com artifactregistry.googleapis.com \
  monitoring.googleapis.com logging.googleapis.com cloudbuild.googleapis.com \
  cloudarmor.googleapis.com secretmanager.googleapis.com

# Create Artifact Registry
gcloud artifacts repositories create mmp-images \
  --repository-format=docker \
  --location=us-central1 \
  --description="MMP service images"

# Configure Docker auth
gcloud auth configure-docker us-central1-docker.pkg.dev
```

### Phase 3: Build & Push Images

```bash
# AI Director
cd services/ai-director
docker build -t us-central1-docker.pkg.dev/YOUR_PROJECT/mmp-images/ai-director:latest .
docker push us-central1-docker.pkg.dev/YOUR_PROJECT/mmp-images/ai-director:latest

# ComfyUI Worker (large, ~8GB)
cd services/comfyui-worker
docker build -t us-central1-docker.pkg.dev/YOUR_PROJECT/mmp-images/comfyui-worker:latest .
docker push us-central1-docker.pkg.dev/YOUR_PROJECT/mmp-images/comfyui-worker:latest

# Audio Worker
cd services/audio-worker
docker build -t us-central1-docker.pkg.dev/YOUR_PROJECT/mmp-images/audio-worker:latest .
docker push us-central1-docker.pkg.dev/YOUR_PROJECT/mmp-images/audio-worker:latest

# ReSplat Worker
cd services/resplat-worker
docker build -t us-central1-docker.pkg.dev/YOUR_PROJECT/mmp-images/resplat-worker:latest .
docker push us-central1-docker.pkg.dev/YOUR_PROJECT/mmp-images/resplat-worker:latest
```

### Phase 4: Pulumi Deployment

```bash
cd infrastructure/pulumi

# Create virtual environment
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt

# Configure stack
pulumi stack init staging  # or production
pulumi config set project_id YOUR_PROJECT_ID
pulumi config set region us-central1
pulumi config set zone us-central1-a
pulumi config set environment staging
pulumi config set filestore_tier BASIC_HDD  # or BASIC_SSD for prod
pulumi config set filestore_capacity_gb 1024
pulumi config set api_domain api.yourdomain.com

# Preview and deploy
pulumi preview
pulumi up
```

### Phase 5: Post-Deployment Verification

```bash
# Verify cluster
kubectl get nodes -l pool=gpu
kubectl get pods -n comfyui
kubectl get scaledjob -n comfyui

# Test Pub/Sub flow
gcloud pubsub topics publish asset-generation-requests-staging \
  --message='{"test": true}'

# Check Filestore mount
kubectl exec -n comfyui deploy/comfyui-worker -- ls /mnt/filestore/models

# Verify AI Director health
curl http://AI_DIRECTOR_IP/health
```

---

## 7. Immediate Action Items

### Before You Provide Credentials:

1. **Decide on production Filestore tier**:
   - `BASIC_SSD` ($200/TB): Good for <100 concurrent jobs
   - `ENTERPRISE` ($460/TB): Only if you need <10ms latency or 100+ concurrent

2. **Confirm quota limits** in your GCP project for GPUs and CPUs

3. **Choose domain name** for API ingress (need for TLS certificate)

4. **Decide on ReSplat availability**:
   - Option A: Keep 1 replica (always warm, $730/mo)
   - Option B: KEDA-scale to zero (cold start ~2min, $0 idle)
   - Option C: Disable for initial launch

### When You're Ready:

Provide me with:
1. **GCP Project ID**
2. **Preferred domain** (or use nip.io for testing)
3. **Environment** (staging or production)
4. **Budget alert threshold** (daily spend limit)

I'll then execute the gcloud setup and guide you through the deployment.

---

## 8. Appendix: Cost Control Guardrails

```yaml
# Recommended budget alerts to configure:

Budget Alerts:
  - 50% of monthly budget: Email notification
  - 80% of monthly budget: Email + Slack notification  
  - 100% of monthly budget: Email + Disable non-essential APIs

Quotas to Set:
  - NVIDIA_T4_GPUS: 20 (prevent runaway GPU scaling)
  - CPUS: 200 (limit total compute)
  - IN_USE_ADDRESSES: 100 (prevent IP exhaustion)

Auto-shutdown:
  - Staging: Cloud Scheduler to scale GPU pool to 0 nights/weekends
  - Dev environments: Delete after 4 hours idle
```
