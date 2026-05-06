# MMP Status Badges & Visual Indicators

## README Badge Codes

Add these badges to your README.md for quick visual status:

```markdown
# Status Badges

## Deployment Status
[![MMP](https://img.shields.io/badge/MMP-Live-success?style=for-the-badge&logo=google-cloud)](https://your-domain.com)
[![Environment](https://img.shields.io/badge/Environment-Staging-blue?style=for-the-badge)](https://your-domain.com)
[![Cost](https://img.shields.io/badge/Cost-$150%2Fmo-yellow?style=for-the-badge)](docs/COST_TIERS.md)

## Component Health
[![AI Director](https://img.shields.io/badge/AI%20Director-Healthy-success?style=flat-square&logo=fastapi)](http://your-api/health)
[![ComfyUI](https://img.shields.io/badge/ComfyUI-Scaled%20to%200-inactive?style=flat-square)](docs/ARCHITECTURE_DIAGRAMS.md)
[![Pub/Sub](https://img.shields.io/badge/Pub%2FSub-Active-success?style=flat-square&logo=google-cloud)](https://console.cloud.google.com/cloudpubsub/topic/list)

## Build & Test
[![Build](https://img.shields.io/badge/Build-Passing-success?style=flat-square&logo=github-actions)](https://github.com/your-repo/actions)
[![Tests](https://img.shields.io/badge/Tests-87%25%20passing-yellow?style=flat-square&logo=pytest)](docs/QUICK_REFERENCE.md)
[![Coverage](https://img.shields.io/badge/Coverage-78%25-yellow?style=flat-square&logo=codecov)](docs/QUICK_REFERENCE.md)

## Security
[![Security](https://img.shields.io/badge/Security-Enabled-success?style=flat-square&logo=cloudflare)](docs/ARCHITECTURE_DIAGRAMS.md)
[![WAF](https://img.shields.io/badge/WAF-Active-success?style=flat-square&logo=google-cloud)](docs/ARCHITECTURE_DIAGRAMS.md)
[![Audit](https://img.shields.io/badge/Audit%20Logs-Enabled-success?style=flat-square&logo=google-cloud)](docs/ARCHITECTURE_DIAGRAMS.md)
```

---

## ASCII Status Indicators

Use these in terminal output or documentation:

```
Service Status Indicators:
  🟢 Healthy    - Service running normally
  🟡 Warning    - Service running with issues
  🔴 Critical   - Service down or failed
  ⚪ Standby    - Service scaled to 0 (ready)
  🔄 Loading    - Service starting/stopping
  ❓ Unknown    - Status cannot be determined

Pipeline Stage Status:
  ✅ Complete   - Stage finished successfully
  ⏳ Pending    - Stage waiting to start
  🔄 Active     - Stage currently running
  ❌ Failed     - Stage failed with error
  ⏭️ Skipped    - Stage skipped (optional)

Cost Indicators:
  💰 On Budget  - Within expected cost
  ⚠️ Warning    - Approaching budget limit
  🚨 Over Budget - Exceeded budget threshold
  🎯 Optimized  - Running cost-optimized config
```

---

## Cost Dashboard ASCII

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                         💰 LIVE COST DASHBOARD                                   │
│                         (Update with gcloud CLI)                                 │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                  │
│  CURRENT MONTH: April 2026                                                       │
│  ┌───────────────────────────────────────────────────────────────────────────┐  │
│  │                                                                           │  │
│  │  GKE Cluster       ████████████████████░░░░░░░░░░  $89.45 (60%)          │  │
│  │  Filestore         ████████░░░░░░░░░░░░░░░░░░░░░░  $28.00 (35%)          │  │
│  │  Pub/Sub           ██░░░░░░░░░░░░░░░░░░░░░░░░░░░░  $4.20  (5%)           │  │
│  │  Networking        ████░░░░░░░░░░░░░░░░░░░░░░░░░░  $18.50                │  │
│  │                                                                           │  │
│  │  TOTAL: $140.15 / $200.00 budget (70%)                    🟢 On Budget  │  │
│  │                                                                           │  │
│  └───────────────────────────────────────────────────────────────────────────┘  │
│                                                                                  │
│  PREDICTED MONTHLY: $210.00 (based on current usage)                             │
│                                                                                  │
│  ACTIVE GPU NODES: 0  │  PENDING JOBS: 0  │  IDLE: $0.12/hour                  │
│                                                                                  │
│  Last Updated: 2026-04-12 21:45 UTC                                              │
│                                                                                  │
└─────────────────────────────────────────────────────────────────────────────────┘

To update this dashboard:
  gcloud billing accounts list
  gcloud billing budgets list
