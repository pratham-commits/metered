# Person 1 — GCP platform, Rider, Driver

You own letters **a**, **d**, and **g**, plus Rider Service and Driver Service.
You also own the shared Python package, the image-push script, the GCP
emulators, and the platform that Person 2 and Person 3 build on.

The AWS implementation is retained for comparison. It is disabled; do not apply
it. GCP is the default.

Replace only these tokens:

- `PROJECT_ID` — GCP project id, for example `rideshare-prod-123456`
- `REPLACE_SHA` — output of `scripts/push.sh`, after each image build

Pass the Argo CD clone URL as `github_repo` to the `infra/k8s` Terraform stack;
the two `deploy/gitops` Application files must point at the same repository.

Region is `asia-south1`. Zone is `asia-south1-a`.

## 0. Tools and access

```bash
brew install --cask google-cloud-sdk
brew install terraform kubectl helm jq
gcloud auth login
gcloud auth application-default login
gcloud config set project PROJECT_ID
gcloud services enable serviceusage.googleapis.com cloudresourcemanager.googleapis.com
terraform version
docker version
python3.12 --version
```

The account needs Owner or Editor on the project, plus permission to create
service accounts, GKE, Cloud SQL, Firestore, Pub/Sub, GCS, Artifact Registry,
Secret Manager, Cloud Run, Eventarc and Dataproc.

## 1. Bootstrap the project

`infra/bootstrap/gcp-versions.tf` uses the Google provider and a local backend.
`infra/bootstrap/gcp-main.tf` creates:

- `gs://rideshare-tfstate-PROJECT_ID`
- object versioning, uniform bucket-level access and public access prevention
- the project APIs used by the other stacks

Apply:

```bash
terraform -chdir=infra/bootstrap init
terraform -chdir=infra/bootstrap apply -var="project_id=PROJECT_ID"
```

If the bucket name is taken, change the suffix in `infra/bootstrap/gcp-main.tf`
and in every GCS backend block.

## 2. Platform Terraform

Every stack uses a GCS backend:

```hcl
backend "gcs" {
  bucket = "rideshare-tfstate-PROJECT_ID"
  prefix = "platform"
}
```

Terraform backends cannot read variables. Replace `PROJECT_ID` in the backend
blocks before `terraform init`, or run `scripts/configure.py`.

### 2.1 Network

`infra/platform/gcp-network.tf` creates:

- `rideshare-vpc` `10.20.0.0/16`
- `rideshare-subnet` `10.20.0.0/20` in `asia-south1`
- secondary ranges `rideshare-pods` `10.24.0.0/14` and
  `rideshare-services` `10.28.0.0/20`
- Cloud Router and Cloud NAT for private nodes
- firewall rules for internal traffic, health checks and Kafka
- Private Service Access for Cloud SQL

Private Google Access is enabled on the subnet so nodes can reach Artifact
Registry, Cloud Logging and Cloud Storage without public IPs.

### 2.2 GKE

`infra/platform/gke.tf` creates a **zonal** GKE Standard cluster:

- name `rideshare`
- location `asia-south1-a`
- VPC-native networking with the pod/service secondary ranges
- Workload Identity enabled
- release channel `REGULAR`
- node pool `default`, `e2-standard-2`, min 2, max 4, autoscaling
- `GKE_METADATA` on the node pool
- horizontal pod autoscaling and HTTP load balancing addons enabled
- Cloud Logging and Cloud Monitoring enabled

No AWS Load Balancer Controller and no EBS CSI driver are created.

### 2.3 Data

`infra/platform/gcp-data.tf` creates:

- Cloud SQL `rideshare-pg`, PostgreSQL 16, `db-f1-micro`, zonal, private IP,
  20 GB SSD, backups enabled, deletion protection disabled for the course
- database `rideshare`, user `rideshare`, random password
- Firestore Native `(default)` in `asia-south1`
- composite index `rideshare_demand_windows`: `zone` ascending,
  `window_start` descending
- GCS `rideshare-trip-files-PROJECT_ID`, uniform access, versioning, lifecycle
  for `gps/` after 7 days
- GCS `rideshare-function-source-PROJECT_ID`
- GCS `rideshare-dataproc-PROJECT_ID` for the Flink staging area
- Pub/Sub `rideshare-match-jobs`, subscription `rideshare-match-jobs-sub`, DLQ
  `rideshare-match-jobs-dlq`, retry policy, 5 delivery attempts
- Secret Manager `rideshare-database` with the URL and fields, and
  `rideshare-demo-token`

### 2.4 Artifact Registry

`infra/platform/artifact_registry.tf` creates:

- Docker repository `rideshare` in `asia-south1`
- cleanup policy keeping the last 10 versions

