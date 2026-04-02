output "ip_address" {
  description = "NFS server IP address for PersistentVolume configuration."
  value       = google_filestore_instance.model_cache.networks[0].ip_addresses[0]
}

output "share_name" {
  description = "NFS share name."
  value       = google_filestore_instance.model_cache.file_shares[0].name
}