```

---

## Service Health Dashboard

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                      🏥 SERVICE HEALTH DASHBOARD                                 │
│                      (View with: kubectl get pods -A)                            │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                  │
│  CORE SERVICES                                                                   │
│  ┌───────────────────────────────────────────────────────────────────────────┐  │
│  │  ai-director      │  🟢 Healthy  │  3/3 pods ready  │  99.9% uptime    │  │
│  │  comfyui          │  ⚪ Standby   │  0/0 pods ready  │  N/A             │  │
│  │  audio-worker     │  🟢 Healthy  │  1/1 pods ready  │  99.5% uptime    │  │
│  │  resplat          │  ⚪ Standby   │  0/0 pods ready  │  N/A             │  │
│  └───────────────────────────────────────────────────────────────────────────┘  │
│                                                                                  │
│  INFRASTRUCTURE                                                                  │
│  ┌───────────────────────────────────────────────────────────────────────────┐  │
│  │  Pub/Sub          │  🟢 Healthy  │  0 lag           │  100% delivery   │  │
│  │  Filestore        │  🟢 Healthy  │  45% used        │  120ms latency   │  │
│  │  Load Balancer    │  🟢 Healthy  │  95% healthy     │  12ms latency    │  │
│  │  GKE Cluster      │  🟢 Healthy  │  3 nodes ready   │  1.35.1          │  │
│  └───────────────────────────────────────────────────────────────────────────┘  │
│                                                                                  │
│  Last Check: 2026-04-12 21:45 UTC                                                │
│                                                                                  │
└─────────────────────────────────────────────────────────────────────────────────┘
```

---

## Pipeline Status Visualization

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                      🔄 ACTIVE PIPELINE JOBS                                     │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                  │
│  Job: fcb2e54c-e4d6-4142-88c7-0a64dab43098                                      │
│  User: test-123                                                                  │
│  Started: 2026-04-12 21:43:12 UTC                                                │
│  Duration: 32 seconds                                                            │
│                                                                                  │
│  Progress:                                                                       │
│  ┌───────────────────────────────────────────────────────────────────────────┐  │
│  │  Intake          ✅ Complete     50ms                                     │  │
│  │  2D Drafts       ✅ Complete     8.2s    [████] 4 drafts                  │  │
│  │  Evaluation      ✅ Complete     180ms   Selected draft #3                │  │
│  │  Upscale         ✅ Complete     4.8s    [██████████] 2048x2048           │  │
│  │  3D Generation   ✅ Complete     12.5s   [████████████] .ply file         │  │
│  │  Audio           ✅ Complete     3.9s    [██████] mp3 generated           │  │
│  │  Mint            ⏭️ Skipped      (user opted out)                        │  │
│  │                                                                           │  │
│  │  [████████████████████████████████████████] 100% Complete                 │  │
│  └───────────────────────────────────────────────────────────────────────────┘  │
│                                                                                  │
│  Result:                                                                         │
│  • 2D Image: https://storage.../upscaled.png                                     │
│  • 3D Asset: https://storage.../character.ply                                    │
│  • Audio: https://storage.../soundscape.mp3                                      │
│                                                                                  │
└─────────────────────────────────────────────────────────────────────────────────┘
```

---

## Deployment Timeline

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                      📅 DEPLOYMENT TIMELINE                                      │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                  │
│  Max Mini (dev) Deployment:                                                      │
│  ┌───────────────────────────────────────────────────────────────────────────┐  │
│  │  00:00  Start           make deploy-dev                                    │  │
│  │  00:30  ✓ Prerequisites validated                                          │  │
│  │  02:00  ✓ GKE Cluster creating...                                          │  │
│  │  08:00  ✓ GKE Cluster ready                                                │  │
│  │  10:00  ✓ Filestore provisioning...                                        │  │
│  │  12:00  ✓ Pub/Sub topics created                                           │  │
│  │  14:00  ✓ Load balancer configuring...                                     │  │
│  │  17:00  ✓ Health checks passing                                            │  │
│  │  20:00  🎉 DEPLOYMENT COMPLETE                                             │  │
│  │                                                                           │  │
│  │  Total Time: ~20 minutes                                                   │  │
│  └───────────────────────────────────────────────────────────────────────────┘  │
│                                                                                  │
│  First Request Latency: 32 seconds (cold start)                                  │
│  Subsequent Requests: ~8 seconds (warm)                                          │
│                                                                                  │
└─────────────────────────────────────────────────────────────────────────────────┘
```

---

## Emoji Quick Reference

```
Category              Icons
────────────────────────────────────────────────────────────────
Cloud Services        ☁️ 🌩️ 🖥️ 🗄️ 📊
Status                ✅ ❌ ⚠️ 🔴 🟢 🟡 🔵
Actions               🚀 🔧 📝 📋 🧹 🧪
Money                 💰 💵 💸 🏦
Security              🔒 🔐 🛡️ 🔑
Time                  ⏱️ ⏰ 🕐 📅
Communication         📡 📶 📞 📧
Data                  📁 💾 📀 🔢
AI/ML                 🤖 🧠 🎨 🎭
Gaming                🎮 🎯 🏆 🎲
```

---

## ASCII Progress Bars

```python
# For use in CLI tools or scripts

def print_progress(current, total, width=40):
    """Print ASCII progress bar."""
    filled = int(width * current / total)
    bar = '█' * filled + '░' * (width - filled)
    pct = int(100 * current / total)
    print(f'\r|{bar}| {pct}% ({current}/{total})', end='', flush=True)

# Example usage:
# for i in range(101):
#     print_progress(i, 100)
#     time.sleep(0.1)
# print()  # New line when done
```

Output:
```
|████████████████████████████████████████| 100% (100/100)
```

---

## Terminal Color Codes

```bash
# For colored terminal output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${GREEN}✓ Success${NC}"
echo -e "${RED}✗ Failed${NC}"
echo -e "${YELLOW}⚠ Warning${NC}"
echo -e "${BLUE}ℹ Info${NC}"
```

---

**Use these visuals to make your tutorial more engaging and easier to scan!** 🎨
