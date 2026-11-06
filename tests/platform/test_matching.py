"""Person 2. Matching must group live H3 cells by ring owner, then ack a job
only after the ride row is updated."""

from unittest.mock import MagicMock

from rideshare.hashring import HashRing
from rideshare.zones import cells_around, neighbors, zone_for


def test_each_zone_is_filed_under_its_owner(apps):
    group = apps["matching"].group_zones_by_partition
    ring = HashRing(["p0", "p1", "p2", "p3"])
    zones = ["aa", "bb", "cc", "dd", "ee"]
    grouped = group(zones, ring)
    seen = []
    for partition, members in grouped.items():
        assert partition in {"p0", "p1", "p2", "p3"}
        for zone in members:
            assert ring.owner(zone) == partition
            seen.append(zone)
    assert sorted(seen) == sorted(zones)


def test_empty_zone_list_groups_nothing(apps):
    group = apps["matching"].group_zones_by_partition
    assert group([], HashRing(["p0", "p1", "p2", "p3"])) == {}


def test_live_h3_disk_is_partitioned_once(apps):
    group = apps["matching"].group_zones_by_partition
    pickup = zone_for(12.9716, 77.5946)
    zones = cells_around(12.9716, 77.5946, 3)
    ring = HashRing(["p0", "p1", "p2", "p3"])
    grouped = group(zones, ring)
    flat = [zone for members in grouped.values() for zone in members]
    assert sorted(flat) == sorted(zones)
    assert len(flat) == len(set(flat)) == 37
    assert pickup in flat
    assert set(grouped) <= {"p0", "p1", "p2", "p3"}
    assert set(neighbors(pickup)) <= set(flat)


def test_duplicate_driver_is_offered_once(apps, monkeypatch):
    module = apps["matching"]
    pickup = zone_for(19.076, 72.877)
    zone = neighbors(pickup)[0]
    ring = HashRing(["p0"])
    monkeypatch.setattr(module, "ring", lambda: ring)

    candidate = MagicMock(driver_id="driver-1", partition_id="p0")
    driver = MagicMock()
    driver.GetCandidates.return_value = MagicMock(candidates=[candidate, candidate])
    monkeypatch.setattr(module, "driver_stub", lambda: (driver, MagicMock()))

    assign = MagicMock()
    assign.Assign.return_value = MagicMock(assigned=True, reason="assigned")
    monkeypatch.setattr(module, "dispatch_stub", lambda: (assign, MagicMock()))

    conn = MagicMock()
    monkeypatch.setattr(module, "connection", _connection(conn))
    store = MagicMock()
    monkeypatch.setattr(module, "get_store", lambda: store)

    module.handle_job({"ride_id": "ride-1", "pickup_zone": pickup, "rider_id": "rider-1"})

    assert driver.GetCandidates.call_count == 1
    assign.Assign.assert_not_called()
    update = conn.execute.call_args_list[-1]
    assert "REQUESTED" in update.args[0]
    assert update.args[1][0] == "REQUESTED"
    store.publish.assert_not_called()
    assert zone in driver.GetCandidates.call_args.args[0].neighbor_zones


def test_second_candidate_wins_when_the_first_is_taken(apps, monkeypatch):
    module = apps["matching"]
    pickup = zone_for(28.6139, 77.2090)
    monkeypatch.setattr(module, "ring", lambda: HashRing(["p0"]))
    first = MagicMock(driver_id="driver-1", partition_id="p0")
    second = MagicMock(driver_id="driver-2", partition_id="p0")
    driver = MagicMock()
    driver.GetCandidates.return_value = MagicMock(candidates=[first, second])
    monkeypatch.setattr(module, "driver_stub", lambda: (driver, MagicMock()))
    assign = MagicMock()
    assign.Assign.side_effect = [
        MagicMock(assigned=False, reason="driver_not_available"),
        MagicMock(assigned=True, reason="assigned"),
    ]
    monkeypatch.setattr(module, "dispatch_stub", lambda: (assign, MagicMock()))
    conn = MagicMock()
    monkeypatch.setattr(module, "connection", _connection(conn))
    store = MagicMock()
    monkeypatch.setattr(module, "get_store", lambda: store)

    module.handle_job({"ride_id": "ride-2", "pickup_zone": pickup, "rider_id": "rider-2"})

    assign.Assign.assert_not_called()
    update = conn.execute.call_args_list[-1]
    assert "REQUESTED" in update.args[0]
    assert update.args[1][0] == "REQUESTED"
    store.publish.assert_not_called()


def test_no_driver_does_not_publish_assignment(apps, monkeypatch):
    module = apps["matching"]
    pickup = zone_for(13.0827, 80.2707)
    monkeypatch.setattr(module, "ring", lambda: HashRing(["p0"]))
    driver = MagicMock()
    driver.GetCandidates.return_value = MagicMock(candidates=[])
    monkeypatch.setattr(module, "driver_stub", lambda: (driver, MagicMock()))
    assign = MagicMock()
    assign.Assign.return_value = MagicMock(assigned=False, reason="driver_not_available")
    monkeypatch.setattr(module, "dispatch_stub", lambda: (assign, MagicMock()))
    conn = MagicMock()
    monkeypatch.setattr(module, "connection", _connection(conn))
    store = MagicMock()
    monkeypatch.setattr(module, "get_store", lambda: store)

    module.handle_job({"ride_id": "ride-3", "pickup_zone": pickup, "rider_id": "rider-3"})

    update = conn.execute.call_args_list[-1]
    assert "status = %s" in update.args[0]
    assert update.args[1][0] == "NO_DRIVER"
    assign.Assign.assert_not_called()
    store.publish.assert_not_called()


def test_failed_job_is_not_acked(apps, monkeypatch):
    module = apps["matching"]
    monkeypatch.setattr(module, "POLL_IDLE_SEC", 0)
    stop_calls = {"n": 0}
    store = MagicMock()

    def receive(_limit):
        stop_calls["n"] += 1
        if stop_calls["n"] == 1:
            return [("ack-1", {"ride_id": "ride-x", "pickup_zone": "not-a-cell"})]
        module_stop.set()
        return []

    store.receive_jobs.side_effect = receive
    monkeypatch.setattr(module, "get_store", lambda: store)
    import threading

    global module_stop
    module_stop = threading.Event()
    module.poll_loop(module_stop)
    store.delete_job.assert_not_called()


def test_successful_job_is_acked(apps, monkeypatch):
    module = apps["matching"]
    monkeypatch.setattr(module, "POLL_IDLE_SEC", 0)
    monkeypatch.setattr(module, "handle_job", lambda job: None)
    store = MagicMock()
    state = {"n": 0}

    def receive(_limit):
        state["n"] += 1
        if state["n"] == 1:
            return [("ack-9", {"ride_id": "ride-ok", "pickup_zone": "cell"})]
        done.set()
        return []

    store.receive_jobs.side_effect = receive
    monkeypatch.setattr(module, "get_store", lambda: store)
    import threading

    global done
    done = threading.Event()
    module.poll_loop(done)
    store.delete_job.assert_called_once_with("ack-9")


def _connection(conn):
    from contextlib import contextmanager

    @contextmanager
    def connection():
        yield conn

    return connection
