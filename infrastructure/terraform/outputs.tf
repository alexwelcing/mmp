output "cluster_endpoint" {
  description = "GKE cluster API server endpoint."
  value       = module.gke.cluster_endpoint
  sensitive   = true
}

output "cluster_ca_certificate" {
  description = "GKE cluster CA certificate (base64 encoded)."
  value       = module.gke.cluster_ca_certificate
  sensitive   = true
}

output "filestore_ip_address" {
  description = "IP address of the Filestore NFS server."
  value       = module.filestore.ip_address
}

output "filestore_share_name" {
  description = "NFS share name to use in PersistentVolume definitions."
  value       = module.filestore.share_name
}

output "pubsub_topic_name" {
  description = "Full Pub/Sub topic name for asset generation requests."
  value       = module.pubsub.topic_name
}

output "pubsub_subscription_name" {
  description = "Full Pub/Sub subscription name consumed by the AI Director."
  value       = module.pubsub.subscription_name
}

output "artifact_registry_url" {
  description = "Docker image registry URL for pushing service images."
  value       = "${var.region}-docker.pkg.dev/${var.project_id}/mmp-images"
}
