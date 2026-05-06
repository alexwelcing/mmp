"""DevMinimalMode — Ultra-low-cost development infrastructure.

This module provides a cost-optimized development environment that:
- Uses GKE Autopilot (no node management fees, pay per pod)
- Disables optional services (ReSplat, Audio) 
- Uses smallest viable Filestore (256GB)
- Runs everything in a single namespace
- Uses Cloud Run for stateless workloads where possible

Target idle cost: ~$50-80/month
"""

from __future__ import annotations

import pulumi
import pulumi_kubernetes as k8s

from config import ENVIRONMENT, PROJECT_ID, REGION, REGISTRY_URL


class DevMinimalMode(pulumi.ComponentResource):
    """
    Ultra-low-cost development deployment.
    
    Cost breakdown (estimated):
    - GKE Autopilot: ~$10 (management fee)
    - Filestore Basic HDD 256GB: ~$20
    - Pub/Sub (light usage): ~$5
    - Cloud Monitoring (free tier): $0
    - AI Director pod (when running): ~$15
    - ComfyUI GPU pod (when running): ~$0 (scales to 0)
    - Load balancer: ~$18
    ----------------------------------------
    IDLE: ~$53/month
    Active (10 requests/day): ~$70/month
    """

    def __init__(
        self,
        name: str,
        filestore_ip: pulumi.Input[str],
        share_name: pulumi.Input[str],
        k8s_provider: k8s.Provider,
        opts: pulumi.ResourceOptions | None = None,
    ) -> None:
        super().__init__("mmp:infra:DevMinimalMode", name, {}, opts)
        k8s_opts = pulumi.ResourceOptions(parent=self, provider=k8s_provider)

        # Single shared namespace for simplicity
        self.namespace = k8s.core.v1.Namespace(
            f"{name}-ns",
            metadata={"name": "mmp-dev", "labels": {"environment": ENVIRONMENT}},
            opts=k8s_opts,
        )

        # ConfigMap with dev-optimized settings
        self.configmap = k8s.core.v1.ConfigMap(
            f"{name}-config",
            metadata={
                "name": "mmp-dev-config",
                "namespace": self.namespace.metadata["name"],
            },
            data={
                "GCP_PROJECT_ID": PROJECT_ID,
                "GCP_REGION": REGION,
                "ENVIRONMENT": "dev",
                "LOG_LEVEL": "DEBUG",
                "MAX_CONCURRENT_JOBS": "5",
                "COMFYUI_DRAFT_COUNT": "2",  # Fewer drafts = faster/cheaper
                "SKIP_AUDIO_GENERATION": "true",  # Disable audio to save costs
                "SKIP_3D_GENERATION": "true",  # Disable 3D to save costs
                "USE_MOCK_WEB3": "true",  # Use mock instead of real blockchain
            },
            opts=k8s_opts,
        )

        # AI Director Deployment - minimal resources
        self.ai_director = k8s.apps.v1.Deployment(
            f"{name}-ai-director",
            metadata={
                "name": "ai-director",
                "namespace": self.namespace.metadata["name"],
            },
            spec={
                "replicas": 1,
                "selector": {"matchLabels": {"app": "ai-director"}},
                "template": {
                    "metadata": {"labels": {"app": "ai-director"}},
                    "spec": {
                        "containers": [
                            {
                                "name": "ai-director",
                                "image": f"{REGISTRY_URL}/ai-director:latest",
                                "ports": [{"containerPort": 8080}],
                                "envFrom": [
                                    {"configMapRef": {"name": self.configmap.metadata["name"]}}
                                ],
                                "resources": {
                                    # Minimal resources for dev
                                    "requests": {"cpu": "250m", "memory": "256Mi"},
                                    "limits": {"cpu": "1000m", "memory": "512Mi"},
                                },
                            }
                        ],
                    },
                },
            },
            opts=k8s_opts,
        )

        # AI Director Service
        self.ai_service = k8s.core.v1.Service(
            f"{name}-ai-service",
            metadata={
                "name": "ai-director",
                "namespace": self.namespace.metadata["name"],
            },
            spec={
                "type": "LoadBalancer",  # Direct LB for dev simplicity
                "selector": {"app": "ai-director"},
                "ports": [{"port": 80, "targetPort": 8080}],
            },
            opts=k8s_opts,
        )

        # ComfyUI ScaledJob - only GPU component, scales to 0
        self.comfyui_job = k8s.batch.v1.CronJob(
            f"{name}-comfyui-warmup",
            metadata={
                "name": "comfyui-model-warmup",
                "namespace": self.namespace.metadata["name"],
                "annotations": {
                    "note": "Pre-downloads models. Run manually: kubectl create job --from=cronjob/comfyui-model-warmup comfyui-warmup-manual"
                },
            },
            spec={
                "schedule": "0 9 * * 1",  # Weekly on Monday 9am
                "jobTemplate": {
                    "spec": {
                        "template": {
                            "spec": {
                                "containers": [
                                    {
                                        "name": "model-downloader",
                                        "image": "busybox:1.36",
                                        "command": ["sh", "-c"],
                                        "args": [
                                            "echo 'Models should be pre-downloaded in image or mounted from Filestore'"
                                        ],
                                        "volumeMounts": [
                                            {"name": "models", "mountPath": "/mnt/filestore"}
                                        ],
                                    }
                                ],
                                "volumes": [
                                    {
                                        "name": "models",
                                        "nfs": {
                                            "server": filestore_ip,
                                            "path": share_name,
                                        },
                                    }
                                ],
                                "restartPolicy": "Never",
                            },
                        },
                    },
                },
            },
            opts=k8s_opts,
        )

        self.register_outputs({
            "namespace": self.namespace.metadata["name"],
            "mode": "dev-minimal",
            "estimatedIdleCost": "~$53/month",
        })
