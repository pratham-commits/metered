# Ride Sharing operator runbook

This is the document for bringing the GCP project back, checking every screen, and shutting it down so the only thing left is the Terraform state bucket. It was written against the repository at `https://github.com/pratham-commits/metered.git`, branch `main`, and against the stack that was actually running in project `metered-513804`.

Where `docs/platform-runbook.md` or `docs/02-person-2.md` disagree with what ran, this file is the one to follow. The older guides still say `PROJECT_ID`, `YOUR_HOST`, and `REPO_URL`. Those values are filled in below.

Do not delete `gs://rideshare-tfstate-metered-513804`. Do not rename frozen resources: the VPC, subnet, cluster, node pool, Cloud SQL instance, database name, Pub/Sub topics and subscription, buckets, Kafka cluster, Kubernetes service names, or ports. Argo CD is the only deploy path for those Deployments. Never `kubectl set image`. Stopping pods does not stop the bill.

## 1. What this project is

Eight services for a ride-sharing demo on Google Cloud, region `asia-south1`, zone `asia-south1-a`. Riders and drivers never call GCP themselves. They use one public URL, the Ride Request service. Every other call stays inside the VPC.

A ride, as the group designed it:

1. Ride Request proxies a rider and a driver to Rider Service and Driver Service. Profiles land in Cloud SQL. Driver presence is an H3 cell, hashed onto the ring `p0,p1,p2,p3`, and written to Firestore.
2. Ride Request inserts `ride_requests`, publishes a match job to Pub/Sub, and publishes `RIDE_REQUESTED` to Kafka topic `ride-events`.
3. Matching pulls Pub/Sub, calls Driver gRPC `GetCandidates`, then Dispatch gRPC `Assign`.
4. Trip Tracking, the Fare Cloud Run functions, and Flink on Dataproc are Person 3. They are not running.

The public page is `services/ride-request/static/index.html`, served at `/`. The nav is Ride, Trace, Ring, Checklist, plus Switch role (one browser tab as the rider, one as the driver). There is no Demand item on this page.

Ownership:

| Person | Running now | Still to write |
|---|---|---|
| Person 1 | Terraform, GKE, Cloud SQL, Firestore, GCS, Pub/Sub, Artifact Registry, IAM, Strimzi Kafka, Rider, Driver, migrate job | — |
| Person 2 | Ride Request, Matching, Dispatch, the public UI, both HPAs, k6, Prometheus, Grafana | — |
| Person 3 | Nothing deployed | Trip Tracking, Fare, Demand Analytics, demand sink, the demand page |

Git remote: `https://github.com/pratham-commits/metered.git`. Argo CD `targetRevision` is `main`.

## 2. What is running, and what Person 3 still writes

After teardown none of this is running. The names below are what the next apply creates. Do not rename them.

These were created by `infra/platform` and `infra/k8s`. Functions and Dataproc were never applied. There is no `functions/` or `dataproc/` prefix in the state bucket. Cluster `rideshare-flink` did not exist. Cloud Run had no services. The state bucket still has prefixes `platform/` and `k8s/` from the destroy. Keep them.

### Platform (`infra/platform`, state prefix `platform/`)

| Thing | Name |
|---|---|
| Project | `metered-513804` |
| VPC | `rideshare-vpc`, custom mode (no VPC CIDR), routing `GLOBAL` |
| Subnet | `rideshare-subnet`, `10.20.0.0/20`, Private Google Access on |
| Pods range | `rideshare-pods`, `10.24.0.0/14` |
| Services range | `rideshare-services`, `10.28.0.0/20` |
| Internal firewall sources | `10.20.0.0/16`, `10.24.0.0/14`, `10.28.0.0/20` (the `/16` is wider than the subnet) |
| Cloud Router | `rideshare-router` |
| Cloud NAT | `rideshare-nat`, `AUTO_ONLY`, all subnet ranges |
| Private Service Access | global internal address `rideshare-psa`, prefix length 16. The torn-down allocation was `10.116.0.0/16`. `infra/platform/gcp-network.tf` does not set `address`, so the next apply can receive a different `/16`. |
| GKE | cluster `rideshare`, zonal `asia-south1-a`, `deletion_protection = false`, private nodes, public control-plane endpoint, master CIDR `172.16.0.0/28` |
| Control-plane allowlist | `master_authorized_networks` uses `var.admin_cidr` (default `0.0.0.0/0`) |
| Node pool | `default`, `e2-standard-2`, min 2, max 4, 50 GB `pd-balanced`, image `COS_CONTAINERD` |
| Node service account | `rideshare-gke-node@metered-513804.iam.gserviceaccount.com` (`roles/artifactregistry.reader` is on this account) |
| Cloud SQL | `rideshare-pg`, `POSTGRES_16`, `db-f1-micro`, zonal, private IP only (`ipv4_enabled = false`), 20 GB `PD_SSD`, `deletion_protection = false` |
| Database / user | database `rideshare`, user `rideshare`, password a random 24 characters with no symbols |
| Secret Manager | `rideshare-database` (JSON, field `url` is the SQLAlchemy URL) and `rideshare-demo-token` |
| Firestore | Native database `(default)` in `asia-south1`, deletion policy `DELETE` |
| Collections | `rideshare_driver_live`, `rideshare_demand_windows` |
| Pub/Sub | topic `rideshare-match-jobs`, subscription `rideshare-match-jobs-sub` (dead letter after 5 attempts), topic `rideshare-match-jobs-dlq` |
| Artifact Registry | `asia-south1-docker.pkg.dev/metered-513804/rideshare` |
| Buckets | `rideshare-trip-files-metered-513804`, `rideshare-function-source-metered-513804`, `rideshare-dataproc-metered-513804` |
| Workload Identity | `rideshare-<service>@metered-513804.iam.gserviceaccount.com` |

Workload accounts from `infra/platform/gcp-iam.tf`: `rideshare-driver`, `rideshare-matching`, `rideshare-dispatch`, `rideshare-ride-request`, `rideshare-rider`, `rideshare-fare`, `rideshare-trip-tracking`, `rideshare-demand-sink`, `rideshare-demand-analytics`, `rideshare-eventarc`, `rideshare-dataproc`.

Ride Request's Google service account is `rideshare-ride-request@metered-513804.iam.gserviceaccount.com`. It needs `roles/datastore.user` or Firestore reads return 403 and the rider map never gets a car (`GET /api/live-drivers` and `GET /api/drivers/{id}/location` fail). That binding is already in `infra/platform/gcp-iam.tf`. Do not remove it.

