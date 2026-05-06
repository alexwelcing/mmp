"""ResplatWorker — KEDA-scaled GPU-enabled jobs for 3D Gaussian Splatting."""

from __future__ import annotations

import pulumi
import pulumi_kubernetes as k8s
from pulumi_kubernetes.apiextensions import CustomResource

from config import ENVIRONMENT, REGISTRY_URL


class ResplatWorker(pulumi.ComponentResource):
    """
    Deploys the ReSplat namespace, Filestore PVC, and KEDA ScaledJob.
    
    Uses KEDA ScaledJob for true serverless scaling (0-to-N) to minimize
    idle costs while still providing GPU acceleration when needed.
    """

    def __init__(
        self,
        name: str,
        filestore_ip: pulumi.Input[str],
        share_name: pulumi.Input[str],
        subscription_name: pulumi.Input[str],
        k8s_provider: k8s.Provider,
        opts: pulumi.ResourceOptions | None = None,
    ) -> None:
        super().__init__("mmp:infra:ResplatWorker", name, {}, opts)
        k8s_opts = pulumi.ResourceOptions(parent=self, provider=k8s_provider)

        # Namespace
        self.namespace = k8s.core.v1.Namespace(
            f"{name}-ns",
            metadata={"name": "resplat", "labels": {"environment": ENVIRONMENT}},
            opts=k8s_opts,
        )

        # PersistentVolume
        self.pv = k8s.core.v1.PersistentVolume(
            f"{name}-pv",
            metadata={"name": "resplat-models-pv", "labels": {"app": "resplat"}},
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
                "name": "resplat-models-pvc",
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

        # TriggerAuthentication for KEDA GCP scaler
        self.trigger_auth = CustomResource(
            f"{name}-trigger-auth",
            api_version="keda.sh/v1alpha1",
            kind="TriggerAuthentication",
            metadata={
                "name": "keda-gcp-auth-resplat",
                "namespace": self.namespace.metadata["name"],
            },
            spec={"podIdentity": {"provider": "gcp"}},
            opts=k8s_opts,
        )

        # KEDA ScaledJob for serverless GPU scaling
        # This scales from 0 to N based on Pub/Sub queue depth
        self.scaled_job = CustomResource(
            f"{name}-scaledjob",
            api_version="keda.sh/v1alpha1",
            kind="ScaledJob",
            metadata={
                "name": "resplat-worker",
                "namespace": self.namespace.metadata["name"],
            },
            spec={
                "minReplicaCount": 0,
                "maxReplicaCount": 5,
                "pollingInterval": 15,
                "successfulJobsHistoryLimit": 3,
                "failedJobsHistoryLimit": 5,
                "triggers": [
                    {
                        "type": "gcp-pub-sub",
                        "metadata": {
                            "subscriptionName": subscription_name,
                            "subscriptionNamePrefix": "resplat-",
                            "mode": "SubscriptionSize",
                            "value": "1",
                            "activationValue": "0",
                        },
                        "authenticationRef": {"name": self.trigger_auth.metadata["name"]},
                    }
                ],
                "jobTargetRef": {
                    "parallelism": 1,
                    "completions": 1,
                    "backoffLimit": 3,
                    "activeDeadlineSeconds": 600,  # 10 min max per job
                    "template": {
                        "metadata": {
                            "labels": {"app": "resplat-worker", "version": "1.0"},
                        },
                        "spec": {
                            "nodeSelector": {"pool": "gpu"},
                            "tolerations": [
                                {
                                    "key": "nvidia.com/gpu",
                                    "operator": "Exists",
                                    "effect": "NoSchedule",
                                }
                            ],
                            "restartPolicy": "Never",
                            "initContainers": [
                                {
                                    "name": "wait-for-nfs",
                                    "image": "busybox:1.36",
                                    "command": [
                                        "sh",
                                        "-c",
                                        "until ls /mnt/filestore/models > /dev/null 2>&1; do echo 'Waiting for NFS...'; sleep 2; done",
                                    ],
                                    "volumeMounts": [
                                        {"name": "filestore-resplat", "mountPath": "/mnt/filestore"}
                                    ],
                                }
                            ],
                            "containers": [
                                {
                                    "name": "resplat",
                                    "image": f"{REGISTRY_URL}/resplat-worker:latest",
                                    "imagePullPolicy": "Always",
                                    "ports": [
                                        {
                                            "name": "http",
                                            "containerPort": 9001,
                                            "protocol": "TCP",
                                        }
                                    ],
                                    "env": [
                                        {"name": "RESPLAT_MODEL_PRESET", "value": "dl3dv_8v_512x960"},
                                        {"name": "JOB_MODE", "value": "true"},  # Run once and exit
                                    ],
                                    "resources": {
                                        "requests": {
                                            "cpu": "2",
                                            "memory": "8Gi",
                                            "nvidia.com/gpu": "1",
                                        },
                                        "limits": {
                                            "cpu": "4",
                                            "memory": "16Gi",
                                            "nvidia.com/gpu": "1",
                                        },
                                    },
                                    "volumeMounts": [
                                        {
                                            "name": "filestore-resplat",
                                            "mountPath": "/mnt/filestore",
                                        }
                                    ],
                                }
                            ],
                            "volumes": [
                                {
                                    "name": "filestore-resplat",
                                    "persistentVolumeClaim": {
                                        "claimName": self.pvc.metadata["name"]
                                    },
                                }
                            ],
                        },
                    },
                },
            },
            opts=k8s_opts,
        )

        # Keep a minimal Service for health checks / direct calls
        # This uses a deployment with 0 replicas that can be scaled up if needed
        self.deployment = k8s.apps.v1.Deployment(
            f"{name}-deployment",
            metadata={
                "name": "resplat-service",
                "namespace": self.namespace.metadata["name"],
                "annotations": {
                    "resplat.keda.scaling": "scaledjob",
                    "note": "This deployment is for service discovery only. Jobs are created by KEDA ScaledJob.",
                },
            },
            spec={
                "replicas": 0,  # Always 0 - jobs handle actual work
                "selector": {"matchLabels": {"app": "resplat-worker"}},
                "template": {
                    "metadata": {"labels": {"app": "resplat-worker"}},
                    "spec": {
                        "nodeSelector": {"pool": "gpu"},
                        "tolerations": [
                            {
                                "key": "nvidia.com/gpu",
                                "operator": "Exists",
                                "effect": "NoSchedule",
                            }
                        ],
                        "containers": [
                            {
                                "name": "resplat",
                                "image": f"{REGISTRY_URL}/resplat-worker:latest",
                                "imagePullPolicy": "Always",
                                "ports": [
                                    {
                                        "name": "http",
                                        "containerPort": 9001,
                                        "protocol": "TCP",
                                    }
                                ],
                                "env": [
                                    {"name": "RESPLAT_MODEL_PRESET", "value": "dl3dv_8v_512x960"}
                                ],
                                "resources": {
                                    "requests": {
                                        "cpu": "2",
                                        "memory": "8Gi",
                                        "nvidia.com/gpu": "1",
                                    },
                                    "limits": {
                                        "cpu": "4",
                                        "memory": "16Gi",
                                        "nvidia.com/gpu": "1",
                                    },
                                },
                                "volumeMounts": [
                                    {
                                        "name": "filestore-resplat",
                                        "mountPath": "/mnt/filestore",
                                    }
                                ],
                            }
                        ],
                        "volumes": [
                            {
                                "name": "filestore-resplat",
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

        # Service for AI Director to call
        self.service = k8s.core.v1.Service(
            f"{name}-service",
            metadata={
                "name": "resplat-worker",
                "namespace": self.namespace.metadata["name"],
                "labels": {"app": "resplat-worker"},
            },
            spec={
                "type": "ClusterIP",
                "selector": {"app": "resplat-worker"},
                "ports": [
                    {
                        "name": "http",
                        "port": 9001,
                        "targetPort": 9001,
                        "protocol": "TCP",
                    }
                ],
            },
            opts=k8s_opts,
        )

        self.register_outputs({
            "namespace": self.namespace.metadata["name"],
            "scalingMode": "keda-scaledjob",
        })
