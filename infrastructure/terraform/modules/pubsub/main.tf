# Pub/Sub module — request queue and dead-letter handling.

# Dead-letter topic for failed / undeliverable generation requests.
resource "google_pubsub_topic" "dead_letter" {
  name = "asset-generation-dlq-${var.environment}"

  message_retention_duration = "604800s"  # 7 days

  labels = {
    environment = var.environment
    managed_by  = "terraform"
  }
}

# Main topic: AI Director publishes generation requests here.
resource "google_pubsub_topic" "requests" {
  name = "asset-generation-requests-${var.environment}"

  message_retention_duration = "86400s"  # 24 hours

  labels = {
    environment = var.environment
    managed_by  = "terraform"
  }
}

# Pull subscription consumed by the AI Director (and KEDA ScaledJob trigger).
resource "google_pubsub_subscription" "requests_sub" {
  name  = "asset-generation-requests-sub-${var.environment}"
  topic = google_pubsub_topic.requests.name

  # Messages stay available for up to 60 minutes if not acknowledged.
  ack_deadline_seconds       = 600
  message_retention_duration = "86400s"
  retain_acked_messages      = false

  dead_letter_policy {
    dead_letter_topic     = google_pubsub_topic.dead_letter.id
    max_delivery_attempts = 5
  }

  retry_policy {
    minimum_backoff = "10s"
    maximum_backoff = "600s"
  }

  labels = {
    environment = var.environment
    managed_by  = "terraform"
  }
}

# Dead-letter subscription (for monitoring / manual replay).
resource "google_pubsub_subscription" "dead_letter_sub" {
  name  = "asset-generation-dlq-sub-${var.environment}"
  topic = google_pubsub_topic.dead_letter.name

  ack_deadline_seconds = 60

  labels = {
    environment = var.environment
    managed_by  = "terraform"
  }
}
