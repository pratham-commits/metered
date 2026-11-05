"""Person 2 owns the ring algorithm tests.

No GCP credentials are required. Run:

  PYTHONPATH=services/common pytest services/common/tests/test_ring.py

The same cases also live under tests/platform/test_shared.py so
scripts/check-platform.sh covers them in the Person 1 suite.
"""

from rideshare.hashring import HashRing, nodes_from_env
from rideshare.zones import cells_around


def test_nodes_from_env_splits_and_strips():
    assert nodes_from_env("p0, p1,p2, p3") == ["p0", "p1", "p2", "p3"]
    assert nodes_from_env("") == []


def test_owner_is_stable_across_constructions():
    zones = cells_around(12.9716, 77.5946, 2)
    first = HashRing(["p0", "p1", "p2", "p3"]).ownership(zones)
    second = HashRing(["p0", "p1", "p2", "p3"]).ownership(zones)
    assert first == second
    assert set(first.values()) <= {"p0", "p1", "p2", "p3"}


def test_adding_p4_moves_some_cells_and_leaves_some():
    zones = cells_around(12.9716, 77.5946, 3)
    before = HashRing(["p0", "p1", "p2", "p3"]).ownership(zones)
    after = HashRing(["p0", "p1", "p2", "p3", "p4"]).ownership(zones)
    moved = [zone for zone in zones if before[zone] != after[zone]]
    stayed = [zone for zone in zones if before[zone] == after[zone]]
    assert moved, "adding p4 must move at least one cell"
    assert stayed, "adding p4 must leave at least one cell put"
    assert set(after.values()) <= {"p0", "p1", "p2", "p3", "p4"}
    assert all(after[zone] == "p4" for zone in moved)