The image prefix is:

```text
asia-south1-docker.pkg.dev/PROJECT_ID/rideshare/SERVICE
```

### 2.5 Kafka

`infra/platform` does not install Kafka because it needs the GKE cluster
credentials. `infra/k8s/gcp-kafka.tf` installs the Strimzi operator, the
`rideshare-kafka` cluster, both topics and a second internal load-balancer
listener on port `9095` so Dataproc can reach Kafka from the same VPC. GKE
clients use the internal listener on `9094`.

### 2.6 IAM and Workload Identity

`infra/platform/gcp-iam.tf` creates one Google service account per Kubernetes
service account:

| KSA | GSA | Roles |
|---|---|---|
| `rider` | `rideshare-rider` | logging, monitoring, trace |
| `driver` | `rideshare-driver` | logging, monitoring, trace, `datastore.user` |
| `ride-request` | `rideshare-ride-request` | logging, monitoring, trace, `pubsub.publisher` |
| `matching` | `rideshare-matching` | logging, monitoring, trace, `datastore.user`, Pub/Sub publisher and subscriber |
| `dispatch` | `rideshare-dispatch` | logging, monitoring, trace, `datastore.user`, Pub/Sub publisher and subscriber |
| `trip-tracking` | `rideshare-trip-tracking` | logging, monitoring, trace, `datastore.user`, `pubsub.publisher`; `objectCreator` on the trip bucket |
| `demand-sink` | `rideshare-demand-sink` | logging, monitoring, trace, `datastore.user` |
| `fare` | `rideshare-fare` | logging, monitoring, trace, `cloudsql.client`, `datastore.user`; `objectViewer` on the trip bucket; the functions stack also adds `secretmanager.secretAccessor` |
| `eventarc` | `rideshare-eventarc` | `eventarc.eventReceiver`, `pubsub.publisher`; `run.invoker` on the final function |
| `dataproc` | `rideshare-dataproc` | `dataproc.worker`, `pubsub.publisher`, `datastore.user`, `storage.objectAdmin` on the Dataproc staging bucket |

Each Kubernetes GSA is bound with `roles/iam.workloadIdentityUser` to:

```text
serviceAccount:PROJECT_ID.svc.id.goog[rideshare/KSA]
```

The Kubernetes manifests annotate each ServiceAccount with:

```yaml
iam.gke.io/gcp-service-account: rideshare-driver@PROJECT_ID.iam.gserviceaccount.com
```

### 2.7 Apply

```bash
terraform -chdir=infra/platform init
terraform -chdir=infra/platform apply -var="project_id=PROJECT_ID"
terraform -chdir=infra/platform output
```

Cloud SQL private IP can take 5–15 minutes.

## 3. Shared Python library

`services/common/requirements.txt` now includes:

```text
h3
google-cloud-firestore
google-cloud-storage
google-cloud-pubsub
```

`services/common/rideshare/zones.py` is H3-backed:

- `zone_for(lat, lng)` returns an H3 cell at `H3_RESOLUTION`
- `center(zone)` returns the cell centroid
- `neighbors(zone, k=1)` returns the grid disk
- `cells_around(lat, lng, k=3)` returns a live sample for the ring page
- `all_zones()` is removed

`services/common/rideshare/fare.py` adds:

```python
quote_coordinates(lat1, lng1, lat2, lng2, imbalance)
```

`quote_between` remains as a compatibility wrapper that uses cell centres.

`services/common/rideshare/store.py` chooses the backend:

```text
STORAGE_BACKEND=gcp  -> rideshare.gcp.get_store()
STORAGE_BACKEND=aws  -> rideshare.aws.get_store()
```

The AWS module is unchanged except that `latest_all()` no longer calls
`all_zones()`. It scans the demand table and groups by zone, so the legacy tests
stay valid.

`services/common/rideshare/gcp.py` implements Firestore, Pub/Sub, GCS and Kafka.
Read that file before changing the service code.

## 4. Rider and Driver

`services/rider/app.py` is unchanged. It uses Cloud SQL only.

`services/driver/app.py` changes:

- imports `get_store` from `rideshare.store`
- computes the H3 cell from the browser's live latitude/longitude
- validates an optional client-supplied cell
- writes Firestore and publishes `DRIVER_STATUS`

The driver never calls a geocoding service. The browser sends coordinates; the
server computes the cell.

Tests use the AWS store through `STORAGE_BACKEND=aws` or by monkeypatching
`get_store`, so they do not need GCP credentials.

## 5. Kubernetes

`infra/k8s` uses the GKE endpoint and CA from `infra/platform` outputs and a
Google access token from `data.google_client_config`.

It creates:

