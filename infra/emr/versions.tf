terraform {
  required_version = ">= 1.9.0"
  required_providers {
    aws        = { source = "hashicorp/aws", version = "~> 5.70" }
  }
  backend "s3" {
    bucket         = "rideshare-tfstate-ACCOUNT_ID"
    key            = "emr/terraform.tfstate"
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

