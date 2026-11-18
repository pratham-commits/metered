# Metered

Cloud-native **ride matching** on **Google Cloud Platform** (`asia-south1`, project `metered-513804`).

Eight microservices, one public BFF (Ride Request), GitOps with Argo CD, H3 consistent hashing, serverless Fare, and Flink demand analytics on Dataproc.

## Submission files (repo root)

| File | What it is |
|---|---|
| [`design.md`](design.md) | Full design document (six required parts; **self-contained**, inline Mermaid only) |
| [`presentation.pdf`](presentation.pdf) | Architecture presentation (19 slides) |
| [`task_division.txt`](task_division.txt) | Team IDs, services, letters a–h |
| [`live_links.md`](live_links.md) | Public demo URLs only (no GCP Console) |
| [`metered-runbook.md`](metered-runbook.md) | Operator runbook (deploy / smoke / teardown) |
| [`gcp-migration.md`](gcp-migration.md) | AWS → GCP migration notes |

## Who owns what

| Person | ID | Services | Letters |
|---|---|---|---|
| Ved Pahune | 2026H1030056P | Rider, Driver (+ Terraform, Argo, stores) | a, d, g |
| Pratham Shah | 2026H1030063P | Ride Request, Matching, Dispatch (+ UI, HPA, hashing, observability) | c, f, h |
| Vidhu Kant Sharma | 2026H1030053P | Trip Tracking, Fare, Demand Analytics | b, e |

## Layout

```text
design.md / presentation.pdf / task_division.txt / metered-runbook.md / gcp-migration.md
infra/bootstrap     GCS state bucket and project APIs
infra/platform      VPC, GKE, Cloud SQL, Firestore, GCS, Pub/Sub, Artifact Registry, IAM
infra/k8s           namespaces, secrets, config, Argo CD, Strimzi, Kafka topics
infra/functions     Fare Cloud Run functions + Eventarc
infra/dataproc      Flink cluster (demo window)
services/           one directory per service + shared rideshare package
proto/ride/v1       gRPC contracts
deploy/apps         service manifests (Argo CD)
deploy/gitops       Argo CD Applications
loadtest/k6         HPA load test + results/
scripts/            push, configure, run-flink, smoke helpers
```

## Steps — from zero to live

Replace `PROJECT_ID` with `metered-513804` (or your project). Region `asia-south1`, zone `asia-south1-a`.

### 1. Prerequisites

```bash
gcloud auth login
gcloud auth application-default login
gcloud config set project PROJECT_ID
brew install --cask google-cloud-sdk
brew install terraform kubectl helm jq
```

### 2. Configure placeholders

```bash
uv venv --python 3.12 .venv
uv pip install --python .venv/bin/python -r requirements-dev.txt
.venv/bin/python scripts/configure.py --project-id PROJECT_ID
```

### 3. Apply Terraform (foundation)

```bash
terraform -chdir=infra/bootstrap init && terraform -chdir=infra/bootstrap apply -auto-approve
terraform -chdir=infra/platform init && terraform -chdir=infra/platform apply -auto-approve -var="project_id=PROJECT_ID"
terraform -chdir=infra/k8s init && terraform -chdir=infra/k8s apply -auto-approve \
  -var="github_repo=https://github.com/pratham-commits/metered.git"
```

### 4. Build and push images (git SHA tags)

```bash
SHA=$(git rev-parse --short HEAD)
# build/push each service image to Artifact Registry, then pin tags in deploy/apps
# (see metered-runbook.md / scripts/push.sh)
```

### 5. GitOps

Push manifests to `main`. Argo CD syncs Deployments — do **not** `kubectl set image` for normal deploys.

### 6. Fare functions (letter b)

```bash
terraform -chdir=infra/functions init && terraform -chdir=infra/functions apply -auto-approve -var="project_id=PROJECT_ID"
```

### 7. Dataproc + Flink (letter e) — demo window only

```bash
# upload Kafka truststore + JAR, then:
terraform -chdir=infra/dataproc apply -auto-approve -var="project_id=PROJECT_ID"
./scripts/run-flink.sh
# Destroy after the presentation — do not leave Dataproc up.
```

### 8. Prove the system

1. Open the **Ride Request** Ingress URL — create rider, online driver, request, accept, board, finish.  
2. Open **Trace** / **Checklist** — hops and letters.  
3. Confirm **final fare** after GCS completion → Eventarc.  
4. Open **Demand** page — Flink windows.  
5. Open **Grafana** / **Prometheus** — metrics (letter h).  
6. Open **Argo CD** — Synced / Healthy (letter d).  
7. Optional: `loadtest/k6` — HPA scale-out (letter c).

Exact operator commands, smoke checks, and teardown: **[`metered-runbook.md`](metered-runbook.md)**.  
Architecture and rationale: **[`design.md`](design.md)**.  
Slide deck: **[`presentation.pdf`](presentation.pdf)**.

## Local checks

```bash
uv venv --python 3.12 .venv
uv pip install --python .venv/bin/python -r requirements-dev.txt
.venv/bin/python -m pytest -q tests/platform
scripts/check-platform.sh
```

## Notes

- Default storage backend is GCP (`STORAGE_BACKEND=gcp`). AWS baseline remains in-repo for comparison only.  
- Images are tagged with a **git SHA** and rolled by **Argo CD**.  
- After the viva, destroy **Dataproc** first, then tear down Terraform when the course allows.
