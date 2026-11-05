terraform {
  required_version = ">= 1.9.0"

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 6.0"
    }
    google-beta = {
      source  = "hashicorp/google-beta"
      version = "~> 6.0"
    }
    archive = {
      source  = "hashicorp/archive"
      version = "~> 2.7"
    }
  }

  backend "gcs" {
    bucket = "rideshare-tfstate-metered-513804"
    prefix = "functions"
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

data "google_project" "this" {
  project_id = var.project_id
}

locals {
  platform = data.terraform_remote_state.platform.outputs
}

provider "google" {
  project = var.project_id
  region  = var.region
}

provider "google-beta" {
  project = var.project_id
  region  = var.region
}
