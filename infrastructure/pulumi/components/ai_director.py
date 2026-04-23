"""AIDirectorService — FastAPI deployment, HPA, Ingress, and Workload Identity."""

from __future__ import annotations

import pulumi
import pulumi_kubernetes as k8s

from config import API_DOMAIN, ENVIRONMENT, REGISTRY_URL


class AIDirectorService(pulumi.ComponentResource):
    """
    Deploys the AI Director namespace, ServiceAccount, ConfigMap,
    Deployment, Service, HPA, and Ingress.
    """

    def __init__(
        self,
        name: str,
        ai_director_sa_email: pulumi.Input[str],
        filestore_ip: pulumi.Input[str],
        share_name: pulumi.Input[str],
        k8s_provider: k8s.Provider,
        opts: pulumi.ResourceOptions | None = None,
    ) -> None:
        super().__init__("mmp:infra:AIDirectorService", name, {}, opts)
        k8s_opts = pulumi.ResourceOptions(parent=self, provider=k8s_provider)

        # Namespace
        self.namespace = k8s.core.v1.Namespace(
            f"{name}-ns",
            metadata={"name": "ai-director", "labels": {"environment": ENVIRONMENT}},
            opts=k8s_opts,
        )

        # ServiceAccount with Workload Identity annotation
        self.sa = k8s.core.v1.ServiceAccount(
            f"{name}-sa",
            metadata={
                "name": "ai-director",
                "namespace": self.namespace.metadata["name"],
                "annotations": {
                    "iam.gke.io/gcp-service-account": ai_director_sa_email,
                },
            },
            opts=k8s_opts,
        )

        # ConfigMap
        self.configmap = k8s.core.v1.ConfigMap(
            f"{name}-config",
            metadata={
                "name": "ai-director-config",
                "namespace": self.namespace.metadata["name"],
            },
            data={
                "GCP_PROJECT_ID": pulumi.Config().require("project_id"),
                "GCP_REGION": pulumi.Config().get("region") or "us-central1",
                "ENVIRONMENT": ENVIRONMENT,
                "LOG_LEVEL": "INFO",
                "MAX_CONCURRENT_JOBS": "20",
                "PUBSUB_TOPIC": f"asset-generation-requests-{ENVIRONMENT}",
                "PUBSUB_SUBSCRIPTION": f"asset-generation-requests-sub-{ENVIRONMENT}",
                "PUBSUB_STATUS_TOPIC": f"asset-generation-status-{ENVIRONMENT}",
                "PUBSUB_MAX_MESSAGES": "10",
                "AI_K8S_NAMESPACES": "ai-director,comfyui,resplat,audio",
                "FILESTORE_MOUNT_PATH": "/mnt/filestore",
                "OUTPUT_BASE_PATH": "/mnt/filestore/outputs",
                "COMFYUI_ENDPOINT": "http://comfyui-service.comfyui.svc.cluster.local:8188",
                "COMFYUI_TIMEOUT_SECONDS": "120",
                "COMFYUI_DRAFT_COUNT": "4",
                "AUDIO_MODEL": "moshi",
                "AUDIO_ENDPOINT": "http://audio-service.ai-director.svc.cluster.local:9000",
                "BASE_RPC_URL": "https://sepolia.base.org",
                "BUNDLER_URL": "https://api.pimlico.io/v2/base-sepolia/rpc",
                "ENABLE_MCP_SERVER": "true",
                "CORS_ALLOW_ORIGINS": "*",
            },
            opts=k8s_opts,
        )

        # PersistentVolume (same Filestore export)
        self.pv = k8s.core.v1.PersistentVolume(
            f"{name}-pv",
            metadata={
                "name": "comfyui-models-pv-ai-director",
                "labels": {"app": "ai-director"},
            },
            spec={
                "capacity": {"storage": "1Ti"},
                "accessModes": ["ReadWriteMany"],
                "persistentVolumeReclaimPolicy": "Retain",
                "storageClassName": "",
                "nfs": {"server": filestore_ip, "path": share_name},
            },
            opts=k8s_opts,
        )

        # PersistentVolumeClaim
        self.pvc = k8s.core.v1.PersistentVolumeClaim(
            f"{name}-pvc",
            metadata={
                "name": "comfyui-models-pvc",
                "namespace": self.namespace.metadata["name"],
            },
            spec={
                "accessModes": ["ReadWriteMany"],
                "storageClassName": "",
                "resources": {"requests": {"storage": "1Ti"}},
                "volumeName": self.pv.metadata["name"],
            },
            opts=k8s_opts,
        )

        # Deployment
        self.deployment = k8s.apps.v1.Deployment(
            f"{name}-deployment",
            metadata={"name": "ai-director", "namespace": self.namespace.metadata["name"]},
            spec={
                "replicas": 1,
                "selector": {"matchLabels": {"app": "ai-director"}},
                "template": {
                    "metadata": {"labels": {"app": "ai-director"}},
                    "spec": {
                        "serviceAccountName": self.sa.metadata["name"],
                        "nodeSelector": {"pool": "system"},
                        "containers": [
                            {
                                "name": "ai-director",
                                "image": f"{REGISTRY_URL}/ai-director:latest",
                                "imagePullPolicy": "Always",
                                "ports": [
                                    {"name": "http", "containerPort": 8080, "protocol": "TCP"}
                                ],
                                "envFrom": [
                                    {"configMapRef": {"name": self.configmap.metadata["name"]}}
                                ],
                                "resources": {
                                    "requests": {"cpu": "500m", "memory": "512Mi"},
                                    "limits": {"cpu": "2000m", "memory": "2Gi"},
                                },
                                "livenessProbe": {
                                    "httpGet": {"path": "/health", "port": "http"},
                                    "initialDelaySeconds": 10,
                                    "periodSeconds": 10,
                                    "failureThreshold": 3,
                                },
                                "readinessProbe": {
                                    "httpGet": {"path": "/health", "port": "http"},
                                    "initialDelaySeconds": 5,
                                    "periodSeconds": 5,
                                    "failureThreshold": 3,
                                },
                                "volumeMounts": [
                                    {
                                        "name": "filestore-outputs",
                                        "mountPath": "/mnt/filestore",
                                    }
                                ],
                            }
                        ],
                        "volumes": [
                            {
                                "name": "filestore-outputs",
                                "persistentVolumeClaim": {
                                    "claimName": self.pvc.metadata["name"]
                                },
                            }
                        ],
                    },
                },
            },
            opts=k8s_opts,
        )

        # Service
        self.service = k8s.core.v1.Service(
            f"{name}-service",
            metadata={
                "name": "ai-director",
                "namespace": self.namespace.metadata["name"],
                "labels": {"app": "ai-director"},
            },
            spec={
                "type": "ClusterIP",
                "selector": {"app": "ai-director"},
                "ports": [
                    {"name": "http", "port": 8080, "targetPort": 8080, "protocol": "TCP"}
                ],
            },
            opts=k8s_opts,
        )

        # HPA
        self.hpa = k8s.autoscaling.v2.HorizontalPodAutoscaler(
            f"{name}-hpa",
            metadata={
                "name": "ai-director",
                "namespace": self.namespace.metadata["name"],
            },
            spec={
                "scaleTargetRef": {
                    "apiVersion": "apps/v1",
                    "kind": "Deployment",
                    "name": self.deployment.metadata["name"],
                },
                "minReplicas": 1,
                "maxReplicas": 5,
                "metrics": [
                    {
                        "type": "Resource",
                        "resource": {
                            "name": "cpu",
                            "target": {
                                "type": "Utilization",
                                "averageUtilization": 70,
                            },
                        },
                    }
                ],
                "behavior": {
                    "scaleUp": {"stabilizationWindowSeconds": 30},
                    "scaleDown": {"stabilizationWindowSeconds": 300},
                },
            },
            opts=k8s_opts,
        )

        # Ingress
        self.ingress = k8s.networking.v1.Ingress(
            f"{name}-ingress",
            metadata={
                "name": "ai-director",
                "namespace": self.namespace.metadata["name"],
                "annotations": {
                    "kubernetes.io/ingress.class": "gce",
                },
            },
            spec={
                "rules": [
                    {
                        "host": API_DOMAIN,
                        "http": {
                            "paths": [
                                {
                                    "path": "/",
                                    "pathType": "Prefix",
                                    "backend": {
                                        "service": {
                                            "name": self.service.metadata["name"],
                                            "port": {"number": 8080},
                                        }
                                    },
                                }
                            ]
                        },
                    }
                ]
            },
            opts=k8s_opts,
        )

        self.register_outputs({"namespace": self.namespace.metadata["name"]})
