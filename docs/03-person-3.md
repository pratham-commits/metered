# Person 3 — Trip Tracking, Fare, Demand Analytics

You own letters **b** and **e**, plus Trip Tracking, Fare, Demand Analytics, the
demand sink, the Flink job, and the demand page. Person 1 has already created
the GCP platform, Rider, Driver and the shared library. Person 2 owns the ride
path and the public ride UI. Do not add the demand page to that UI.

## 1. What exists before you start

- Cloud SQL PostgreSQL 16 with the schema from `rideshare.migrate`.
- GCS trip bucket `rideshare-trip-files-PROJECT_ID`.
- Firestore collections `rideshare_driver_live` and
  `rideshare_demand_windows`.
- Pub/Sub is not used by you directly; Trip Tracking publishes Kafka events.
- Strimzi Kafka with `ride-events` and `demand-results`.
- Cloud Run functions Terraform in `infra/functions`.
- Dataproc Terraform in `infra/dataproc`.
- Trip Tracking, Fare and Demand Analytics are comment-only scaffolds.

Do not edit Person 2 service code. Do not rename topics, buckets, ports or
environment variables.

## 2. Trip Tracking Service

Port `8006`. No Ingress.

### Endpoint

```text
POST /trips/{ride_id}/progress
{
  "status": "ARRIVING" | "IN_PROGRESS" | "COMPLETED",
  "lat": 12.9716,
  "lng": 77.5946,
  "distance_km": 4.2,
  "duration_sec": 600
}
```

Rules:

- Upsert `trips`.
- Update `ride_requests.status`.
- Record a `REST/SQL` hop.
- Write the GPS sample to `gps/{ride_id}/{timestamp}.json`.
- Publish `TRIP_UPDATED` to `ride-events`; `zone` is the pickup H3 cell.
- `COMPLETED` requires `distance_km` and `duration_sec`.
- On `COMPLETED`, write `completions/{ride_id}.json` with:

```json
{
  "ride_id": "uuid",
  "rider_id": "uuid",
  "driver_id": "uuid",
  "partition_id": "p1",
  "pickup_zone": "8928308280fffff",
  "drop_zone": "8928308281fffff",
  "pickup_lat": 12.9716,
  "pickup_lng": 77.5946,
  "drop_lat": 12.9352,
  "drop_lng": 77.6245,
  "distance_km": 4.2,
  "duration_sec": 600,
  "completed_at": "2026-10-28T12:00:00Z"
}
```

- Release the driver back to `AVAILABLE`.
- Record an `EVENT/OBJECT` hop with both GCS keys.
- `GET /demand` returns `{topic: "demand-results", windows: [...]}`.

The completion JSON must contain the **actual pickup/drop coordinates**. Fare
uses those coordinates, not the cell centres.

## 3. Fare Service

One Cloud Run function source tree, two entry points.

### 3.1 GCP signatures

`services/fare/handler.py` must expose:

```python
def estimate(request):
    # HTTP entry point. request is a Flask request.
    ...

def finalize(cloud_event):
    # CloudEvent entry point for google.cloud.storage.object.v1.finalized.
    ...
```

The old AWS `estimate(event, context)` and `finalize(event, context)` handlers
stay in the file as commented legacy examples. Do not delete them.

### 3.2 Estimate

Request body:

```json
{
  "pickup_zone": "...",
  "drop_zone": "...",
  "pickup_lat": 12.9716,
  "pickup_lng": 77.5946,
  "drop_lat": 12.9352,
  "drop_lng": 77.6245
}
```

Steps:

1. Read the latest demand window for `pickup_zone` from Firestore. Default
   imbalance `1.0`.
2. If coordinates are present, call
   `quote_coordinates(pickup_lat, pickup_lng, drop_lat, drop_lng, imbalance)`.
3. Otherwise fall back to `quote_between(pickup_zone, drop_zone, imbalance)`.
4. Return the quote as JSON.
5. `GET /health` returns `{ok: true, service: "fare"}`.

### 3.3 Finalize

The Eventarc trigger receives every object in the trip bucket. Ignore anything
whose name does not start with `completions/` and end with `.json`.

For a completion object:

1. Read the JSON from GCS.
2. Use `quote_coordinates` with the stored pickup/drop coordinates.
3. Insert `fare_quotes` with kind `FINAL`.
4. Update `ride_requests.final_fare_cents` and `surge`.
5. Insert a `ride_hops` row: service `fare`, mechanism `EVENT`, store `SQL`.
6. Print a JSON log line with `event=final_fare`, `ride_id`, `amount_cents`.

The function reads the database URL from Secret Manager secret
`rideshare-database`, field `url`.

Do not copy the fare formula into `handler.py`. Import `rideshare.fare`.

### 3.4 Build

`services/fare/build.sh` builds `services/fare/dist/fare.zip` for the
`python312` Cloud Run runtime:

- copy `handler.py` to `main.py` so the Python runtime finds it
- copy `services/fare/requirements.txt`
- copy the shared `rideshare/` package
- zip from inside `dist` so the zip root contains `main.py`,
  `requirements.txt` and `rideshare/`

Cloud Build installs `requirements.txt`; the zip contains source only. The
Cloud Run functions runtime supplies the function framework, so do not bundle
it.

