import importlib.util
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "scripts/configure.py"
spec = importlib.util.spec_from_file_location("configure", SCRIPT)
configure = importlib.util.module_from_spec(spec)
spec.loader.exec_module(configure)


@pytest.mark.parametrize("arguments", [
    ["--project-id", "short"],
    ["--project-id", "Bad_Project"],
    ["--project-id", "good-project-123", "--rider-tag", "bad/tag"],
    ["--project-id", "good-project-123", "--tag", "unknown=tag"],
    ["--project-id", "good-project-123", "--tag", "matching=bad/tag"],
])
def test_invalid_identifiers(arguments):
    with pytest.raises(SystemExit):
        configure.parse_args(arguments)


def test_configuration_updates_each_service_and_migration(tmp_path):
    infra = tmp_path / "infra"
    infra.mkdir()
    terraform = infra / "main.tf"
    terraform.write_text('project = "PROJECT_ID"\n')
    for name in configure.DEPLOYMENT_FILES:
        path = tmp_path / "deploy/apps" / name
        path.parent.mkdir(parents=True)
        service = "driver" if path.parent.name == "driver" else "rider"
        path.write_text(
            f"image: asia-south1-docker.pkg.dev/PROJECT_ID/rideshare/{service}:old\n"
        )
    args = configure.parse_args([
        "--project-id", "good-project-123", "--rider-tag", "rider-v2",
        "--driver-tag", "driver-v3",
    ])
    configure.configure_files(tmp_path, args)
    assert terraform.read_text() == 'project = "good-project-123"\n'
    for name in configure.DEPLOYMENT_FILES:
        path = tmp_path / "deploy/apps" / name
        expected_tag = "driver-v3" if path.parent.name == "driver" else "rider-v2"
        assert path.read_text().endswith(f":{expected_tag}\n")
        assert "PROJECT_ID" not in path.read_text()
    previous = terraform.stat().st_mtime_ns
    configure.configure_files(tmp_path, args)
    assert terraform.stat().st_mtime_ns == previous


def test_tag_option_updates_named_service(tmp_path):
    infra = tmp_path / "infra"
    infra.mkdir()
    path = tmp_path / "deploy/apps/matching/deployment.yaml"
    path.parent.mkdir(parents=True)
    path.write_text(
        "image: asia-south1-docker.pkg.dev/PROJECT_ID/rideshare/matching:old\n"
    )
    args = configure.parse_args([
        "--project-id", "good-project-123", "--tag", "matching=match-v2",
    ])
    configure.configure_files(tmp_path, args)
    assert path.read_text().endswith(":match-v2\n")
    assert "PROJECT_ID" not in path.read_text()
