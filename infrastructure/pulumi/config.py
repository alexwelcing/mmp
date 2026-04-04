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
