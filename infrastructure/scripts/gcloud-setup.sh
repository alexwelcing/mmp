#!/usr/bin/env bash
# gcloud-setup.sh — Pre-deployment GCP configuration for MMP
#
# Usage:
#   export GCP_PROJECT_ID=your-project-id
#   export GCP_BILLING_ACCOUNT=XXXXXX-XXXXXX-XXXXXX
#   ./gcloud-setup.sh

set -euo pipefail

# Configuration
PROJECT_ID="${GCP_PROJECT_ID:-}"
BILLING_ACCOUNT="${GCP_BILLING_ACCOUNT:-}"
REGION="${GCP_REGION:-us-central1}"
ZONE="${GCP_ZONE:-us-central1-a}"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Validate required variables
if [[ -z "$PROJECT_ID" ]]; then
    log_error "GCP_PROJECT_ID is not set. Please export it first:"
    echo "  export GCP_PROJECT_ID=your-project-id"
    exit 1
fi

# Check gcloud is installed
if ! command -v gcloud &> /dev/null; then
    log_error "gcloud CLI is not installed. Please install it first:"
    echo "  https://cloud.google.com/sdk/docs/install"
    exit 1
fi

log_info "Starting GCP setup for project: $PROJECT_ID"

# Step 1: Set project
log_info "Setting active project..."
gcloud config set project "$PROJECT_ID"

# Step 2: Verify billing is enabled
log_info "Checking billing status..."
if ! gcloud billing projects describe "$PROJECT_ID" &> /dev/null; then
    log_error "Billing is not enabled for project $PROJECT_ID"
    echo "Please enable billing at: https://console.cloud.google.com/billing"
    exit 1
fi
log_info "Billing is enabled ✓"

# Step 3: Enable required APIs
log_info "Enabling required GCP APIs (this may take a few minutes)..."

APIS=(
    "compute.googleapis.com"
    "container.googleapis.com"
    "file.googleapis.com"
    "pubsub.googleapis.com"
    "artifactregistry.googleapis.com"
    "monitoring.googleapis.com"
    "logging.googleapis.com"
    "cloudbuild.googleapis.com"
    "cloudarmor.googleapis.com"
    "secretmanager.googleapis.com"
    "cloudasset.googleapis.com"
    "billingbudgets.googleapis.com"
)

for api in "${APIS[@]}"; do
    log_info "  Enabling $api..."
    gcloud services enable "$api" --project "$PROJECT_ID" || {
        log_warn "Failed to enable $api, continuing..."
    }
done

log_info "All APIs enabled ✓"

# Step 4: Check quotas
log_info "Checking resource quotas..."

QUOTAS=(
    "CPUS:100"
    "NVIDIA_T4_GPUS:10"
    "IN_USE_ADDRESSES:50"
    "FILESTORE_INSTANCES:5"
    "DISKS_TOTAL_GB:10000"
)

for quota_spec in "${QUOTAS[@]}"; do
    IFS=':' read -r metric limit <<< "$quota_spec"
    current=$(gcloud compute project-info describe --project "$PROJECT_ID" --format="json" 2>/dev/null | \
        jq -r ".quotas[] | select(.metric==\"$metric\") | .limit" 2>/dev/null || echo "0")
    
    if [[ "$current" == "0" || -z "$current" ]]; then
        log_warn "Quota for $metric not found or zero. You may need to request an increase."
    elif [[ "${current%.*}" -lt "$limit" ]]; then
        log_warn "$metric quota is $current, recommended minimum is $limit"
        echo "  Request increase at: https://console.cloud.google.com/iam-admin/quotas"
    else
        log_info "  $metric: $current ✓"
    fi
done

# Step 5: Create Artifact Registry
log_info "Creating Artifact Registry repository..."
if ! gcloud artifacts repositories describe mmp-images --location="$REGION" &> /dev/null; then
    gcloud artifacts repositories create mmp-images \
        --repository-format=docker \
        --location="$REGION" \
        --description="MMP service images" \
        --project "$PROJECT_ID"
    log_info "Artifact Registry created ✓"