The public static IP name `rideshare-ip` is not in Terraform. It was created by hand. The Ingress annotation `kubernetes.io/ingress.global-static-ip-name: rideshare-ip` points at it. The last address was `136.81.121.175`. The ManagedCertificate domain in `deploy/apps/ride-request/ingress.yaml` is `136.81.121.175.nip.io`. That address was deleted during teardown. Section 7 reserves a new one.

### Kubernetes (`infra/k8s`, state prefix `k8s/`)

Terraform installs:

- Namespaces `rideshare`, `monitoring`, `argocd`.
- Secret `rideshare-secret` in `rideshare`, keys `DATABASE_URL` and `DEMO_TOKEN` only. `MAPBOX_ACCESS_TOKEN` is not in this secret. See the gotchas.
- Secret `rideshare-secret` in `monitoring`, keys `admin-user=admin` and `admin-password` set to the same demo token.
- ConfigMap `rideshare-config` (project, Firestore, Pub/Sub, Kafka, hash ring `p0,p1,p2,p3`, H3 resolution 8, neighbour k 1, empty `FARE_ESTIMATE_URL` until Person 3).
- Helm release `argocd`, chart `argo-cd` version `10.11.6`, server Service type `ClusterIP`.
- Helm chart `infra/k8s/charts/applications`, release `rideshare-applications`. It creates the Argo CD Application objects from `deploy/gitops/rideshare-app.yaml` and `deploy/gitops/platform-app.yaml` and injects `repoURL` from `-var=github_repo`.

Strimzi, also from `infra/k8s/gcp-kafka.tf`:

- Operator chart `strimzi-kafka-operator` version `0.48.0` in namespace `kafka`, `watchAnyNamespace=true`. Version `0.45` crashes on GKE 1.36 because `/version` includes `emulationMajor`. Do not downgrade the chart.
- Kafka cluster `rideshare-kafka`, Kafka `4.0.0`, KRaft, node pool `dual-role` with roles `controller` and `broker`, 3 replicas, ephemeral JBOD (not a persistent disk).
- Listeners: internal TLS on `9094`, external TLS on `9095` with `networking.gke.io/load-balancer-type: Internal`.
- Bootstrap for pods: `rideshare-kafka-kafka-bootstrap.rideshare.svc.cluster.local:9094`.
- CA secret `rideshare-kafka-cluster-ca-cert`, key `ca.crt`, mounted at `/etc/kafka/ca.crt`. `KAFKA_SSL_CHECK_HOSTNAME=false`. There is no `ca.p12` and no `ca.password` on this secret.
- Topics `ride-events` (6 partitions, replication 3) and `demand-results` (3 partitions, replication 3) are Kubernetes `KafkaTopic` objects in this file. `deploy/apps/topics/job.yaml` is still a comment and is not in the Argo include.

### What Argo CD syncs

Changing `deploy/gitops/*.yaml` in git does not update the live Application object. The Application spec is rendered by the Helm release at `terraform -chdir=infra/k8s apply` time. After you edit an include list or `targetRevision`, run that apply again.

Files under `deploy/apps` and `deploy/platform` are synced by those Applications from git `main`.

`deploy/gitops/rideshare-app.yaml` include, and only this include:

```text
migrate/job.yaml
rider/deployment.yaml
driver/deployment.yaml
ride-request/deployment.yaml
ride-request/hpa.yaml
ride-request/ingress.yaml
matching/deployment.yaml
matching/hpa.yaml
dispatch/deployment.yaml
```

The HPA reader Role and RoleBinding live inside `deploy/apps/ride-request/hpa.yaml`. A separate `rbac.yaml` is not in the include. Leave the Role in that file.

`deploy/gitops/platform-app.yaml` syncs `deploy/platform`, excluding `*.stub`, `.gitkeep`, and `README.md`, into namespace `monitoring`. That is what installs the Prometheus Application.

### Services that actually run

| Service | Ports | Ingress | Tag still written in the YAML |
|---|---|---|---|
| rider | 8001 | no | `rider:e71c841` |
| driver | HTTP 8002, gRPC 9002 | no | `driver:6c6e678` |
| ride-request | 8003 | yes, the only one | `ride-request:ca83bd0` |
| matching | 8004 | no | `matching:ca83bd0` |
| dispatch | HTTP 8005, gRPC 9005 | no | `dispatch:517ef2c` |
| trip-tracking | 8006 | no (Person 3 scaffold) | not deployed |
| demand-sink | 8010 | no (Person 3 scaffold) | not deployed |
| migrate job `schema-migrate` | — | — | the rider image, `rider:e71c841` |

Every running service exposes `/healthz`, `/readyz`, and `/metrics`. Pods run as UID 65532. CPU request is `100m`, limit `500m`. The two HPAs (ride-request and matching) target 60% of that `100m` request, min 2, max 6.

Git tip that was pushed is `ce064e2`. The deployment YAML on that commit still names the tags in the table. Those tags died with Artifact Registry. They will not pull. A rebuild writes new tags. Do not try to run the old ones. Section 8 is how the SHA is chosen.

### Person 3, not deployed

These files are comments. `scripts/push.sh` accepts the names `trip-tracking` and `demand-sink`, but their Dockerfiles are not Dockerfiles yet, so a build fails.

- `services/trip-tracking/app.py` and `services/trip-tracking/Dockerfile` — port 8006, no Ingress.
- `services/demand-sink/app.py` and `services/demand-sink/Dockerfile` — port 8010.
- `services/fare/handler.py` — comments only. The Cloud Functions and Cloud Run services in `infra/functions` are created only when the file contains real lines `def estimate(` and `def finalize(`. The build service account and IAM in that stack are not behind that `count`. Do not apply it until section 14.
- `services/demand-analytics` — Flink job, main class `edu.bits.rideshare.DemandJob`. `scripts/run-flink.sh` submits it.
- Terraform `infra/functions` (state prefix `functions/`) and `infra/dataproc` (state prefix `dataproc/`). Neither prefix exists. Neither stack was applied.
- The demand page is section 4.3 of `docs/03-person-3.md`. Trip Tracking serves it next to `GET /demand`. Open it with a port-forward to port 8006. It is not a section of the public UI.

When that code exists, section 14 is the apply order. Destroy Dataproc the same day. It is the cost spike.

## 3. Tools

From `docs/platform-runbook.md` and `README.md`:

```bash
brew install --cask google-cloud-sdk
brew install terraform kubectl helm jq
```

Python 3.12 lives in the repo virtualenv:

```bash
uv venv --python 3.12 .venv
uv pip install --python .venv/bin/python -r requirements-dev.txt
```

Docker on this Mac is Colima. The machine is arm64. GKE nodes are amd64. Images must be `linux/amd64`. `scripts/push.sh` already passes `--platform linux/amd64`.

```bash
colima start
docker context use colima
docker info
```

The socket is `unix:///Users/prathamshah/.colima/default/docker.sock`. If `docker info` fails, run `colima start` again.

k6 is not installed by anything in the repo. On this machine the binary is `/opt/homebrew/bin/k6`. The load test is `k6 run`. Python commands in this file use `.venv/bin/python`.

Check:

```bash
gcloud config get-value project
terraform version
kubectl version --client
helm version
docker version
```

Terraform in this repo needs `>= 1.9.0`.

Local checks, which do not create GCP resources and do not replace GKE:

```bash
.venv/bin/python -m pytest -q tests/platform
scripts/check-platform.sh
docker compose up
```

`docker compose up` starts Postgres 16, the Firestore emulator, the Pub/Sub emulator, fake GCS, a single-node Kafka, the migrate job, Rider on `127.0.0.1:8001`, and Driver on `127.0.0.1:8002` and `127.0.0.1:9002`. It does not start Ride Request, Matching, Dispatch, or GKE.

`scripts/bootstrap-gcp.sh` is not the bring-up. It applies `infra/k8s` before any image exists, and it does not reserve `rideshare-ip`. Use sections 6 through 9 instead. The truststore upload at the bottom of that script matters only on the Dataproc day (section 14).

## 4. Login

```bash
gcloud auth login
gcloud auth application-default login
gcloud config set project metered-513804
gcloud services enable serviceusage.googleapis.com cloudresourcemanager.googleapis.com
```

`infra/bootstrap` enables the rest of the APIs (container, sqladmin, firestore, pubsub, artifactregistry, secretmanager, servicenetworking, run, cloudfunctions, eventarc, dataproc, and the others listed in `infra/bootstrap/gcp-main.tf`). You need Owner or Editor on `metered-513804`.

Clone and stay on `main`:

```bash
git clone https://github.com/pratham-commits/metered.git
cd metered
git checkout main
```

## 5. State bucket

Bucket: `gs://rideshare-tfstate-metered-513804`.

Backends already point at it:

| Stack | Prefix |
|---|---|
| `infra/platform` | `platform/` |
| `infra/k8s` | `k8s/` |
| `infra/functions` | `functions/` (never created) |
| `infra/dataproc` | `dataproc/` (never created) |

`infra/bootstrap` has no remote backend. Its state is local. The bucket itself has `prevent_destroy` and `force_destroy = false`.

Apply bootstrap only when the bucket is gone:

```bash
gcloud storage buckets describe gs://rideshare-tfstate-metered-513804
```

If that describes the bucket, skip this section. If it is missing:

```bash
terraform -chdir=infra/bootstrap init
terraform -chdir=infra/bootstrap apply -var="project_id=metered-513804"
```

After a normal teardown the bucket is still there, with `platform/` and `k8s/` state from the destroy. Re-apply uses that state. Do not create a second bucket.

## 6. Bring the platform up

Order for a new checkout: gcloud auth (section 4), then `configure.py` with the project id, then this platform apply, then a new `rideshare-ip` (section 7) before any Ingress syncs, then images (section 8), then `infra/k8s` (section 9). Platform apply and destroy do not take `github_repo`.

```bash
.venv/bin/python scripts/configure.py --project-id metered-513804
terraform -chdir=infra/platform init
terraform -chdir=infra/platform apply -var="project_id=metered-513804"
terraform -chdir=infra/platform output
```

`configure.py --project-id` replaces a leftover literal `PROJECT_ID` in `infra/**/*.tf` and the deployment YAML. This clone of `main` already says `metered-513804`, so the command may change nothing. It does not create cloud resources. Do not pass `--tag` here. Image tags are section 8, after the images exist.

Wait until:

- GKE cluster `rideshare` is `RUNNING`
- Cloud SQL `rideshare-pg` is `RUNNABLE`
- Private Service Access is `READY`
- Firestore database `(default)` is `READY`

If the Cloud SQL private IP fails, the `servicenetworking` API must be enabled and address `rideshare-psa` must exist. Both are in this apply.

Passwords are new on every fresh database. Print them when you need them. Do not paste them into git or into this file.

```bash
terraform -chdir=infra/platform output -raw demo_token
terraform -chdir=infra/platform output -raw database_url
```

`demo_token` is the Grafana admin password and the value of `DEMO_TOKEN` in the rideshare secret. `database_url` is sensitive and is injected into that secret as `DATABASE_URL`.

Cluster credentials:

```bash
gcloud container clusters get-credentials rideshare \
  --zone=asia-south1-a --project=metered-513804
kubectl get nodes
kubectl get storageclass
```

The default StorageClass is `standard-rwo`. Kafka in this demo uses ephemeral storage, so that class is not what the brokers sit on.

Do not apply `infra/k8s` yet. Artifact Registry is empty, and the Ingress will sync as soon as Argo CD is installed. Reserve the address and push images first.

## 7. Reserve rideshare-ip and fix the ingress host

`rideshare-ip` is not a Terraform resource. Reserve it by hand, before `infra/k8s` apply and before Argo CD syncs the Ingress. If the named address does not exist when the Ingress is created, the load balancer does not come up.

```bash
gcloud compute addresses create rideshare-ip --global
gcloud compute addresses describe rideshare-ip --global --format='get(address)'
```

Call that address `NEW_IP`. Edit `deploy/apps/ride-request/ingress.yaml`:

- The comment at the top, so it names `NEW_IP` instead of `136.81.121.175`.
- `spec.domains` on ManagedCertificate `rideshare-cert`, so the only domain is `NEW_IP.nip.io`.

Leave the annotation `kubernetes.io/ingress.global-static-ip-name: rideshare-ip` as it is. `nip.io` resolves `NEW_IP.nip.io` to `NEW_IP`, which is what the Google managed certificate checks.

FrontendConfig `rideshare-https` has `redirectToHttps.enabled: false`. Leave it false. Until ManagedCertificate `rideshare-cert` is `Active`, the site is HTTP:

- `http://NEW_IP`
- `http://NEW_IP.nip.io`

