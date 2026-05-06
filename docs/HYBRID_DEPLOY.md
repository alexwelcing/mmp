# Hybrid Deployment: GCP + Hugging Face

## 🎯 The 85% Cheaper Architecture

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                    HYBRID: Cheap GCP + Free* Hugging Face                        │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                  │
│  GCP Control Plane ($20-40/mo)          Hugging Face Inference (FREE with Pro)   │
│  ┌─────────────────────────────────┐    ┌─────────────────────────────────────┐  │
│  │ • Cloud Run (AI Director)       │    │ • SDXL (image generation)          │  │
│  │ • Pub/Sub (queue)               │───▶│ • Upscalers (4x quality)           │  │
│  │ • Filestore 50GB (cache)        │    │ • AudioGen (sound)                 │  │
│  │ • Cloud Storage (frontend)      │    │ • 1000+ models available           │  │
│  └─────────────────────────────────┘    └─────────────────────────────────────┘  │
│                                                                                  │
│  Smart Contracts (Base Sepolia)                                                  │
│  ┌─────────────────────────────────┐                                             │
│  │ • CharacterNFT (ERC-721)        │                                             │
│  │ • Gasless minting (ERC-4337)    │                                             │
│  └─────────────────────────────────┘                                             │
│                                                                                  │
└─────────────────────────────────────────────────────────────────────────────────┘

* With Hugging Face Pro: $9/mo = unlimited inference
  Without Pro: ~$0.001-0.01 per generation (still cheap!)
```

## 💰 Cost Comparison

| Component | Full GCP | Hybrid | Savings |
|-----------|----------|--------|---------|
| **GPU Nodes** | $150-300/mo | **$0** | 100% |
| **AI Inference** | Free (self-hosted) | $9/mo (HF Pro) | - |
| **Control Plane** | $100/mo | $20-40/mo | 70% |
| **Frontend** | $18/mo | $0 (Vercel) | 100% |
| **TOTAL** | **~$300-400/mo** | **~$30-50/mo** | **90%** |

## 🚀 Quick Deploy

### Step 1: Get Hugging Face Token

```bash
# 1. Sign up at https://huggingface.co
# 2. Get Pro subscription ($9/mo) for unlimited inference
# 3. Create token at https://huggingface.co/settings/tokens

export HF_TOKEN=hf_...your_token...
```

### Step 2: Deploy GCP Infrastructure

```bash
cd infrastructure/pulumi

# Select hybrid stack
pulumi stack init hybrid
pulumi config set project_id $GCP_PROJECT_ID
pulumi config set environment dev

# Set HF token (encrypted)
pulumi config set --secret hf_token $HF_TOKEN

# Deploy (no GPUs!)
pulumi up --yes
```

### Step 3: Deploy Frontend

```bash
cd frontend
npm run build

# Option A: Vercel (free)
vercel --prod

# Option B: Cloud Storage
# Upload build/ to GCS bucket
```

### Step 4: Deploy Contracts

```bash
cd contracts
npx hardhat run scripts/deploy.ts --network base-sepolia

# Update AI Director with contract addresses
pulumi config set character_nft_address 0x...
```

## 🔧 Configuration

### Environment Variables (AI Director)

```bash
# Required
export HF_TOKEN=hf_...your_token...
export GCP_PROJECT_ID=your-project
export PUBSUB_TOPIC=asset-generation-requests-dev

# Optional (with defaults)
export AI_PROVIDER=huggingface  # or "mock" for testing
export HF_MODEL_SD=stabilityai/stable-diffusion-xl-base-1.0
export HF_MODEL_UPSCALER=stabilityai/stable-diffusion-x4-upscaler
export HF_MODEL_AUDIO=facebook/audiogen-medium
```

### Pulumi Config

```yaml
# Pulumi.hybrid.yaml
config:
  mmp:use_huggingface: "true"
  mmp:ai_provider: "huggingface"
  mmp:use_cloud_run: "true"  # Instead of GKE
  mmp:filestore_capacity_gb: "50"
```

## 🧪 Testing

```bash
# Test HF integration directly
python -c "
from agents.huggingface_agent import HuggingFaceAgent
import asyncio

agent = HuggingFaceAgent()
async def test():
    images = await agent.generate_drafts('warrior character', count=1)
    print(f'Generated {len(images)} images')
    
asyncio.run(test())
"

# Test via API
curl -X POST http://your-api/generate \
  -H "Content-Type: application/json" \
  -d '{"user_id":"test","prompt":"wizard"}'
```

## 📊 Monitoring

### HF API Usage
```bash
# Check rate limits
curl https://api-inference.huggingface.co/status \
  -H "Authorization: Bearer $HF_TOKEN"
```

### GCP Costs
```bash
# Cloud Run metrics
gcloud monitoring metrics list | grep run

# Pub/Sub metrics
gcloud pubsub subscriptions pull asset-generation-requests-sub-dev
```

## 🎨 Available Models

| Task | Model | Speed | Quality |
|------|-------|-------|---------|
| 2D Generation | `stabilityai/stable-diffusion-xl-base-1.0` | Medium | ⭐⭐⭐⭐⭐ |
| 2D Fast | `runwayml/stable-diffusion-v1-5` | Fast | ⭐⭐⭐⭐ |
| Upscaling | `stabilityai/stable-diffusion-x4-upscaler` | Slow | ⭐⭐⭐⭐⭐ |
| Image Edit | `timbrooks/instruct-pix2pix` | Medium | ⭐⭐⭐⭐ |
| Audio | `facebook/audiogen-medium` | Fast | ⭐⭐⭐⭐ |
| Voice | `suno/bark` | Medium | ⭐⭐⭐⭐⭐ |

## 🔒 Security

1. **Token Storage**: Use GCP Secret Manager or Pulumi secrets
2. **Rate Limiting**: Implement per-user limits in AI Director
3. **CORS**: Restrict to your frontend domain
4. **Audit**: Log all generation requests

## 🆘 Troubleshooting

| Issue | Solution |
|-------|----------|
| `401 Unauthorized` | Check HF_TOKEN is valid |
| `503 Model loading` | Model warming up, retry in 30s |
| Slow generation | HF Pro has priority queues |
| Out of credits | Upgrade to HF Pro ($9/mo) |

## 🎯 Next Steps

1. ✅ Test HF integration locally
2. ✅ Deploy hybrid infrastructure
3. ✅ Mint first NFT
4. 🔄 Optimize model selection based on quality/speed needs

**Ready to deploy the 90% cheaper architecture?** 🚀
