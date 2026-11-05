terraform {
  required_version = ">= 1.9.0"

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 6.0"
    }
    kubernetes = {
      source  = "hashicorp/kubernetes"
      version = "~> 2.30"
    }
    helm = {
      source  = "hashicorp/helm"
      version = "~> 2.15"
    }
    kubectl = {
      source  = "gavinbunney/kubectl"
      version = "~> 1.14"
    }
  }

  backend "gcs" {
    bucket = "rideshare-tfstate-metered-513804"
    prefix = "k8s"
  }
}

variable "github_repo" {
  type        = string
  description = "Git remote used by Argo CD, for example https://github.com/org/repo.git"
}

variable "fare_estimate_url" {
  type    = string
  default = ""
}

data "terraform_remote_state" "platform" {
  backend = "gcs"
  config = {
    bucket = "rideshare-tfstate-metered-513804"
    prefix = "platform"
  }
}

data "google_client_config" "default" {}

provider "google" {
  project = data.terraform_remote_state.platform.outputs.project_id
  region  = data.terraform_remote_state.platform.outputs.region
}

provider "kubernetes" {
  host                   = data.terraform_remote_state.platform.outputs.cluster_endpoint
  token                  = data.google_client_config.default.access_token
  cluster_ca_certificate = base64decode(data.terraform_remote_state.platform.outputs.cluster_ca_certificate)
}

provider "helm" {
  kubernetes {
    host                   = data.terraform_remote_state.platform.outputs.cluster_endpoint
    token                  = data.google_client_config.default.access_token
    cluster_ca_certificate = base64decode(data.terraform_remote_state.platform.outputs.cluster_ca_certificate)
  }
}

provider "kubectl" {
  host                   = data.terraform_remote_state.platform.outputs.cluster_endpoint
  token                  = data.google_client_config.default.access_token
  cluster_ca_certificate = base64decode(data.terraform_remote_state.platform.outputs.cluster_ca_certificate)
  load_config_file       = false
}
