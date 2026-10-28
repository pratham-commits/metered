# Person 1. Remote state.
# Backend bucket rideshare-tfstate-ACCOUNT_ID, key platform/terraform.tfstate,
# region ap-south-1, lock table rideshare-tf-lock, encrypt true.
# Replace ACCOUNT_ID in the backend block before init. Backends cannot use variables.
# Providers: aws ~> 5.70, random ~> 3.6. Region ap-south-1.
# Data: availability zones, slice the first 3.
