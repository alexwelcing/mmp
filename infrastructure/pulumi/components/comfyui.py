"""ComfyUIWorkerPool — KEDA ScaledJob, ConfigMaps, and Filestore mount."""

from __future__ import annotations

import pulumi
import pulumi_kubernetes as k8s
from pulumi_kubernetes.apiextensions import CustomResource

from config import ENVIRONMENT, REGISTRY_URL


class ComfyUIWorkerPool(pulumi.ComponentResource):
    """
    Deploys the ComfyUI namespace, ConfigMaps, Filestore PVC,
    KEDA TriggerAuthentication, and ScaledJob for GPU workers.
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
        super().__init__("mmp:infra:ComfyUIWorkerPool", name, {}, opts)
        k8s_opts = pulumi.ResourceOptions(parent=self, provider=k8s_provider)

        # Namespace
        self.namespace = k8s.core.v1.Namespace(
            f"{name}-ns",
            metadata={"name": "comfyui", "labels": {"environment": ENVIRONMENT}},
            opts=k8s_opts,
        )

        # ConfigMap: runtime config + model download script
        self.configmap = k8s.core.v1.ConfigMap(
            f"{name}-config",
            metadata={"name": "comfyui-config", "namespace": self.namespace.metadata["name"]},
            data={
                "extra_model_paths.yaml": """mmp_filestore:
  base_path: /mnt/filestore/models
  checkpoints: checkpoints/
  clip: clip/
  clip_vision: clip_vision/
  configs: configs/
  controlnet: controlnet/
  embeddings: embeddings/
  loras: loras/
  upscale_models: upscale_models/
  vae: vae/
""",
                "download_models.sh": """#!/usr/bin/env bash
set -euo pipefail
MODELS_DIR=/mnt/filestore/models
if [ ! -f "${MODELS_DIR}/checkpoints/sdxl_lightning_6step.safetensors" ]; then
  echo "Downloading SDXL-Lightning..."
  wget -q -O "${MODELS_DIR}/checkpoints/sdxl_lightning_6step.safetensors" \
    "https://huggingface.co/ByteDance/SDXL-Lightning/resolve/main/sdxl_lightning_6step_unet.safetensors"
fi
if [ ! -f "${MODELS_DIR}/upscale_models/clarity_upscaler.pth" ]; then
  echo "Downloading Clarity Upscaler..."
  wget -q -O "${MODELS_DIR}/upscale_models/clarity_upscaler.pth" \
    "https://huggingface.co/philz1337x/clarity-upscaler/resolve/main/4x-ClearRealityV1.pth"
fi
echo "All models ready."
""",
            },
            opts=k8s_opts,
        )

        # ConfigMap: snapshot scripts
        self.snapshot_cm = k8s.core.v1.ConfigMap(
            f"{name}-snapshot-cm",
            metadata={
                "name": "comfyui-snapshot-scripts",
                "namespace": self.namespace.metadata["name"],
            },
            data={
                "checkpoint.sh": """#!/usr/bin/env bash
set -euo pipefail
CHECKPOINT_DIR="/mnt/filestore/checkpoints/comfyui"
mkdir -p "${CHECKPOINT_DIR}"
echo "Creating gVisor checkpoint..."
runsc checkpoint --image-path="${CHECKPOINT_DIR}" --leave-running
echo "Checkpoint saved to ${CHECKPOINT_DIR}"
""",
                "restore.sh": """#!/usr/bin/env bash
set -euo pipefail
CHECKPOINT_DIR="/mnt/filestore/checkpoints/comfyui"
if [ -d "${CHECKPOINT_DIR}" ]; then
  echo "Restoring from checkpoint..."
  runsc restore --image-path="${CHECKPOINT_DIR}"
else
  echo "No checkpoint found; starting fresh."
  python /app/ComfyUI/main.py --listen 0.0.0.0 --port 8188
fi
""",
            },
            opts=k8s_opts,
        )

        # PersistentVolume
        self.pv = k8s.core.v1.PersistentVolume(
            f"{name}-pv",
            metadata={"name": "comfyui-models-pv", "labels": {"app": "comfyui"}},
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

        # TriggerAuthentication for KEDA GCP scaler
        self.trigger_auth = CustomResource(
            f"{name}-trigger-auth",
            api_version="keda.sh/v1alpha1",
            kind="TriggerAuthentication",
            metadata={
                "name": "keda-gcp-auth",
                "namespace": self.namespace.metadata["name"],
            },
            spec={"podIdentity": {"provider": "gcp"}},
            opts=k8s_opts,
        )

        # KEDA ScaledJob
        self.scaled_job = CustomResource(
            f"{name}-scaledjob",
            api_version="keda.sh/v1alpha1",
            kind="ScaledJob",
            metadata={
                "name": "comfyui-worker",
                "namespace": self.namespace.metadata["name"],
            },
            spec={
                "minReplicaCount": 0,
                "maxReplicaCount": 15,
                "pollingInterval": 10,
                "successfulJobsHistoryLimit": 3,
                "failedJobsHistoryLimit": 5,
                "triggers": [
                    {
                        "type": "gcp-pub-sub",
                        "metadata": {
                            "subscriptionName": subscription_name,
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
                    "activeDeadlineSeconds": 300,
                    "template": {
                        "metadata": {
                            "labels": {"app": "comfyui-worker", "version": "1.0"},
                            "annotations": {"io.kubernetes.cri-o.SandboxConfig": "gvisor"},
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
                                        {"name": "filestore-models", "mountPath": "/mnt/filestore"}
                                    ],
                                }
                            ],
                            "containers": [
                                {
                                    "name": "comfyui",
                                    "image": f"{REGISTRY_URL}/comfyui-worker:latest",
                                    "imagePullPolicy": "Always",
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
                                    "env": [
                                        {"name": "COMFYUI_MODEL_PATH", "value": "/mnt/filestore/models"},
                                        {"name": "COMFYUI_OUTPUT_PATH", "value": "/mnt/filestore/outputs"},
                                        {
                                            "name": "AI_DIRECTOR_WEBHOOK_URL",
                                            "value": "http://ai-director.ai-director.svc.cluster.local:8080/webhook/comfyui",
                                        },
                                    ],
                                    "volumeMounts": [
                                        {"name": "filestore-models", "mountPath": "/mnt/filestore"}
                                    ],
                                    "livenessProbe": {
                                        "httpGet": {"path": "/system_stats", "port": 8188},
                                        "initialDelaySeconds": 30,
                                        "periodSeconds": 15,
                                        "failureThreshold": 3,
                                    },
                                }
                            ],
                            "volumes": [
                                {
                                    "name": "filestore-models",
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

        self.register_outputs({"namespace": self.namespace.metadata["name"]})