Browser geolocation needs HTTPS or `localhost`. The map and "go online here" will not see a GPS fix on plain HTTP. After the certificate is `Active`, use `https://NEW_IP.nip.io`. For a demo before that, port-forward and open `http://localhost:8003` (section 10).

`scripts/push.sh` refuses to run if the git tree is dirty. Commit this ingress edit and push it before building images, so the SHA identifies a tree that already contains the new host:

```bash
git add deploy/apps/ride-request/ingress.yaml
git commit -m "Point the managed certificate at the new rideshare-ip."
git push origin main
```

## 8. Build images and roll them with two commits

Registry: `asia-south1-docker.pkg.dev/metered-513804/rideshare`.

`scripts/push.sh` does all of the following. Do not build by hand with a different platform or tag.

- Exits if `git status --porcelain` is non-empty.
- Tag is `git rev-parse --short HEAD`.
- Project is `gcloud config get-value project` unless `GCP_PROJECT` is set.
- Runs `gcloud auth configure-docker asia-south1-docker.pkg.dev --quiet`.
- Builds `docker build --platform linux/amd64 -f services/SERVICE/Dockerfile`.
- Pushes `asia-south1-docker.pkg.dev/metered-513804/rideshare/SERVICE:SHA`.

Allowed `SERVICE` names: `rider`, `driver`, `ride-request`, `matching`, `dispatch`, `trip-tracking`, `demand-sink`. Build only the five that have real Dockerfiles:

```bash
./scripts/push.sh rider
./scripts/push.sh driver
./scripts/push.sh ride-request
./scripts/push.sh matching
./scripts/push.sh dispatch
```

Each line prints `IMAGE .../SERVICE:SHA`. The migrate job uses the rider image. There is no migrate image.

The tags still written on git tip `ce064e2` (`rider:e71c841`, migrate job `rider:e71c841`, `driver:6c6e678`, `ride-request:ca83bd0`, `matching:ca83bd0`, `dispatch:517ef2c`) died with Artifact Registry. The YAML may still name them after you clone. That does not mean they can be pulled. Rebuild, then let `configure.py` replace those lines. The new tag is whatever `git rev-parse --short HEAD` printed at build time.

All five builds from one clean source commit share that commit's short SHA. You get that same SHA again only when you build from that source commit, before the tag commit. After the tag commit, `HEAD` is a new SHA, and a later `scripts/push.sh` will not reproduce the tags you just wrote into the YAML.

Write every tag in one configure. `--tag rider=SHA` rewrites both `deploy/apps/rider/deployment.yaml` and `deploy/apps/migrate/job.yaml`, because the job's image repository path is `rideshare/rider`.

```bash
.venv/bin/python scripts/configure.py --project-id metered-513804 \
  --tag rider=SHA \
  --tag driver=SHA \
  --tag ride-request=SHA \
  --tag matching=SHA \
  --tag dispatch=SHA
git diff
```

`configure.py` also replaces the literal string `PROJECT_ID` in `infra/**/*.tf` and the deployment YAML. This clone already says `metered-513804`, so the diff you want is the `image:` lines.

That is the second commit. Argo CD rolls from git. Do not `kubectl set image`. Commit and push the tag YAML:

```bash
git add deploy/apps/rider/deployment.yaml \
  deploy/apps/driver/deployment.yaml \
  deploy/apps/ride-request/deployment.yaml \
  deploy/apps/matching/deployment.yaml \
  deploy/apps/dispatch/deployment.yaml \
  deploy/apps/migrate/job.yaml
git commit -m "Pin service images to the rebuilt SHA."
git push origin main
```

Two commits are required: the source commit first (so the SHA identifies the source), then this tag commit. One `configure.py` with every `--tag`, one commit, one push. Build the images while `HEAD` is still the source commit.

## 9. Install Kubernetes, Argo CD, and Kafka

The tag commit must be on `main` before this apply. Argo CD will sync `main` immediately.

`github_repo` has no default. Apply and destroy of `infra/k8s` both need `-var=github_repo=https://github.com/pratham-commits/metered.git`. Platform apply and destroy do not. `fare_estimate_url` defaults to empty; pass it empty until Person 3's estimate function exists. Ride Request then uses the in-process fare quote (`source=local-fallback`).

```bash
terraform -chdir=infra/k8s init
terraform -chdir=infra/k8s apply \
  -var="github_repo=https://github.com/pratham-commits/metered.git" \
  -var="fare_estimate_url="
```

This apply is what publishes the Application objects. Later edits to `deploy/gitops/*.yaml` do nothing to the cluster until you run it again.

Watch:

```bash
kubectl -n argocd get applications
kubectl -n rideshare get pods
kubectl -n rideshare get kafka
kubectl -n rideshare get kafkatopics
kubectl -n rideshare get pods -l strimzi.io/cluster=rideshare-kafka
kubectl -n rideshare get ingress ride-request
kubectl -n rideshare get managedcertificate rideshare-cert
```

Applications you should see: `rideshare`, `rideshare-platform`, and, after the platform Application syncs `deploy/platform/prometheus.yaml`, `prometheus`.

The migrate Job `schema-migrate` is an Argo CD Sync hook (`sync-wave: -1`) using the rider image and command `python -m rideshare.migrate`. It must complete before the API pods become useful. If it ImagePullBackOff, the tag commit is not the SHA you pushed.

Kafka is ready when the broker pods are ready and both topics exist. Pods mount `rideshare-kafka-cluster-ca-cert` at `/etc/kafka`.

## 10. Open every screen

Port-forwards die when the shell exits. A finished shell is `connection refused`. Leave each forward in its own long-lived terminal.

### Argo CD

The Service is ClusterIP `argocd-server`, ports 80 and 443. Helm chart `argo-cd` `10.11.6`.

```bash
kubectl -n argocd port-forward --address 127.0.0.1 svc/argocd-server 8080:443
```

Open `https://127.0.0.1:8080`. The certificate warning is expected. User `admin`. The password from the previous cluster is dead. Read the new one after this install:

```bash
kubectl -n argocd get secret argocd-initial-admin-secret \
  -o jsonpath='{.data.password}' | base64 -d; echo
```

Apps: `rideshare`, `rideshare-platform`, `prometheus`. The git SHA on `rideshare` should match `git rev-parse HEAD` on `main`. Sync is automated (`prune` and `selfHeal`). A service change is a commit to `deploy/apps` or `deploy/platform`, not `kubectl apply`.

### Grafana

