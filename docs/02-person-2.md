# Person 2 — Ride Request, Matching, Dispatch, UI, observability

You own letters **c**, **f** and **h**, plus Ride Request, Matching, Dispatch and
the public web application. You also own the HPAs, the k6 test, the ring page,
the demand page, and the Prometheus/Grafana/Cloud Logging evidence.

Person 1 has already migrated the platform to GCP and implemented Rider,
Driver and the shared library. Person 2 builds on top of that.

## 1. What exists before you start

- GKE cluster `rideshare` in `asia-south1-a`.
- Cloud SQL, Firestore, GCS, Pub/Sub, Secret Manager and Artifact Registry.
- Strimzi Kafka with `ride-events` and `demand-results`.
- Rider and Driver running through Argo CD.
- `services/common/rideshare/store.py` with a GCP backend.
- `services/common/rideshare/zones.py` with live H3 cells.
- `services/common/rideshare/fare.py` with coordinate-based quotes.
- Person 2 and Person 3 service files are comment-only scaffolds.

Do not change Person 3 service logic. Do not rename frozen resources, ports,
topics or environment variables.

## 2. Ride Request Service

Port `8003`. The only service with a public Ingress. It is the BFF for the
browser.

### Endpoints

```text
GET  /                       static/index.html
GET  /api/config             public config: graph, H3 resolution, topics
GET  /api/zones?lat=&lng=&k=3
                             live H3 cells around a coordinate
POST /api/riders             proxy to RIDER_URL/riders
POST /api/drivers            proxy to DRIVER_HTTP/drivers
POST /api/drivers/{id}/presence
                             proxy to DRIVER_HTTP/drivers/{id}/presence
POST /api/ride-requests      create a ride
GET  /api/ride-requests/{id} ride + ride_hops
POST /api/trips/{ride_id}/progress
                             proxy to TRIP_URL
GET  /api/demand             proxy to TRIP_URL/demand
GET  /api/ring?lat=&lng=&k=3 live ring ownership for the sample cells
POST /api/ring/preview       before/after for {nodes, zones}
POST /api/demo/conflict      requires X-Demo-Token
GET  /api/checklist          health and evidence rows
```

### Ride creation

Request body:

```json
{
  "rider_id": "uuid",
  "pickup_lat": 12.9716,
  "pickup_lng": 77.5946,
  "drop_lat": 12.9352,
  "drop_lng": 77.6245,
  "idempotency_key": "optional"
}
```

Steps:

1. Return the existing ride if `idempotency_key` was already used.
2. Compute `pickup_zone = zone_for(pickup_lat, pickup_lng)` and
   `drop_zone = zone_for(drop_lat, drop_lng)`.
3. Insert `ride_requests` with status `REQUESTED`.
4. Call Fare:

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

   If `FARE_ESTIMATE_URL` is empty, use `quote_coordinates(..., imbalance=1.0)`
   and mark `source=local-fallback`.
5. Publish a Pub/Sub job to `MATCH_TOPIC` and record the message id in a
   `QUEUE` hop.
6. Publish `RIDE_REQUESTED` to Kafka.
7. Record hops:
   - REST/SQL for the insert
   - REST/NONE for the Fare call
   - QUEUE/NONE for Pub/Sub
   - EVENT/NONE for Kafka

### Idempotency

`ride_requests.idempotency_key` is unique. On conflict, select the existing row
and return it with the same response shape. The insert and the Pub/Sub publish
must not duplicate a ride.

## 3. Matching Engine

Port `8004`. No Ingress. A daemon thread pulls Pub/Sub.

For each job:

1. Read `ride_id` and `pickup_zone`.
2. Compute `neighbors(zone, k=H3_NEIGHBOR_K)`.
3. Group neighbour cells by `ring.owner(cell)`.
4. For each partition group, call Driver gRPC `GetCandidates` with:
   - `partition_id`
   - `pickup_zone`
   - `neighbor_zones` for that partition
   - `limit`
5. Merge candidates. Do not call the same driver twice.
6. For each candidate, call Dispatch gRPC `Assign`.
7. On success:
   - update `ride_requests` to `ASSIGNED`
   - store `assigned_driver_id` and `assigned_partition_id`
   - publish `RIDE_ASSIGNED`
8. On exhaustion:
   - update to `NO_DRIVER`
9. Delete/ack the Pub/Sub message only after the database update succeeds.
10. Record a `GRPC/NOSQL` hop for `GetCandidates` with candidate count,
    neighbour count and partition count.
11. Record a `GRPC/NOSQL` hop for `Assign` with `assigned` and `reason`.

If the job raises, do not ack it. Pub/Sub redelivers it. `assign` is
idempotent for the same `ride_id`.

## 4. Dispatch Service

- HTTP `8005` for health and metrics.
- gRPC `9005` for `Assign`.
- `Assign` calls `store.assign(partition_id, driver_id, ride_id)`.
- Record a `GRPC/NOSQL` hop on the ride with `assigned` and reason.
- Reason is `assigned` or `driver_not_available`.
- Two matchers cannot both win because Firestore runs the status check and
  update in one transaction.

## 5. Public UI

The page has six sections: Rider, Driver, Trace, Ring, Demand, Checklist. It
talks only to its own origin under `/api/*`.

### Live location

