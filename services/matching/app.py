# Person 2. Matching Engine. Port 8004. No public ingress.
#
# On startup, a daemon thread polls SQS.
# For each job: hash the pickup zone, gRPC GetCandidates on DRIVER_GRPC for that
# partition and its neighbor zones, then gRPC Assign on DISPATCH_GRPC until one candidate wins.
# Record a GRPC/NOSQL hop for GetCandidates, including the candidate count.
# Update ride_requests to ASSIGNED or NO_DRIVER, and store the driver id and partition id.
# On success, publish RIDE_ASSIGNED to ride-events.
# Delete the SQS message only after the database update succeeds.
# A thrown job is left on the queue so the visibility timeout retries it. The assign is idempotent.
