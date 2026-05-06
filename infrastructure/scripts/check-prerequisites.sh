#!/usr/bin/env bash
# check-prerequisites.sh — Validate prerequisites before MMP deployment
#
# Usage:
#   export GCP_PROJECT_ID=your-project-id
#   ./check-prerequisites.sh

set -euo pipefail

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

PASS=0
WARN=0
FAIL=0

check_pass() {
    echo -e "${GREEN}✓${NC} $1"
    ((PASS++))
}

check_warn() {
    echo -e "${YELLOW}⚠${NC} $1"
    ((WARN++))
}

check_fail() {
    echo -e "${RED}✗${NC} $1"
    ((FAIL++))
}

echo "=========================================="
echo "MMP Deployment Prerequisites Check"
echo "=========================================="
echo ""

# Check 1: gcloud installed
if command -v gcloud &> /dev/null; then
    VERSION=$(gcloud --version | head -1)
    check_pass "gcloud installed: $VERSION"
else
    check_fail "gcloud not installed. Install: https://cloud.google.com/sdk/docs/install"
fi

# Check 2: Pulumi installed
if command -v pulumi &> /dev/null; then
    VERSION=$(pulumi version)
    check_pass "Pulumi installed: $VERSION"
else
    check_fail "Pulumi not installed. Install: https://www.pulumi.com/docs/install/"
fi

# Check 3: Docker installed
if command -v docker &> /dev/null; then
    VERSION=$(docker --version)
    check_pass "Docker installed: $VERSION"
else
    check_fail "Docker not installed"
fi

# Check 4: GCP_PROJECT_ID set
if [[ -n "${GCP_PROJECT_ID:-}" ]]; then
    check_pass "GCP_PROJECT_ID set: $GCP_PROJECT_ID"
else
    check_fail "GCP_PROJECT_ID not set. Run: export GCP_PROJECT_ID=your-project-id"
fi

# Check 5: gcloud authentication
echo ""
echo "Checking GCP authentication..."
if gcloud auth list --filter=status:ACTIVE --format="value(account)" 2>/dev/null | grep -q "@"; then
    ACCOUNT=$(gcloud auth list --filter=status:ACTIVE --format="value(account)" 2>/dev/null | head -1)
    check_pass "Authenticated as: $ACCOUNT"
else
    check_fail "Not authenticated. Run: gcloud auth login"
fi

# Check 6: Project exists and billing enabled
if [[ -n "${GCP_PROJECT_ID:-}" ]]; then
    echo ""
    echo "Checking GCP project..."
    if gcloud projects describe "$GCP_PROJECT_ID" &>/dev/null; then
        check_pass "Project exists: $GCP_PROJECT_ID"
        
        # Check billing
        if gcloud billing projects describe "$GCP_PROJECT_ID" 2>/dev/null | grep -q "billingEnabled: true"; then
            check_pass "Billing enabled"
        else
            check_fail "Billing not enabled for project"
        fi
    else
        check_fail "Project not found: $GCP_PROJECT_ID"
    fi
fi

# Check 7: Required APIs enabled
if [[ -n "${GCP_PROJECT_ID:-}" ]]; then
    echo ""
    echo "Checking required GCP APIs..."
    
    REQUIRED_APIS=(
        "compute.googleapis.com"
        "container.googleapis.com"
        "file.googleapis.com"
        "pubsub.googleapis.com"
        "artifactregistry.googleapis.com"
        "monitoring.googleapis.com"
        "logging.googleapis.com"
    )
    
    for api in "${REQUIRED_APIS[@]}"; do
        if gcloud services list --project="$GCP_PROJECT_ID" --enabled 2>/dev/null | grep -q "$api"; then
            check_pass "API enabled: $api"
        else
            check_warn "API not enabled: $api (will be enabled during deploy)"
        fi
    done
fi

# Check 8: Quota check
if [[ -n "${GCP_PROJECT_ID:-}" ]]; then
    echo ""
    echo "Checking GCP quotas..."
    
    # Check CPU quota
    CPU_QUOTA=$(gcloud compute project-info describe --project="$GCP_PROJECT_ID" --format="json" 2>/dev/null | \
        python3 -c "import sys,json; d=json.load(sys.stdin); print([q for q in d.get('quotas',[]) if q['metric']=='CPUS'][0]['limit'])" 2>/dev/null || echo "0")
    if [[ "${CPU_QUOTA%.*}" -ge 50 ]]; then
        check_pass "CPU quota: $CPU_QUOTA (>= 50 recommended)"
    else
        check_warn "CPU quota low: $CPU_QUOTA (50+ recommended)"
    fi
    
    # Check GPU quota
    GPU_QUOTA=$(gcloud compute project-info describe --project="$GCP_PROJECT_ID" --format="json" 2>/dev/null | \
        python3 -c "import sys,json; d=json.load(sys.stdin); g=[q for q in d.get('quotas',[]) if 'NVIDIA_T4' in q['metric']]; print(g[0]['limit'] if g else '0')" 2>/dev/null || echo "0")
    if [[ "${GPU_QUOTA%.*}" -ge 4 ]]; then
        check_pass "T4 GPU quota: $GPU_QUOTA (>= 4 recommended)"
    else
        check_warn "T4 GPU quota low: $GPU_QUOTA (4+ recommended). Request increase: https://console.cloud.google.com/iam-admin/quotas"
    fi
fi

# Check 9: Service account key
if [[ -n "${GOOGLE_APPLICATION_CREDENTIALS:-}" ]]; then
    if [[ -f "$GOOGLE_APPLICATION_CREDENTIALS" ]]; then
        check_pass "Service account key exists: $GOOGLE_APPLICATION_CREDENTIALS"
    else
        check_fail "Service account key not found: $GOOGLE_APPLICATION_CREDENTIALS"
    fi
else
    check_warn "GOOGLE_APPLICATION_CREDENTIALS not set (will be created during setup)"
fi

# Check 10: Pulumi config
if [[ -f "infrastructure/pulumi/Pulumi.$(pulumi stack current 2>/dev/null || echo 'dev').yaml" ]]; then
    check_pass "Pulumi stack config exists"
else
    check_warn "Pulumi stack config not found (will use defaults)"
fi

# Summary
echo ""
echo "=========================================="
echo "Summary"
echo "=========================================="
echo -e "${GREEN}Passed: $PASS${NC}"
echo -e "${YELLOW}Warnings: $WARN${NC}"
echo -e "${RED}Failed: $FAIL${NC}"
echo ""

if [[ $FAIL -gt 0 ]]; then
    echo -e "${RED}Please fix the failed checks before deploying.${NC}"
    exit 1
elif [[ $WARN -gt 0 ]]; then
    echo -e "${YELLOW}Deployment may proceed with warnings.${NC}"
    exit 0
else
    echo -e "${GREEN}All checks passed! Ready to deploy.${NC}"
    exit 0
fi
