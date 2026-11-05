# Person 3. Fare Service. Cloud Run functions (2nd gen). Two entry points, one source tree.
#
# estimate(request): HTTP entry point. request is a Flask request.
#   GET /health returns {ok, service: fare}.
#   POST body {pickup_zone, drop_zone, pickup_lat, pickup_lng, drop_lat, drop_lng}.
#   Read the latest imbalance from Firestore (rideshare_demand_windows) for the
#   pickup zone, default 1.0. Use quote_coordinates when coordinates are present,
#   otherwise quote_between. Return the quote as JSON.
# finalize(cloud_event): CloudEvent entry point for
#   google.cloud.storage.object.v1.finalized. Ignore objects that are not
#   completions/*.json. Read the completion JSON from GCS and compute the fare with
#   quote_coordinates on the stored pickup/drop coordinates.
#   Insert fare_quotes kind FINAL. Update ride_requests.final_fare_cents and surge.
#   Insert a ride_hops row: service fare, mechanism EVENT, store SQL.
#   Print a JSON log line with event final_fare, ride_id, and amount_cents.
# The database URL comes from Secret Manager secret rideshare-database, field "url".
# Do not copy the fare formula into this file. Import rideshare.fare.
#
# infra/functions only deploys when this file defines both `def estimate(` and
# `def finalize(`. Keep the stubs as comments until those functions exist.
