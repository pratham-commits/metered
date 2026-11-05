# Ride Sharing

Cloud Computing assignment. Eight services on **Google Cloud Platform** in
`asia-south1`. The platform infrastructure and the Rider/Driver services are
implemented in this contribution. Ride Request, Matching, Dispatch, the public
UI and observability are Person 2 scaffolds. Trip Tracking, Fare, Demand
Analytics and the demand sink are Person 3 scaffolds.

The AWS baseline is retained in the repository and in the migration guide. It is
disabled with comments or by the provider-neutral `STORAGE_BACKEND=aws` switch;
the default is GCP.

Start with:

- [Group overview](docs/00-overview.md)
- [AWS to GCP migration](docs/gcp-migration.md)
- [Platform runbook](docs/platform-runbook.md)
- [Person 1 guide](docs/01-person-1.md)
- [Person 2 guide](docs/02-person-2.md)
- [Person 3 guide](docs/03-person-3.md)

## Who owns what

| Person | Write these paths | Defends |
|---|---|---|
| Person 1 / platform maintainer | `infra/`, `services/common/` except the ring test, `services/rider/`, `services/driver/`, `deploy/apps/migrate/`, `deploy/apps/rider/`, `deploy/apps/driver/`, `deploy/gitops/`, `scripts/`, `docker-compose.yml` | Terraform, GitOps, GCS + Cloud SQL + Firestore |
| Person 2 | `services/ride-request/`, `services/matching/`, `services/dispatch/`, `services/common/rideshare/hashring.py`, `services/common/tests/`, `proto/`, `deploy/apps/ride-request/`, `deploy/apps/matching/`, `deploy/apps/dispatch/`, `deploy/platform/`, `loadtest/` | GKE scale, HPA, consistent hashing, Prometheus, Grafana, Cloud Logging, the public UI |
| Person 3 | `services/trip-tracking/`, `services/fare/`, `services/demand-analytics/`, `services/demand-sink/`, `deploy/apps/trip-tracking/`, `deploy/apps/demand-sink/`, `infra/functions/`, `infra/dataproc/` | Cloud Run functions, REST/gRPC/Pub/Sub on the trace, Flink on Dataproc |

`docs/design.md` and `task_division.txt` are filled in before submission. The
platform maintainer merges the design document.

## Layout

```text
infra/bootstrap     GCS state bucket and project API enablement
infra/platform      VPC, GKE, Cloud SQL, Firestore, GCS, Pub/Sub, Artifact Registry, IAM
infra/k8s           namespaces, secrets, config, Argo CD, Strimzi, Kafka topics
infra/functions     Fare Cloud Run functions and the Eventarc trigger
infra/dataproc      Flink cluster, created only for the demo
services/           one directory per service, plus the shared rideshare package
proto/ride/v1       gRPC contracts
deploy/apps         service manifests, synced by Argo CD
deploy/gitops       the two Argo CD Application pointers
deploy/platform     Person 2 Prometheus/Grafana stubs (*.yaml.stub); logs go to Cloud Logging
loadtest/k6         the scale test
scripts/push.sh     build and push one image by git SHA
```

Images are published with `scripts/push.sh`. The printed tags are written into
the manifests with `scripts/configure.py`; Argo CD rolls the pods. `kubectl
apply` is not the deploy path for a service.

## Order

The platform maintainer applies `infra/bootstrap`, then `infra/platform`, then
`infra/k8s`. Person 2 and Person 3 implement against the comments in their
directories. `infra/functions` builds its own source zip from the Fare source and stays
disabled until `estimate` and `finalize` exist;
`scripts/build-fare.sh` is optional inspection. `infra/dataproc` is applied on
the demo day and destroyed the same day.

## Local checks

```bash
uv venv --python 3.12 .venv
uv pip install --python .venv/bin/python -r requirements-dev.txt
.venv/bin/python -m pytest -q tests/platform
scripts/check-platform.sh
```

The AWS tests are preserved and run with Moto. GCP adapter tests run with
mocked Google clients so no credentials are required. Docker Compose starts
GCP emulators for local development.