The Service is `prometheus-grafana` in namespace `monitoring`. It is a LoadBalancer. `docs/02-person-2.md` port-forwards `svc/kube-prometheus-stack-grafana`. That Service does not exist. `docs/platform-runbook.md` does not name the Grafana Service; do not invent `kube-prometheus-stack-grafana` from the chart name. The chart is `kube-prometheus-stack` `69.8.2`, installed by Argo Application `prometheus`, and the Helm release name is `prometheus`, so the Service is `prometheus-grafana`.

```bash
kubectl -n monitoring get svc prometheus-grafana
kubectl -n monitoring port-forward --address 127.0.0.1 svc/prometheus-grafana 3000:80
```

Open `http://127.0.0.1:3000`, or `http://<EXTERNAL-IP>` from that Service. HTTP, not HTTPS. Do not open Grafana with `https://`.

Username `admin`. Password is the platform demo token. Read it after this recreate. An old demo token does not work:

```bash
terraform -chdir=infra/platform output -raw demo_token
```

or, from the cluster:

```bash
kubectl -n monitoring get secret rideshare-secret \
  -o jsonpath='{.data.admin-password}' | base64 -d; echo
```

Dashboard title `Ride Sharing`, uid `rideshare`, from `deploy/platform/dashboard.yaml`. Panels:

| Panel | Query |
|---|---|
| RPS | `sum(rate(http_requests_total[1m]))` |
| Error rate | `(sum(rate(http_requests_total{status=~"5.."}[1m])) or vector(0)) / clamp_min(sum(rate(http_requests_total[1m])), 1)` |
| Latency p95 | `histogram_quantile(0.95, sum by (le) (rate(http_request_duration_seconds_bucket[1m])))` |
| Nodes ready | `sum(kube_node_status_condition{condition="Ready",status="true"})` |

The error-rate query uses `or vector(0)` and `clamp_min(..., 1)`, so a zero line is drawn when there are no 5xx. A blank panel previously meant zero 5xx, not a broken dashboard. Refresh is 10s, range is the last hour.

Pod scrape is `deploy/platform/podmonitor.yaml`: every pod in `rideshare` with an `app` label, port name `http`, path `/metrics`, every 15s. There is no Fluent Bit. GKE ships container stdout to Cloud Logging.

### Prometheus

Service `prometheus-kube-prometheus-prometheus`, port 9090, ClusterIP, no login. The ConfigMap value `PROMETHEUS_URL` still says `http://kube-prometheus-stack-prometheus.monitoring.svc.cluster.local:9090`. That name is wrong. Use the real Service:

```bash
kubectl -n monitoring port-forward --address 127.0.0.1 svc/prometheus-kube-prometheus-prometheus 9090:9090
```

Open `http://127.0.0.1:9090`. Run the four queries from the table above. Open Status, then Targets, and confirm the rideshare pods are up.

### The public UI

After the Ingress has an address (it should be `NEW_IP`):

```bash
kubectl -n rideshare get ingress ride-request
curl -fsS "http://NEW_IP/healthz"
curl -fsS "http://NEW_IP.nip.io/healthz"
```

Open `http://NEW_IP/` or `http://NEW_IP.nip.io/`.

| Nav | What you should see |
|---|---|
| Ride | Switch role, then a rider tab and a driver tab. Pickup, drop, nearby drivers. Place search calls Mapbox. |
| Trace | Paste a ride id. Hops for that ride. |
| Ring | Live H3 cells around the browser location, then a preview that adds `p4` and shows stayed and moved cells. The preview does not change `HASH_NODES`. |
| Checklist | `GET /api/checklist`. Rows below. |

Geolocation on the public HTTP URL will be denied by the browser. Either wait until `kubectl -n rideshare get managedcertificate rideshare-cert` shows `Active` and use `https://NEW_IP.nip.io`, or:

```bash
kubectl -n rideshare port-forward --address 127.0.0.1 svc/ride-request 8003:8003
```

Open `http://localhost:8003`. `localhost` is a secure context, so geolocation works. Leave that shell open.

Maps still draw with no Mapbox token. Place search does not. `GET /api/geocode` returns 503 with detail `MAPBOX_ACCESS_TOKEN not configured` until the token is added. See the gotchas. Do not put the token in git.

### Other services

Only Ride Request has an Ingress. The others are ClusterIP. To hit health directly:

```bash
kubectl -n rideshare port-forward --address 127.0.0.1 svc/rider 8001:8001
kubectl -n rideshare port-forward --address 127.0.0.1 svc/driver 8002:8002
kubectl -n rideshare port-forward --address 127.0.0.1 svc/matching 8004:8004
kubectl -n rideshare port-forward --address 127.0.0.1 svc/dispatch 8005:8005
curl -fsS http://127.0.0.1:8001/healthz
curl -fsS http://127.0.0.1:8002/healthz
curl -fsS http://127.0.0.1:8004/healthz
curl -fsS http://127.0.0.1:8005/healthz
curl -fsS http://127.0.0.1:8003/readyz
curl -fsS http://127.0.0.1:8003/metrics
```

Trip Tracking would be `svc/trip-tracking` port 8006 and the demand sink `svc/demand-sink` port 8010. Those Services are not in the Argo include, and the processes are not implemented.

### Checklist

```bash
curl -fsS "http://NEW_IP/api/checklist" | jq
```

`GET /api/checklist` marks a row `proven` only when it can see the evidence:

| Id | Proven when |
|---|---|
| `health` | rider, driver, matching, and dispatch `/healthz` are all ok |
| `hops` | a `COMPLETED` ride whose hops include REST, SQL, QUEUE, GRPC, NOSQL, and EVENT |
| `ring` | a ring preview with at least one stayed cell |
| `hpa` | current replicas of both `ride-request` and `matching` are greater than 2 |

The HPA row reads the Kubernetes API (`autoscaling/v2` horizontal pod autoscalers) with the in-cluster service account token. It does not query Prometheus. The Role `ride-request-hpa-reader` and its RoleBinding live inside `deploy/apps/ride-request/hpa.yaml`, not a separate `rbac.yaml`. The live Argo include does not list `rbac.yaml`. The row flips back to `todo` when replicas fall to 2 after k6. That is the minimum, so a quiet cluster is supposed to show `todo`. `HASH_NODES` stays `p0,p1,p2,p3`. The ring preview adds `p4` in a separate `HashRing` and must not change the live value. H3 resolution is 8.

These four stay `show` on purpose. The page will not mark them proven:

