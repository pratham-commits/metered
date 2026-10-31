from math import asin, cos, radians, sin, sqrt

MIN_LAT, MAX_LAT = 17.30, 17.50
MIN_LNG, MAX_LNG = 78.30, 78.50
ROWS, COLS = 4, 4


def all_zones() -> list[str]:
    return [f"z{row}{col}" for row in range(ROWS) for col in range(COLS)]


def zone_for(lat: float, lng: float) -> str:
    lat = min(max(lat, MIN_LAT), MAX_LAT - 1e-9)
    lng = min(max(lng, MIN_LNG), MAX_LNG - 1e-9)
    row = int((lat - MIN_LAT) / (MAX_LAT - MIN_LAT) * ROWS)
    col = int((lng - MIN_LNG) / (MAX_LNG - MIN_LNG) * COLS)
    return f"z{row}{col}"


def center(zone: str) -> tuple[float, float]:
    row, col = int(zone[1]), int(zone[2])
    height = (MAX_LAT - MIN_LAT) / ROWS
    width = (MAX_LNG - MIN_LNG) / COLS
    return (MIN_LAT + (row + 0.5) * height, MIN_LNG + (col + 0.5) * width)


def neighbors(zone: str) -> list[str]:
    row, col = int(zone[1]), int(zone[2])
    found = []
    for d_row in (-1, 0, 1):
        for d_col in (-1, 0, 1):
            next_row, next_col = row + d_row, col + d_col
            if 0 <= next_row < ROWS and 0 <= next_col < COLS:
                found.append(f"z{next_row}{next_col}")
    return found


def distance_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    radius = 6371.0
    phi1, phi2 = radians(lat1), radians(lat2)
    d_phi = radians(lat2 - lat1)
    d_lmb = radians(lng2 - lng1)
    a = sin(d_phi / 2) ** 2 + cos(phi1) * cos(phi2) * sin(d_lmb / 2) ** 2
    return 2 * radius * asin(sqrt(a))
