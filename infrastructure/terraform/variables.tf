variable "project_id" {
  type        = string
  description = "GCP project ID where all resources will be created."
}

variable "region" {
  type        = string
  description = "GCP region (e.g. us-central1)."
  default     = "us-central1"
}

variable "zone" {
  type        = string
  description = "GCP zone for zonal resources (e.g. us-central1-a)."
  default     = "us-central1-a"
}

variable "cluster_name" {
  type        = string
  description = "Name of the GKE cluster."
  default     = "mmp-cluster"
}

variable "environment" {
  type        = string
  description = "Deployment environment: staging or production."
  default     = "staging"

  validation {
    condition     = contains(["staging", "production"], var.environment)
    error_message = "environment must be 'staging' or 'production'."
  }
}

variable "filestore_tier" {
  type        = string
  description = "Filestore service tier. Use ENTERPRISE for HA; BASIC_HDD for dev."
  default     = "BASIC_HDD"

  validation {
    condition     = contains(["BASIC_HDD", "BASIC_SSD", "HIGH_SCALE_SSD", "ENTERPRISE"], var.filestore_tier)
    error_message = "filestore_tier must be one of BASIC_HDD, BASIC_SSD, HIGH_SCALE_SSD, ENTERPRISE."
  }
}
