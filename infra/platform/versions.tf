terraform {
  required_version = ">= 1.9.0"
  required_providers {
    aws    = { source = "hashicorp/aws", version = "~> 5.70" }
    random = { source = "hashicorp/random", version = "~> 3.6" }
  }
  backend "s3" {
    bucket         = "rideshare-tfstate-ACCOUNT_ID"
    key            = "platform/terraform.tfstate"
    region         = "ap-south-1"
    dynamodb_table = "rideshare-tf-lock"
    encrypt        = true
  }
}

provider "aws" {
  region = "ap-south-1"
}

data "aws_availability_zones" "available" {
  state = "available"
}

locals {
  azs    = slice(data.aws_availability_zones.available.names, 0, 3)
  region = "ap-south-1"
}
