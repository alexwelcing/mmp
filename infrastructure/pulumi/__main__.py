"""
MMP Pulumi Program — deploys the entire GCP-native AI + Web3 pipeline.

Usage:
    cd infrastructure/pulumi
    pulumi stack init staging
    pulumi config set project_id YOUR_PROJECT
    pulumi up

Cost Tiers:
    Max Mini (dev):    pulumi config set filestore_capacity_gb 256
                       pulumi config set enable_resplat false
                       pulumi config set enable_audio false
    
    Standard Dev:      pulumi config set use_spot_system_pool true
    
    Production:        (default settings)
"""

import os

import pulumi
import pulumi_kubernetes as k8s

from components import (
    AIDirectorService,
    AudioWorker,
    ComfyUIWorkerPool,
    FilestoreCache,
    MMPCluster,
    MonitoringStack,
    PubSubPipeline,
    ResplatWorker,
    SecurityPolicy,
)
from config import ENABLE_AUDIO, ENABLE_RESPLAT

# Load service account key for image pull secrets
# This should be the same key used for GOOGLE_APPLICATION_CREDENTIALS
_service_account_key = ""
if "GOOGLE_APPLICATION_CREDENTIALS" in os.environ:
    try:
        with open(os.environ["GOOGLE_APPLICATION_CREDENTIALS"]) as f:
            _service_account_key = f.read()
    except Exception:
        pass

# ── Step 1: Foundation ───────────────────────────────────────────────────────
cluster = MMPCluster("mmp")

filestore = FilestoreCache(
    "mmp",
    network_name=cluster.network.name,
    opts=pulumi.ResourceOptions(depends_on=[cluster]),
)

pubsub = PubSubPipeline("mmp")

# ── Step 1b: Security & Monitoring ───────────────────────────────────────────
security = SecurityPolicy("mmp")

monitoring = MonitoringStack(
    "mmp",
    api_domain=pulumi.Config().get("api_domain") or "api.example.com",
)

# ── Step 2: K8s Provider (uses cluster kubeconfig) ───────────────────────────
k8s_provider = k8s.Provider(
    "gke-k8s",
    kubeconfig=cluster.kubeconfig,
)

# ── Step 3: ComfyUI Worker Pool ──────────────────────────────────────────────
comfyui = ComfyUIWorkerPool(
    "mmp",
    filestore_ip=filestore.ip_address,
    share_name=filestore.share_name,
    subscription_name=pubsub.subscription.name,
    k8s_provider=k8s_provider,
    opts=pulumi.ResourceOptions(depends_on=[cluster, filestore]),
)

# ── Step 4: AI Director Service ──────────────────────────────────────────────
ai_director = AIDirectorService(
    "mmp",
    ai_director_sa_email=cluster.ai_director_sa.email,
    filestore_ip=filestore.ip_address,
    share_name=filestore.share_name,
    k8s_provider=k8s_provider,
    service_account_key=_service_account_key,
    opts=pulumi.ResourceOptions(depends_on=[cluster, filestore]),
)

# ── Step 5: ReSplat Worker (optional, KEDA-scaled) ────────────────────────────
if ENABLE_RESPLAT:
    resplat = ResplatWorker(
        "mmp",
        filestore_ip=filestore.ip_address,
        share_name=filestore.share_name,
        subscription_name=pubsub.resplat_subscription.name,
        k8s_provider=k8s_provider,
        opts=pulumi.ResourceOptions(depends_on=[cluster, filestore]),
    )

# ── Step 6: Audio Worker (optional, KEDA scale-to-zero) ───────────────────────
if ENABLE_AUDIO:
    audio = AudioWorker(
        "mmp",
        k8s_provider=k8s_provider,
        opts=pulumi.ResourceOptions(depends_on=[cluster]),
    )

# ── Stack Outputs ────────────────────────────────────────────────────────────
pulumi.export("clusterEndpoint", cluster.cluster.endpoint)
pulumi.export("filestoreIp", filestore.ip_address)
pulumi.export("filestoreShare", filestore.share_name)
pulumi.export("pubsubTopic", pubsub.topic.name)
pulumi.export("pubsubSubscription", pubsub.subscription.name)
pulumi.export("aiDirectorSa", cluster.ai_director_sa.email)
pulumi.export("resplatEnabled", ENABLE_RESPLAT)
pulumi.export("audioEnabled", ENABLE_AUDIO)
from config import PROJECT_ID, REGION

pulumi.export("artifactRegistryUrl", f"{REGION}-docker.pkg.dev/{PROJECT_ID}/mmp-images")