| Id | Evidence the page prints |
|---|---|
| `terraform` | `terraform -chdir=infra/platform state list` |
| `argocd` | `kubectl -n argocd get applications` |
| `grafana` | `http://127.0.0.1:3000` dashboard Ride Sharing |
| `logging` | the Cloud Logging query in section 12 |

Show those screens yourself. Person 3's demand window is not a row on this checklist.

## 11. One full ride, then k6

Use `http://NEW_IP` or `http://127.0.0.1:8003` if you port-forwarded. The load test creates rides around latitude `23.03`, longitude `72.54`. The same area works for a manual ride.

`POST /api/ride-requests/{id}/board` and `.../finish` have no body. The GKE load balancer returns 411 Length Required unless the request sets `Content-Length: 0` or sends a body.

```bash
HOST=http://NEW_IP

RIDER=$(curl -fsS -X POST "$HOST/api/riders" \
  -H 'Content-Type: application/json' \
  -d '{"name":"Ada","phone":"+919800000001"}')
RIDER_ID=$(jq -r .id <<<"$RIDER")

DRIVER=$(curl -fsS -X POST "$HOST/api/drivers" \
  -H 'Content-Type: application/json' \
  -d '{"name":"Grace","phone":"+919800000002"}')
DRIVER_ID=$(jq -r .id <<<"$DRIVER")

curl -fsS -X POST "$HOST/api/drivers/$DRIVER_ID/presence" \
  -H 'Content-Type: application/json' \
  -d '{"status":"ONLINE","lat":23.03,"lng":72.54}'

RIDE=$(curl -fsS -X POST "$HOST/api/ride-requests" \
  -H 'Content-Type: application/json' \
  -d "{\"rider_id\":\"$RIDER_ID\",\"pickup_lat\":23.03,\"pickup_lng\":72.54,\"drop_lat\":23.05,\"drop_lng\":72.58}")
RIDE_ID=$(jq -r .id <<<"$RIDE")

curl -fsS -X POST "$HOST/api/ride-requests/$RIDE_ID/accept" \
  -H 'Content-Type: application/json' \
  -d "{\"driver_id\":\"$DRIVER_ID\",\"lat\":23.03,\"lng\":72.54}"

curl -fsS -X POST "$HOST/api/ride-requests/$RIDE_ID/board" \
  -H 'Content-Length: 0'

curl -fsS -X POST "$HOST/api/ride-requests/$RIDE_ID/finish" \
  -H 'Content-Length: 0'

curl -fsS "$HOST/api/ride-requests/$RIDE_ID" | jq
```

Open Trace and paste `RIDE_ID`. A completed ride from this path records REST, SQL, the Pub/Sub QUEUE hop, gRPC Assign, Firestore (NOSQL), and the Kafka EVENT hop. `FARE_ESTIMATE_URL` is empty, so the estimate is the local fallback, not Cloud Run.

In the browser the same path is: Switch role, create the rider, create the driver, go online at the live location, request, accept, board, finish, then Trace.

### k6

`loadtest/k6/ride.js` stages are 30s to 40 VUs, 4 minutes at 120, 30s back to 0. Each iteration posts `/api/ride-requests` around lat `23.03` lng `72.54` with a unique `idempotency_key`. The in-repo script creates one rider in `setup` and does not complete trips. The docs say the script also creates drivers and finishes trips; the file does not. Run the file.

```bash
/opt/homebrew/bin/k6 run -e BASE_URL=http://NEW_IP loadtest/k6/ride.js
```

In another terminal:

```bash
kubectl -n rideshare get hpa -w
```

Success is both `ride-request` and `matching` above 2. The last run before teardown was about 10445 requests, 99% success, ride-request scaled to 6, matching to 5. CPU target is 60% of the `100m` request. Min replicas 2, max 6.

Keep Checklist open during the hold. The HPA row goes `proven` only while both current replica counts are greater than 2, then returns to `todo` when they settle at 2. Grafana's RPS panel should move over the same four minutes.

`kubectl top pods -n rideshare` needs the metrics pipeline. Do not remove the CPU request from the Deployments or the HPAs have nothing to scale on.

## 12. Logs

`JsonFormatter` in `services/common/rideshare/logging_setup.py` prints `ride_id` as a top-level JSON field. GKE parses stdout JSON into `jsonPayload.ride_id`. No Fluent Bit.

Cloud SQL from the previous run is gone. Do not look up an old proof ride id. Use the `RIDE_ID` from the ride you just finished in section 11. An id from before teardown will not be in SQL or in current logs.

```text
resource.type="k8s_container"
resource.labels.namespace_name="rideshare"
jsonPayload.ride_id="RIDE_ID"
```

Events the services actually log:

| Service | `jsonPayload.event` |
|---|---|
| ride-request | `ride_created` |
| matching | `match_job` |
| dispatch | `dispatch_assign_success` |

One ride id should show up in more than one service. That is the Cloud Logging screen for the checklist's `show` row.

Dataproc and Cloud Run queries in `docs/platform-runbook.md` (`cloud_dataproc_cluster` / `rideshare-flink`, and `cloud_run_revision` / `rideshare-fare-final`) apply only after section 14. They return nothing today.

## 13. Known gotchas

**Grafana Service name.** Use `prometheus-grafana`. `kube-prometheus-stack-grafana` does not exist. Port-forward `--address 127.0.0.1` `3000:80`, then `http://127.0.0.1:3000`, or the LoadBalancer `http://<EXTERNAL-IP>`.

**Prometheus Service name.** Use `prometheus-kube-prometheus-prometheus:9090`. `rideshare-config` key `PROMETHEUS_URL` still says `kube-prometheus-stack-prometheus`. Nothing in the running UI reads that URL for the dashboard. Do not port-forward the name in the ConfigMap.

**Mapbox is not in Terraform.** Secret `rideshare-secret` in namespace `rideshare` is only `DATABASE_URL` and `DEMO_TOKEN`. After recreate, geocoding returns 503 until someone adds `MAPBOX_ACCESS_TOKEN` to that secret and restarts ride-request. Maps still render. Do not commit the token.

```bash
kubectl -n rideshare patch secret rideshare-secret --type=merge \
  -p '{"stringData":{"MAPBOX_ACCESS_TOKEN":"PASTE_THE_PK_TOKEN"}}'
kubectl -n rideshare rollout restart deployment/ride-request
```

A later `terraform -chdir=infra/k8s apply` rewrites that secret from Terraform and drops the key. Add it again after any apply that touches `kubernetes_secret.rideshare`.

