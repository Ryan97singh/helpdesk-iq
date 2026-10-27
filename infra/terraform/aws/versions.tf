terraform {
  required_version = ">= 1.6"
  required_providers {
    aws = { source = "hashicorp/aws", version = "~> 5.80" }
  }
  # Remote state with locking (create the bucket/table once, out of band):
  # backend "s3" {
  #   bucket         = "helpdesk-iq-tfstate"
  #   key            = "prod/terraform.tfstate"
  #   region         = "ap-south-1"
  #   dynamodb_table = "terraform-locks"
  #   encrypt        = true
  # }
}

provider "aws" {
  region = var.region
  default_tags {
    tags = { Project = "helpdesk-iq", Environment = var.environment, ManagedBy = "terraform" }
  }
}
