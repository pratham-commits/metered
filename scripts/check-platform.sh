#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
python -m pytest -q tests/platform --disable-warnings
python -m compileall -q services/common/rideshare services/rider services/driver
python - <<'PY'
from pathlib import Path
import hcl2, yaml
for path in Path('infra').rglob('*.tf'):
    hcl2.loads(path.read_text())
for path in Path('deploy').rglob('*.yaml'):
    list(yaml.safe_load_all(path.read_text()))
yaml.safe_load(Path('docker-compose.yml').read_text())
from kafka import KafkaProducer
print('Python imports, Terraform syntax and YAML parsing passed (not provider validation).')
PY
bash -n scripts/push.sh
sh -n scripts/localstack-init.sh
if command -v docker >/dev/null; then docker compose config --quiet; fi
