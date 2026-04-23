"""
k8s_ai_service.py — Kubernetes-aware AI serving inspection for MCP tools.

This module keeps Kubernetes access in one place so the FastAPI app can expose
AI-serving operations through MCP without scattering cluster glue across route
handlers.
"""

from __future__ import annotations

from typing import Any

from kubernetes import client, config
from kubernetes.client import ApiException
from kubernetes.config.config_exception import ConfigException

from config import Settings


class KubernetesAIService:
    """Read-only view of the AI-serving workloads running in Kubernetes."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._config_source = "unconfigured"
        self._apps_api: client.AppsV1Api | None = None
        self._batch_api: client.BatchV1Api | None = None
        self._core_api: client.CoreV1Api | None = None

    def list_ai_workloads(self) -> dict[str, Any]:
        """Return a namespaced snapshot of AI-serving resources."""
        if not self._ensure_client():
            namespaces = self._configured_namespaces()
            return {
                "config_source": self._config_source,
                "namespaces": namespaces,
                "workloads": [],
                "warning": (
                    "Kubernetes configuration is unavailable. Run inside the cluster "
                    "or provide kubeconfig to inspect live AI workloads."
                ),
            }

        workloads: list[dict[str, Any]] = []
        for namespace in self._configured_namespaces():
            try:
                deployments = self._apps_api.list_namespaced_deployment(namespace=namespace).items
                services = self._core_api.list_namespaced_service(namespace=namespace).items
                jobs = self._batch_api.list_namespaced_job(namespace=namespace).items
            except ApiException as exc:
                workloads.append(
                    {
                        "namespace": namespace,
                        "error": f"Kubernetes API error {exc.status}: {exc.reason}",
                        "deployments": [],
                        "services": [],
                        "jobs": [],
                    }
                )
                continue

            workloads.append(
                {
                    "namespace": namespace,
                    "deployments": [self._serialize_deployment(item) for item in deployments],
                    "services": [self._serialize_service(item) for item in services],
                    "jobs": [self._serialize_job(item) for item in jobs],
                }
            )

        return {
            "config_source": self._config_source,
            "namespaces": self._configured_namespaces(),
            "workloads": workloads,
        }

    def get_ai_workload(self, namespace: str, kind: str, name: str) -> dict[str, Any]:
        """Return a single deployment, service, or job from the AI-serving plane."""
        if not self._ensure_client():
            return {
                "config_source": self._config_source,
                "namespace": namespace,
                "kind": kind,
                "name": name,
                "error": "Kubernetes configuration is unavailable",
            }

        normalized_kind = kind.lower()
        if normalized_kind not in {"deployment", "service", "job"}:
            return {
                "config_source": self._config_source,
                "namespace": namespace,
                "kind": kind,
                "name": name,
                "error": "Unsupported kind; expected deployment, service, or job",
            }

        try:
            if normalized_kind == "deployment":
                resource = self._apps_api.read_namespaced_deployment(
                    name=name,
                    namespace=namespace,
                )
                payload = self._serialize_deployment(resource)
            elif normalized_kind == "service":
                resource = self._core_api.read_namespaced_service(
                    name=name,
                    namespace=namespace,
                )
                payload = self._serialize_service(resource)
            else:
                resource = self._batch_api.read_namespaced_job(
                    name=name,
                    namespace=namespace,
                )
                payload = self._serialize_job(resource)
        except ApiException as exc:
            return {
                "config_source": self._config_source,
                "namespace": namespace,
                "kind": normalized_kind,
                "name": name,
                "error": f"Kubernetes API error {exc.status}: {exc.reason}",
            }

        return {
            "config_source": self._config_source,
            "namespace": namespace,
            "kind": normalized_kind,
            "resource": payload,
        }

    def _ensure_client(self) -> bool:
        """Load Kubernetes configuration lazily."""
        if self._apps_api and self._batch_api and self._core_api:
            return True

        try:
            config.load_incluster_config()
            self._config_source = "in-cluster"
        except ConfigException:
            try:
                config.load_kube_config()
                self._config_source = "kubeconfig"
            except ConfigException:
                self._config_source = "unavailable"
                return False

        self._apps_api = client.AppsV1Api()
        self._batch_api = client.BatchV1Api()
        self._core_api = client.CoreV1Api()
        return True

    def _configured_namespaces(self) -> list[str]:
        """Return the configured AI-serving namespaces."""
        return [
            namespace.strip()
            for namespace in self._settings.ai_k8s_namespaces.split(",")
            if namespace.strip()
        ]

    @staticmethod
    def _serialize_deployment(resource: client.V1Deployment) -> dict[str, Any]:
        containers = resource.spec.template.spec.containers if resource.spec else []
        status = resource.status
        return {
            "name": resource.metadata.name,
            "ready_replicas": status.ready_replicas or 0 if status else 0,
            "available_replicas": status.available_replicas or 0 if status else 0,
            "replicas": status.replicas or 0 if status else 0,
            "images": [container.image for container in containers],
        }

    @staticmethod
    def _serialize_service(resource: client.V1Service) -> dict[str, Any]:
        spec = resource.spec
        return {
            "name": resource.metadata.name,
            "type": spec.type if spec else None,
            "cluster_ip": spec.cluster_ip if spec else None,
            "ports": [
                {
                    "name": port.name,
                    "port": port.port,
                    "target_port": str(port.target_port),
                }
                for port in (spec.ports or [] if spec else [])
            ],
        }

    @staticmethod
    def _serialize_job(resource: client.V1Job) -> dict[str, Any]:
        status = resource.status
        return {
            "name": resource.metadata.name,
            "active": status.active or 0 if status else 0,
            "succeeded": status.succeeded or 0 if status else 0,
            "failed": status.failed or 0 if status else 0,
        }
