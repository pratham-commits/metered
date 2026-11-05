# Platform runbook — GCP

This is the operator runbook. It assumes the repository is checked out at the
commit you want to deploy and that you have Owner or Editor on the GCP project.

Replace `PROJECT_ID` with the real project id. Region is `asia-south1`, zone is
`asia-south1-a`.

## 1. Prerequisites

```bash
gcloud auth login
gcloud auth application-default login
gcloud config set project PROJECT_ID
gcloud services enable serviceusage.googleapis.com cloudresourcemanager.googleapis.com
```

Install:

```bash
brew install --cask google-cloud-sdk
brew install terraform kubectl helm jq
```

Check:

```bash
gcloud config get-value project
terraform version
kubectl version --client
helm version
docker version
```

## 2. Configure placeholders

```bash
.venv/bin/python scripts/configure.py --project-id PROJECT_ID
```

The script replaces `PROJECT_ID` in the Terraform and manifests. Pass
`--rider-tag` and `--driver-tag`, or `--tag SERVICE=TAG` for any other service,
after its first image push. It does not print secrets. Argo CD's `repoURL` is
set with the `github_repo` Terraform variable.

## 3. State bucket

```bash
terraform -chdir=infra/bootstrap init
terraform -chdir=infra/bootstrap apply -var="project_id=PROJECT_ID"
```

The bucket is `gs://rideshare-tfstate-PROJECT_ID`.

## 4. Platform

```bash
terraform -chdir=infra/platform init
terraform -chdir=infra/platform apply -var="project_id=PROJECT_ID"
terraform -chdir=infra/platform output
```

Wait for:

- GKE cluster `rideshare` to be `RUNNING`
- Cloud SQL `rideshare-pg` to be `RUNNABLE`
- Private Service Access to be `READY`
- Firestore database `(default)` to be `READY`

If Cloud SQL private IP fails, check that the `servicenetworking` API is enabled
and that the Private Service Access range exists.

## 5. Cluster credentials

```bash
gcloud container clusters get-credentials rideshare \
  --zone=asia-south1-a --project=PROJECT_ID
kubectl get nodes
kubectl get storageclass
```

The default StorageClass is `standard-rwo`.

## 6. First images

```bash
./scripts/push.sh rider
./scripts/push.sh driver
```

Write the printed tags into the repository with:

```bash
.venv/bin/python scripts/configure.py --project-id PROJECT_ID \
  --rider-tag RIDER_TAG --driver-tag DRIVER_TAG
```

For Person 2 and Person 3 images, add `--tag matching=TAG`, `--tag
ride-request=TAG`, and so on. This updates the manifests. Commit the diff. Do
not use `kubectl set image`.

## 7. Kubernetes and Argo CD

```bash
terraform -chdir=infra/k8s init
terraform -chdir=infra/k8s apply \
  -var="github_repo=REPO_URL" \
  -var="fare_estimate_url="
kubectl -n argocd get applications
kubectl -n rideshare get pods
```

Port-forward Argo CD:

```bash
kubectl -n argocd port-forward svc/argocd-server 8080:443
```

Get the initial password:

```bash
kubectl -n argocd get secret argocd-initial-admin-secret \
  -o jsonpath='{.data.password}' | base64 -d
```

Argo CD syncs:

- `deploy/apps` for the services
- `deploy/platform` for Prometheus and Grafana

At first, `deploy/gitops/rideshare-app.yaml` includes only migrate, rider and
driver. Person 2 removes the include after the remaining manifests exist.
`deploy/platform` starts with `*.yaml.stub` files only; `platform-app.yaml`
excludes `*.stub`, so the platform Application stays healthy until Person 2
renames the stubs to real manifests.

## 8. Kafka

Terraform installs the Strimzi operator and the Kafka cluster. Check:

```bash
kubectl -n rideshare get kafka
kubectl -n rideshare get kafkatopics
kubectl -n rideshare get pods -l strimzi.io/cluster=rideshare-kafka
```

The internal bootstrap service is:

```text
rideshare-kafka-kafka-bootstrap.rideshare.svc.cluster.local:9094
```

The CA secret is:

```text
rideshare-kafka-cluster-ca-cert
```

That secret contains PEM `ca.crt`. Pods mount it at `/etc/kafka/ca.crt`.
`scripts/bootstrap-gcp.sh` imports `ca.crt` into a JKS truststore and uploads
`gs://rideshare-dataproc-PROJECT_ID/flink/kafka.truststore.jks` for Dataproc.
Do not expect `ca.p12` / `ca.password` on this secret.

## 9. Fare function

Person 3 implements `estimate` and `finalize` in the handler. Terraform builds
the source zip itself; this command is only for inspection:

```bash
services/fare/build.sh
ls -lh services/fare/dist/fare.zip
```

Then:

