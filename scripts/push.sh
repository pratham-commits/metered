#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
SERVICE="${1:?Usage: scripts/push.sh SERVICE}"
case "$SERVICE" in rider|driver|ride-request|matching|dispatch|trip-tracking|demand-sink) ;; *) echo "Unknown service" >&2; exit 2;; esac
if test -n "$(git status --porcelain --untracked-files=normal)"; then
  echo "Commit source changes first so the image tag identifies the source." >&2; exit 1
fi
SHA="$(git rev-parse --short HEAD)"
PROJECT="${GCP_PROJECT:-$(gcloud config get-value project 2>/dev/null)}"
REGION="${GCP_REGION:-asia-south1}"
if [ -z "$PROJECT" ] || [ "$PROJECT" = "(unset)" ]; then
  echo "Set GCP_PROJECT or run: gcloud config set project PROJECT_ID" >&2; exit 1
fi
REGISTRY="${REGION}-docker.pkg.dev"
REPO="${REGISTRY}/${PROJECT}/rideshare/${SERVICE}"
gcloud auth configure-docker "$REGISTRY" --quiet
docker build --platform linux/amd64 -f "services/${SERVICE}/Dockerfile" -t "${REPO}:${SHA}" .
docker push "${REPO}:${SHA}"
echo "IMAGE ${REPO}:${SHA}"
echo "Set that tag with scripts/configure.py, commit, and let Argo CD roll. Do not kubectl set image."

# ---------------------------------------------------------------------------
# LEGACY AWS BASELINE — retained for reference only.
# SHA="$(git rev-parse --short HEAD)"
# ACCOUNT="$(aws sts get-caller-identity --query Account --output text)"
# REGION="${AWS_REGION:-ap-south-1}"
# REGISTRY="${ACCOUNT}.dkr.ecr.${REGION}.amazonaws.com"
# REPO="${REGISTRY}/rideshare/${SERVICE}"
# aws ecr get-login-password --region "$REGION" | docker login --username AWS --password-stdin "$REGISTRY"
# docker build --platform linux/amd64 -f "services/${SERVICE}/Dockerfile" -t "${REPO}:${SHA}" .
# docker push "${REPO}:${SHA}"
# ---------------------------------------------------------------------------
