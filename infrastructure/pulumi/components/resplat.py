"""ResplatWorker — GPU-enabled deployment for recurrent 3D Gaussian Splatting."""

from __future__ import annotations

import pulumi
import pulumi_kubernetes as k8s

from config import ENVIRONMENT, REGISTRY_URL


class ResplatWorker(pulumi.ComponentResource):
    """
    Deploys the ReSplat namespace, Filestore PVC, Deployment, and Service.
    """

    def __init__(
        self,
        name: str,
        filestore_ip: pulumi.Input[str],
        share_name: pulumi.Input[str],
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

        # Deployment
        self.deployment = k8s.apps.v1.Deployment(
            f"{name}-deployment",
            metadata={
                "name": "resplat-worker",
                "namespace": self.namespace.metadata["name"],
            },
            spec={
                "replicas": 1,
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
                                "livenessProbe": {
                                    "httpGet": {"path": "/health", "port": "http"},
                                    "initialDelaySeconds": 60,
                                    "periodSeconds": 15,
                                    "failureThreshold": 3,
                                },
                                "readinessProbe": {
                                    "httpGet": {"path": "/health", "port": "http"},
                                    "initialDelaySeconds": 30,
                                    "periodSeconds": 10,
                                    "failureThreshold": 3,
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

        # Service
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

        self.register_outputs({"namespace": self.namespace.metadata["name"]})
