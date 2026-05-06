"""AudioWorker — CPU-only deployment with KEDA scale-to-zero for AudioGen inference."""

from __future__ import annotations

import pulumi
import pulumi_kubernetes as k8s
from pulumi_kubernetes.apiextensions import CustomResource

from config import ENVIRONMENT, REGISTRY_URL


class AudioWorker(pulumi.ComponentResource):
    """
    Deploys the Audio Worker namespace, Deployment, Service, and KEDA ScaledObject.
    
    Uses KEDA ScaledObject to scale to zero when idle, eliminating idle costs
    while providing fast cold-start via CPU-based scaling.
    """

    def __init__(
        self,
        name: str,
        k8s_provider: k8s.Provider,
        opts: pulumi.ResourceOptions | None = None,
    ) -> None:
        super().__init__("mmp:infra:AudioWorker", name, {}, opts)
        k8s_opts = pulumi.ResourceOptions(parent=self, provider=k8s_provider)

        # Namespace
        self.namespace = k8s.core.v1.Namespace(
            f"{name}-ns",
            metadata={"name": "audio", "labels": {"environment": ENVIRONMENT}},
            opts=k8s_opts,
        )

        # Deployment - starts with 0 replicas, KEDA will scale up
        self.deployment = k8s.apps.v1.Deployment(
            f"{name}-deployment",
            metadata={
                "name": "audio-worker",
                "namespace": self.namespace.metadata["name"],
                "labels": {"app": "audio-worker"},
            },
            spec={
                "replicas": 0,  # KEDA manages this
                "selector": {"matchLabels": {"app": "audio-worker"}},
                "template": {
                    "metadata": {"labels": {"app": "audio-worker"}},
                    "spec": {
                        "nodeSelector": {"pool": "system"},
                        "containers": [
                            {
                                "name": "audio",
                                "image": f"{REGISTRY_URL}/audio-worker:latest",
                                "imagePullPolicy": "Always",
                                "ports": [
                                    {
                                        "name": "http",
                                        "containerPort": 9000,
                                        "protocol": "TCP",
                                    }
                                ],
                                "resources": {
                                    "requests": {"cpu": "500m", "memory": "2Gi"},
                                    "limits": {"cpu": "2", "memory": "8Gi"},
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
                "name": "audio-service",
                "namespace": self.namespace.metadata["name"],
                "labels": {"app": "audio-worker"},
            },
            spec={
                "type": "ClusterIP",
                "selector": {"app": "audio-worker"},
                "ports": [
                    {
                        "name": "http",
                        "port": 9000,
                        "targetPort": 9000,
                        "protocol": "TCP",
                    }
                ],
            },
            opts=k8s_opts,
        )

        # KEDA ScaledObject for scale-to-zero
        # Scales based on CPU utilization and HTTP requests
        self.scaled_object = CustomResource(
            f"{name}-scaledobject",
            api_version="keda.sh/v1alpha1",
            kind="ScaledObject",
            metadata={
                "name": "audio-worker",
                "namespace": self.namespace.metadata["name"],
            },
            spec={
                "scaleTargetRef": {
                    "name": "audio-worker",
                    "kind": "Deployment",
                    "apiVersion": "apps/v1",
                },
                "minReplicaCount": 0,
                "maxReplicaCount": 3,
                "cooldownPeriod": 300,  # Scale down after 5 min idle
                "pollingInterval": 15,
                "triggers": [
                    {
                        "type": "cpu",
                        "metricType": "Utilization",
                        "metadata": {
                            "value": "50",  # Scale up at 50% CPU
                        },
                    },
                ],
            },
            opts=k8s_opts,
        )

        self.register_outputs({
            "namespace": self.namespace.metadata["name"],
            "scalingMode": "keda-scaledobject",
        })
