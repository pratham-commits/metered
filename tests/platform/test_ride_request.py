"""Person 2. Ride Request is the public API: zones, ring preview, and geocoding.
The Mapbox token stays on the server."""

import json
from unittest.mock import MagicMock
from urllib.error import URLError

from fastapi.testclient import TestClient

from rideshare.zones import cells_around, zone_for


def test_zones_follow_the_live_coordinate(apps):
    client = TestClient(apps["ride-request"].app)
    response = client.get("/api/zones", params={"lat": 12.9716, "lng": 77.5946, "k": 0})
    assert response.status_code == 200
    body = response.json()
    assert body["zones"] == [zone_for(12.9716, 77.5946)]


def test_ring_preview_moves_only_a_fraction_when_p4_is_added(apps):
    client = TestClient(apps["ride-request"].app)
    zones = cells_around(12.9716, 77.5946, 3)
    response = client.post(
        "/api/ring/preview",
        json={"nodes": ["p0", "p1", "p2", "p3", "p4"], "zones": zones},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["moved"]
    assert body["stayed"]
    assert set(body["moved"]).isdisjoint(body["stayed"])
    assert set(body["moved"]) | set(body["stayed"]) == set(zones)
    assert 0 < body["moved_fraction"] < 1
    assert all(body["after"][zone] == "p4" for zone in body["moved"])


def test_geocode_rejects_a_short_query(apps):
    response = TestClient(apps["ride-request"].app).get("/api/geocode", params={"q": "a"})
    assert response.status_code == 400


def test_geocode_reports_a_missing_token(apps, monkeypatch):
    monkeypatch.setattr(apps["ride-request"], "MAPBOX_ACCESS_TOKEN", "")
    response = TestClient(apps["ride-request"].app).get("/api/geocode", params={"q": "India Gate"})
    assert response.status_code == 503


def test_geocode_returns_label_and_coordinates(apps, monkeypatch):
    module = apps["ride-request"]
    monkeypatch.setattr(module, "MAPBOX_ACCESS_TOKEN", "pk.test")
    payload = {
        "features": [
            {"place_name": "India Gate, Delhi", "center": [77.229385, 28.602232]},
            {"place_name": "skipped", "center": [1]},
        ]
    }
    response_body = MagicMock()
    response_body.read.return_value = json.dumps(payload).encode()
    response_body.__enter__.return_value = response_body
    response_body.__exit__.return_value = False
    monkeypatch.setattr(module.urllib.request, "urlopen", lambda *args, **kwargs: response_body)

    response = TestClient(module.app).get("/api/geocode", params={"q": "India Gate", "limit": 5})

    assert response.status_code == 200
    body = response.json()
    assert body["query"] == "India Gate"
    assert body["results"] == [{"label": "India Gate, Delhi", "lng": 77.229385, "lat": 28.602232}]


def test_geocode_turns_a_provider_outage_into_502(apps, monkeypatch):
    module = apps["ride-request"]
    monkeypatch.setattr(module, "MAPBOX_ACCESS_TOKEN", "pk.test")

    def explode(*args, **kwargs):
        raise URLError("down")

    monkeypatch.setattr(module.urllib.request, "urlopen", explode)
    response = TestClient(module.app).get("/api/geocode", params={"q": "India Gate"})
    assert response.status_code == 502


def test_ride_request_rejects_impossible_coordinates(apps):
    response = TestClient(apps["ride-request"].app).post(
        "/api/ride-requests",
        json={
            "rider_id": "00000000-0000-0000-0000-000000000001",
            "pickup_lat": 120,
            "pickup_lng": 77,
            "drop_lat": 12,
            "drop_lng": 77,
        },
    )
    assert response.status_code == 422


def test_public_config_names_the_graph_without_a_secret_token_shape(apps):
    body = TestClient(apps["ride-request"].app).get("/api/config").json()
    assert body["h3_resolution"] == 8
    assert "ride-request" not in body["graph"]
    assert set(body["graph"]) == {"rider", "driver", "trip", "dispatch_grpc"}
    token = body["mapbox_token"]
    assert token == "" or token.startswith("pk.")