- namespaces `rideshare`, `monitoring` and `argocd`
- Kubernetes Secret `rideshare-secret` from the platform Terraform state
- ConfigMap `rideshare-config`
- Argo CD Helm release
- the two Argo CD Applications
- Strimzi operator
- Kafka cluster `rideshare-kafka`
- `ride-events` and `demand-results` topics
- no AWS Load Balancer Controller and no metrics-server Helm release

Apply:

```bash
gcloud container clusters get-credentials rideshare \
  --zone=asia-south1-a --project=PROJECT_ID
terraform -chdir=infra/k8s init
terraform -chdir=infra/k8s apply \
  -var="github_repo=REPO_URL" \
  -var="fare_estimate_url="
kubectl -n argocd get applications
kubectl -n rideshare get pods
```

Argo CD is a ClusterIP service. Open it with:

```bash
kubectl -n argocd port-forward svc/argocd-server 8080:443
```

The initial admin password is in the `argocd-initial-admin-secret` Secret.

### Strimzi and TLS

The Kubernetes manifests mount:

```yaml
volumeMounts:
  - name: kafka-ca
    mountPath: /etc/kafka
    readOnly: true
volumes:
  - name: kafka-ca
    secret:
      secretName: rideshare-kafka-cluster-ca-cert
      items:
        - key: ca.crt
          path: ca.crt
```

The ConfigMap sets:

```text
KAFKA_SECURITY_PROTOCOL=SSL
KAFKA_SSL_CA_FILE=/etc/kafka/ca.crt
KAFKA_SSL_CHECK_HOSTNAME=false
```

Strimzi listeners use TLS with `authentication.type: none` and **no**
`authorization` block. Adding `authorization.type: simple` without Kafka users
denies every client. `scripts/bootstrap-gcp.sh` builds the Dataproc truststore
from the PEM `ca.crt` in `rideshare-kafka-cluster-ca-cert` (not a PKCS12).

## 6. Images

`scripts/push.sh SERVICE` builds for `linux/amd64` and pushes to Artifact
Registry:

```bash
./scripts/push.sh rider
./scripts/push.sh driver
```

Then write both tags and commit the diff:

```bash
.venv/bin/python scripts/configure.py --project-id PROJECT_ID \
  --rider-tag RIDER_TAG --driver-tag DRIVER_TAG
```

This updates `deploy/apps/rider/deployment.yaml`,
`deploy/apps/driver/deployment.yaml` and `deploy/apps/migrate/job.yaml`.
Other services use `--tag SERVICE=TAG`. Argo CD rolls the pods.

## 7. Fare functions and Dataproc

Person 3 owns the code. Person 1 applies the infrastructure after the artifacts
exist:

```bash
# after services/fare/handler.py defines estimate and finalize
terraform -chdir=infra/functions init
terraform -chdir=infra/functions apply -var="project_id=PROJECT_ID"

# after the Kafka truststore is staged in gs://rideshare-dataproc-PROJECT_ID
terraform -chdir=infra/dataproc init
terraform -chdir=infra/dataproc apply -var="project_id=PROJECT_ID"
```

`infra/functions` creates the HTTP estimate function and the Eventarc-triggered
final function. `infra/dataproc` creates the Flink cluster.

## 8. Local development

```bash
uv venv --python 3.12 .venv
uv pip install --python .venv/bin/python -r requirements-dev.txt
docker compose up --build
```

Compose starts:

- PostgreSQL
- Firestore emulator
- Pub/Sub emulator
- fake GCS server
- Kafka in PLAINTEXT
- migrate, rider and driver with `STORAGE_BACKEND=gcp`

The AWS LocalStack service remains in the file for reference but is not used by
the GCP services.

## 9. Tests

```bash
.venv/bin/python -m pytest -q tests/platform services/common/tests/test_ring.py
scripts/check-platform.sh
```

The suite contains:

- AWS store tests with Moto
- GCP store tests with mocked clients
- H3 round-trip, neighbour and ring tests
- Rider/Driver service tests
- configure script tests
- Terraform syntax and YAML parsing

Commit the `infra/*/.terraform.lock.hcl` files with the GCP stacks so everyone
resolves the same Google provider versions. Do not commit `.terraform/` or
`*.tfstate`.

## 10. Teardown

```bash
terraform -chdir=infra/dataproc destroy -auto-approve -var="project_id=PROJECT_ID"
terraform -chdir=infra/functions destroy -auto-approve -var="project_id=PROJECT_ID"
terraform -chdir=infra/k8s destroy -auto-approve -var="github_repo=REPO_URL"
terraform -chdir=infra/platform destroy -auto-approve -var="project_id=PROJECT_ID"
```

Delete the bootstrap bucket manually only when the project is finished.
