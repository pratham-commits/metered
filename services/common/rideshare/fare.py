from rideshare.zones import center, distance_km


def quote_cents(distance_km_value: float, imbalance: float) -> tuple[int, float, float]:
    if imbalance >= 3:
        surge = 2.0
    elif imbalance >= 1.5:
        surge = 1.5
    else:
        surge = 1.0
    duration_min = distance_km_value / 25.0 * 60.0
    raw = 4000 + distance_km_value * 1200 + duration_min * 200
    return int(round(raw * surge)), surge, duration_min


def quote_between(zone_a: str, zone_b: str, imbalance: float) -> dict:
    lat1, lng1 = center(zone_a)
    lat2, lng2 = center(zone_b)
    kilometres = distance_km(lat1, lng1, lat2, lng2)
    cents, surge, minutes = quote_cents(kilometres, imbalance)
    return {
        "amount_cents": cents,
        "surge": surge,
        "duration_min": round(minutes, 3),
        "distance_km": round(kilometres, 3),
    }
