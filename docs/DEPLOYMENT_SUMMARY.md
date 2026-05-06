# MMP GCP Deployment Summary

## 💰 Three Cost Tiers Available

Choose your deployment tier:

| Tier | Idle Cost | Best For | Details |
|------|-----------|----------|---------|
| **Max Mini** | ~$50-70/mo | Solo dev, 2D images only | [See COST_TIERS.md](COST_TIERS.md) |
| **Standard Dev** | ~$150/mo | Team dev, full 3D+audio pipeline | [See COST_TIERS.md](COST_TIERS.md) |
| **Production** | ~$285/mo | Live users, high availability | Below |

---

## Idle Cost Fix Complete

The original architecture had **~$1,255/month idle cost**. This has been reduced to **~$285/month** with these changes:

| Component | Before | After | Savings |
|-----------|--------|-------|---------|
| **ReSplat worker** | Always 1 GPU replica ($730/mo) | KEDA ScaledJob (0 idle) | **$730/mo** |
| **Audio worker** | Always 1 replica ($100/mo) | KEDA scale-to-zero | **$100/mo** |
| **Filestore** | ENTERPRISE tier ($460/mo/TB) | BASIC_HDD ($80/mo/TB) | **$380/mo** |
| **System pool** | Standard instances | Optional Spot | **$50/mo** |
| **TOTAL IDLE** | **~$1,255/mo** | **~$285/mo** | **~$970/mo** |

---

## Changes Made

### 1. ReSplat Worker → KEDA ScaledJob
**File:** `infrastructure/pulumi/components/resplat.py`

- Converted from always-on Deployment to KEDA ScaledJob
- Scales from **0 to 5 GPU nodes** based on Pub/Sub queue depth
- **$0 idle cost**, ~2 minute cold start for 3D generation jobs
- New dedicated Pub/Sub topic: `resplat-3d-generation-{ENVIRONMENT}`

### 2. Audio Worker → KEDA ScaledObject
**File:** `infrastructure/pulumi/components/audio_worker.py`

- Added KEDA ScaledObject with `minReplicaCount: 0`
- Scales based on CPU utilization (50% threshold)
- 5-minute cooldown period before scaling down
- **$0 idle cost**, ~30 second cold start

### 3. Filestore → BASIC_HDD for All Environments
**Files:** `Pulumi.production.yaml`, `config.py`

- Production now uses BASIC_HDD ($80/TB) instead of ENTERPRISE ($460/TB)
- HDD is sufficient for model storage (sequential reads)
- **Saves $380/mo per TB**

### 4. System Pool → Optional Spot Instances
**Files:** `cluster.py`, `config.py`, `Pulumi.production.yaml`

- Added `use_spot_system_pool: true` config option
- AI Director and Audio worker are stateless, handle interruptions
- **Saves ~$50/mo per node** (~60% reduction)

---

## New Idle Cost Breakdown (~$285/mo)

| Component | Cost | Notes |
|-----------|------|-------|
| GKE cluster management | $75 | Fixed cost |
| System pool (1 node, Spot) | ~$50 | e2-standard-4, handles AI Director |
| GPU pool | $0 | KEDA scales to zero |
| Filestore (1TB BASIC_HDD) | ~$80 | Shared model cache |
| Pub/Sub | ~$10 | Base cost for topics |
| Cloud Monitoring | ~$50 | Logs and metrics |
| Secret Manager | ~$20 | API keys, certs |
| **TOTAL** | **~$285** | **~77% reduction** |

---

## To Reach $100/Month Idle Target

Enable **Aggressive Cost Mode** in Pulumi config:

```yaml
# Pulumi.staging.yaml or Pulumi.production.yaml
config:
  mmp:filestore_capacity_gb: "256"           # Downsize from 1TB
  mmp:system_pool_machine_type: "e2-medium"  # Smaller instance
  mmp:scheduled_shutdown: "0 20 * * *"       # 8pm-8am UTC shutdown
```

**Expected idle cost: ~$95/month**

---

## What I Need From You

Same as before, but now with cost-optimized defaults:

1. **GCP Project ID** (required)
2. **Domain name** for API (or "use nip.io")
3. **Environment**: staging or production
4. **Aggressive cost mode?** (yes/no) - for $100 idle target

---

## Deployment Commands

```bash
# 1. Setup GCP project
export GCP_PROJECT_ID=your-project-id
./infrastructure/scripts/gcloud-setup.sh

# 2. Build images
./infrastructure/scripts/build-images.sh

# 3. Deploy
cd infrastructure/pulumi
pulumi stack init production
pulumi config set project_id $GCP_PROJECT_ID
pulumi config set api_domain api.yourdomain.com
pulumi config set use_spot_system_pool true
pulumi up
```

---

## Files Modified

```
infrastructure/pulumi/
├── components/
│   ├── resplat.py          # KEDA ScaledJob, zero idle
│   ├── audio_worker.py     # KEDA scale-to-zero
│   ├── pubsub.py           # Added ReSplat queue
│   └── cluster.py          # Spot option for system pool
├── Pulumi.production.yaml  # BASIC_HDD default
└── config.py               # New cost config options

docs/
├── GCP_DEPLOYMENT_READINESS.md  # Updated costs
└── DEPLOYMENT_SUMMARY.md        # This file
```

---

## Trade-offs Summary

| Optimization | Trade-off |
|--------------|-----------|
| ReSplat KEDA ScaledJob | ~2 min cold start for 3D generation |
| Audio scale-to-zero | ~30 sec cold start for audio gen |
| BASIC_HDD Filestore | Higher latency for random reads (fine for sequential model loading) |
| Spot system pool | Possible interruptions (AI Director restarts, jobs retry) |

All trade-offs are acceptable for a tutorial/demo deployment and significantly reduce costs.
