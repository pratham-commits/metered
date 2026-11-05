#!/usr/bin/env bash
# Person 3. Optional local zip for inspecting the Cloud Run function source tree.
# Terraform infra/functions builds its own archive from these sources when
# estimate and finalize exist. Cloud Build installs requirements.txt in the cloud.
set -euo pipefail
cd "$(dirname "$0")/../.."
DIST="services/fare/dist"
rm -rf "$DIST"
mkdir -p "$DIST"
cp services/fare/handler.py "$DIST/main.py"
cp services/fare/requirements.txt "$DIST/requirements.txt"
cp -a services/common/rideshare "$DIST/rideshare"
find "$DIST/rideshare" -type d -name __pycache__ -prune -exec rm -rf {} +
(cd "$DIST" && zip -qr fare.zip main.py requirements.txt rideshare)
echo "$DIST/fare.zip"
