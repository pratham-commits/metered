"""Person 2. Dispatch.Assign is the lock: one driver, one ride."""

import json
from contextlib import contextmanager
from unittest.mock import MagicMock


def db_mock(monkeypatch, module):
    conn = MagicMock()

    @contextmanager
    def connection():
        yield conn

    monkeypatch.setattr(module, "connection", connection)
    return conn


def test_assign_wins_and_records_the_hop(apps, monkeypatch):
    module = apps["dispatch"]
    store = MagicMock()
    store.assign.return_value = True
    monkeypatch.setattr(module, "get_store", lambda: store)
    conn = db_mock(monkeypatch, module)

    response = module.DispatchServicer().Assign(
        module.dispatch_pb2.AssignRequest(ride_id="ride-1", driver_id="driver-1", partition_id="p0"),
        None,
    )

    assert response.assigned is True
    assert response.reason == "assigned"
    store.assign.assert_called_once_with("p0", "driver-1", "ride-1")
    sql, params = conn.execute.call_args.args
    detail = json.loads(params[4])
    assert "ride_hops" in sql
    assert detail["assigned"] is True
    assert detail["reason"] == "assigned"


def test_taken_driver_is_rejected(apps, monkeypatch):
    module = apps["dispatch"]
    store = MagicMock()
    store.assign.return_value = False
    monkeypatch.setattr(module, "get_store", lambda: store)
    conn = db_mock(monkeypatch, module)

    response = module.DispatchServicer().Assign(
        module.dispatch_pb2.AssignRequest(ride_id="ride-2", driver_id="driver-1", partition_id="p1"),
        None,
    )

    assert response.assigned is False
    assert response.reason == "driver_not_available"
    assert json.loads(conn.execute.call_args.args[1][4])["assigned"] is False


def test_store_error_does_not_grant_the_driver(apps, monkeypatch):
    module = apps["dispatch"]
    store = MagicMock()
    store.assign.side_effect = RuntimeError("firestore down")
    monkeypatch.setattr(module, "get_store", lambda: store)
    conn = db_mock(monkeypatch, module)

    response = module.DispatchServicer().Assign(
        module.dispatch_pb2.AssignRequest(ride_id="ride-3", driver_id="driver-9", partition_id="p2"),
        None,
    )

    assert response.assigned is False
    assert response.reason == "driver_not_available"
    assert json.loads(conn.execute.call_args.args[1][4])["assigned"] is False
