import importlib.util
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "scripts/configure.py"
spec = importlib.util.spec_from_file_location("configure", SCRIPT)
configure = importlib.util.module_from_spec(spec)
spec.loader.exec_module(configure)


@pytest.mark.parametrize("arguments", [
    ["--account-id", "123"],
    ["--account-id", "123456789012", "--rider-tag", "bad/tag"],
])
def test_invalid_identifiers(arguments):
    with pytest.raises(SystemExit):
        configure.parse_args(arguments)


def test_configuration_updates_each_service_and_migration(tmp_path):
    infra = tmp_path / "infra"
    infra.mkdir()
    terraform = infra / "main.tf"
    terraform.write_text('account = "ACCOUNT_ID"\n')
    for name in configure.DEPLOYMENT_FILES:
        path = tmp_path / "deploy/apps" / name
        path.parent.mkdir(parents=True)
        service = "driver" if path.parent.name == "driver" else "rider"
        path.write_text(f"image: ACCOUNT_ID.registry/rideshare/{service}:old\n")
    args = configure.parse_args([
        "--account-id", "123456789012", "--rider-tag", "rider-v2",
        "--driver-tag", "driver-v3",
    ])
    configure.configure_files(tmp_path, args)
    assert terraform.read_text() == 'account = "123456789012"\n'
    for name in configure.DEPLOYMENT_FILES:
        path = tmp_path / "deploy/apps" / name
        expected_tag = "driver-v3" if path.parent.name == "driver" else "rider-v2"
        assert path.read_text().endswith(f":{expected_tag}\n")
        assert "ACCOUNT_ID" not in path.read_text()
    previous = terraform.stat().st_mtime_ns
    configure.configure_files(tmp_path, args)
    assert terraform.stat().st_mtime_ns == previous
