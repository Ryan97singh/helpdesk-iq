output "cluster_name" { value = module.eks.cluster_name }
output "ecr_repositories" { value = { for k, r in aws_ecr_repository.repos : k => r.repository_url } }
output "db_endpoint" { value = aws_db_instance.postgres.address }
output "redis_endpoint" { value = aws_elasticache_replication_group.redis.primary_endpoint_address }
output "docs_bucket" { value = aws_s3_bucket.docs.bucket }
output "events_queue_url" { value = aws_sqs_queue.events.url }
output "api_irsa_role_arn" { value = module.api_irsa.iam_role_arn }
