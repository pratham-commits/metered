terraform {
  required_version = ">= 1.9.0"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 6.0"
    }
  }
}

variable "project_id" {
  type        = string
  description = "GCP project id that owns the state bucket and all rideshare resources."
}

variable "region" {
  type    = string
  default = "asia-south1"
}

provider "google" {
  project = var.project_id
  region  = var.region
}
