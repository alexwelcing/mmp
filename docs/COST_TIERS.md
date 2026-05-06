# MMP Cost Tiers: From "Max Mini" to Production

## Quick Comparison

| Tier | Idle Cost | Active Cost | Best For |
|------|-----------|-------------|----------|
| **Max Mini** | ~$50-70/mo | ~$100-200/mo | Solo dev, early prototyping |
| **Standard Dev** | ~$150/mo | ~$300-500/mo | Team dev, integration testing |
| **Production** | ~$285/mo | ~$1,500-9,000/mo | Live users, high availability |

---

## Tier 1: "Max Mini" — ~$50-70/month idle

### What You Get
✅ Full AI Director pipeline  
✅ ComfyUI image generation (on-demand GPU)  
✅ Pub/Sub message queue  
✅ Shared model storage (256GB)  
⚠️ **Mock audio** (returns placeholder)  
⚠️ **No 3D/ReSplat** (2D images only)  
⚠️ **Mock Web3** (no real blockchain)  
⚠️ Basic auth (API key only)  

### Architecture
```
┌──────────────────────────────────────────────────────┐
│  GKE Autopilot (no mgmt fee, pay per pod)            │
│  ┌──────────────────┐  ┌──────────────────────────┐  │
│  │ AI Director      │  │ ComfyUI KEDA ScaledJob   │  │
│  │ 250m CPU, 256MB  │  │ 0-1 GPU (scales to 0)    │  │
│  └──────────────────┘  └──────────────────────────┘  │
└──────────────────────────────────────────────────────┘
  Filestore Basic 256GB ($20/mo)
  Pub/Sub topics ($5/mo base)
  Load Balancer ($18/mo)
```

### Cost Breakdown
| Component | Cost | Why |
|-----------|------|-----|
| GKE Autopilot | ~$0 | No management fee |
| AI Director pod | ~$15 | 250m CPU, only when running |
| Filestore 256GB | ~$20 | Smallest viable |
| Load balancer | ~$18 | Required for ingress |
| Pub/Sub | ~$5 | Base cost |
| Monitoring (free tier) | $0 | <10GB logs/mo |
| **TOTAL IDLE** | **~$58** | AI Director always on |
| **Scale-to-zero AI Director** | **~$43** | Use Cloud Run instead |

### Activation
```bash
pulumi stack init dev-mini
pulumi config set environment dev
pulumi config set filestore_tier BASIC_HDD
pulumi config set filestore_capacity_gb 256
pulumi config set enable_resplat false
pulumi config set enable_audio false
pulumi config set use_mock_web3 true
pulumi config set ai_director_min_replicas 0  # Scale to zero
pulumi up
```

---

## Tier 2: "Standard Dev" — ~$150/month idle

### What You Get
✅ Everything in Max Mini  
✅ **Real audio generation** (KEDA scaled)  
✅ **Real 3D generation** (ReSplat, KEDA scaled)  
✅ **Real Web3** (testnet)  
✅ Proper monitoring & alerts  
✅ WAF/Cloud Armor  
✅ Team collaboration features  

### Architecture
```
┌─────────────────────────────────────────────────────────────┐
│  GKE Standard + Spot instances                              │
│  ┌──────────────┐ ┌─────────────┐ ┌─────────────────────┐  │
│  │ AI Director  │ │ Audio       │ │ ComfyUI/ReSplat     │  │
│  │ 500m CPU     │ │ Scale-to-0  │ │ KEDA ScaledJobs     │  │
│  └──────────────┘ └─────────────┘ └─────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
  Filestore Basic 1TB ($80/mo)
  Cloud Armor WAF ($10/mo)
  Full monitoring ($50/mo)
```

### Cost Breakdown
| Component | Cost | Notes |
|-----------|------|-------|
| GKE Standard (1 node Spot) | ~$50 | e2-standard-2 |
| Filestore 1TB | ~$80 | Room for growth |
| Load balancer + WAF | ~$28 | Production-like security |
| Pub/Sub | ~$10 | Moderate usage |
| Monitoring | ~$20 | Beyond free tier |
| **TOTAL IDLE** | **~$188** | All services scale to 0 except system node |

