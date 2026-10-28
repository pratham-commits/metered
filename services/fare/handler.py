# Person 3. Fare Service. The only Lambda. Two handlers, one zip.
#
# estimate(event, context): GET /health returns {ok, service: fare}.
#   POST body {pickup_zone, drop_zone}. Read the latest imbalance from DEMAND_TABLE
#   for the pickup zone, default 1.0. Return quote_between as JSON.
# finalize(event, context): S3 event. GetObject the completion JSON.
#   Compute the fare with quote_between on the pickup and drop zones.
#   Insert fare_quotes kind FINAL. Update ride_requests.final_fare_cents and surge.
#   Insert a ride_hops row: service fare, mechanism EVENT, store SQL.
#   Print a JSON log line with event final_fare, ride_id, and amount_cents.
# Database URL comes from SECRET_ARN via Secrets Manager, field "url".
# Do not copy the fare formula into this file. Import rideshare.fare.