else
    log_info "Artifact Registry already exists ✓"
fi

# Step 6: Configure Docker authentication
log_info "Configuring Docker authentication..."
gcloud auth configure-docker "${REGION}-docker.pkg.dev" --quiet

# Step 7: Create service account for CI/CD (optional)
log_info "Setting up deployment service account..."
SA_NAME="mmp-deployer"
SA_EMAIL="${SA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"

if ! gcloud iam service-accounts describe "$SA_EMAIL" &> /dev/null; then
    gcloud iam service-accounts create "$SA_NAME" \
        --display-name="MMP Deployment Service Account" \
        --project "$PROJECT_ID"
    log_info "Service account created ✓"
else
    log_info "Service account already exists ✓"
fi

# Grant necessary roles
ROLES=(
    "roles/compute.admin"
    "roles/container.admin"
    "roles/file.editor"
    "roles/pubsub.admin"
    "roles/resourcemanager.projectIamAdmin"
    "roles/iam.serviceAccountAdmin"
    "roles/artifactregistry.admin"
    "roles/monitoring.admin"
    "roles/logging.admin"
    "roles/secretmanager.admin"
)

for role in "${ROLES[@]}"; do
    gcloud projects add-iam-policy-binding "$PROJECT_ID" \
        --member="serviceAccount:${SA_EMAIL}" \
        --role="$role" \
        --condition=None \
        --quiet > /dev/null
done

log_info "Service account permissions granted ✓"

# Step 8: Create and download service account key (for Pulumi)
KEY_FILE="mmp-deployer-key.json"
if [[ ! -f "$KEY_FILE" ]]; then
    log_info "Creating service account key..."
    gcloud iam service-accounts keys create "$KEY_FILE" \
        --iam-account="$SA_EMAIL" \
        --project "$PROJECT_ID"
    log_info "Key saved to $KEY_FILE"
    log_warn "Keep this key secure! Do not commit it to git."
else
    log_info "Service account key already exists: $KEY_FILE"
fi

# Step 9: Set up budget alert (if billing account is provided)
if [[ -n "$BILLING_ACCOUNT" ]]; then
    log_info "Setting up budget alert..."
    
    # Note: Budget creation via gcloud is limited, recommend console for full setup
    log_warn "Please create budget alert manually in Cloud Console:"
    echo "  https://console.cloud.google.com/billing/budgets"
    echo "  Recommended: $1000/month with 50%, 80%, 100% thresholds"
else
    log_warn "GCP_BILLING_ACCOUNT not set. Skipping budget setup."
    echo "  To set up budget alerts, visit:"
    echo "  https://console.cloud.google.com/billing/budgets"
fi

# Step 10: Summary
log_info "=========================================="
log_info "GCP Setup Complete!"
log_info "=========================================="
echo ""
echo "Project: $PROJECT_ID"
echo "Region: $REGION"
echo "Zone: $ZONE"
echo ""
echo "Next steps:"
echo "  1. Set the service account key environment variable:"
echo "     export GOOGLE_APPLICATION_CREDENTIALS=$(pwd)/$KEY_FILE"
echo ""
echo "  2. Build and push Docker images:"
echo "     ./infrastructure/scripts/build-images.sh"
echo ""
echo "  3. Deploy with Pulumi:"
echo "     cd infrastructure/pulumi"
echo "     pulumi stack init staging"
echo "     pulumi config set project_id $PROJECT_ID"
echo "     pulumi up"
echo ""
echo "  4. For local development, set:"
echo "     export GCP_PROJECT_ID=$PROJECT_ID"
echo ""

# Export variables for the current shell
echo "# Run these commands in your current shell:"
echo "export GCP_PROJECT_ID=$PROJECT_ID"
echo "export GOOGLE_APPLICATION_CREDENTIALS=$(pwd)/$KEY_FILE"
