#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

if [ -x .venv/bin/python ]; then
  PYTHON=".venv/bin/python"
elif command -v python3 >/dev/null 2>&1; then
  PYTHON="python3"
else
  PYTHON="${PYTHON:-python}"
fi

"$PYTHON" -m pytest -q tests/platform services/common/tests/test_ring.py --disable-warnings
"$PYTHON" -m compileall -q services/common/rideshare services/rider services/driver
"$PYTHON" - <<'PY'
from pathlib import Path
import hcl2, yaml

for path in Path("infra").rglob("*.tf"):
    # Comment-only legacy AWS files are still valid HCL (empty).
    hcl2.loads(path.read_text())

for path in Path("deploy").rglob("*.yaml"):
    list(yaml.safe_load_all(path.read_text()))

# Stub manifests kept next to the live tree must not be applied by Argo CD.
for path in Path("deploy").rglob("*.yaml.stub"):
    text = path.read_text().strip()
    assert text, f"{path} is empty"

yaml.safe_load(Path("docker-compose.yml").read_text())
from kafka import KafkaProducer  # noqa: F401
print("Python imports, Terraform syntax and YAML parsing passed (not provider validation).")
PY
bash -n scripts/push.sh
bash -n scripts/bootstrap-gcp.sh
bash -n scripts/build-fare.sh
bash -n scripts/run-flink.sh
bash -n services/fare/build.sh
if command -v docker >/dev/null; then
  docker compose config --quiet
fi