## 4. Demand Analytics and demand sink

### 4.1 Flink job

`services/demand-analytics` is a Maven project for Flink 1.20.

Args:

```text
--bootstrap <kafka-bootstrap> --input ride-events --output demand-results
```

Rules:

- Kafka security protocol `SSL`.
- Truststore from the Strimzi CA (PKCS12 or JKS), supplied by the run script.
- Event time from `event_time`, UTC with `Z`.
- Watermark: bounded out of order 10 seconds.
- Key by `zone` (the H3 cell string).
- Tumbling event-time window of 1 minute.
- Accumulate:
  - unique rider ids for `RIDE_REQUESTED`
  - request count
  - assigned count
  - last `DRIVER_STATUS` per driver in the window
- Emit:
  - `zone`
  - `window_start`
  - `window_end`
  - `unique_riders`
  - `request_count`
  - `assigned_count`
  - `online_drivers`
  - `queue_length = max(0, request_count - assigned_count)`
  - `imbalance = request_count / max(online_drivers, 1)`
- Sink only to `demand-results`.
- Checkpoint every 60 seconds.

Package:

```bash
mvn -q -DskipTests package
gsutil cp target/demand-analytics-1.0.0.jar \
  gs://rideshare-trip-files-PROJECT_ID/flink/demand-analytics.jar
```

### 4.2 Demand sink

Port `8010`. Part of Demand Analytics, not a ninth service.

- Consume `demand-results`, group `demand-sink`, from earliest.
- On each record, `put_demand` with:
  - `zone`
  - `window_start`
  - `window_end`
  - `unique_riders`
  - `request_count`
  - `assigned_count`
  - `online_drivers`
  - `queue_length`
  - `imbalance`
  - `topic`
- If the topic does not exist, catch the error, sleep 5 seconds, retry. Keep the
  thread alive.
- Expose `/healthz`, `/readyz` and `/metrics`.

### 4.3 Demand page

Serve this from Trip Tracking, next to `GET /demand`. It is not a section of
Person 2's public UI, and Trip Tracking stays without an Ingress. Open it with
a port-forward to port `8006`.

The page reads `{topic, windows}` from `GET /demand` and shows, for each
window:

- `zone`
- `unique_riders`
- `request_count`
- `assigned_count`
- `online_drivers`
- `queue_length`
- `imbalance`
- `window_start` and `window_end`
- topic `demand-results`

A window whose `window_end` is newer than 15 minutes is the proof for letter
**e**. The page only displays windows the sink has written. It does not invent
them.

## 5. Infrastructure

### 5.1 Cloud Run functions

`infra/functions` creates:

- `rideshare-fare-estimate` with an HTTP trigger
- `rideshare-fare-final` with an Eventarc `google.cloud.storage.object.v1.finalized`
  trigger on the trip bucket
- a build service account; the runtime service account is `rideshare-fare`,
  created in `infra/platform`
- Secret Manager access for the database URL
- GCS object viewer for the completion file
- Cloud SQL client
- Firestore user
- Eventarc receiver and Cloud Run invoker permissions

Terraform builds the source zip from `services/fare/handler.py`, the common
`rideshare` package and `services/fare/requirements.txt`, uploads it to
`rideshare-function-source-PROJECT_ID`, and skips the function resources if the
handler is missing or still the comment-only scaffold. `scripts/build-fare.sh` can also produce
`services/fare/dist/fare.zip` for inspection.

The Eventarc trigger fires for every object in the bucket. The handler filters
`completions/`.

### 5.2 Dataproc

`infra/dataproc` creates:

- cluster `rideshare-flink`
- image with the `FLINK` optional component
- one master and two workers, internal IP only
- service account `rideshare-dataproc` (IAM comes from `infra/platform`)
- Dataproc staging bucket `rideshare-dataproc-PROJECT_ID` (created by `infra/platform`)
- firewall/network access to the Strimzi internal load-balancer listener on
  port `9095`

The bootstrap script builds the Kafka truststore from the Strimzi CA secret,
uploads it to the Dataproc staging bucket, and the cluster initialization action
installs it at `/opt/kafka/kafka.truststore.jks`. `scripts/run-flink.sh` then
submits the job against the internal load-balancer bootstrap on port `9095`.

### 5.3 Scripts

- `scripts/run-flink.sh` — submit the Flink job to Dataproc.
- `scripts/build-fare.sh` — wrapper around `services/fare/build.sh`, if needed.
- `scripts/check-platform.sh` — keep passing.

## 6. Tests

- Unit-test the completion JSON filter.
- Unit-test the estimate request with mocked Firestore and SQL.
- Unit-test `quote_coordinates` separately in `tests/platform/test_shared.py`.
- Do not require GCP credentials in CI.
- If you add a test for Eventarc, mock the CloudEvent envelope.

## 7. Definition of done

- Completing a trip writes `completions/{ride_id}.json` with coordinates.
- The Fare final function reads it and writes the final amount.
- Cloud Logging shows the final-fare JSON line with the ride id.
- The demand page shows a 1-minute window for an H3 cell.
- `demand-results` is a separate topic from `ride-events`.
- The Flink job runs on Dataproc, not on a local process.
- No AWS resource is required for any of the above.
