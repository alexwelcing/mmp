#!/usr/bin/env bash
# build-images.sh — Build and push all MMP service images
#
# Usage:
#   export GCP_PROJECT_ID=your-project-id
#   ./build-images.sh

set -euo pipefail

PROJECT_ID="${GCP_PROJECT_ID:-}"
REGION="${GCP_REGION:-us-central1}"
REGISTRY="${REGION}-docker.pkg.dev/${PROJECT_ID}/mmp-images"

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

if [[ -z "$PROJECT_ID" ]]; then
    echo "Error: GCP_PROJECT_ID is not set"
    echo "  export GCP_PROJECT_ID=your-project-id"
    exit 1
fi

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$(dirname "$SCRIPT_DIR")")"

cd "$PROJECT_ROOT"

log_info "Building MMP images for project: $PROJECT_ID"
log_info "Registry: $REGISTRY"
echo ""

# Ensure we're authenticated
log_info "Verifying Docker authentication..."
gcloud auth configure-docker "${REGION}-docker.pkg.dev" --quiet

# Build AI Director
log_info "Building ai-director..."
docker build \
    -t "${REGISTRY}/ai-director:latest" \
    -t "${REGISTRY}/ai-director:$(date +%Y%m%d-%H%M%S)" \
    -f services/ai-director/Dockerfile \
    services/ai-director
docker push "${REGISTRY}/ai-director:latest"
log_info "ai-director pushed ✓"

# Build ComfyUI Worker (this is large and takes time)
log_warn "Building comfyui-worker (this may take 10-15 minutes)..."
docker build \
    -t "${REGISTRY}/comfyui-worker:latest" \
    -t "${REGISTRY}/comfyui-worker:$(date +%Y%m%d-%H%M%S)" \
    -f services/comfyui-worker/Dockerfile \
    services/comfyui-worker
docker push "${REGISTRY}/comfyui-worker:latest"
log_info "comfyui-worker pushed ✓"

# Build Audio Worker
log_info "Building audio-worker..."
docker build \
    -t "${REGISTRY}/audio-worker:latest" \
    -t "${REGISTRY}/audio-worker:$(date +%Y%m%d-%H%M%S)" \
    -f services/audio-worker/Dockerfile \
    services/audio-worker
docker push "${REGISTRY}/audio-worker:latest"
log_info "audio-worker pushed ✓"

# Build ReSplat Worker (optional)
log_info "Building resplat-worker..."
docker build \
    -t "${REGISTRY}/resplat-worker:latest" \
    -t "${REGISTRY}/resplat-worker:$(date +%Y%m%d-%H%M%S)" \
    -f services/resplat-worker/Dockerfile \
    services/resplat-worker
docker push "${REGISTRY}/resplat-worker:latest"
log_info "resplat-worker pushed ✓"

echo ""
log_info "All images built and pushed successfully!"
echo ""
echo "Available images:"
gcloud artifacts docker images list "${REGISTRY}" --format="table(tags,digest,updateTime)" || true
