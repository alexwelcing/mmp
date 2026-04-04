# GKE module — creates the cluster and GPU node pool.

# Service account for GKE nodes (least-privilege).
resource "google_service_account" "gke_nodes" {
  account_id   = "${var.cluster_name}-nodes"
  display_name = "GKE Node Service Account for ${var.cluster_name}"
}

resource "google_project_iam_member" "gke_nodes_log_writer" {
  project = var.project_id
  role    = "roles/logging.logWriter"
  member  = "serviceAccount:${google_service_account.gke_nodes.email}"
}

resource "google_project_iam_member" "gke_nodes_metric_writer" {
  project = var.project_id
  role    = "roles/monitoring.metricWriter"
  member  = "serviceAccount:${google_service_account.gke_nodes.email}"
}

resource "google_project_iam_member" "gke_nodes_pubsub" {
  project = var.project_id
  role    = "roles/pubsub.subscriber"
  member  = "serviceAccount:${google_service_account.gke_nodes.email}"
}

# Service account for the AI Director (Workload Identity).
resource "google_service_account" "ai_director" {
  account_id   = "${var.cluster_name}-ai-director"
  display_name = "AI Director Service Account for ${var.cluster_name}"
}

resource "google_project_iam_member" "ai_director_pubsub" {
  project = var.project_id
  role    = "roles/pubsub.subscriber"
  member  = "serviceAccount:${google_service_account.ai_director.email}"
}

resource "google_project_iam_member" "ai_director_pubsub_publisher" {
  project = var.project_id
  role    = "roles/pubsub.publisher"
  member  = "serviceAccount:${google_service_account.ai_director.email}"
}

resource "google_project_iam_member" "ai_director_metric_writer" {
  project = var.project_id
  role    = "roles/monitoring.metricWriter"
  member  = "serviceAccount:${google_service_account.ai_director.email}"
}

# Workload Identity binding: allow the K8s ServiceAccount in the ai-director
# namespace to impersonate the Google Service Account above.
resource "google_service_account_iam_member" "ai_director_workload_identity" {
  service_account_id = google_service_account.ai_director.name
  role               = "roles/iam.workloadIdentityUser"
  member             = "serviceAccount:${var.project_id}.svc.id.goog[ai-director/ai-director]"
}

# VPC network for the cluster.
resource "google_compute_network" "gke_network" {
  name                    = "${var.cluster_name}-network"
  auto_create_subnetworks = false
}

resource "google_compute_subnetwork" "gke_subnet" {
  name          = "${var.cluster_name}-subnet"
  ip_cidr_range = "10.0.0.0/16"
  region        = var.region
  network       = google_compute_network.gke_network.id

  secondary_ip_range {
    range_name    = "pods"
    ip_cidr_range = "10.1.0.0/16"
  }

  secondary_ip_range {
    range_name    = "services"
    ip_cidr_range = "10.2.0.0/16"
  }
}

# GKE cluster (Autopilot disabled; we need custom GPU node pools).
resource "google_container_cluster" "main" {
  provider = google-beta

  name     = var.cluster_name
  location = var.region

  # Use a separate node pool; remove the default one.
  remove_default_node_pool = true
  initial_node_count       = 1

  network    = google_compute_network.gke_network.name
  subnetwork = google_compute_subnetwork.gke_subnet.name

  ip_allocation_policy {
    cluster_secondary_range_name  = "pods"
    services_secondary_range_name = "services"
  }

  # Workload Identity — pods authenticate to GCP APIs without key files.
  workload_identity_config {
    workload_pool = "${var.project_id}.svc.id.goog"
  }

  # Enable gVisor (sandbox) for enhanced pod isolation.
  # Required for CUDA checkpointing via CRIU inside gVisor.
  node_config {
    sandbox_config {
      sandbox_type = "gvisor"
    }
  }

  # Logging and monitoring via GCP Operations Suite.
  logging_service    = "logging.googleapis.com/kubernetes"
  monitoring_service = "monitoring.googleapis.com/kubernetes"

  release_channel {
    channel = "REGULAR"
  }

  resource_labels = {
    environment = var.environment
    managed_by  = "terraform"
  }
}

# CPU system node pool (for non-GPU workloads: AI Director, ingress, etc.).
resource "google_container_node_pool" "system" {
  name     = "system-pool"
  cluster  = google_container_cluster.main.id
  location = var.region

  initial_node_count = 1

  autoscaling {
    min_node_count = 1
    max_node_count = 5
  }

  node_config {
    machine_type = "e2-standard-4"
    spot         = var.environment != "production"

    service_account = google_service_account.gke_nodes.email
    oauth_scopes    = ["https://www.googleapis.com/auth/cloud-platform"]

    workload_metadata_config {
      mode = "GKE_METADATA"
    }

    labels = {
      pool        = "system"
      environment = var.environment
    }
  }
}

# GPU node pool (for ComfyUI workers).
# Uses spot/preemptible T4 GPUs for significant cost savings (~70%).
resource "google_container_node_pool" "gpu" {
  provider = google-beta

  name     = "gpu-pool"
  cluster  = google_container_cluster.main.id
  location = var.zone  # GPU pools must be zonal

  initial_node_count = 0

  autoscaling {
    min_node_count = 0   # Scale to zero when no jobs are running
    max_node_count = 10
  }

  node_config {
    machine_type = "n1-standard-4"
    spot         = true  # Preemptible for cost savings

    guest_accelerator {
      type  = "nvidia-tesla-t4"
      count = 1

      # Enable GPU time-sharing to improve utilisation during low load.
      gpu_sharing_config {
        gpu_sharing_strategy       = "TIME_SHARING"
        max_shared_clients_per_gpu = 4
      }
    }

    service_account = google_service_account.gke_nodes.email
    oauth_scopes    = ["https://www.googleapis.com/auth/cloud-platform"]

    # gVisor sandbox enables CUDA checkpointing for fast pod restore.
    sandbox_config {
      sandbox_type = "gvisor"
    }

    workload_metadata_config {
      mode = "GKE_METADATA"
    }

    labels = {
      pool        = "gpu"
      environment = var.environment
    }

    taint {
      key    = "nvidia.com/gpu"
      value  = "present"
      effect = "NO_SCHEDULE"
    }
  }
}
