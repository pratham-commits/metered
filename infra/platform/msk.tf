# Person 1. Kafka for letter e. Brokers are private.
#
# Security group rideshare-msk: TCP 9094 from the VPC CIDR only.
# CloudWatch log group /rideshare/msk, 14 day retention.
# MSK cluster name rideshare, kafka_version 3.9.x, 3 brokers kafka.t3.small,
# private subnets, 20 GiB EBS, TLS in transit, unauthenticated client auth, encryption at rest.
# Data source aws_msk_bootstrap_brokers. Output the TLS bootstrap string.
# This apply takes about 30 minutes.
