"""MonitoringStack — Cloud Monitoring dashboards, alerts, and custom metrics."""

from __future__ import annotations

import json

import pulumi
import pulumi_gcp as gcp

from config import ENVIRONMENT, PROJECT_ID


class MonitoringStack(pulumi.ComponentResource):
    """
    Encapsulates observability infrastructure:
      - Custom dashboards for pipeline health
      - Alerting policies for critical metrics
      - Log-based metrics for business KPIs
      - Uptime checks for external endpoints
    """

    def __init__(
        self,
        name: str,
        api_domain: str,
        opts: pulumi.ResourceOptions | None = None,
    ) -> None:
        super().__init__("mmp:infra:MonitoringStack", name, {}, opts)

        # ── Custom Dashboard: Pipeline Health ──────────────────────────────
        dashboard_json = json.dumps({
            "displayName": f"MMP Pipeline Health - {ENVIRONMENT}",
            "gridLayout": {
                "columns": "2",
                "widgets": [
                    {
                        "title": "Job Completion Rate",
                        "xyChart": {
                            "dataSets": [{
                                "timeSeriesQuery": {
                                    "timeSeriesFilter": {
                                        "filter": "resource.type=\"k8s_container\" AND metric.type=\"logging.googleapis.com/user/mmp_jobs_completed\"",
                                        "aggregation": {
                                            "alignmentPeriod": {"seconds": 60},
                                            "perSeriesAligner": "ALIGN_RATE",
                                        },
                                    },
                                },
                            }],
                        },
                    },
                    {
                        "title": "Pub/Sub Subscription Lag",
                        "xyChart": {
                            "dataSets": [{
                                "timeSeriesQuery": {
                                    "timeSeriesFilter": {
                                        "filter": f"resource.type=\"pubsub_subscription\" AND resource.label.subscription_id=\"asset-generation-requests-sub-{ENVIRONMENT}\" AND metric.type=\"pubsub.googleapis.com/subscription/oldest_unacked_message_age\"",
                                        "aggregation": {
                                            "alignmentPeriod": {"seconds": 60},
                                            "perSeriesAligner": "ALIGN_MEAN",
                                        },
                                    },
                                },
                            }],
                        },
                    },
                    {
                        "title": "GPU Pool Utilization",
                        "xyChart": {
                            "dataSets": [{
                                "timeSeriesQuery": {
                                    "timeSeriesFilter": {
                                        "filter": "resource.type=\"k8s_node\" AND metric.type=\"kubernetes.io/node/gpu/utilization\"",
                                        "aggregation": {
                                            "alignmentPeriod": {"seconds": 60},
                                            "perSeriesAligner": "ALIGN_MEAN",
                                        },
                                    },
                                },
                            }],
                        },
                    },
                    {
                        "title": "Pipeline Latency (p95)",
                        "xyChart": {
                            "dataSets": [{
                                "timeSeriesQuery": {
                                    "timeSeriesFilter": {
                                        "filter": "resource.type=\"k8s_container\" AND metric.type=\"logging.googleapis.com/user/mmp_pipeline_latency\"",
                                        "aggregation": {
                                            "alignmentPeriod": {"seconds": 60},
                                            "perSeriesAligner": "ALIGN_PERCENTILE_95",
                                        },
                                    },
                                },
                            }],
                        },
                    },
                ],
            },
        })

        self.dashboard = gcp.monitoring.Dashboard(
            f"{name}-dashboard",
            dashboard_json=dashboard_json,
            opts=pulumi.ResourceOptions(parent=self),
        )

        # ── Alerting Policies ──────────────────────────────────────────────
        
        # Alert: High Pub/Sub lag
        self.pubsub_lag_alert = gcp.monitoring.AlertPolicy(
            f"{name}-pubsub-lag-alert",
            display_name=f"MMP High Pub/Sub Lag - {ENVIRONMENT}",
            combiner="OR",
            conditions=[
                gcp.monitoring.AlertPolicyConditionArgs(
                    display_name="Subscription lag > 5 minutes",
                    condition_threshold=gcp.monitoring.AlertPolicyConditionConditionThresholdArgs(
                        filter=f"resource.type=\"pubsub_subscription\" AND resource.label.subscription_id=\"asset-generation-requests-sub-{ENVIRONMENT}\" AND metric.type=\"pubsub.googleapis.com/subscription/oldest_unacked_message_age\"",
                        aggregations=[
                            gcp.monitoring.AlertPolicyConditionConditionThresholdAggregationArgs(
                                alignment_period="300s",
                                per_series_aligner="ALIGN_MEAN",
                            ),
                        ],
                        comparison="COMPARISON_GT",
                        threshold_value=300,  # 5 minutes in seconds
                        duration="0s",
                        trigger=gcp.monitoring.AlertPolicyConditionConditionThresholdTriggerArgs(
                            count=1,
                        ),
                    ),
                ),
            ],
            alert_strategy=gcp.monitoring.AlertPolicyAlertStrategyArgs(
                auto_close="86400s",
            ),
            severity="WARNING",
            opts=pulumi.ResourceOptions(parent=self),
        )

        # Alert: GKE Container restarts (indicates crashes)
        self.restart_alert = gcp.monitoring.AlertPolicy(
            f"{name}-restart-alert",
            display_name=f"MMP Container Restarts - {ENVIRONMENT}",
            combiner="OR",
            conditions=[
                gcp.monitoring.AlertPolicyConditionArgs(
                    display_name="Container restart rate > 0.1/min",
                    condition_threshold=gcp.monitoring.AlertPolicyConditionConditionThresholdArgs(
                        filter="resource.type=\"k8s_container\" AND metric.type=\"kubernetes.io/container/restart_count\"",
                        aggregations=[
                            gcp.monitoring.AlertPolicyConditionConditionThresholdAggregationArgs(
                                alignment_period="300s",
                                per_series_aligner="ALIGN_RATE",
                            ),
                        ],
                        comparison="COMPARISON_GT",
                        threshold_value=0.1,
                        duration="0s",
                    ),
                ),
            ],
            alert_strategy=gcp.monitoring.AlertPolicyAlertStrategyArgs(
                auto_close="86400s",
            ),
            severity="WARNING",
            opts=pulumi.ResourceOptions(parent=self),
        )

        # ── Uptime Check ────────────────────────────────────────────────────
        if api_domain and api_domain != "api.example.com":
            self.uptime_check = gcp.monitoring.UptimeCheckConfig(
                f"{name}-uptime-check",
                display_name=f"MMP API Uptime - {ENVIRONMENT}",
                timeout="10s",
                period="60s",
                http_check=gcp.monitoring.UptimeCheckConfigHttpCheckArgs(
                    path="/health",
                    port=443,
                    use_ssl=True,
                ),
                monitored_resource=gcp.monitoring.UptimeCheckConfigMonitoredResourceArgs(
                    type="uptime_url",
                    labels={
                        "project_id": PROJECT_ID,
                        "host": api_domain,
                    },
                ),
                opts=pulumi.ResourceOptions(parent=self),
            )

        # ── Log-based Metrics ──────────────────────────────────────────────
        # Custom metric: Pipeline job completions
        self.jobs_completed_metric = gcp.logging.Metric(
            f"{name}-jobs-completed-metric",
            name="mmp_jobs_completed",
            filter="resource.type=\"k8s_container\" AND jsonPayload.message=\"Job completed\"",
            metric_descriptor=gcp.logging.MetricMetricDescriptorArgs(
                metric_kind="DELTA",
                value_type="INT64",
                labels=[
                    gcp.logging.MetricMetricDescriptorLabelArgs(
                        key="stage",
                        value_type="STRING",
                        description="Pipeline stage",
                    ),
                ],
            ),
            label_extractors={
                "stage": "EXTRACT(jsonPayload.stage)",
            },
            opts=pulumi.ResourceOptions(parent=self),
        )

        self.register_outputs({
            "dashboardId": self.dashboard.id,
        })
