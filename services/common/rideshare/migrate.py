# Person 1. Applied by the schema-migrate Argo CD hook, not by hand.
#
# CREATE TABLE IF NOT EXISTS for riders, drivers, ride_requests, trips, fare_quotes, ride_hops.
# Index ride_hops (ride_id, id).
# ride_requests.rider_id references riders. trips.ride_id references ride_requests.
# ride_requests.idempotency_key is unique. riders.phone and drivers.phone are unique.
# Status values used later: REQUESTED, ASSIGNED, NO_DRIVER, ARRIVING, IN_PROGRESS, COMPLETED.
# python -m rideshare.migrate
