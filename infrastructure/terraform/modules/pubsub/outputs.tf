output "topic_name" {
  description = "Full Pub/Sub topic name."
  value       = google_pubsub_topic.requests.name
}

output "subscription_name" {
  description = "Full Pub/Sub subscription name."
  value       = google_pubsub_subscription.requests_sub.name
}

output "dead_letter_topic_name" {
  description = "Dead-letter topic name."
  value       = google_pubsub_topic.dead_letter.name
}
