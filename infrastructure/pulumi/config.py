"""Shared Pulumi configuration helpers."""

import pulumi

_cfg = pulumi.Config()

# GCP
PROJECT_ID = _cfg.require("project_id")
REGION = _cfg.get("region") or "us-central1"
ZONE = _cfg.get("zone") or "us-central1-a"

# Cluster
CLUSTER_NAME = _cfg.get("cluster_name") or "mmp-cluster"
ENVIRONMENT = _cfg.get("environment") or "staging"

# Filestore
FILESTORE_TIER = _cfg.get("filestore_tier") or "BASIC_HDD"
FILESTORE_CAPACITY_GB = int(_cfg.get("filestore_capacity_gb") or "1024")

# Image registry
REGISTRY_URL = f"{REGION}-docker.pkg.dev/{PROJECT_ID}/mmp-images"

# Domain / networking
API_DOMAIN = _cfg.get("api_domain") or "api.example.com"

# Billing
BILLING_ACCOUNT = _cfg.get("billing_account")

# Cost optimization
USE_SPOT_SYSTEM_POOL = _cfg.get_bool("use_spot_system_pool") or False
IDLE_COST_TARGET = int(_cfg.get("idle_cost_target") or "100")

# Feature flags (for cost tiers)
ENABLE_RESPLAT = _cfg.get_bool("enable_resplat") if _cfg.get("enable_resplat") is not None else True
ENABLE_AUDIO = _cfg.get_bool("enable_audio") if _cfg.get("enable_audio") is not None else True
USE_MOCK_WEB3 = _cfg.get_bool("use_mock_web3") or False
USE_GKE_AUTOPILOT = _cfg.get_bool("use_gke_autopilot") or False

# Dev mode settings
AI_DIRECTOR_MIN_REPLICAS = int(_cfg.get("ai_director_min_replicas") or "1")
