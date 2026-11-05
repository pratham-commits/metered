#!/usr/bin/env bash
set -euo pipefail
PROJECT="$(curl -fsS -H 'Metadata-Flavor: Google' \
  http://metadata.google.internal/computeMetadata/v1/project/project-id)"
mkdir -p /opt/kafka
gsutil cp "gs://rideshare-dataproc-${PROJECT}/flink/kafka.truststore.jks" \
  /opt/kafka/kafka.truststore.jks
chmod 0644 /opt/kafka/kafka.truststore.jks
