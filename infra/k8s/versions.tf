terraform {
  required_version = ">= 1.9.0"
  required_providers {
    aws        = { source = "hashicorp/aws", version = "~> 5.70" }
    kubernetes = { source = "hashicorp/kubernetes", version = "~> 2.35" }
    helm       = { source = "hashicorp/helm", version = "~> 2.17" }
    time       = { source = "hashicorp/time", version = "~> 0.12" }
    http       = { source = "hashicorp/http", version = "~> 3.4" }
  }
  backend "s3" {
    bucket         = "rideshare-tfstate-ACCOUNT_ID"
    key            = "k8s/terraform.tfstate"
    region         = "ap-south-1"
    dynamodb_table = "rideshare-tf-lock"
    encrypt        = true
  }
}

provider "aws" { region = "ap-south-1" }

data "terraform_remote_state" "platform" {
  backend = "s3"
  config = {
    bucket         = "rideshare-tfstate-ACCOUNT_ID"
    key            = "platform/terraform.tfstate"
    region         = "ap-south-1"
    dynamodb_table = "rideshare-tf-lock"
  }
}


provider "kubernetes" {
  host                   = data.terraform_remote_state.platform.outputs.cluster_endpoint
  cluster_ca_certificate = base64decode(data.terraform_remote_state.platform.outputs.cluster_ca)
  exec {
      api_version = "client.authentication.k8s.io/v1beta1"
      command = "aws"
      args = ["eks", "get-token", "--region", "ap-south-1", "--cluster-name", data.terraform_remote_state.platform.outputs.cluster_name]
    }
}

provider "helm" {
  kubernetes {
    host                   = data.terraform_remote_state.platform.outputs.cluster_endpoint
    cluster_ca_certificate = base64decode(data.terraform_remote_state.platform.outputs.cluster_ca)
    exec {
      api_version = "client.authentication.k8s.io/v1beta1"
      command = "aws"
      args = ["eks", "get-token", "--region", "ap-south-1", "--cluster-name", data.terraform_remote_state.platform.outputs.cluster_name]
    }
  }
}

variable "github_repo" {
  type = string
  default = "https://github.com/pratham-commits/metered.git"
}
