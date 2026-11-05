import os


def get_store():
    """Return the configured store.

    GCP is the default. Set STORAGE_BACKEND=aws to use the retained AWS adapter
    for the legacy baseline and the Moto-backed tests.
    """
    backend = os.environ.get("STORAGE_BACKEND", "gcp").strip().lower()
    if backend == "aws":
        from rideshare.aws import get_store as aws_store

        return aws_store()
    if backend == "gcp":
        from rideshare.gcp import get_store as gcp_store

        return gcp_store()
    raise ValueError(f"unknown STORAGE_BACKEND: {backend}")
