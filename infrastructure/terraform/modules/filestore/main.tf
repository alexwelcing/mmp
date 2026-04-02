# Filestore module — NFS-backed shared model cache for ComfyUI workers.

resource "google_filestore_instance" "model_cache" {
  name     = "mmp-model-cache-${var.environment}"
  tier     = var.filestore_tier
  location = var.region

  file_shares {
    name        = "comfyui_models"
    capacity_gb = var.filestore_tier == "ENTERPRISE" ? 1024 : 1024

    # Allow NFS access from all nodes in the VPC.
    nfs_export_options {
      ip_ranges   = ["10.0.0.0/8"]
      access_mode = "READ_WRITE"
      squash_mode = "NO_ROOT_SQUASH"
    }
  }

  networks {
    network      = var.network_name
    modes        = ["MODE_IPV4"]
    connect_mode = "DIRECT_PEERING"
  }

  labels = {
    environment = var.environment
    managed_by  = "terraform"
    purpose     = "comfyui-model-cache"
  }
}