- Use `navigator.geolocation.getCurrentPosition` for the rider's pickup.
- Use `navigator.geolocation.watchPosition` for the driver while online,
  throttled to about 15 seconds.
- Use Leaflet + OpenStreetMap for the map. No API key.
- The rider can drag the pickup marker and click the map for the destination.
- The driver's "Go online here" uses the live location.
- Show the computed H3 cell for pickup, destination and driver.
- If permission is denied, show manual latitude/longitude inputs. Do not fall
  back to a fixed city.

Geolocation requires HTTPS or `localhost`. The GKE Ingress must use HTTPS for
the public demo. Add a reserved static IP and a ManagedCertificate, or run the
demo on `localhost` through port-forward.

### Ring page

- Call `/api/zones?lat=&lng=&k=3` with the live location.
- Show the current ownership for those cells.
- Call `/api/ring/preview` with `nodes=["p0","p1","p2","p3","p4"]` and the same
  cells.
- Show `before`, `after`, `moved`, `stayed`, `moved_fraction`.
- The preview must never change `HASH_NODES`.

### Checklist page

Each row has a title, status (`proven`, `show`, `todo`) and evidence. Prove a row
only from live data:

- health checks green
- a completed ride with every hop
- a ring preview with at least one stayed cell
- a demand window newer than 15 minutes
- Ride Request and Matching replicas above 2 while k6 runs

Terraform, Argo CD, Grafana and Cloud Logging are `show` rows with the exact
command or URL.

## 6. Manifests

Implement these files under `deploy/apps`:

- `ride-request/deployment.yaml`
- `ride-request/hpa.yaml`
- `ride-request/ingress.yaml`
- `matching/deployment.yaml`
- `matching/hpa.yaml`
- `dispatch/deployment.yaml`

Rules:

- image `asia-south1-docker.pkg.dev/PROJECT_ID/rideshare/SERVICE:REPLACE_SHA`
  (write it with `scripts/configure.py --tag SERVICE=TAG`)
- ServiceAccount annotation
  `iam.gke.io/gcp-service-account: rideshare-SERVICE@PROJECT_ID.iam.gserviceaccount.com`
- `envFrom` the `rideshare-secret` and `rideshare-config`
- `SERVICE_NAME`
- non-root UID `65532`
- CPU request `100m`, limit `500m`
- readiness `/readyz`, liveness `/healthz`
- HTTP Service port must be named `http` for PodMonitor
- gRPC ports named `grpc`
- no Ingress except Ride Request
- Kafka client pods mount `rideshare-kafka-cluster-ca-cert` at `/etc/kafka`

HPAs:

- Ride Request and Matching
- min 2, max 6
- CPU target 60 percent
- require the CPU request

Ingress:

- GKE Ingress (`kubernetes.io/ingress.class: gke` or the GKE default class)
- static IP annotation `kubernetes.io/ingress.global-static-ip-name`
- ManagedCertificate for HTTPS
- path `/` to `ride-request:8003`

After the manifests are real, remove the `directory.include` restriction from
`deploy/gitops/rideshare-app.yaml` so Argo CD syncs every service.

## 7. Load test

`loadtest/k6/ride.js` creates riders, drivers, ride requests, and completes
trips. It must produce enough sustained CPU load to push both HPAs above 2
replicas. Run against the public HTTPS URL:

```bash
k6 run -e BASE_URL=https://YOUR_HOST loadtest/k6/ride.js
```

Keep the checklist page open and capture the replica counts.

## 8. Observability

`deploy/platform` starts with `*.yaml.stub` scaffolds so Argo CD can sync an
empty directory safely (`platform-app.yaml` excludes `*.stub`). When you
implement letter **h**, rename each stub to the live name:

- `prometheus.yaml` — Argo CD Application for `kube-prometheus-stack`
- `dashboard.yaml` — Grafana dashboard ConfigMap
- `podmonitor.yaml` — scrape every pod with an `app` label on `/metrics`
- Do **not** deploy Fluent Bit. GKE already ships stdout to Cloud Logging.
  `fluent-bit.yaml.stub` is a reminder only.

Grafana access:

```bash
kubectl -n monitoring port-forward svc/kube-prometheus-stack-grafana 3000:80
```

Cloud Logging query:

```text
resource.type="k8s_container"
resource.labels.namespace_name="rideshare"
jsonPayload.ride_id="YOUR_RIDE_ID"
```

Dataproc logs are under `resource.type="cloud_dataproc_cluster"`. Cloud Run logs
are under `resource.type="cloud_run_revision"`.

## 9. Tests

- `tests/platform/test_shared.py` covers H3 cells, neighbours and ring moves.
- `tests/platform/test_services.py` covers Rider/Driver.
- Add unit tests for the Matching partition grouping function.
- `services/common/tests/test_ring.py` is the independent ring test.
- Use `HASH_NODES=p0,p1,p2,p3` in tests.
- The ring test uses `cells_around(lat, lng, k=3)`, not a fixed list.

## 10. Definition of done

- One ride shows REST, SQL, Pub/Sub, gRPC, Firestore and Kafka hops.
- The same driver cannot be assigned twice.
- The ring page moves only a fraction of live cells when `p4` is added.
- Both HPAs scale above 2 under k6.
- Grafana shows RPS, error rate, p95 latency and node health.
- Cloud Logging contains a ride id from at least two services.
- No fixed `z00`–`z33` or Hyderabad fallback remains in the UI or services.
