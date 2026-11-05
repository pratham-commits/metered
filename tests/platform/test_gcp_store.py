import json
from types import SimpleNamespace
from unittest.mock import MagicMock

from rideshare.gcp import Store, _doc_id


class Doc:
    def __init__(self, data):
        self._data = data

    def to_dict(self):
        return self._data


class Collection:
    def __init__(self):
        self.docs = {}
        self._filters = []
        self._desc = False
        self._limit = None

    def document(self, doc_id):
        return DocRef(self, doc_id)

    def where(self, field, op, value):
        assert op == "=="
        self._filters.append((field, value))
        return self

    def order_by(self, field, direction=None):
        self._desc = direction is not None
        return self

    def limit(self, value):
        self._limit = value
        return self

    def stream(self):
        rows = list(self.docs.values())
        for field, value in self._filters:
            rows = [row for row in rows if row.get(field) == value]
        rows.sort(key=lambda row: row.get("window_start", ""), reverse=self._desc)
        if self._limit is not None:
            rows = rows[: self._limit]
        result = [Doc(row) for row in rows]
        self._filters = []
        self._desc = False
        self._limit = None
        return result


class DocRef:
    def __init__(self, collection, doc_id):
        self.collection = collection
        self.doc_id = doc_id

    def set(self, data):
        self.collection.docs[self.doc_id] = dict(data)

    def update(self, data):
        self.collection.docs.setdefault(self.doc_id, {}).update(data)


class Client:
    def __init__(self):
        self.collections = {}

    def collection(self, name):
        return self.collections.setdefault(name, Collection())


def store():
    value = Store.__new__(Store)
    value.project = "test-project"
    value.client = Client()
    value.demand_collection = "rideshare_demand_windows"
    value.driver_collection = "rideshare_driver_live"
    value.bucket = "rideshare-trip-files-test"
    value.topic = "rideshare-match-jobs"
    value.subscription = "rideshare-match-jobs-sub"
    value.storage = MagicMock()
    value.publisher = MagicMock()
    value.subscriber = MagicMock()
    value._producer = None
    return value


def test_doc_id_and_demand(monkeypatch):
    monkeypatch.delenv("KAFKA_BOOTSTRAP", raising=False)
    s = store()
    s.put_demand({"zone": "8928308280fffff", "window_start": "2026-10-29T00:00:00Z", "request_count": 3})
    s.put_demand({"zone": "8928308280fffff", "window_start": "2026-10-29T00:01:00Z", "request_count": 5})
    s.put_demand({"zone": "8928308281fffff", "window_start": "2026-10-29T00:00:00Z", "request_count": 2})

    assert _doc_id("p0", "driver-1") == "p0__driver-1"
    assert s.latest_demand("8928308280fffff")["request_count"] == 5
    assert {row["zone"]: row["request_count"] for row in s.latest_all()} == {
        "8928308280fffff": 5,
        "8928308281fffff": 2,
    }
    assert s.publish({"event_type": "TEST"}) is False


def test_pubsub_round_trip(monkeypatch):
    s = store()
    s.publisher.topic_path.return_value = "projects/test/topics/jobs"
    s.publisher.publish.return_value.result.return_value = "message-1"
    s.subscriber.subscription_path.return_value = "projects/test/subscriptions/jobs"
    s.subscriber.pull.return_value = SimpleNamespace(
        received_messages=[
            SimpleNamespace(ack_id="ack-1", message=SimpleNamespace(data=json.dumps({"ride_id": "r1"}).encode()))
        ]
    )

    assert s.send_job({"ride_id": "r1"}) == "message-1"
    jobs = s.receive_jobs()
    assert jobs == [("ack-1", {"ride_id": "r1"})]
    s.delete_job("ack-1")
    s.subscriber.acknowledge.assert_called_once_with(
        request={"subscription": "projects/test/subscriptions/jobs", "ack_ids": ["ack-1"]}
    )


def test_storage_and_available_drivers():
    s = store()
    s.put_object("gps/r1/1.json", b"{}")
    s.storage.bucket.return_value.blob.return_value.upload_from_string.assert_called_once()

    ref = s.client.collection(s.driver_collection).document("p0__driver-1")
    ref.set(
        {
            "partition_id": "p0",
            "driver_id": "driver-1",
            "status": "AVAILABLE",
            "zone": "8928308280fffff",
        }
    )
    s.client.collection(s.driver_collection).document("p0__driver-2").set(
        {
            "partition_id": "p0",
            "driver_id": "driver-2",
            "status": "ASSIGNED",
            "zone": "8928308280fffff",
        }
    )
    found = s.query_available("p0", ["8928308280fffff"])
    assert [row["driver_id"] for row in found] == ["driver-1"]
