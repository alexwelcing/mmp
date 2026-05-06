"""MMPCluster — VPC, GKE cluster, node pools, and Workload Identity."""

from __future__ import annotations

import pulumi
import pulumi_gcp as gcp

from config import CLUSTER_NAME, ENVIRONMENT, PROJECT_ID, REGION, USE_SPOT_SYSTEM_POOL, ZONE


class MMPCluster(pulumi.ComponentResource):
    """
    Encapsulates the entire GKE foundation:
      - VPC + subnet with secondary IP ranges
      - GKE cluster with Workload Identity
      - System node pool (CPU)
      - GPU node pool (Spot T4 with gVisor)
      - IAM service accounts and bindings
    """

    def __init__(self, name: str, opts: pulumi.ResourceOptions | None = None) -> None:
        super().__init__("mmp:infra:Cluster", name, {}, opts)

        protect = ENVIRONMENT == "production"

        # ── Service Accounts ──────────────────────────────────────────────
        self.node_sa = gcp.serviceaccount.Account(
            f"{name}-nodes",
            account_id=f"{CLUSTER_NAME}-nodes",
            display_name=f"GKE Node SA for {CLUSTER_NAME}",
            opts=pulumi.ResourceOptions(parent=self, protect=protect),
        )

        self.ai_director_sa = gcp.serviceaccount.Account(
            f"{name}-ai-director",
            account_id=f"{CLUSTER_NAME}-ai-director",
            display_name=f"AI Director SA for {CLUSTER_NAME}",
            opts=pulumi.ResourceOptions(parent=self, protect=protect),
        )

        # Node SA IAM
        gcp.projects.IAMMember(
            f"{name}-nodes-logwriter",
            project=PROJECT_ID,
            role="roles/logging.logWriter",
            member=self.node_sa.email.apply(lambda e: f"serviceAccount:{e}"),
            opts=pulumi.ResourceOptions(parent=self.node_sa),
        )
        gcp.projects.IAMMember(
            f"{name}-nodes-metricwriter",
            project=PROJECT_ID,
            role="roles/monitoring.metricWriter",
            member=self.node_sa.email.apply(lambda e: f"serviceAccount:{e}"),
            opts=pulumi.ResourceOptions(parent=self.node_sa),
        )
        gcp.projects.IAMMember(
            f"{name}-nodes-pubsub",
            project=PROJECT_ID,
            role="roles/pubsub.subscriber",
            member=self.node_sa.email.apply(lambda e: f"serviceAccount:{e}"),
            opts=pulumi.ResourceOptions(parent=self.node_sa),
        )

        # AI Director SA IAM
        gcp.projects.IAMMember(
            f"{name}-ai-pubsub-sub",
            project=PROJECT_ID,
            role="roles/pubsub.subscriber",
            member=self.ai_director_sa.email.apply(lambda e: f"serviceAccount:{e}"),
            opts=pulumi.ResourceOptions(parent=self.ai_director_sa),
        )
        gcp.projects.IAMMember(
            f"{name}-ai-pubsub-pub",
            project=PROJECT_ID,
            role="roles/pubsub.publisher",
            member=self.ai_director_sa.email.apply(lambda e: f"serviceAccount:{e}"),
            opts=pulumi.ResourceOptions(parent=self.ai_director_sa),
        )
        gcp.projects.IAMMember(
            f"{name}-ai-metricwriter",
            project=PROJECT_ID,
            role="roles/monitoring.metricWriter",
            member=self.ai_director_sa.email.apply(lambda e: f"serviceAccount:{e}"),
            opts=pulumi.ResourceOptions(parent=self.ai_director_sa),
        )

        # ── VPC ────────────────────────────────────────────────────────────
        self.network = gcp.compute.Network(
            f"{name}-network",
            name=f"{CLUSTER_NAME}-network",
            auto_create_subnetworks=False,
            opts=pulumi.ResourceOptions(parent=self, protect=protect),
        )

        self.subnet = gcp.compute.Subnetwork(
            f"{name}-subnet",
            name=f"{CLUSTER_NAME}-subnet",
            ip_cidr_range="10.0.0.0/16",
            region=REGION,
            network=self.network.id,
            secondary_ip_ranges=[
                gcp.compute.SubnetworkSecondaryIpRangeArgs(
                    range_name="pods", ip_cidr_range="10.1.0.0/16"
                ),
                gcp.compute.SubnetworkSecondaryIpRangeArgs(
                    range_name="services", ip_cidr_range="10.2.0.0/16"
                ),
            ],
            opts=pulumi.ResourceOptions(parent=self.network, protect=protect),
        )

        # ── GKE Cluster ────────────────────────────────────────────────────
        self.cluster = gcp.container.Cluster(
            f"{name}-cluster",
            name=CLUSTER_NAME,
            location=REGION,
            remove_default_node_pool=True,
            initial_node_count=1,
            network=self.network.name,
            subnetwork=self.subnet.name,
            ip_allocation_policy=gcp.container.ClusterIpAllocationPolicyArgs(
                cluster_secondary_range_name="pods",
                services_secondary_range_name="services",
            ),
            workload_identity_config=gcp.container.ClusterWorkloadIdentityConfigArgs(
                workload_pool=f"{PROJECT_ID}.svc.id.goog"
            ),
            logging_config=gcp.container.ClusterLoggingConfigArgs(
                enable_components=["SYSTEM_COMPONENTS", "WORKLOADS"]
            ),
            monitoring_config=gcp.container.ClusterMonitoringConfigArgs(
                enable_components=["SYSTEM_COMPONENTS"]
            ),
            release_channel=gcp.container.ClusterReleaseChannelArgs(
                channel="REGULAR"
            ),
            resource_labels={
                "environment": ENVIRONMENT,
                "managed_by": "pulumi",
            },
            opts=pulumi.ResourceOptions(parent=self, protect=protect),
        )

        # ── System Node Pool ───────────────────────────────────────────────
        # Use Spot instances for cost savings even in production if configured
        # System workloads (AI Director, Audio) are stateless and can handle interruptions
        self.system_pool = gcp.container.NodePool(
            f"{name}-system-pool",
            name="system-pool",
            cluster=self.cluster.id,
            location=REGION,
            initial_node_count=1,
            autoscaling=gcp.container.NodePoolAutoscalingArgs(
                min_node_count=1, max_node_count=5
            ),
            node_config=gcp.container.NodePoolNodeConfigArgs(
                machine_type="e2-standard-4",
                spot=(ENVIRONMENT != "production") or USE_SPOT_SYSTEM_POOL,
                service_account=self.node_sa.email,
                oauth_scopes=["https://www.googleapis.com/auth/cloud-platform"],
                workload_metadata_config=gcp.container.NodePoolNodeConfigWorkloadMetadataConfigArgs(
                    mode="GKE_METADATA"
                ),
                labels={"pool": "system", "environment": ENVIRONMENT},
            ),
            opts=pulumi.ResourceOptions(parent=self.cluster, protect=protect),
        )

        # ── GPU Node Pool ───────────────────────────────────────────────────
        self.gpu_pool = gcp.container.NodePool(
            f"{name}-gpu-pool",
            name="gpu-pool",
            cluster=self.cluster.id,
            location=ZONE,
            initial_node_count=0,
            autoscaling=gcp.container.NodePoolAutoscalingArgs(
                min_node_count=0, max_node_count=10
            ),
            node_config=gcp.container.NodePoolNodeConfigArgs(
                machine_type="n1-standard-4",
                spot=True,
                guest_accelerators=[
                    gcp.container.NodePoolNodeConfigGuestAcceleratorArgs(
                        type="nvidia-tesla-t4",
                        count=1,
                        gpu_sharing_config=gcp.container.NodePoolNodeConfigGuestAcceleratorGpuSharingConfigArgs(
                            gpu_sharing_strategy="TIME_SHARING",
                            max_shared_clients_per_gpu=4,
                        ),
                    )
                ],
                service_account=self.node_sa.email,
                oauth_scopes=["https://www.googleapis.com/auth/cloud-platform"],
                sandbox_config=gcp.container.NodePoolNodeConfigSandboxConfigArgs(
                    sandbox_type="gvisor"
                ),
                workload_metadata_config=gcp.container.NodePoolNodeConfigWorkloadMetadataConfigArgs(
                    mode="GKE_METADATA"
                ),
                labels={"pool": "gpu", "environment": ENVIRONMENT},
                taints=[
                    gcp.container.NodePoolNodeConfigTaintArgs(
                        key="nvidia.com/gpu", value="present", effect="NO_SCHEDULE"
                    )
                ],
            ),
            opts=pulumi.ResourceOptions(parent=self.cluster, protect=protect),
        )

        # ── Kubeconfig ─────────────────────────────────────────────────────
        self.kubeconfig = pulumi.Output.all(
            self.cluster.endpoint,
            self.cluster.name,
            self.cluster.master_auth["cluster_ca_certificate"],
        ).apply(lambda args: _build_kubeconfig(*args))

        # Workload Identity binding - must be created after cluster for WI pool
        self.workload_identity_binding = gcp.serviceaccount.IAMMember(
            f"{name}-ai-wi",
            service_account_id=self.ai_director_sa.name,
            role="roles/iam.workloadIdentityUser",
            member=pulumi.Output.format(
                "serviceAccount:{}.svc.id.goog[ai-director/ai-director]", PROJECT_ID
            ),
            opts=pulumi.ResourceOptions(parent=self.ai_director_sa, depends_on=[self.cluster]),
        )

        self.register_outputs({
            "endpoint": self.cluster.endpoint,
            "networkName": self.network.name,
            "nodeServiceAccount": self.node_sa.email,
            "aiDirectorServiceAccount": self.ai_director_sa.email,
            "kubeconfig": self.kubeconfig,
        })


def _build_kubeconfig(endpoint: str, cluster_name: str, ca_cert: str) -> str:
    return f"""apiVersion: v1
clusters:
- cluster:
    certificate-authority-data: {ca_cert}
    server: https://{endpoint}
  name: {cluster_name}
contexts:
- context:
    cluster: {cluster_name}
    user: {cluster_name}
  name: {cluster_name}
current-context: {cluster_name}
kind: Config
preferences: {{}}
users:
- name: {cluster_name}
  user:
    exec:
      apiVersion: client.authentication.k8s.io/v1beta1
      command: gke-gcloud-auth-plugin
      installHint: Install gke-gcloud-auth-plugin
      provideClusterInfo: true
"""
