#!/usr/bin/env bash
# Person 1. LocalStack ready hook. Not used on AWS.
#
# Create DynamoDB rideshare_driver_live (PK partition_id, SK driver_id).
# Create DynamoDB rideshare_demand_windows (PK zone, SK window_start).
# Create SQS queue rideshare-match-jobs.
# Create S3 bucket rideshare-trip-files-local.
# Billing mode PAY_PER_REQUEST. Region ap-south-1.
