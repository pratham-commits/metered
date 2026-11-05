#!/usr/bin/env python3
"""Set non-secret GCP identifiers without creating cloud resources."""

import argparse
import re
from pathlib import Path

PROJECT_ID_PATTERN = re.compile(r"[a-z][a-z0-9-]{4,28}[a-z0-9]")
IMAGE_TAG_PATTERN = re.compile(r"[A-Za-z0-9_][A-Za-z0-9_.-]{0,127}")
IMAGE_REFERENCE_PATTERN = re.compile(
    r"(image: \S+/rideshare/(?P<service>[a-z][a-z0-9-]*):)[^\s]+"
)

SERVICE_FILES = {
    "rider": "rider/deployment.yaml",
    "driver": "driver/deployment.yaml",
    "migrate": "migrate/job.yaml",
    "ride-request": "ride-request/deployment.yaml",
    "matching": "matching/deployment.yaml",
    "dispatch": "dispatch/deployment.yaml",
    "trip-tracking": "trip-tracking/deployment.yaml",
    "demand-sink": "demand-sink/deployment.yaml",
}
DEPLOYMENT_FILES = tuple(SERVICE_FILES.values())
IMAGE_SERVICES = {
    "rider",
    "driver",
    "ride-request",
    "matching",
    "dispatch",
    "trip-tracking",
    "demand-sink",
}


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-id", required=True)
    parser.add_argument("--rider-tag")
    parser.add_argument("--driver-tag")
    parser.add_argument(
        "--tag",
        action="append",
        default=[],
        metavar="SERVICE=TAG",
        help="tag for any service; may be repeated",
    )
    args = parser.parse_args(argv)
    if not PROJECT_ID_PATTERN.fullmatch(args.project_id):
        parser.error("--project-id must be a valid 6-30 character GCP project id")

    tags: dict[str, str] = {}
    if args.rider_tag:
        tags["rider"] = args.rider_tag
    if args.driver_tag:
        tags["driver"] = args.driver_tag
    for item in args.tag:
        service, separator, tag = item.partition("=")
        if not separator or service not in IMAGE_SERVICES:
            parser.error(f"--tag expects SERVICE=TAG with SERVICE in {sorted(IMAGE_SERVICES)}")
        tags[service] = tag
    for tag in tags.values():
        if not IMAGE_TAG_PATTERN.fullmatch(tag):
            parser.error("invalid image tag")
    args.tags = tags
    return args


def configure_files(root: Path, args: argparse.Namespace) -> None:
    paths = sorted((root / "infra").rglob("*.tf"))
    paths.extend(root / "deploy/apps" / name for name in DEPLOYMENT_FILES)
    for path in paths:
        if not path.exists():
            continue
        original = path.read_text()
        updated = original.replace("PROJECT_ID", args.project_id)
        if path.suffix == ".yaml":
            updated = IMAGE_REFERENCE_PATTERN.sub(
                lambda match: (
                    match.group(1) + args.tags[match.group("service")]
                    if match.group("service") in args.tags
                    else match.group(0)
                ),
                updated,
            )
        if updated != original:
            path.write_text(updated)


def main() -> None:
    args = parse_args()
    configure_files(Path(__file__).resolve().parents[1], args)
    print("Configured GCP project and image tags. Review git diff before committing. No GCP resources created.")


if __name__ == "__main__":
    main()
