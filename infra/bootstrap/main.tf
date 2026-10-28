# Person 1. Letter a.
#
# Variable: account_id.
# S3 bucket rideshare-tfstate-<account_id>: versioning, AES256, block all public access.
# DynamoDB table rideshare-tf-lock: PAY_PER_REQUEST, hash key LockID (S).
