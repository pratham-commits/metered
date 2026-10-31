resource "random_password" "db" {
  length  = 24
  special = false
}

resource "random_password" "demo" {
  length  = 24
  special = false
}

resource "aws_security_group" "rds" {
  name   = "rideshare-rds"
  vpc_id = aws_vpc.this.id
  ingress {
    from_port       = 5432
    to_port         = 5432
    protocol        = "tcp"
    security_groups = [module.eks.node_security_group_id]
  }
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

resource "aws_db_subnet_group" "this" {
  name       = "rideshare"
  subnet_ids = aws_subnet.private[*].id
}

resource "aws_db_instance" "this" {
  identifier                 = "rideshare"
  engine                     = "postgres"
  engine_version             = "16"
  instance_class             = "db.t3.micro"
  allocated_storage          = 20
  storage_encrypted          = true
  db_name                    = "rideshare"
  username                   = "rideshare"
  password                   = random_password.db.result
  db_subnet_group_name       = aws_db_subnet_group.this.name
  vpc_security_group_ids     = [aws_security_group.rds.id]
  publicly_accessible        = false
  backup_retention_period    = 7
  skip_final_snapshot        = true
  deletion_protection        = false
  auto_minor_version_upgrade = true
}

resource "aws_secretsmanager_secret" "db" {
  name = "rideshare/database"
}

resource "aws_secretsmanager_secret_version" "db" {
  secret_id = aws_secretsmanager_secret.db.id
  secret_string = jsonencode({
    username = "rideshare"
    password = random_password.db.result
    host     = aws_db_instance.this.address
    port     = 5432
    dbname   = "rideshare"
    url      = "postgresql://rideshare:${random_password.db.result}@${aws_db_instance.this.address}:5432/rideshare"
  })
}

resource "aws_dynamodb_table" "drivers" {
  name         = "rideshare_driver_live"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "partition_id"
  range_key    = "driver_id"
  attribute {
    name = "partition_id"
    type = "S"
  }
  attribute {
    name = "driver_id"
    type = "S"
  }
  point_in_time_recovery { enabled = true }
  server_side_encryption { enabled = true }
}

resource "aws_dynamodb_table" "demand" {
  name         = "rideshare_demand_windows"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "zone"
  range_key    = "window_start"
  attribute {
    name = "zone"
    type = "S"
  }
  attribute {
    name = "window_start"
    type = "S"
  }
  point_in_time_recovery { enabled = true }
  server_side_encryption { enabled = true }
}

resource "aws_s3_bucket" "trips" {
  bucket = "rideshare-trip-files-${data.aws_caller_identity.current.account_id}"
}

data "aws_caller_identity" "current" {}

resource "aws_s3_bucket_versioning" "trips" {
  bucket = aws_s3_bucket.trips.id
  versioning_configuration { status = "Enabled" }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "trips" {
  bucket = aws_s3_bucket.trips.id
  rule {
    apply_server_side_encryption_by_default { sse_algorithm = "AES256" }
  }
}

resource "aws_s3_bucket_public_access_block" "trips" {
  bucket                  = aws_s3_bucket.trips.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_lifecycle_configuration" "trips" {
  bucket = aws_s3_bucket.trips.id
  rule {
    id     = "expire-gps"
    status = "Enabled"
    filter { prefix = "gps/" }
    expiration { days = 7 }
  }
}

resource "aws_sqs_queue" "dlq" {
  name                      = "rideshare-match-jobs-dlq"
  message_retention_seconds = 1209600
  sqs_managed_sse_enabled   = true
}

resource "aws_sqs_queue" "match" {
  name                       = "rideshare-match-jobs"
  visibility_timeout_seconds = 60
  sqs_managed_sse_enabled    = true
  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.dlq.arn
    maxReceiveCount     = 5
  })
}
