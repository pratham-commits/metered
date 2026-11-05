terraform {
  required_version = ">= 1.9.0"

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 6.0"
    }
  }

  backend "gcs" {
    bucket = "rideshare-tfstate-metered-513804"
    prefix = "dataproc"
  }
}

variable "project_id" {
  type = string
}

variable "region" {
  type    = string
  default = "asia-south1"
}

data "terraform_remote_state" "platform" {
  backend = "gcs"
  config = {
    bucket = "rideshare-tfstate-metered-513804"
    prefix = "platform"
  }
}

locals {
  platform    = data.terraform_remote_state.platform.outputs
  dataproc_sa = local.platform.workload_service_accounts["dataproc"]
}

provider "google" {
  project = var.project_id
  region  = var.region
}
