# MMP (Autonomous AI Director) — Development Makefile
# 
# Quick Start:
#   make check          # Verify prerequisites
#   make deploy-dev     # Deploy to dev environment
#   make test-api       # Test the API endpoint

.PHONY: help check setup deploy-dev deploy-staging destroy-dev test-api logs clean

# Default target
help:
	@echo "MMP Development Commands"
	@echo "========================"
	@echo ""
	@echo "Setup:"
	@echo "  make check              Verify prerequisites"
	@echo "  make setup              Run gcloud setup script"
	@echo ""
	@echo "Deploy:"
	@echo "  make deploy-dev         Deploy to dev (Max Mini tier, ~$50/mo)"
	@echo "  make deploy-staging     Deploy to staging (Standard Dev tier, ~$150/mo)"
	@echo "  make deploy-prod        Deploy to production"
	@echo ""
	@echo "Test & Debug:"
	@echo "  make test-api           Test API health endpoint"
	@echo "  make logs               Follow AI Director logs"
	@echo "  make kubeconfig         Configure kubectl access"
	@echo ""
	@echo "Cleanup:"
	@echo "  make destroy-dev        Destroy dev environment"
	@echo "  make clean              Remove build artifacts"
	@echo ""

# Verify prerequisites
check:
	@echo "Checking prerequisites..."
	@./infrastructure/scripts/check-prerequisites.sh

# Initial setup
setup: check
	@echo "Running gcloud setup..."
	@./infrastructure/scripts/gcloud-setup.sh

# Build and push images
build-images:
	@echo "Building Docker images..."
	@./infrastructure/scripts/build-images.sh

# Configure kubectl
kubeconfig:
	@echo "Configuring kubectl..."
	@gcloud container clusters get-credentials mmp-cluster --region=us-central1 --project=$(GCP_PROJECT_ID)
	@echo "kubectl configured. Test with: kubectl get nodes"

# Deploy to dev (Max Mini tier - minimal cost)
deploy-dev: check
	@echo "Deploying to DEV (Max Mini tier, ~$50/mo)..."
	@cd infrastructure/pulumi && \
	pulumi stack select dev --create 2>/dev/null || true && \
	pulumi config set environment dev && \
	pulumi config set filestore_capacity_gb 100 && \
	pulumi config set enable_resplat false && \
	pulumi config set enable_audio false && \
	pulumi config set use_spot_system_pool true && \
	pulumi up --yes
	@echo ""
	@echo "Deployment complete! Get the load balancer IP:"
	@echo "  make get-ip"

# Deploy to staging (Standard Dev tier)
deploy-staging: check
	@echo "Deploying to STAGING (Standard Dev tier, ~$150/mo)..."
	@cd infrastructure/pulumi && \
	pulumi stack select staging --create 2>/dev/null || true && \
	pulumi config set environment staging && \
	pulumi config set filestore_capacity_gb 1024 && \
	pulumi config set enable_resplat true && \
	pulumi config set enable_audio true && \
	pulumi config set use_spot_system_pool true && \
	pulumi up --yes
	@echo ""
	@echo "Deployment complete! Get the load balancer IP:"
	@echo "  make get-ip"

# Deploy to production
deploy-prod: check
	@echo "Deploying to PRODUCTION (~$285/mo)..."
	@cd infrastructure/pulumi && \
	pulumi stack select production --create 2>/dev/null || true && \
	pulumi config set environment production && \
	pulumi config set filestore_capacity_gb 1024 && \
	pulumi config set enable_resplat true && \
	pulumi config set enable_audio true && \
	pulumi config set use_spot_system_pool false && \
	pulumi up --yes

# Get the load balancer IP
get-ip:
	@cd infrastructure/pulumi && \
	IP=$$(pulumi stack output lb_ip 2>/dev/null || kubectl get ingress ai-director -n ai-director -o jsonpath='{.status.loadBalancer.ingress[0].ip}' 2>/dev/null || echo "pending"); \
	echo "Load Balancer IP: http://$$IP"

# Test API endpoint
test-api:
	@cd infrastructure/pulumi && \
	IP=$$(kubectl get ingress ai-director -n ai-director -o jsonpath='{.status.loadBalancer.ingress[0].ip}' 2>/dev/null || echo ""); \
	if [[ -n "$$IP" ]]; then \
		echo "Testing API at http://$$IP..."; \
		curl -s -H "Host: api.endlesse.dev" http://$$IP/health || echo "Failed to connect"; \
	else \
		echo "Load balancer IP not found. Wait for deployment to complete: make get-ip"; \
	fi

# Follow AI Director logs
logs:
	@kubectl logs -f -n ai-director deployment/ai-director --tail=50

# Port forward for local testing
port-forward:
	@echo "Port forwarding AI Director to localhost:8080..."
	@kubectl port-forward -n ai-director svc/ai-director 8080:8080

# Generate character
test-generate:
	@cd infrastructure/pulumi && \
	IP=$$(kubectl get ingress ai-director -n ai-director -o jsonpath='{.status.loadBalancer.ingress[0].ip}' 2>/dev/null); \
	curl -X POST -H "Host: api.endlesse.dev" -H "Content-Type: application/json" \
		-d '{"user_id":"test-123","preferences":{"role":"warrior"},"mint_on_chain":false}' \
		http://$$IP/generate 2>/dev/null || echo "Failed to connect"

# Destroy dev environment
destroy-dev:
	@echo "WARNING: This will destroy the dev environment and all data!"
	@read -p "Are you sure? [y/N] " -n 1 -r; \
	echo; \
	if [[ $$REPLY =~ ^[Yy]$$ ]]; then \
		cd infrastructure/pulumi && pulumi stack select dev && pulumi destroy --yes; \
	else \
		echo "Cancelled."; \
	fi

# Quick deploy for development (skip builds)
quick-deploy:
	@cd infrastructure/pulumi && pulumi up --yes

# Refresh Pulumi state from cloud
refresh:
	@cd infrastructure/pulumi && pulumi refresh --yes

# Show Pulumi stack outputs
outputs:
	@cd infrastructure/pulumi && pulumi stack output

# Clean build artifacts
clean:
	@find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	@find . -type f -name "*.pyc" -delete 2>/dev/null || true
	@rm -rf infrastructure/pulumi/venv infrastructure/pulumi/__pycache__
	@echo "Cleaned build artifacts"

# Lint Python code
lint:
	@cd services/ai-director && ruff check .
	@mypy services/ai-director

# Run tests
test:
	@cd services/ai-director && pytest -v

# Full CI pipeline
ci: lint test
	@echo "CI checks passed!"