**Port-forwards must stay in a living terminal.** Bind them with `--address 127.0.0.1`: Argo `8080:443`, Grafana `3000:80`, Prometheus `9090:9090`, Ride Request `8003:8003`. They die with the shell. Connection refused means the forward exited. Grafana is `http://`, not `https://`.

**HTTP until the certificate is Active.** `rideshare-https` does not redirect. Use `http://NEW_IP` and `http://NEW_IP.nip.io`. Geolocation needs `https://NEW_IP.nip.io` or `http://localhost:8003`.

**HPA checklist row.** Proven only while k6 has pushed both HPAs above 2. At rest both sit at 2 and the row is `todo`. The reader is the in-cluster token against `autoscaling/v2`, using Role `ride-request-hpa-reader` inside `deploy/apps/ride-request/hpa.yaml`. The other `show` rows never flip.

**Argo Application spec.** Edits to `deploy/gitops/rideshare-app.yaml` or `platform-app.yaml` reach the cluster only through `terraform -chdir=infra/k8s apply`. Edits under `deploy/apps` and `deploy/platform` sync from git after `git push origin main`.

**Dirty tree.** `scripts/push.sh` exits if git is dirty. Commit the ingress host, and any source, before the first image build. Then configure, then the tag commit. Build while `HEAD` is still the source commit.

**arm64.** Building without `--platform linux/amd64` produces an image the nodes cannot run. Use `scripts/push.sh`.

**411 on board and finish.** Send `Content-Length: 0` or a body.

**Strimzi 0.45.** Do not pin it. `0.48.0` is the version in `infra/k8s/gcp-kafka.tf`.

**Firestore IAM.** `rideshare-ride-request@metered-513804.iam.gserviceaccount.com` needs `roles/datastore.user` or Firestore reads return 403 and the rider map never gets a car. The binding is already in `infra/platform/gcp-iam.tf`.

**Images and the registry.** Platform destroy deletes Artifact Registry. Old tags will not pull. Rebuild, then one configure, then one tag commit.

## 14. Person 3, when that code exists

Skip this section until `services/fare/handler.py` defines `def estimate(` and `def finalize(`, and the Trip Tracking, demand-sink, and Flink sources are real. The Cloud Functions `rideshare-fare-estimate` and `rideshare-fare-final`, and their Cloud Run services, are created only when both of those lines exist (`count` is zero otherwise, and `fare_estimate_url` stays empty). The same `infra/functions` apply still creates the build service account `rideshare-fare-build` and IAM bindings even while the handler is comments, so do not apply it early. `infra/functions` and `infra/dataproc` were never applied on this project. Applying `infra/dataproc` creates cluster `rideshare-flink` immediately, and that cluster is the cost spike. Destroy it the same day.

Fare, from `docs/platform-runbook.md`. The zip command is only for inspection. Terraform builds its own archive.

```bash
services/fare/build.sh
ls -lh services/fare/dist/fare.zip

terraform -chdir=infra/functions init
terraform -chdir=infra/functions apply -var="project_id=metered-513804"
terraform -chdir=infra/functions output fare_estimate_url
```

Put the URL into the cluster:

```bash
terraform -chdir=infra/k8s apply \
  -var="github_repo=https://github.com/pratham-commits/metered.git" \
  -var="fare_estimate_url=$(terraform -chdir=infra/functions output -raw fare_estimate_url)"
```

Check:

```bash
gcloud run services list --region=asia-south1
gcloud functions list --regions=asia-south1
```

`infra/functions` creates `rideshare-fare-estimate` (HTTP) and `rideshare-fare-final` (Eventarc `google.cloud.storage.object.v1.finalized` on the trip bucket). The handler must ignore objects that are not `completions/*.json`.

Trip Tracking and the demand sink, once their Dockerfiles are real, are two more `scripts/push.sh` names and two more `--tag` values. They are not in the Argo include. Adding them means editing `deploy/gitops/rideshare-app.yaml` and applying `infra/k8s` again. Until then Argo will not create them.

Demand page: `docs/03-person-3.md` section 4.3. Trip Tracking serves it next to `GET /demand`. It is not a section of the public UI (Rider, Driver, Trace, Ring, Checklist). Port-forward 8006 and leave that shell open.

```bash
kubectl -n rideshare port-forward --address 127.0.0.1 svc/trip-tracking 8006:8006
```

Flink, same day only. Upload, apply, submit, destroy before you stop for the day.

```bash
mvn -q -DskipTests -f services/demand-analytics/pom.xml package
gsutil cp services/demand-analytics/target/demand-analytics-1.0.0.jar \
  gs://rideshare-trip-files-metered-513804/flink/demand-analytics.jar

terraform -chdir=infra/dataproc init
terraform -chdir=infra/dataproc apply -var="project_id=metered-513804"
./scripts/run-flink.sh
```

`scripts/run-flink.sh` reads the internal load balancer `rideshare-kafka-kafka-external-bootstrap` in namespace `rideshare` and submits class `edu.bits.rideshare.DemandJob` to cluster `rideshare-flink`, listener port `9095`. The truststore path it passes is `/opt/kafka/kafka.truststore.jks`. `scripts/bootstrap-gcp.sh` builds that JKS from `rideshare-kafka-cluster-ca-cert` key `ca.crt` and uploads `gs://rideshare-dataproc-metered-513804/flink/kafka.truststore.jks`. The Dataproc init action in `infra/dataproc` installs it. Do not leave the cluster up overnight.

```bash
terraform -chdir=infra/dataproc destroy -auto-approve -var="project_id=metered-513804"
```

## 15. Shut everything down

This is the order that was used. Destroy Kubernetes first, while the cluster still exists, because the Kubernetes provider needs it. Then delete orphan load-balancer pieces, then the hand-created address, then the platform. There is no Dataproc cluster and no functions stack, so do not run those destroys. They have no state prefix.

Stopping pods, scaling the node pool to zero, or deleting Deployments leaves the bill. While the stack is up the standing cost is the GKE control plane, Cloud NAT, Cloud SQL, the load balancers, an unused static IP, and Artifact Registry storage. After this teardown the only intentional cost is the state bucket. Do not delete the `default` VPC.

### 15.1 Kubernetes

`github_repo` has no default, so this destroy needs it. Platform destroy does not.

```bash
terraform -chdir=infra/k8s destroy -auto-approve \
  -var="github_repo=https://github.com/pratham-commits/metered.git"
```

