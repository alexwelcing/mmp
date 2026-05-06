#!/bin/bash
#
# Deploy AI Director with Hugging Face provider
# Usage: ./deploy_hf.sh [tag]
#

set -e

TAG="${1:-hf}"
PROJECT_ID="endlesse"
REGION="us-central1"
REGISTRY="${REGION}-docker.pkg.dev/${PROJECT_ID}/mmp"
IMAGE="${REGISTRY}/ai-director:${TAG}"

echo "=========================================="
echo "Deploying AI Director with HF Provider"
echo "=========================================="
echo "Image: ${IMAGE}"
echo ""

# Step 1: Build Docker image
echo "Step 1: Building Docker image..."
cd services/ai-director
docker build -t "${IMAGE}" .
echo "✓ Build complete"
echo ""

# Step 2: Push to GCR
echo "Step 2: Pushing to GCR..."
docker push "${IMAGE}"
echo "✓ Push complete"
echo ""

# Step 3: Update deployment image
echo "Step 3: Updating Kubernetes deployment..."
kubectl set image deployment/ai-director ai-director="${IMAGE}" -n ai-director
echo "✓ Deployment updated"
echo ""

# Step 4: Wait for rollout
echo "Step 4: Waiting for rollout..."
kubectl rollout status deployment/ai-director -n ai-director --timeout=120s
echo "✓ Rollout complete"
echo ""

# Step 5: Verify health
echo "Step 5: Verifying health..."
sleep 5
kubectl get pods -n ai-director -l app=ai-director

echo ""
echo "=========================================="
echo "Deployment complete!"
echo "=========================================="
echo ""
echo "Test the API:"
echo "  curl http://34.8.224.143/health"
echo ""
echo "Generate a character:"
echo "  curl -X POST http://34.8.224.143/generate \\"
echo "    -H 'Content-Type: application/json' \\"
echo "    -d '{\"user_id\":\"test\",\"preferences\":{\"role\":\"warrior\"}}'"
echo ""
echo "Run batch mint:"
echo "  pip install httpx"
echo "  python scripts/batch_mint.py"
