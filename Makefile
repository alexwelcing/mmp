# MMP — Local Development Makefile
#
# Quick reference:
#   make dev-native      # Best dev experience: native AI Director + Frontend, Docker ComfyUI
#   make dev-docker      # Run everything inside Docker
#   make contracts-local # Deploy contracts to local Hardhat node
#   make stop            # Stop all Docker containers
#   make clean           # Stop containers and remove volumes

.PHONY: help dev-native dev-docker contracts-local stop clean install

help: ## Show this help message
	@echo "MMP Local Development Commands"
	@echo "=============================="
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / {printf "  %-20s %s\n", $$1, $$2}' $(MAKEFILE_LIST)

# ── Installation ────────────────────────────────────────────────────────────

install: ## Install all dependencies (frontend, contracts, ai-director)
	cd frontend && npm install --legacy-peer-deps
	cd contracts && npm install --legacy-peer-deps
	cd services/ai-director && python -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt

# ── Local Development (Recommended) ─────────────────────────────────────────

dev-native: ## Run ComfyUI + Audio in Docker, AI Director + Frontend natively
	@echo "🚀 Starting local development stack..."
	@echo "   ComfyUI  → http://localhost:8188"
	@echo "   Audio    → http://localhost:9000"
	@echo "   AI Director will start on http://localhost:8080"
	@echo "   Frontend will start on http://localhost:5173"
	@echo ""
	@# Start ComfyUI and Audio workers in background
	docker compose up --build -d comfyui audio
	@echo "⏳ Waiting for ComfyUI to be healthy..."
	@until curl -sf http://localhost:8188/system_stats > /dev/null 2>&1; do sleep 2; done
	@echo "✅ ComfyUI is ready!"
	@echo "⏳ Waiting for Audio worker to be healthy..."
	@until curl -sf http://localhost:9000/health > /dev/null 2>&1; do sleep 2; done
	@echo "✅ Audio worker is ready!"
	@echo ""
	@echo "Next steps (run in separate terminals):"
	@echo "  1. make contracts-local    # Deploy local contracts"
	@echo "  2. cd services/ai-director && source .venv/bin/activate && uvicorn main:app --reload --port 8080"
	@echo "  3. cd frontend && npm run dev"

dev-docker: ## Run AI Director, ComfyUI, and Hardhat entirely in Docker
	docker compose --profile full --profile docker-ai-director up --build

dev-resplat: ## Start ComfyUI + Audio + ReSplat in Docker (requires CUDA 12.8 GPU)
	@echo "🚀 Starting local stack WITH ReSplat (requires NVIDIA GPU + CUDA 12.8)..."
	docker compose --profile resplat up --build -d comfyui audio resplat
	@echo "⏳ Waiting for services to be healthy..."
	@until curl -sf http://localhost:8188/system_stats > /dev/null 2>&1; do sleep 2; done
	@echo "✅ ComfyUI is ready!"
	@until curl -sf http://localhost:9000/health > /dev/null 2>&1; do sleep 2; done
	@echo "✅ Audio worker is ready!"
	@until curl -sf http://localhost:9001/health > /dev/null 2>&1; do sleep 2; done
	@echo "✅ ReSplat worker is ready!"
	@echo ""
	@echo "Next steps:"
	@echo "  1. make contracts-local"
	@echo "  2. cd services/ai-director && source .venv/bin/activate && uvicorn main:app --reload --port 8080"
	@echo "  3. cd frontend && npm run dev"
	@echo ""
	@echo "⚠️  Remember to set USE_RESPLAT_FOR_3D=true in your .env to route 3D generation through ReSplat"

# ── Smart Contracts ─────────────────────────────────────────────────────────

contracts-local: ## Start Hardhat node and deploy contracts locally
	@echo "🚀 Starting local Hardhat node..."
	@cd contracts && npx hardhat node &
	@sleep 3
	@echo "📝 Deploying contracts to local node..."
	@cd contracts && npx hardhat run scripts/deploy-local.ts --network localhost
	@echo ""
	@echo "✅ Contracts deployed! Addresses written to .env.contracts"
	@echo "Source them with:  export \$$(cat .env.contracts | xargs)"

# ── Cleanup ─────────────────────────────────────────────────────────────────

stop: ## Stop all running Docker containers
	docker compose --profile full --profile docker-ai-director --profile resplat down

clean: ## Stop containers and remove all volumes (⚠️ destroys cached models)
	docker compose --profile full --profile docker-ai-director --profile resplat down -v
