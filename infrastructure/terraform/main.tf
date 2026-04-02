# Root infrastructure module — composes the three sub-modules.

# Enable required GCP APIs before creating any resources.
resource "google_project_service" "apis" {
  for_each = toset([
    "container.googleapis.com",
    "file.googleapis.com",
    "pubsub.googleapis.com",
    "artifactregistry.googleapis.com",
    "iam.googleapis.com",
  ])

  service            = each.key
  disable_on_destroy = false
}

# ── GKE Cluster ──────────────────────────────────────────────────────
module "gke" {
  source = "./modules/gke"

  project_id   = var.project_id
  region       = var.region
  zone         = var.zone
  cluster_name = var.cluster_name
  environment  = var.environment

  depends_on = [google_project_service.apis]
}

# ── Filestore (NFS model cache) ───────────────────────────────────────
module "filestore" {
  source = "./modules/filestore"

  project_id      = var.project_id
  region          = var.region
  environment     = var.environment
  filestore_tier  = var.filestore_tier
  network_name    = module.gke.network_name

  depends_on = [google_project_service.apis]
}

# ── Pub/Sub ───────────────────────────────────────────────────────────
module "pubsub" {
  source = "./modules/pubsub"

  project_id  = var.project_id
  environment = var.environment

  depends_on = [google_project_service.apis]
}

# ── Artifact Registry (Docker images) ────────────────────────────────
resource "google_artifact_registry_repository" "images" {
  repository_id = "mmp-images"
  location      = var.region
  format        = "DOCKER"
  description   = "Container images for the MMP platform"
}
