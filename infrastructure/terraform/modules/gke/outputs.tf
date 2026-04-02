output "cluster_endpoint" {
  description = "GKE cluster API server endpoint."
  value       = google_container_cluster.main.endpoint
  sensitive   = true
}

output "cluster_ca_certificate" {
  description = "Base64-encoded cluster CA certificate."
  value       = google_container_cluster.main.master_auth[0].cluster_ca_certificate
  sensitive   = true
}

output "network_name" {
  description = "VPC network name (passed to Filestore module for peering)."
  value       = google_compute_network.gke_network.name
}

output "node_service_account_email" {
  description = "Email of the GKE node service account."
  value       = google_service_account.gke_nodes.email
}
