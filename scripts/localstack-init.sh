#!/bin/sh
set -eu
for table in rideshare_driver_live rideshare_demand_windows; do
  if ! awslocal dynamodb describe-table --table-name "$table" >/dev/null 2>&1; then
    if [ "$table" = rideshare_driver_live ]; then pk=partition_id; sk=driver_id; else pk=zone; sk=window_start; fi
    awslocal dynamodb create-table --table-name "$table" \
      --attribute-definitions AttributeName="$pk",AttributeType=S AttributeName="$sk",AttributeType=S \
      --key-schema AttributeName="$pk",KeyType=HASH AttributeName="$sk",KeyType=RANGE \
      --billing-mode PAY_PER_REQUEST
  fi
done
awslocal sqs create-queue --queue-name rideshare-match-jobs-dlq
awslocal sqs create-queue --queue-name rideshare-match-jobs --attributes '{"VisibilityTimeout":"60","RedrivePolicy":"{\"deadLetterTargetArn\":\"arn:aws:sqs:ap-south-1:000000000000:rideshare-match-jobs-dlq\",\"maxReceiveCount\":\"5\"}"}'
awslocal s3api head-bucket --bucket rideshare-trip-files-local 2>/dev/null || awslocal s3 mb s3://rideshare-trip-files-local
touch /tmp/rideshare-ready
