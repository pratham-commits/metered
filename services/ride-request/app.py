# Person 2. Public Ride Request Service and the BFF for the web UI. Port 8003.
#
# GET / serves service/static/index.html.
# GET /api/zones returns the 16 zone ids and their centers.
# POST /api/riders proxies to RIDER_URL/riders.
# POST /api/drivers and POST /api/drivers/{id}/presence proxy to DRIVER_HTTP
#   (default http://driver.rideshare.svc.cluster.local:8002).
# POST /api/ride-requests {rider_id, pickup lat/lng, drop lat/lng, idempotency_key}.
#   Return the existing ride when the idempotency key was already used.
#   Derive zones, insert ride_requests status REQUESTED, call Fare for the estimate.
#   If FARE_ESTIMATE_URL is set, POST {pickup_zone, drop_zone} there and mark source lambda.
#   If it is empty, quote_between(..., imbalance 1.0) and mark source local-fallback.
#   Record hops: REST/SQL for the insert, REST/NONE for the estimate.
#   send_job to SQS and publish RIDE_REQUESTED. Record a QUEUE hop with the message id.
# GET /api/ride-requests/{id} returns the ride plus ride_hops in order.
# POST /api/trips/{ride_id}/progress proxies to TRIP_URL.
# GET /api/demand proxies to TRIP_URL/demand.
# GET /api/ring returns live HASH_NODES ownership.
# POST /api/ring/preview {nodes} returns before, after, moved, stayed, moved_fraction.
#   This must not change the live ring.
# POST /api/demo/conflict requires header X-Demo-Token equal to DEMO_TOKEN.
#   Assign a new probe ride id to the same driver. Expect assigned false.
#   Record that result as a GRPC/NOSQL hop on the original ride.
# GET /api/checklist reports health of rider, driver, matching, dispatch, trip, and the sink.
#   HPA row is proven only when Prometheus shows ride-request and matching replicas above 2.
#   Terraform, Argo CD, Grafana, logs, and Flink stay status "show" with the command or screen to open.
