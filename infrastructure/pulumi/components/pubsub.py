"""PubSubPipeline — request queue and dead-letter handling."""

from __future__ import annotations

import pulumi
import pulumi_gcp as gcp

from config import ENVIRONMENT


class PubSubPipeline(pulumi.ComponentResource):
    """
    Creates the Pub/Sub topic, dead-letter topic, and pull subscription
    consumed by the AI Director and KEDA scaler.
    """

    def __init__(self, name: str, opts: pulumi.ResourceOptions | None = None) -> None:
        super().__init__("mmp:infra:PubSubPipeline", name, {}, opts)

        self.dlq_topic = gcp.pubsub.Topic(
            f"{name}-dlq",
            name=f"asset-generation-dlq-{ENVIRONMENT}",
            message_retention_duration="604800s",
            labels={"environment": ENVIRONMENT, "managed_by": "pulumi"},
            opts=pulumi.ResourceOptions(parent=self),
        )

        self.topic = gcp.pubsub.Topic(
            f"{name}-topic",
            name=f"asset-generation-requests-{ENVIRONMENT}",
            message_retention_duration="86400s",
            labels={"environment": ENVIRONMENT, "managed_by": "pulumi"},
            opts=pulumi.ResourceOptions(parent=self),
        )

        self.subscription = gcp.pubsub.Subscription(
            f"{name}-sub",
            name=f"asset-generation-requests-sub-{ENVIRONMENT}",
            topic=self.topic.id,
            ack_deadline_seconds=600,
            message_retention_duration="86400s",
            dead_letter_policy=gcp.pubsub.SubscriptionDeadLetterPolicyArgs(
                dead_letter_topic=self.dlq_topic.id,
                max_delivery_attempts=5,
            ),
            retry_policy=gcp.pubsub.SubscriptionRetryPolicyArgs(
                minimum_backoff="10s", maximum_backoff="600s"
            ),
            labels={"environment": ENVIRONMENT, "managed_by": "pulumi"},
            opts=pulumi.ResourceOptions(parent=self),
        )

        self.dlq_subscription = gcp.pubsub.Subscription(
            f"{name}-dlq-sub",
            name=f"asset-generation-dlq-sub-{ENVIRONMENT}",
            topic=self.dlq_topic.id,
            ack_deadline_seconds=60,
            labels={"environment": ENVIRONMENT, "managed_by": "pulumi"},
            opts=pulumi.ResourceOptions(parent=self),
        )

        # ── ReSplat 3D Generation Queue ────────────────────────────────────
        self.resplat_topic = gcp.pubsub.Topic(
            f"{name}-resplat-topic",
            name=f"resplat-3d-generation-{ENVIRONMENT}",
            message_retention_duration="86400s",
            labels={"environment": ENVIRONMENT, "managed_by": "pulumi", "service": "resplat"},
            opts=pulumi.ResourceOptions(parent=self),
        )

        self.resplat_subscription = gcp.pubsub.Subscription(
            f"{name}-resplat-sub",
            name=f"resplat-3d-generation-sub-{ENVIRONMENT}",
            topic=self.resplat_topic.id,
            ack_deadline_seconds=600,
            message_retention_duration="86400s",
            dead_letter_policy=gcp.pubsub.SubscriptionDeadLetterPolicyArgs(
                dead_letter_topic=self.dlq_topic.id,
                max_delivery_attempts=5,
            ),
            retry_policy=gcp.pubsub.SubscriptionRetryPolicyArgs(
                minimum_backoff="10s", maximum_backoff="300s"
            ),
            labels={"environment": ENVIRONMENT, "managed_by": "pulumi", "service": "resplat"},
            opts=pulumi.ResourceOptions(parent=self),
        )

        self.register_outputs({
            "topicName": self.topic.name,
            "subscriptionName": self.subscription.name,
            "dlqTopicName": self.dlq_topic.name,
            "resplatTopicName": self.resplat_topic.name,
            "resplatSubscriptionName": self.resplat_subscription.name,
        })
