# AWS to GCP migration

This document is the short, complete version of the migration. The person guides
contain the copy-paste commands. The AWS resources remain in the repository for
comparison; they are disabled and are not applied by default.

## 1. What stays the same

- Eight services, one public URL.
- REST, gRPC, Pub/Sub/Kafka, SQL, NoSQL, object storage and the completion
  trigger.
- Consistent hashing with partitions `p0,p1,p2,p3`.
- One serverless Fare service with an HTTP estimate and an object-completion
  final trigger.
- Argo CD as the only service deployment path.
- Prometheus and Grafana on the cluster, plus centralized logs.
- The service ports, the database schema, the Kafka event envelope and the
  fare formula.

## 2. What changes

| Concern | AWS baseline | GCP implementation |
|---|---|---|
| Compute | EKS | GKE Standard, zonal `asia-south1-a` |
| SQL | RDS PostgreSQL 16 | Cloud SQL PostgreSQL 16, private IP |
| NoSQL | DynamoDB | Firestore Native |
| Object store | S3 | Cloud Storage |
| Work queue | SQS + DLQ | Pub/Sub topic + subscription + DLQ |
| Event log | MSK | Strimzi Kafka on GKE |
| Images | ECR | Artifact Registry |
| Serverless | Lambda + API Gateway | Cloud Run functions 2nd gen |
| Event trigger | S3 notification | Eventarc GCS finalized object |
| Stream | EMR Flink | Dataproc with Flink |
| Identity | IRSA | Workload Identity |
| Ingress | AWS Load Balancer Controller | GKE Ingress |
| Logs | CloudWatch Logs | Cloud Logging |
| Secrets | Secrets Manager | Secret Manager |
| State | S3 + DynamoDB lock | GCS backend + GCS object generation |
| Zones | Fixed 4x4 Hyderabad grid | Live H3 cells |
| Fare distance | Zone centres | Actual pickup/drop coordinates |

## 3. Resource ownership

### `infra/bootstrap`

- GCS state bucket `rideshare-tfstate-<project-id>`.
- Versioning, uniform bucket-level access, public access prevention.
- Enables the project APIs needed by the other stacks.

### `infra/platform`

- VPC, subnet, secondary ranges, Cloud Router, Cloud NAT, firewall.
- Private Service Access for Cloud SQL.
- GKE Standard cluster and node pool.
- Cloud SQL PostgreSQL 16, database, user, private IP.
- Firestore Native database and composite index.
- GCS trip bucket, lifecycle for `gps/`, function source bucket and Dataproc
  staging bucket.
- Pub/Sub topic, subscription and dead-letter topic.
- Artifact Registry repository and cleanup policy.
- Secret Manager secrets for the database URL and demo token.
- Google service accounts, Workload Identity bindings and IAM.
- Outputs consumed by `infra/k8s` and `infra/functions`.

### `infra/k8s`

- `rideshare`, `monitoring` and `argocd` namespaces.
- Kubernetes Secret and ConfigMap.
- Argo CD Helm release and the two Argo CD Applications.
- Strimzi operator, Kafka cluster, `ride-events` and `demand-results` topics.
- Kafka listeners are TLS with authentication `none` and without a Kafka
  authorization plugin, so Workload Identity pods and Dataproc can connect with
  the cluster CA alone.
- No AWS Load Balancer Controller. GKE Ingress is used later by Person 2.
- `deploy/platform` keeps `*.yaml.stub` scaffolds until Person 2 renames them;
  `platform-app.yaml` excludes `*.stub` so Argo CD syncs cleanly.

### `infra/functions`

- Cloud Run function `rideshare-fare-estimate` with an HTTP trigger.
- Cloud Run function `rideshare-fare-final` with an Eventarc GCS trigger.
- Service accounts, invoker permissions and Secret Manager access.
- Outputs the estimate URL for `infra/k8s`.

### `infra/dataproc`

- Dataproc cluster `rideshare-flink` with the `FLINK` optional component.
- Uses the platform Dataproc staging bucket, a truststore initialization action
  and internal networking.
- The Flink JAR is uploaded to the trip bucket; `scripts/run-flink.sh` submits
  the job.

## 4. Code layout after migration

```text
services/common/rideshare/
  aws.py       Legacy AWS adapter. Kept and callable with STORAGE_BACKEND=aws.
  gcp.py       GCP adapter: Firestore, Pub/Sub, GCS, Kafka.
  store.py     Chooses gcp or aws from STORAGE_BACKEND. Default gcp.
  zones.py     Live H3 cells. No fixed bounding box.
  fare.py      quote_coordinates plus a quote_between compatibility wrapper.
  hashring.py  Unchanged consistent-hash ring.
```

Services import `from rideshare.store import get_store`. The AWS tests still
import `rideshare.aws.Store` directly and continue to run with Moto.

## 5. Live location and H3

The previous implementation mapped a coordinate into a fixed 4x4 grid over a
Hyderabad box. That is removed.

- `zone_for(lat, lng)` uses `h3.latlng_to_cell` at resolution 8.
- `center(zone)` uses `h3.cell_to_latlng`.
- `neighbors(zone, k=1)` uses `h3.grid_disk`.
- `cells_around(lat, lng, k=3)` generates the live sample used by the ring page.
- `all_zones()` is removed; no code enumerates a fixed world.
- Matching groups H3 neighbour cells by partition owner and calls the Driver
  service once per partition.

