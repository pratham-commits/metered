# Person 1. Letter g. The three stores, plus the match queue.
#
# random_password db and demo, length 24, special = false.
# RDS PostgreSQL 16, db.t3.micro, db name rideshare, user rideshare, encrypted,
# private subnets, not public, backup 7 days, skip_final_snapshot true.
# Security group rideshare-rds: 5432 from the EKS node security group.
# Secret rideshare/database in Secrets Manager. JSON includes the full url.
# DynamoDB rideshare_driver_live: PK partition_id (S), SK driver_id (S), PITR, encryption.
# DynamoDB rideshare_demand_windows: PK zone (S), SK window_start (S), PITR, encryption.
# S3 rideshare-trip-files-<account_id>: versioning, AES256, block public access.
# Lifecycle: expire prefix gps/ after 7 days.
# SQS rideshare-match-jobs, visibility 60, SSE, redrive to rideshare-match-jobs-dlq after 5 receives.
