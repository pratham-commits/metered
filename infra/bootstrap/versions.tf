# Person 1. Local-state Terraform that creates the remote-state bucket and the lock table.
# Provider: hashicorp/aws ~> 5.70, region ap-south-1.
# This is the only stack that uses a local backend.
# After apply, every other stack uses the S3 backend created here.
