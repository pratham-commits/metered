#!/usr/bin/env python3
"""Set non-secret AWS identifiers without creating cloud resources."""

import argparse
import re
from pathlib import Path

ACCOUNT_ID_PATTERN = re.compile(r"[0-9]{12}")
IMAGE_TAG_PATTERN = re.compile(r"[A-Za-z0-9_][A-Za-z0-9_.-]{0,127}")
IMAGE_REFERENCE_PATTERN = re.compile(r"(image: \S+/rideshare/(?:rider|driver):)[^\s]+")
DEPLOYMENT_FILES = (
    "rider/deployment.yaml",
    "driver/deployment.yaml",
    "migrate/job.yaml",
)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--account-id", required=True)
    parser.add_argument("--rider-tag")
    parser.add_argument("--driver-tag")
    args = parser.parse_args(argv)
    if not ACCOUNT_ID_PATTERN.fullmatch(args.account_id):
        parser.error("--account-id must be exactly 12 digits")
    for tag in (args.rider_tag, args.driver_tag):
        if tag and not IMAGE_TAG_PATTERN.fullmatch(tag):
            parser.error("invalid image tag")
    return args


def configure_files(root: Path, args: argparse.Namespace) -> None:
    paths = sorted((root / "infra").rglob("*.tf"))
    paths.extend(root / "deploy/apps" / name for name in DEPLOYMENT_FILES)
    for path in paths:
        original = path.read_text()
        updated = original.replace("ACCOUNT_ID", args.account_id)
        if path.suffix == ".yaml":
            tag = args.driver_tag if path.parent.name == "driver" else args.rider_tag
            if tag:
                updated = IMAGE_REFERENCE_PATTERN.sub(lambda match: match[1] + tag, updated)
        if updated != original:
            path.write_text(updated)


def main() -> None:
    args = parse_args()
    configure_files(Path(__file__).resolve().parents[1], args)
    print("Configured platform and profile service files. Review git diff before committing. No AWS resources created.")


if __name__ == "__main__":
    main()
