"""
MMP Pulumi Program — deploys the entire GCP-native AI + Web3 pipeline.

Usage:
    cd infrastructure/pulumi
    pulumi stack init staging
    pulumi config set project_id YOUR_PROJECT
    pulumi up
"""

import pulumi
import pulumi_kubernetes as k8s

from components import (
    AIDirectorService,
    AudioWorker,
    ComfyUIWorkerPool,
    FilestoreCache,
    MMPCluster,
    PubSubPipeline,
    ResplatWorker,
)

# ── Step 1: Foundation ───────────────────────────────────────────────────────
cluster = MMPCluster("mmp")

filestore = FilestoreCache(
    "mmp",
    network_name=cluster.network.name,
    opts=pulumi.ResourceOptions(depends_on=[cluster]),
)

pubsub = PubSubPipeline("mmp")

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
    opts=pulumi.ResourceOptions(depends_on=[cluster, filestore]),
)

# ── Step 5: ReSplat Worker (experimental) ────────────────────────────────────
resplat = ResplatWorker(
    "mmp",
    filestore_ip=filestore.ip_address,
    share_name=filestore.share_name,
    k8s_provider=k8s_provider,
    opts=pulumi.ResourceOptions(depends_on=[cluster, filestore]),
)

# ── Step 6: Audio Worker ─────────────────────────────────────────────────────
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
pulumi.export("pubsubStatusTopic", pubsub.status_topic.name)
pulumi.export("pubsubSubscription", pubsub.subscription.name)
pulumi.export("aiDirectorSa", cluster.ai_director_sa.email)
from config import PROJECT_ID, REGION

pulumi.export("artifactRegistryUrl", f"{REGION}-docker.pkg.dev/{PROJECT_ID}/mmp-images")
