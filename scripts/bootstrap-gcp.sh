#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
PROJECT_ID="${1:?Usage: scripts/bootstrap-gcp.sh PROJECT_ID [REGION]}"
REGION="${2:-asia-south1}"
ZONE="${GCP_ZONE:-${REGION}-a}"
GITHUB_REPO="${GITHUB_REPO:?Set GITHUB_REPO to the git clone URL Argo CD should use}"

gcloud auth login
gcloud config set project "$PROJECT_ID"
gcloud services enable serviceusage.googleapis.com cloudresourcemanager.googleapis.com storage.googleapis.com
gcloud auth application-default login

.venv/bin/python scripts/configure.py --project-id "$PROJECT_ID" 2>/dev/null \
  || python3 scripts/configure.py --project-id "$PROJECT_ID"

terraform -chdir=infra/bootstrap init
terraform -chdir=infra/bootstrap apply -var="project_id=$PROJECT_ID"

terraform -chdir=infra/platform init
terraform -chdir=infra/platform apply -var="project_id=$PROJECT_ID"

FARE_URL="${FARE_ESTIMATE_URL:-}"
if [ "${APPLY_FUNCTIONS:-0}" = "1" ]; then
  terraform -chdir=infra/functions init
  terraform -chdir=infra/functions apply -var="project_id=$PROJECT_ID"
  FARE_URL="$(terraform -chdir=infra/functions output -raw fare_estimate_url)"
fi

terraform -chdir=infra/k8s init
terraform -chdir=infra/k8s apply \
  -var="github_repo=$GITHUB_REPO" \
  -var="fare_estimate_url=$FARE_URL"

gcloud container clusters get-credentials rideshare --zone "$ZONE" --project "$PROJECT_ID"

echo "Waiting for Strimzi cluster CA secret rideshare-kafka-cluster-ca-cert..."
for _ in $(seq 1 60); do
  if kubectl get secret rideshare-kafka-cluster-ca-cert -n rideshare >/dev/null 2>&1; then
    break
  fi
  sleep 10
done
kubectl get secret rideshare-kafka-cluster-ca-cert -n rideshare >/dev/null

# Strimzi cluster CA cert secrets expose ca.crt (PEM), not a PKCS12 keystore.
rm -f /tmp/kafka-ca.crt /tmp/kafka.client.truststore.jks
kubectl get secret rideshare-kafka-cluster-ca-cert -n rideshare \
  -o jsonpath='{.data.ca\.crt}' | base64 -d > /tmp/kafka-ca.crt
keytool -importcert -noprompt \
  -alias rideshare-kafka-ca \
  -file /tmp/kafka-ca.crt \
  -keystore /tmp/kafka.client.truststore.jks \
  -storepass changeit
gcloud storage cp /tmp/kafka.client.truststore.jks \
  "gs://rideshare-dataproc-${PROJECT_ID}/flink/kafka.truststore.jks"
rm -f /tmp/kafka-ca.crt /tmp/kafka.client.truststore.jks

if [ "${APPLY_DATAPROC:-0}" = "1" ]; then
  terraform -chdir=infra/dataproc init
  terraform -chdir=infra/dataproc apply -var="project_id=$PROJECT_ID"
fi

echo "Bootstrap complete. kubectl is already configured for the rideshare cluster."
echo "The Kafka truststore is staged for Dataproc. Apply Dataproc only for the stream demo:"
echo "  terraform -chdir=infra/dataproc init && terraform -chdir=infra/dataproc apply -var=project_id=$PROJECT_ID"
echo "When Person 3's Fare source is ready, run:"
echo "  terraform -chdir=infra/functions init && terraform -chdir=infra/functions apply -var=project_id=$PROJECT_ID"
echo "  terraform -chdir=infra/k8s apply -var=github_repo=$GITHUB_REPO -var=fare_estimate_url=\$(terraform -chdir=infra/functions output -raw fare_estimate_url)"
