#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
PROJECT="${GCP_PROJECT:-$(gcloud config get-value project 2>/dev/null)}"
REGION="${GCP_REGION:-asia-south1}"
CLUSTER="${DATAPROC_CLUSTER:-rideshare-flink}"
JAR="${FLINK_JAR:-gs://rideshare-trip-files-${PROJECT}/flink/demand-analytics.jar}"
BOOTSTRAP="${KAFKA_BOOTSTRAP:-}"
if [ -z "$BOOTSTRAP" ]; then
  IP="$(kubectl get svc rideshare-kafka-kafka-external-bootstrap -n rideshare -o jsonpath='{.status.loadBalancer.ingress[0].ip}')"
  BOOTSTRAP="${IP}:9095"
fi
TRUSTSTORE="${KAFKA_TRUSTSTORE:-/opt/kafka/kafka.truststore.jks}"

gcloud dataproc jobs submit flink \
  --project "$PROJECT" \
  --region "$REGION" \
  --cluster "$CLUSTER" \
  --class edu.bits.rideshare.DemandJob \
  --jars "$JAR" \
  -- \
  --bootstrap "$BOOTSTRAP" \
  --input ride-events \
  --output demand-results \
  --truststore "$TRUSTSTORE"
