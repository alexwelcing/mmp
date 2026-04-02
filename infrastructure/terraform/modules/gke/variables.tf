variable "project_id" {
  type        = string
  description = "GCP project ID."
}

variable "region" {
  type        = string
  description = "GCP region."
}

variable "zone" {
  type        = string
  description = "GCP zone (used for GPU node pool)."
}

variable "cluster_name" {
  type        = string
  description = "GKE cluster name."
}

variable "environment" {
  type        = string
  description = "Deployment environment."
}
