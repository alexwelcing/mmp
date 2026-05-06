#!/usr/bin/env bash
# deploy-hybrid.sh - Deploy hybrid architecture (GCP + Hugging Face)
# Usage: export HF_TOKEN=hf_... && ./deploy-hybrid.sh

set -e

echo "🚀 Deploying Hybrid Architecture (GCP + Hugging Face)"
echo "======================================================"

# Check HF_TOKEN is set
if [[ -z "${HF_TOKEN:-}" ]]; then
    echo "❌ Error: HF_TOKEN not set"
    echo "Run: export HF_TOKEN=hf_..."
    exit 1
fi

echo "✓ HF_TOKEN is set"

# Check GCP_PROJECT_ID
if [[ -z "${GCP_PROJECT_ID:-}" ]]; then
    echo "❌ Error: GCP_PROJECT_ID not set"
    echo "Run: export GCP_PROJECT_ID=your-project"
    exit 1
fi

echo "✓ GCP_PROJECT_ID: $GCP_PROJECT_ID"

# Navigate to pulumi
cd "$(dirname "$0")/infrastructure/pulumi"

echo ""
echo "🔧 Configuring Pulumi stack..."

# Select or create stack
pulumi stack select hybrid --create 2>/dev/null || pulumi stack select hybrid

# Set required configs
pulumi config set project_id "$GCP_PROJECT_ID"
pulumi config set environment dev
pulumi config set use_huggingface "true"
pulumi config set ai_provider "huggingface"
pulumi config set use_cloud_run "true"
pulumi config set filestore_capacity_gb "50"
pulumi config set enable_resplat "false"
pulumi config set enable_audio "true"

# Set encrypted secret
echo "🔐 Storing HF token (encrypted)..."
pulumi config set --secret hf_token "$HF_TOKEN"

echo ""
echo "📦 Deploying infrastructure..."
echo "This will create:"
echo "  • Cloud Run service (AI Director)"
echo "  • Pub/Sub topics"
echo "  • Filestore (50GB)"
echo "  • NO GPU nodes (using Hugging Face instead)"
echo ""
echo "Estimated cost: ~$30-50/mo"
echo ""

# Deploy
pulumi up --yes

echo ""
echo "======================================================"
echo "✅ Deployment Complete!"
echo "======================================================"
echo ""
echo "Get the API URL:"
echo "  pulumi stack output serviceUrl"
echo ""
echo "Test the API:"
echo "  curl \$(pulumi stack output serviceUrl)/health"
echo ""
