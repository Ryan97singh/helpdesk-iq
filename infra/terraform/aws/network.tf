data "aws_availability_zones" "available" {}

locals {
  name = "helpdesk-iq-${var.environment}"
  azs  = slice(data.aws_availability_zones.available.names, 0, 3)
}

# Three AZs; public subnets hold only the ALB and NAT, everything else is private.
module "vpc" {
  source  = "terraform-aws-modules/vpc/aws"
  version = "~> 5.16"

  name            = local.name
  cidr            = var.vpc_cidr
  azs             = local.azs
  private_subnets = [for i in range(3) : cidrsubnet(var.vpc_cidr, 4, i)]
  public_subnets  = [for i in range(3) : cidrsubnet(var.vpc_cidr, 8, 48 + i)]

  enable_nat_gateway     = true
  single_nat_gateway     = var.environment != "prod" # one NAT per AZ in prod for AZ-failure tolerance
  one_nat_gateway_per_az = var.environment == "prod"

  public_subnet_tags  = { "kubernetes.io/role/elb" = 1 }
  private_subnet_tags = { "kubernetes.io/role/internal-elb" = 1 }
}
