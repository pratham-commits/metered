# Person 1, code owned by Person 3. Letter b.
#
# Security group rideshare-lambda, egress all, and an ingress rule on the RDS
# security group from this group on 5432.
# Role rideshare-fare: AWSLambdaVPCAccessExecutionRole, s3:GetObject on the trip bucket,
# secretsmanager:GetSecretValue on the db secret, dynamodb:Query/GetItem on the demand table.
# Function rideshare-fare-estimate, handler handler.estimate, python3.12, VPC private subnets.
# Function rideshare-fare-final, handler handler.finalize, same zip.
# HTTP API rideshare-fare: POST /estimate and GET /health to the estimate function.
# S3 notification on prefix completions/ and suffix .json to the final function.
# Output fare_estimate_url. Person 1 puts that into the rideshare-config ConfigMap.
