# Person 2. Matching Engine. Port 8004. No public ingress.
#
# On startup, a daemon thread pulls Pub/Sub subscription rideshare-match-jobs-sub.
# For each job: hash the pickup H3 cell, group neighbors(zone, k=H3_NEIGHBOR_K)
# by ring owner, then call Driver gRPC GetCandidates once per partition with that
# partition's neighbor cells.
# Merge candidates, call Dispatch gRPC Assign until one candidate wins.
# Record a GRPC/NOSQL hop for GetCandidates, including the candidate count,
# neighbor count and partition count.
# Update ride_requests to ASSIGNED or NO_DRIVER, and store the driver id and partition id.
# On success, publish RIDE_ASSIGNED to ride-events.
# Ack the Pub/Sub message only after the database update succeeds.
# A thrown job is left unacked so Pub/Sub redelivers it. The assign is idempotent.
