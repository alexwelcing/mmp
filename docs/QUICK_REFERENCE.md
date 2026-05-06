# MMP Quick Reference Card

## 🚀 One-Page Deploy Guide

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                    🎮 MMP QUICK DEPLOY (Copy-Paste Ready)                        │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                  │
│  STEP 1: PREREQUISITES                                                           │
│  ────────────────────                                                            │
│  export GCP_PROJECT_ID=your-project-id                                           │
│  gcloud auth login                                                               │
│  make check            # Verify everything is ready                              │
│                                                                                  │
│  STEP 2: CHOOSE TIER                                                             │
│  ───────────────────                                                             │
│  ┌──────────────────┬──────────────────┬──────────────────┐                      │
│  │   MAX MINI       │  STANDARD DEV    │  PRODUCTION      │                      │
│  │   $50-70/mo      │  $150/mo         │  $285/mo         │                      │
│  │   Solo Dev       │  Team Dev        │  Live Users      │                      │
│  └──────────────────┴──────────────────┴──────────────────┘                      │
│                                                                                  │
│  STEP 3: DEPLOY                                                                  │
│  ────────────                                                                    │
│  make deploy-dev         # or deploy-staging / deploy-prod                       │
│                                                                                  │
│  STEP 4: TEST                                                                    │
│  ─────────                                                                       │
│  make test-api           # Should return {"status":"ok"}                         │
│  make test-generate      # Test character generation                             │
│                                                                                  │
│  STEP 5: MONITOR                                                                 │
│  ────────────                                                                    │
│  make logs               # Follow AI Director logs                               │
│  make get-ip             # Get load balancer IP                                  │
│                                                                                  │
└─────────────────────────────────────────────────────────────────────────────────┘
```

---

## 📋 Deployment Checklist

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                          ✅ PRE-DEPLOY CHECKLIST                                │
└─────────────────────────────────────────────────────────────────────────────────┘

[ ] GCP Account created
[ ] Billing enabled on project
[ ] gcloud CLI installed and authenticated
[ ] Pulumi CLI installed
[ ] Docker installed
[ ] kubectl installed
[ ] Make installed

[ ] GCP_PROJECT_ID environment variable set
[ ] make check passes all tests
[ ] GPU quota requested (if using GPU features)
[ ] Service account key generated

[ ] Chosen deployment tier (dev/staging/prod)
[ ] Reviewed estimated costs
[ ] Set budget alerts in GCP Console

[ ] Frontend built (optional)
[ ] Docker images built
[ ] Contracts deployed (optional, for Web3)
```

---

## 🔧 Common Commands

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                         🛠️ TROUBLESHOOTING COMMANDS                              │
└─────────────────────────────────────────────────────────────────────────────────┘

GET CLUSTER ACCESS:
  make kubeconfig          # Configure kubectl
  kubectl get nodes        # Verify nodes are ready
  kubectl get pods -A      # Check all pods

DEBUG PODS:
  kubectl logs -n ai-director deployment/ai-director --tail=50
  kubectl describe pod -n ai-director <pod-name>
  kubectl exec -it -n ai-director <pod-name> -- /bin/sh

RESTART SERVICES:
  kubectl rollout restart deployment/ai-director -n ai-director
  kubectl rollout status deployment/ai-director -n ai-director

CHECK PUB/SUB:
  gcloud pubsub topics list
  gcloud pubsub subscriptions pull asset-generation-requests-sub-dev --limit=5

CHECK FILESTORE:
  gcloud filestore instances list
  kubectl get pv,pvc -A

PULUMI OPERATIONS:
  pulumi stack ls                    # List stacks
  pulumi stack output                # Show outputs
  pulumi refresh --yes               # Sync state with cloud
  pulumi cancel                      # Cancel stuck update
  pulumi destroy --yes               # Delete everything
```

---

## 💰 Cost Optimization Cheat Sheet

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                         💸 COST OPTIMIZATION TIPS                               │
└─────────────────────────────────────────────────────────────────────────────────┘

IMMEDIATE SAVINGS (Free):
  • Use Spot instances:                         -60% to -90%
  • Enable KEDA scaling (scale to 0):           -100% when idle
  • Use BASIC_HDD instead of SSD:               -60%
  • Reduce Filestore size (100GB vs 1TB):       -90%

SHORT-TERM SAVINGS:
  • Schedule auto-shutdown (nights/weekends):   -70%
  • Use smaller machine types (e2-medium):      -50%
  • Disable ReSplat (3D) if not needed:         -$730/mo
  • Disable Audio if not needed:                -$100/mo

MONITORING:
  • Set budget alerts at 50%, 80%, 100%
  • Review Cloud Billing dashboard weekly
  • Use gcloud billing budgets list

EMERGENCY STOP:
  make destroy-dev          # Deletes everything in dev
```

---

## 🐛 Error Quick Fix

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                      🔥 COMMON ERRORS & FIXES                                   │
└─────────────────────────────────────────────────────────────────────────────────┘

❌ ImagePullBackOff
   Fix: Check image exists in Artifact Registry
   gcloud artifacts docker images list us-central1-docker.pkg.dev/$GCP_PROJECT_ID/mmp-images

❌ CrashLoopBackOff
   Fix: Check logs for application error
   kubectl logs -n ai-director deployment/ai-director --previous

❌ Pending pods
   Fix: Check node resources
   kubectl describe node

❌ 404 from Load Balancer
   Fix: Wait for health checks (can take 5 min)
   kubectl describe ingress -n ai-director

❌ Pub/Sub permission denied
   Fix: Check Workload Identity binding
   gcloud iam service-accounts list

❌ Filestore mount failed
   Fix: Verify Filestore is in same zone as cluster
   gcloud filestore instances list
```

---

## 📞 Support Resources

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                         📚 USEFUL LINKS                                         │
└─────────────────────────────────────────────────────────────────────────────────┘

Documentation:
  • Full Guide:     /docs/ARCHITECTURE_DIAGRAMS.md
  • Cost Analysis:  /docs/COST_TIERS.md
  • Improvements:   /docs/TUTORIAL_IMPROVEMENTS.md

GCP Console:
  • GKE:      https://console.cloud.google.com/kubernetes/list
  • Pub/Sub:  https://console.cloud.google.com/cloudpubsub/topic/list
  • Billing:  https://console.cloud.google.com/billing/reports
  • Quotas:   https://console.cloud.google.com/iam-admin/quotas

CLI Help:
  • make help          # Show all make targets
  • pulumi --help      # Pulumi CLI help
  • gcloud --help      # gcloud CLI help
```

---

**Print this page and keep it handy during deployment!** 🖨️
