module "eks" {
  source  = "terraform-aws-modules/eks/aws"
  version = "~> 20.31"

  cluster_name                   = local.name
  cluster_version                = "1.31"
  cluster_endpoint_public_access = true
  enable_irsa                    = true

  vpc_id     = module.vpc.vpc_id
  subnet_ids = module.vpc.private_subnets

  eks_managed_node_groups = {
    default = {
      instance_types = var.eks_node_instance_types
      min_size       = 2
      max_size       = 6
      desired_size   = 3
    }
  }
}

# IRSA: the api/worker pods assume this role via their ServiceAccount; no static AWS keys in pods.
module "api_irsa" {
  source  = "terraform-aws-modules/iam/aws//modules/iam-role-for-service-accounts-eks"
  version = "~> 5.48"

  role_name = "${local.name}-api"
  role_policy_arns = {
    app = aws_iam_policy.api.arn
  }
  oidc_providers = {
    main = {
      provider_arn               = module.eks.oidc_provider_arn
      namespace_service_accounts = ["helpdesk-iq:helpdesk-api"]
    }
  }
}

resource "aws_iam_policy" "api" {
  name = "${local.name}-api"
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      { # least privilege: only this app's bucket and prefix
        Effect   = "Allow"
        Action   = ["s3:GetObject", "s3:PutObject", "s3:DeleteObject"]
        Resource = "${aws_s3_bucket.docs.arn}/documents/*"
      },
      {
        Effect   = "Allow"
        Action   = ["sqs:SendMessage", "sqs:ReceiveMessage", "sqs:DeleteMessage", "sqs:GetQueueAttributes"]
        Resource = aws_sqs_queue.events.arn
      },
      {
        Effect   = "Allow"
        Action   = ["dynamodb:PutItem", "dynamodb:Query", "dynamodb:BatchWriteItem"]
        Resource = aws_dynamodb_table.transcripts.arn
      },
      {
        Effect   = "Allow"
        Action   = ["secretsmanager:GetSecretValue"]
        Resource = aws_secretsmanager_secret.app.arn
      },
    ]
  })
}

resource "aws_ecr_repository" "repos" {
  for_each             = toset(["api", "web"])
  name                 = "helpdesk-iq-${each.key}"
  image_tag_mutability = "IMMUTABLE"
  image_scanning_configuration { scan_on_push = true }
}