### Activation
```bash
pulumi stack init dev
pulumi config set environment staging
pulumi config set filestore_capacity_gb 1024
pulumi config set enable_resplat true
pulumi config set enable_audio true
pulumi config set use_spot_system_pool true
pulumi up
```

---

## Tier 3: "Production" — ~$285/month idle

### What You Get
✅ Everything in Standard Dev  
✅ **High availability** (multi-zone)  
✅ **Disaster recovery** (backups, replication)  
✅ **SOC2 compliance features** (audit logs, encryption)  
✅ **SLA guarantees** (99.9% uptime)  
✅ **Dedicated support**  

### Architecture
Same as documented in `GCP_DEPLOYMENT_READINESS.md`

---

## Safety Comparison

| Feature | Max Mini | Standard Dev | Production |
|---------|----------|--------------|------------|
| **HTTPS/TLS** | ✅ | ✅ | ✅ |
| **API authentication** | API key | API key + JWT | OAuth2 + mTLS |
| **DDoS protection** | GCP default | Cloud Armor | Cloud Armor Enterprise |
| **Audit logging** | Basic | Full | Compliance-grade |
| **Data encryption** | GCP default | GCP default | CMEK (customer-managed) |
| **Backup/DR** | None | Weekly | Real-time replication |
| **Secrets management** | Env vars | Secret Manager | Secret Manager + rotation |

### Is "Max Mini" Safe?

**Yes, for development:**
- ✅ Runs in your GCP project (isolated)
- ✅ HTTPS by default
- ✅ No public secrets in code
- ✅ Can restrict API by IP if needed

**No, for production:**
- ❌ No DDoS protection
- ❌ No audit trail
- ❌ Single point of failure
- ❌ No disaster recovery

---

## Decision Tree

```
Are you deploying for users?
├── NO (internal/dev only)
│   ├── Budget < $100/mo? → MAX MINI
│   ├── Budget $100-250/mo? → STANDARD DEV
│   └── Need 3D + Audio + Web3? → STANDARD DEV
│
└── YES (production users)
    ├── < 1000 MAU? → PRODUCTION (single region)
    └── > 1000 MAU? → PRODUCTION (multi-region)
```

---

## Max Mini Quick Start

```bash
# 1. Configure for absolute minimum
cd infrastructure/pulumi
pulumi stack init dev-mini
pulumi config set project_id YOUR_PROJECT
pulumi config set environment dev
pulumi config set filestore_capacity_gb 256
pulumi config set enable_resplat false
pulumi config set enable_audio false
pulumi config set use_mock_web3 true
pulumi config set use_gke_autopilot true

# 2. Deploy
pulumi up

# 3. Estimated cost
# Idle: ~$50-70/mo
# With daily testing: ~$100-150/mo
```

---

## Cost Optimization Tips (All Tiers)

```bash
# Auto-shutdown when not in use
# Add to Pulumi config:
config:
  mmp:scheduled_shutdown: "0 20 * * *"  # 8pm daily
  mmp:scheduled_startup: "0 8 * * 1-5"  # 8am weekdays

# Use preemptible GPUs for dev
gcloud container node-pools create gpu-pool \
  --cluster=mmp-cluster \
  --machine-type=n1-standard-4 \
  --accelerator=type=nvidia-tesla-t4,count=1 \
  --spot  # 60-91% cheaper

# Cleanup old outputs weekly
kubectl create cronjob output-cleanup \
  --image=google/cloud-sdk \
  --schedule="0 2 * * 0" \
  -- gsutil -m rm -rf gs://mmp-outputs/old/
```

---

## My Recommendation

**Start with Standard Dev (~$150/mo idle):**
- You get real 3D and audio (not mocked)
- You can test the full pipeline
- Safe enough for sharing with a small team
- Easy upgrade path to production

**Use Max Mini only if:**
- You're solo hacking on weekends
- You're only testing 2D image generation
- $50/month is a hard constraint

**The $100 difference is worth it** to avoid "works in dev, breaks in prod" surprises.