The rideshare namespace can stay `Terminating` after the Strimzi operator is gone. The holders are KafkaTopic finalizer `strimzi.io/topic-operator`, and GKE ServiceNetworkEndpointGroups. If `kubectl get ns rideshare` stays `Terminating`, patch the stuck objects' finalizers to `[]`:

```bash
kubectl get ns rideshare
kubectl -n rideshare get kafkatopic
kubectl -n rideshare patch kafkatopic ride-events --type=merge \
  -p '{"metadata":{"finalizers":[]}}'
kubectl -n rideshare patch kafkatopic demand-results --type=merge \
  -p '{"metadata":{"finalizers":[]}}'
```

If other objects in the namespace still list finalizers, patch those the same way, `KIND/NAME` and `'{"metadata":{"finalizers":[]}}'`. The namespace then finishes deleting.

### 15.2 Orphan load balancers, NEGs, firewalls, and health checks

The Kafka external listener on 9095 is an internal load balancer. After the namespace is gone, its regional forwarding rules can remain and block deletion of `rideshare-vpc`. The Ingress can also leave NEGs, `k8s2-` firewall rules, backend services, and a shared health check. Delete whatever these lists still show for this project. Do this before the platform destroy. Do not delete `default-allow-icmp`, `default-allow-internal`, `default-allow-rdp`, or `default-allow-ssh`. Those belong to the `default` VPC.

```bash
gcloud compute forwarding-rules list
gcloud compute forwarding-rules list --global
gcloud compute forwarding-rules delete RULE_NAME --region=asia-south1
gcloud compute forwarding-rules delete RULE_NAME --global

gcloud compute backend-services list
gcloud compute backend-services delete BACKEND_NAME --region=asia-south1
gcloud compute backend-services delete BACKEND_NAME --global

gcloud compute network-endpoint-groups list
gcloud compute network-endpoint-groups delete NEG_NAME --zone=asia-south1-a
gcloud compute network-endpoint-groups delete NEG_NAME --region=asia-south1

gcloud compute firewall-rules list --filter="network~rideshare-vpc"
gcloud compute firewall-rules delete FW_NAME

gcloud compute health-checks list
gcloud compute health-checks delete HC_NAME
gcloud compute health-checks delete HC_NAME --region=asia-south1
```

Use the names the list commands print. A zonal NEG takes `--zone`. A regional NEG or health check takes `--region=asia-south1`. A global forwarding rule, backend service, or health check takes `--global` or no region flag, matching the list.

### 15.3 The hand-created address

`rideshare-ip` is not in Terraform. While it is `RESERVED` it keeps billing. The last address `136.81.121.175` was already deleted. On the next teardown:

```bash
gcloud compute addresses delete rideshare-ip --global
```

### 15.4 Platform

```bash
terraform -chdir=infra/platform destroy -auto-approve \
  -var="project_id=metered-513804"
```

That removes GKE, the node pool, Cloud SQL, Cloud NAT, the router, `rideshare-vpc`, the PSA range, Pub/Sub, Firestore, Artifact Registry, and the three data buckets (`rideshare-trip-files-metered-513804`, `rideshare-function-source-metered-513804`, `rideshare-dataproc-metered-513804`). It does not remove the `default` VPC.

Leave `gs://rideshare-tfstate-metered-513804`, prefixes `platform/` and `k8s/`. It is the only intentional cost that should remain, a tiny amount of storage, so this stack can be applied again. Do not `gcloud storage rm` it. Bootstrap will refuse to destroy it anyway (`prevent_destroy`). Apply `infra/bootstrap` only if that bucket is gone.

Cloud SQL's producer peering can stay attached after the instance is gone and block `google_service_networking_connection.psa`. If destroy stops there, remove that peering and run the same destroy again:

```bash
gcloud compute networks peerings list --network=rideshare-vpc
gcloud compute networks peerings delete servicenetworking-googleapis-com \
  --network=rideshare-vpc
terraform -chdir=infra/platform destroy -auto-approve \
  -var="project_id=metered-513804"
```

Delete the peering name the list prints if it is not `servicenetworking-googleapis-com`. Do not delete peerings on the `default` network. There should be none.

If you did apply Person 3 that day, destroy those first, in this order, and only those directories that were actually applied:

```bash
gcloud dataproc clusters delete rideshare-flink --region=asia-south1 --quiet
terraform -chdir=infra/dataproc destroy -auto-approve -var="project_id=metered-513804"
terraform -chdir=infra/functions destroy -auto-approve -var="project_id=metered-513804"
```

Then section 15.1 onward.

## 16. Check that nothing billable remains

```bash
gcloud container clusters list
gcloud sql instances list
gcloud compute forwarding-rules list
gcloud compute forwarding-rules list --global
gcloud compute addresses list
gcloud compute addresses list --global
gcloud compute routers list
gcloud compute networks list
gcloud compute firewall-rules list
gcloud compute disks list
gcloud compute instances list
gcloud compute health-checks list
gcloud compute backend-services list
gcloud compute network-endpoint-groups list
gcloud artifacts repositories list --location=asia-south1
gcloud artifacts repositories list
gcloud storage buckets list
gcloud pubsub topics list
gcloud pubsub subscriptions list
gcloud run services list --region=asia-south1
gcloud functions list --regions=asia-south1
gcloud dataproc clusters list --region=asia-south1
gcloud secrets list
gcloud compute networks peerings list --network=default
gcloud services vpc-peerings list --network=default
```

Empty, except:

- `gcloud storage buckets list` shows only `rideshare-tfstate-metered-513804`. That bucket has prefixes `platform/` and `k8s/`. Keep it. It has a tiny storage cost. Do not delete it.
- `gcloud compute networks list` shows only `default` (auto mode). Keep it.
- `gcloud compute firewall-rules list` shows only `default-allow-icmp`, `default-allow-internal`, `default-allow-rdp`, and `default-allow-ssh`, all on `default`.

The `default` VPC has no addresses, NAT, instances, or disks. It does not bill. Do not delete it. `rideshare-vpc` must be gone. There must be no `rideshare-router`, no `rideshare-nat`, no address named `rideshare-ip`, no `RESERVED` address, no Artifact Registry repository, no Pub/Sub topic or subscription, no secret, and no peering.

While the stack is up, the standing bill is the GKE control plane, Cloud NAT, Cloud SQL, the load balancers, an unused static IP, and Artifact Registry storage. Dataproc, on the day it exists, is the spike. After teardown the only intentional cost is the state bucket.
