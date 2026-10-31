output "database_url" {
  value     = jsondecode(aws_secretsmanager_secret_version.db.secret_string).url
  sensitive = true
}

output "demo_token" {
  value     = random_password.demo.result
  sensitive = true
}

output "kafka_bootstrap" {
  value = data.aws_msk_bootstrap_brokers.this.bootstrap_brokers_tls
}

output "match_queue_url" { value = aws_sqs_queue.match.url }
output "trip_bucket" { value = aws_s3_bucket.trips.bucket }
output "cluster_name" { value = module.eks.cluster_name }
output "cluster_endpoint" { value = module.eks.cluster_endpoint }
output "cluster_ca" { value = module.eks.cluster_certificate_authority_data }
output "oidc_provider_arn" { value = module.eks.oidc_provider_arn }
output "oidc_provider" { value = module.eks.oidc_provider }
output "node_security_group_id" { value = module.eks.node_security_group_id }
output "private_subnet_ids" { value = aws_subnet.private[*].id }
output "vpc_id" { value = aws_vpc.this.id }
output "db_secret_arn" { value = aws_secretsmanager_secret.db.arn }
output "db_security_group_id" { value = aws_security_group.rds.id }
output "driver_table_arn" { value = aws_dynamodb_table.drivers.arn }
output "demand_table_arn" { value = aws_dynamodb_table.demand.arn }

output "rds_endpoint" { value = aws_db_instance.this.address }
output "service_role_arns" { value = { for name, role in aws_iam_role.service : name => role.arn } }
output "ecr_repositories" { value = { for name, repo in aws_ecr_repository.services : name => repo.repository_url } }
