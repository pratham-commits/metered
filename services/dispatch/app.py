# Person 2. Dispatch Service. HTTP 8005 for health only. gRPC 9005 for Assign.
#
# Assign calls store.assign(partition_id, driver_id, ride_id) in a Firestore transaction.
# Record a GRPC/NOSQL hop on the ride id with assigned and reason.
# reason is "assigned" or "driver_not_available".
# Start the gRPC server on 0.0.0.0:9005 from the FastAPI startup hook.
# This service is what stops two rides taking the same driver.
