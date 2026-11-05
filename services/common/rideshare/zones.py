import os
from math import asin, cos, radians, sin, sqrt

import h3

DEFAULT_RESOLUTION = 8
DEFAULT_NEIGHBOR_K = 1


def resolution() -> int:
    value = int(os.environ.get("H3_RESOLUTION", str(DEFAULT_RESOLUTION)))
    if not 0 <= value <= 15:
        raise ValueError("H3_RESOLUTION must be between 0 and 15")
    return value


def neighbor_k() -> int:
    value = int(os.environ.get("H3_NEIGHBOR_K", str(DEFAULT_NEIGHBOR_K)))
    if value < 0:
        raise ValueError("H3_NEIGHBOR_K must be zero or greater")
    return value


def zone_for(lat: float, lng: float) -> str:
    """Return the H3 cell for a live coordinate at the configured resolution."""
    return h3.latlng_to_cell(float(lat), float(lng), resolution())


def center(zone: str) -> tuple[float, float]:
    lat, lng = h3.cell_to_latlng(zone)
    return float(lat), float(lng)


def neighbors(zone: str, k: int | None = None) -> list[str]:
    """Return the H3 grid disk, including the centre cell."""
    return [str(cell) for cell in h3.grid_disk(zone, neighbor_k() if k is None else k)]


def cells_around(lat: float, lng: float, k: int = 3) -> list[str]:
    """Return a live H3 sample around a coordinate for the ring demo."""
    return neighbors(zone_for(lat, lng), k)


def is_valid_zone(zone: str) -> bool:
    try:
        return bool(h3.is_valid_cell(zone))
    except (TypeError, ValueError):
        return False


def distance_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    radius = 6371.0
    phi1, phi2 = radians(lat1), radians(lat2)
    d_phi = radians(lat2 - lat1)
    d_lmb = radians(lng2 - lng1)
    a = sin(d_phi / 2) ** 2 + cos(phi1) * cos(phi2) * sin(d_lmb / 2) ** 2
    return 2 * radius * asin(sqrt(a))
