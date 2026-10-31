#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
SERVICE="${1:?Usage: scripts/push.sh SERVICE}"
case "$SERVICE" in rider|driver|ride-request|matching|dispatch|trip-tracking|demand-sink) ;; *) echo "Unknown service" >&2; exit 2;; esac
if test -n "$(git status --porcelain --untracked-files=normal)"; then
  echo "Commit source changes first so the image tag identifies the source." >&2; exit 1
fi
SHA="$(git rev-parse --short HEAD)"
ACCOUNT="$(aws sts get-caller-identity --query Account --output text)"
REGION="${AWS_REGION:-ap-south-1}"
REGISTRY="${ACCOUNT}.dkr.ecr.${REGION}.amazonaws.com"
REPO="${REGISTRY}/rideshare/${SERVICE}"
aws ecr get-login-password --region "$REGION" | docker login --username AWS --password-stdin "$REGISTRY"
docker build --platform linux/amd64 -f "services/${SERVICE}/Dockerfile" -t "${REPO}:${SHA}" .
docker push "${REPO}:${SHA}"
echo "IMAGE ${REPO}:${SHA}"
echo "Put that tag in deploy/apps/${SERVICE}/deployment.yaml and commit. Do not kubectl set image."
