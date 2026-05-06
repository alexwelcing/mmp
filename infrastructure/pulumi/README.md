# MMP Infrastructure — Pulumi (Python)

This directory contains a [Pulumi](https://www.pulumi.com/) program written in Python that deploys the entire MMP stack to GCP. It replaces the previous Terraform setup with **component resources** that mirror the domain architecture of the application.

## Why Pulumi?

- **Python-native** — the same language as the AI Director service.
- **Component Resources** — infrastructure is organised by subsystem (`MMPCluster`, `AIDirectorService`, `ComfyUIWorkerPool`) rather than raw cloud APIs.
- **Tight K8s integration** — Kubernetes resources are created directly via `pulumi-kubernetes`, no YAML templating required.
- **Fast feedback loop** — `pulumi preview` shows the full graph in seconds.

## Architecture

```
__main__.py
    ├── MMPCluster          → VPC, GKE, node pools, IAM, Workload Identity
    ├── FilestoreCache      → NFS-backed shared model cache
    ├── PubSubPipeline      → Request topic, status topic, DLQ, subscription
    ├── ComfyUIWorkerPool   → KEDA ScaledJob, ConfigMaps, PVC
    ├── AIDirectorService   → Deployment, HPA, Ingress
    └── ResplatWorker       → GPU Deployment for ReSplat
```

## Prerequisites

- [Pulumi CLI](https://www.pulumi.com/docs/install/) ≥ 3.136
- Python 3.11+
- `gcloud` authenticated with access to your GCP project

## Quick Start

```bash
cd infrastructure/pulumi

# Create a Python virtual environment and install dependencies
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Create a stack (e.g. staging)
pulumi stack init staging

# Set required config
pulumi config set project_id YOUR_GCP_PROJECT_ID
pulumi config set region us-central1
pulumi config set zone us-central1-a

# Preview and deploy
pulumi preview
pulumi up
```

## Stack Configuration

The following config keys are supported:

| Key | Default | Description |
|-----|---------|-------------|
| `project_id` | *required* | GCP project ID |
| `region` | `us-central1` | GCP region |
| `zone` | `us-central1-a` | GCP zone (for GPU pool) |
| `cluster_name` | `mmp-cluster` | GKE cluster name |
| `environment` | `staging` | `staging` or `production` |
| `filestore_tier` | `BASIC_HDD` | Filestore service tier |
| `filestore_capacity_gb` | `1024` | Filestore capacity |
| `api_domain` | `api.example.com` | Domain for the AI Director Ingress |

## Outputs

After `pulumi up`, the following outputs are available:

```bash
pulumi stack output clusterEndpoint
pulumi stack output filestoreIp
pulumi stack output pubsubSubscription
pulumi stack output pubsubStatusTopic
pulumi stack output artifactRegistryUrl
```

## Destroy

```bash
pulumi destroy
```

## Migration from Terraform

If you previously used the Terraform setup:

1. Run `terraform destroy` in `infrastructure/terraform/` to tear down old resources.
2. Run `pulumi up` here to recreate them with the new component model.
3. Update CI/CD pipelines to use `pulumi up` instead of `terraform apply`.
