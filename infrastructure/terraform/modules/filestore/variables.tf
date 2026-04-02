variable "project_id" {
  type        = string
  description = "GCP project ID."
}

variable "region" {
  type        = string
  description = "GCP region."
}

variable "environment" {
  type        = string
  description = "Deployment environment."
}

variable "filestore_tier" {
  type        = string
  description = "Filestore service tier (BASIC_HDD, BASIC_SSD, ENTERPRISE)."
  default     = "BASIC_HDD"
}

variable "network_name" {
  type        = string
  description = "VPC network name for Filestore direct peering."
}
