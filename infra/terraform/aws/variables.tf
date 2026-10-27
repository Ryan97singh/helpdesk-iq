variable "region" {
  type    = string
  default = "ap-south-1" # Mumbai: closest AWS region to Gurugram users
}

variable "environment" {
  type    = string
  default = "prod"
}

variable "vpc_cidr" {
  type    = string
  default = "10.20.0.0/16"
}

variable "db_instance_class" {
  type    = string
  default = "db.t4g.medium"
}

variable "eks_node_instance_types" {
  type    = list(string)
  default = ["t3.large"]
}