```bash
terraform -chdir=infra/functions init
terraform -chdir=infra/functions apply -var="project_id=PROJECT_ID"
terraform -chdir=infra/functions output fare_estimate_url
```

Put the URL into `infra/k8s`:

```bash
terraform -chdir=infra/k8s apply \
  -var="github_repo=REPO_URL" \
  -var="fare_estimate_url=$(terraform -chdir=infra/functions output -raw fare_estimate_url)"
```

Check:

```bash
gcloud run services list --region=asia-south1
gcloud functions list --regions=asia-south1
```

## 10. Dataproc

Person 3 uploads the JAR:

```bash
mvn -q -DskipTests -f services/demand-analytics/pom.xml package
gsutil cp services/demand-analytics/target/demand-analytics-1.0.0.jar \
  gs://rideshare-trip-files-PROJECT_ID/flink/demand-analytics.jar
```

Apply:

```bash
terraform -chdir=infra/dataproc init
terraform -chdir=infra/dataproc apply -var="project_id=PROJECT_ID"
```

Submit:

```bash
./scripts/run-flink.sh
```

Destroy the same day:

```bash
terraform -chdir=infra/dataproc destroy -auto-approve -var="project_id=PROJECT_ID"
```

## 11. Public HTTPS and geolocation

Browser geolocation requires a secure context. For the public demo:

1. Reserve a global static IP.
2. Point a DNS name at it.
3. Add a GKE ManagedCertificate.
4. Use the GKE Ingress with the static IP annotation.
5. Wait for the certificate to become `Active`.

For local development, `http://localhost:8003` is a secure context and
geolocation works.

## 12. Verification

```bash
curl -fsS https://YOUR_HOST/healthz
curl -fsS https://YOUR_HOST/api/checklist | jq
kubectl -n rideshare get pods
kubectl -n monitoring get pods
```

Cloud Logging:

```text
resource.type="k8s_container"
resource.labels.namespace_name="rideshare"
jsonPayload.ride_id="YOUR_RIDE_ID"
```

Dataproc:

```text
resource.type="cloud_dataproc_cluster"
resource.labels.cluster_name="rideshare-flink"
```

Cloud Run:

```text
resource.type="cloud_run_revision"
resource.labels.service_name="rideshare-fare-final"
```

## 13. Troubleshooting

### Pods cannot pull images

Check the node service account has `roles/artifactregistry.reader`. For a local
`docker push`, run:

```bash
gcloud auth configure-docker asia-south1-docker.pkg.dev
```

### Driver cannot write Firestore

```bash
kubectl -n rideshare describe sa driver
kubectl -n rideshare get sa driver -o yaml
gcloud iam service-accounts get-iam-policy \
  rideshare-driver@PROJECT_ID.iam.gserviceaccount.com
```

The KSA annotation must be present and the Workload Identity binding must use
`serviceAccount:PROJECT_ID.svc.id.goog[rideshare/driver]`.

### Kafka TLS fails

Check that the CA secret is mounted at `/etc/kafka/ca.crt` and that
`KAFKA_SSL_CA_FILE` points to it. Set `KAFKA_SSL_CHECK_HOSTNAME=false` for the
internal service DNS and the Dataproc load-balancer IP.

### Cloud SQL connection fails from a pod

Cloud SQL uses a private IP. The pod must run on a node in `rideshare-subnet`,
and the Cloud SQL instance must have a Private Service Access range. Private
Google Access is for Google APIs, not for Cloud SQL. Check the `DATABASE_URL` in
the Kubernetes Secret.

### Pub/Sub matching does not receive

```bash
gcloud pubsub subscriptions describe rideshare-match-jobs-sub
gcloud pubsub topics list
```

Check that the matching GSA has `roles/pubsub.subscriber` and that the Pod uses
`STORAGE_BACKEND=gcp`.

### Eventarc does not fire

Check that the Eventarc trigger service account has
`roles/eventarc.eventReceiver` and `roles/run.invoker` on the final function.
The function runtime account has `objectViewer` on the trip bucket. Eventarc
fires for every object; the handler filters `completions/`.

### HPA does not scale

```bash
kubectl -n rideshare get hpa
kubectl top pods -n rideshare
```

The HPA needs the CPU request and the GKE metrics pipeline. Do not remove the
request.

## 14. Teardown

```bash
gcloud dataproc clusters delete rideshare-flink --region=asia-south1 --quiet
terraform -chdir=infra/dataproc destroy -auto-approve -var="project_id=PROJECT_ID"
terraform -chdir=infra/functions destroy -auto-approve -var="project_id=PROJECT_ID"
terraform -chdir=infra/k8s destroy -auto-approve -var="github_repo=REPO_URL"
terraform -chdir=infra/platform destroy -auto-approve -var="project_id=PROJECT_ID"
```

Delete the state bucket only when the project is finished. Cloud SQL deletion
protection is disabled for the course project.