Browser location is captured with `navigator.geolocation`. Pickup is the live
location, the destination is selected on a Leaflet/OpenStreetMap map, and the
driver uses live location for presence. Geolocation requires HTTPS or
`localhost`. A denied permission falls back to manual coordinates; there is no
silent default city.

## 6. GCP adapter contract

`services/common/rideshare/gcp.py` implements the same methods as the AWS store:

| Method | GCP implementation |
|---|---|
| `put_driver(item)` | Firestore set on `rideshare_driver_live/{partition}__{driver}` |
| `set_presence(item, partitions)` | Firestore transaction: remove old partition docs, set target |
| `query_available(partition, zones)` | Firestore query by `partition_id`, filter status/zone |
| `assign(partition, driver, ride)` | Firestore transaction, idempotent for the same ride |
| `release(partition, driver)` | Firestore update back to `AVAILABLE` |
| `put_object(key, body)` | GCS upload to `TRIP_BUCKET` |
| `send_job(body)` | Pub/Sub publish to `MATCH_TOPIC` |
| `receive_jobs(limit)` | Pub/Sub pull from `MATCH_SUBSCRIPTION` |
| `delete_job(ack_id)` | Pub/Sub acknowledge |
| `latest_demand(zone)` | Firestore query by zone, newest `window_start` |
| `latest_all()` | Firestore recent windows grouped by zone |
| `put_demand(item)` | Firestore deterministic document id |
| `publish(event)` | Kafka `ride-events` |
| `publish_topic(topic, event)` | Kafka topic argument |

Kafka TLS uses `KAFKA_SSL_CA_FILE` mounted from the Strimzi cluster CA secret.
`KAFKA_SSL_CHECK_HOSTNAME=false` is the default because the internal listener
uses service DNS and the Dataproc listener uses an internal load-balancer IP.

## 7. Environment changes

New GCP variables:

```text
STORAGE_BACKEND=gcp
GCP_PROJECT
FIRESTORE_DATABASE=(default)
DRIVER_COLLECTION=rideshare_driver_live
DEMAND_COLLECTION=rideshare_demand_windows
MATCH_TOPIC=rideshare-match-jobs
MATCH_SUBSCRIPTION=rideshare-match-jobs-sub
KAFKA_SSL_CA_FILE=/etc/kafka/ca.crt
H3_RESOLUTION=8
H3_NEIGHBOR_K=1
```

Legacy AWS variables kept for `STORAGE_BACKEND=aws`:

```text
AWS_REGION
AWS_ENDPOINT_URL
DRIVER_TABLE
DEMAND_TABLE
MATCH_QUEUE_URL
```

## 8. Migration steps

1. Create the GCP project, link billing, and authenticate.
2. Apply `infra/bootstrap` and create the state bucket.
3. Apply `infra/platform`. This takes the longest because of GKE and Cloud SQL.
4. Build and push Rider and Driver images.
5. Apply `infra/k8s`. Argo CD installs and syncs Rider/Driver/migrate.
6. Implement the Fare handler and apply `infra/functions`.
7. Run the Person 2 implementation and push images.
8. Run the Person 3 implementation and build the Flink JAR.
9. Apply `infra/dataproc` only for the stream demo.
10. Run the full viva script in `docs/00-overview.md`.

## 9. Legacy AWS preservation

- `services/common/rideshare/aws.py` is unchanged except for the removal of the
  fixed-zone dependency in `latest_all`.
- AWS Terraform files are retained but commented out. The `.tf` files still
  parse; every AWS block starts with `#`.
- AWS manifests are retained in comments next to the GCP image and service
  account lines.
- `docker-compose.yml` keeps the LocalStack service for reference but the
  default Rider/Driver path uses GCP emulators.
- The old person guides are replaced by GCP guides. The AWS mapping remains in
  this migration document.

## 10. Validation

```bash
.venv/bin/python -m pytest -q tests/platform
scripts/check-platform.sh
terraform -chdir=infra/bootstrap fmt -check
terraform -chdir=infra/platform fmt -check
terraform -chdir=infra/k8s fmt -check
terraform -chdir=infra/functions fmt -check
terraform -chdir=infra/dataproc fmt -check
terraform -chdir=infra/k8s init -backend=false
terraform -chdir=infra/k8s validate
```

The AWS tests run without credentials. The GCP adapter tests use mocked Google
clients. `terraform validate` checks providers and expressions; it does not
create resources.

## 11. Known risks

- Dataproc's packaged Flink version must match the Flink connector used by the
  Person 3 job. Check `gcloud dataproc clusters describe` before the demo.
- Dataproc must reach the Strimzi internal load-balancer listener. Verify the
  CA and broker DNS/IP before the stream demo.
- Firestore composite index `zone + window_start` must be READY before the
  demand page is used.
- Cloud Run function 2nd gen builds can take several minutes on the first
  deploy.
- GKE Ingress needs a reserved static IP and a ManagedCertificate for HTTPS.
  Browser geolocation will not work on plain HTTP except on localhost.
- Cloud SQL private IP requires Private Service Access to be READY.
- Strimzi TLS requires the CA secret to be mounted in every Kafka client pod.
- The 3-person group split is 3/3/2 because 8 services cannot split into three
  equal pairs. Document the exception in `task_division.txt`.
