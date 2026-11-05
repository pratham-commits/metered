import pytest
from rideshare.fare import quote_between, quote_cents, quote_coordinates
from rideshare.hashring import HashRing
from rideshare.zones import (
    cells_around,
    center,
    distance_km,
    is_valid_zone,
    neighbors,
    zone_for,
)


@pytest.mark.parametrize(
    "lat,lng",
    [
        (12.9716, 77.5946),
        (17.3850, 78.4867),
        (51.5074, -0.1278),
        (-33.8688, 151.2093),
    ],
)
def test_h3_zone_round_trip(lat, lng):
    zone = zone_for(lat, lng)
    assert is_valid_zone(zone)
    assert zone == zone_for(*center(zone))
    assert zone in neighbors(zone)
    assert len(neighbors(zone, 1)) == 7


def test_h3_sample_and_ring_moves_only_a_fraction():
    zones = cells_around(12.9716, 77.5946, 3)
    assert len(zones) == 37
    ring = HashRing(["p0", "p1", "p2", "p3"])
    before = ring.ownership(zones)
    ring.add("p4")
    after = ring.ownership(zones)
    moved = [zone for zone in before if before[zone] != after[zone]]
    assert 0 < len(moved) < len(zones)
    assert all(after[zone] == "p4" for zone in moved)


@pytest.mark.parametrize(
    "imbalance,surge",
    [(0, 1), (1.49, 1), (1.5, 1.5), (3, 2)],
)
def test_fare_thresholds(imbalance, surge):
    amount, actual, minutes = quote_cents(5, imbalance)
    assert actual == surge
    assert minutes == 12
    assert amount == round(12400 * surge)


def test_fare_uses_actual_coordinates_and_has_compatibility_wrapper():
    quote = quote_coordinates(12.9716, 77.5946, 12.9352, 77.6245, 1.0)
    assert quote["distance_km"] > 0
    assert quote_between(zone_for(12.9716, 77.5946), zone_for(12.9352, 77.6245), 1.0)["distance_km"] > 0
    same = quote_between(zone_for(12.9716, 77.5946), zone_for(12.9716, 77.5946), 1.0)
    assert same["distance_km"] == 0
    assert distance_km(12.9716, 77.5946, 12.9716, 77.5946) == 0
