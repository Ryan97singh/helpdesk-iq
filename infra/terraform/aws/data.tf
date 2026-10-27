# --- PostgreSQL + pgvector (RDS) ---------------------------------------------------------------
resource "aws_db_subnet_group" "db" {
  name       = local.name
  subnet_ids = module.vpc.private_subnets
}

resource "aws_security_group" "db" {
  name   = "${local.name}-db"
  vpc_id = module.vpc.vpc_id
  ingress {
    description     = "Postgres from EKS nodes only"
    from_port       = 5432
    to_port         = 5432
    protocol        = "tcp"
    security_groups = [module.eks.node_security_group_id]
  }
}

resource "aws_db_instance" "postgres" {
  identifier                   = local.name
  engine                       = "postgres"
  engine_version               = "16.4" # pgvector is available as an extension on RDS PostgreSQL
  instance_class               = var.db_instance_class
  allocated_storage            = 50
  max_allocated_storage        = 200
  storage_encrypted            = true
  db_name                      = "helpdesk"
  username                     = "helpdesk"
  manage_master_user_password  = true # password generated and rotated in Secrets Manager
  multi_az                     = var.environment == "prod"
  db_subnet_group_name         = aws_db_subnet_group.db.name
  vpc_security_group_ids       = [aws_security_group.db.id]
  backup_retention_period      = 7
  deletion_protection          = var.environment == "prod"
  skip_final_snapshot          = var.environment != "prod"
  final_snapshot_identifier    = "${local.name}-final"
  performance_insights_enabled = true
}

# --- Redis (ElastiCache): LLM response cache, rate limiting, event stream -------------------------
resource "aws_elasticache_subnet_group" "redis" {
  name       = local.name
  subnet_ids = module.vpc.private_subnets
}

resource "aws_security_group" "redis" {
  name   = "${local.name}-redis"
  vpc_id = module.vpc.vpc_id
  ingress {
    from_port       = 6379
    to_port         = 6379
    protocol        = "tcp"
    security_groups = [module.eks.node_security_group_id]
  }
}

resource "aws_elasticache_replication_group" "redis" {
  replication_group_id       = local.name
  description                = "HelpdeskIQ cache and event stream"
  engine                     = "redis"
  engine_version             = "7.1"
  node_type                  = "cache.t4g.small"
  num_cache_clusters         = 2
  automatic_failover_enabled = true
  transit_encryption_enabled = true
  at_rest_encryption_enabled = true
  subnet_group_name          = aws_elasticache_subnet_group.redis.name
  security_group_ids         = [aws_security_group.redis.id]
}

# --- S3: uploaded policy documents ------------------------------------------------------------
resource "aws_s3_bucket" "docs" {
  bucket = "${local.name}-docs"
}

resource "aws_s3_bucket_public_access_block" "docs" {
  bucket                  = aws_s3_bucket.docs.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_versioning" "docs" {
  bucket = aws_s3_bucket.docs.id
  versioning_configuration { status = "Enabled" }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "docs" {
  bucket = aws_s3_bucket.docs.id
  rule {
    apply_server_side_encryption_by_default { sse_algorithm = "AES256" }
  }
}

# --- DynamoDB: chat transcripts (NoSQL; replaces MongoDB on AWS) ---------------------------------
resource "aws_dynamodb_table" "transcripts" {
  name         = "${local.name}-transcripts"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "user_id"
  range_key    = "created_at"
  attribute {
    name = "user_id"
    type = "N"
  }
  attribute {
    name = "created_at"
    type = "S"
  }
  ttl {
    attribute_name = "expires_at" # auto-expire transcripts after the retention period
    enabled        = true
  }
  point_in_time_recovery { enabled = true }
}

# --- SQS: managed alternative to Redis Streams for events, with a dead-letter queue -------------
resource "aws_sqs_queue" "events_dlq" {
  name                      = "${local.name}-events-dlq"
  message_retention_seconds = 1209600
}

resource "aws_sqs_queue" "events" {
  name                       = "${local.name}-events"
  visibility_timeout_seconds = 120
  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.events_dlq.arn
    maxReceiveCount     = 3
  })
}

# --- Secrets Manager: LLM API keys, JWT secret (synced into K8s by External Secrets) -----------
resource "aws_secretsmanager_secret" "app" {
  name = "${local.name}/app"
}
