import json
import os
import threading
from datetime import datetime, timezone

from google.cloud import firestore, pubsub_v1, storage


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _doc_id(partition_id: str, driver_id: str) -> str:
    return f"{partition_id}__{driver_id}"


class Store:
    """GCP adapter used by every service through rideshare.store."""

    def __init__(self):
        self.project = os.environ.get("GCP_PROJECT") or os.environ.get("GOOGLE_CLOUD_PROJECT")
        if not self.project:
            raise RuntimeError("GCP_PROJECT or GOOGLE_CLOUD_PROJECT must be set")
        self.database = os.environ.get("FIRESTORE_DATABASE", "(default)")
        self.driver_collection = os.environ.get("DRIVER_COLLECTION", "rideshare_driver_live")
        self.demand_collection = os.environ.get("DEMAND_COLLECTION", "rideshare_demand_windows")
        self.bucket = os.environ.get("TRIP_BUCKET", "")
        self.topic = os.environ.get("MATCH_TOPIC", "rideshare-match-jobs")
        self.subscription = os.environ.get("MATCH_SUBSCRIPTION", "rideshare-match-jobs-sub")
        self.client = firestore.Client(project=self.project, database=self.database)
        self.storage = storage.Client(project=self.project)
        self.publisher = pubsub_v1.PublisherClient()
        self.subscriber = pubsub_v1.SubscriberClient()
        self._producer = None
        self._lock = threading.Lock()

    # Firestore live driver table -------------------------------------------

    def _driver_ref(self, partition_id: str, driver_id: str):
        return self.client.collection(self.driver_collection).document(
            _doc_id(partition_id, driver_id)
        )

    def _driver(self, data: dict) -> dict:
        data = dict(data)
        data.setdefault("assigned_ride_id", "")
        return data

    def put_driver(self, item: dict) -> None:
        self._driver_ref(item["partition_id"], item["driver_id"]).set(dict(item))

    def set_presence(self, item: dict, partitions: list[str]) -> None:
        target_ref = self._driver_ref(item["partition_id"], item["driver_id"])
        old_partitions = sorted(set(partitions) | {item["partition_id"]})

        @firestore.transactional
        def move(transaction):
            target = target_ref.get(transaction=transaction)
            if target.exists and target.to_dict().get("status") == "ASSIGNED":
                raise ValueError(
                    "driver is assigned; complete the trip before changing presence"
                )
            old_refs = []
            for partition in old_partitions:
                if partition == item["partition_id"]:
                    continue
                ref = self._driver_ref(partition, item["driver_id"])
                snapshot = ref.get(transaction=transaction)
                if snapshot.exists:
                    if snapshot.to_dict().get("status") == "ASSIGNED":
                        raise ValueError(
                            "driver is assigned; complete the trip before changing presence"
                        )
                    old_refs.append(ref)
            for ref in old_refs:
                transaction.delete(ref)
            transaction.set(target_ref, dict(item))

        move(self.client.transaction())

    def query_available(self, partition_id: str, zones: list[str]) -> list[dict]:
        wanted = set(zones)
        query = self.client.collection(self.driver_collection).where(
            "partition_id", "==", partition_id
        )
        found = []
        for doc in query.stream():
            item = self._driver(doc.to_dict() or {})
            if item.get("status") == "AVAILABLE" and item.get("zone") in wanted:
                found.append(item)
        return found

    def list_in_zones(self, partitions: list[str], zones: list[str]) -> list[dict]:
        """Online drivers (available or already assigned) inside these H3 cells."""
        wanted = set(zones)
        found = []
        seen = set()
        for partition_id in partitions:
            query = self.client.collection(self.driver_collection).where(
                "partition_id", "==", partition_id
            )
            for doc in query.stream():
                item = self._driver(doc.to_dict() or {})
                if item.get("status") not in {"AVAILABLE", "ASSIGNED"}:
                    continue
                if item.get("zone") not in wanted:
                    continue
                key = item.get("driver_id")
                if key in seen:
                    continue
                seen.add(key)
                found.append(item)
        return found

    def assign(self, partition_id: str, driver_id: str, ride_id: str) -> bool:
        ref = self._driver_ref(partition_id, driver_id)

        @firestore.transactional
        def take(transaction) -> bool:
            snapshot = ref.get(transaction=transaction)
            if not snapshot.exists:
                return False
            item = snapshot.to_dict() or {}
            status = item.get("status")
            if status == "ASSIGNED" and item.get("assigned_ride_id") == ride_id:
                transaction.update(
                    ref, {"updated_at": _now(), "assigned_ride_id": ride_id}
                )
                return True
            if status != "AVAILABLE":
                return False
            transaction.update(
                ref,
                {
                    "status": "ASSIGNED",
                    "assigned_ride_id": ride_id,
                    "updated_at": _now(),
                },
            )
            return True

        return bool(take(self.client.transaction()))

    def update_location(self, driver_id: str, lat: float, lng: float, zone: str, partitions: list[str]) -> bool:
        """Keep an assigned driver's pin moving without dropping the ride lock."""
        for partition_id in partitions:
            ref = self._driver_ref(partition_id, driver_id)
            snapshot = ref.get()
            if not snapshot.exists:
                continue
            if (snapshot.to_dict() or {}).get("status") != "ASSIGNED":
                continue
            ref.update({"lat": lat, "lng": lng, "zone": zone, "updated_at": _now()})
            return True
        return False

    def find_driver(self, driver_id: str, partitions: list[str]) -> dict | None:
        for partition_id in partitions:
            snapshot = self._driver_ref(partition_id, driver_id).get()
            if snapshot.exists:
                return self._driver(snapshot.to_dict() or {})
        return None

    def release_assigned(self, driver_id: str, partitions: list[str]) -> bool:
        """Drop a leftover trip lock so the driver can go online again."""
        released = False
        for partition_id in partitions:
            ref = self._driver_ref(partition_id, driver_id)
            snapshot = ref.get()
            if not snapshot.exists:
                continue
            if (snapshot.to_dict() or {}).get("status") != "ASSIGNED":
                continue
            ref.update({"status": "AVAILABLE", "assigned_ride_id": "", "updated_at": _now()})
            released = True
        return released

    def release(self, partition_id: str, driver_id: str) -> None:
        self._driver_ref(partition_id, driver_id).update(
            {"status": "AVAILABLE", "assigned_ride_id": "", "updated_at": _now()}
        )

    # Cloud Storage ----------------------------------------------------------

    def put_object(self, key: str, body: bytes) -> None:
        bucket = self.storage.bucket(self.bucket)
        blob = bucket.blob(key)
        blob.upload_from_string(body, content_type="application/json")

    # Pub/Sub ----------------------------------------------------------------

    def send_job(self, body: dict) -> str:
        topic_path = self.publisher.topic_path(self.project, self.topic)
        future = self.publisher.publish(topic_path, json.dumps(body).encode("utf-8"))
        return future.result(timeout=20)

    def receive_jobs(self, limit: int = 5) -> list[tuple[str, dict]]:
        subscription_path = self.subscriber.subscription_path(
            self.project, self.subscription
        )
        response = self.subscriber.pull(
            request={"subscription": subscription_path, "max_messages": limit},
            timeout=20,
        )
        jobs = []
        for message in response.received_messages:
            jobs.append(
                (
                    message.ack_id,
                    json.loads(message.message.data.decode("utf-8")),
                )
            )
        return jobs

    def delete_job(self, receipt: str) -> None:
        subscription_path = self.subscriber.subscription_path(
            self.project, self.subscription
        )
        self.subscriber.acknowledge(
            request={"subscription": subscription_path, "ack_ids": [receipt]}
        )

    # Firestore demand table -------------------------------------------------

    def latest_demand(self, zone: str) -> dict | None:
        query = (
            self.client.collection(self.demand_collection)
            .where("zone", "==", zone)
            .order_by("window_start", direction=firestore.Query.DESCENDING)
            .limit(1)
        )
        for doc in query.stream():
            return dict(doc.to_dict() or {})
        return None

    def latest_all(self) -> list[dict]:
        query = (
            self.client.collection(self.demand_collection)
            .order_by("window_start", direction=firestore.Query.DESCENDING)
            .limit(200)
        )
        latest: dict[str, dict] = {}
        for doc in query.stream():
            row = dict(doc.to_dict() or {})
            zone = row.get("zone")
            if zone and zone not in latest:
                latest[zone] = row
        return list(latest.values())

    def put_demand(self, item: dict) -> None:
        zone = str(item["zone"])
        window_start = str(item["window_start"])
        doc_id = f"{zone}__{window_start}".replace("/", "_")
        self.client.collection(self.demand_collection).document(doc_id).set(dict(item))

    # Kafka ------------------------------------------------------------------

    def publish(self, event: dict) -> bool:
        topic = os.environ.get("KAFKA_TOPIC_EVENTS", "ride-events")
        return self._publish(topic, event)

    def publish_topic(self, topic: str, event: dict) -> bool:
        return self._publish(topic, event)

    def _get_producer(self, brokers: str):
        if self._producer is not None:
            return self._producer
        from kafka import KafkaProducer

        kwargs = {}
        if os.environ.get("KAFKA_SECURITY_PROTOCOL", "SSL") == "SSL":
            ca_file = os.environ.get("KAFKA_SSL_CA_FILE")
            if ca_file:
                kwargs["ssl_cafile"] = ca_file
            kwargs["ssl_check_hostname"] = (
                os.environ.get("KAFKA_SSL_CHECK_HOSTNAME", "false").lower() == "true"
            )
        self._producer = KafkaProducer(
            bootstrap_servers=[part.strip() for part in brokers.split(",") if part.strip()],
            security_protocol=os.environ.get("KAFKA_SECURITY_PROTOCOL", "SSL"),
            value_serializer=lambda value: json.dumps(value).encode("utf-8"),
            retries=3,
            request_timeout_ms=10000,
            **kwargs,
        )
        return self._producer

    def _publish(self, topic: str, event: dict) -> bool:
        brokers = os.environ.get("KAFKA_BOOTSTRAP", "")
        if not brokers:
            return False
        try:
            with self._lock:
                future = self._get_producer(brokers).send(topic, event)
            future.get(timeout=10)
            return True
        except Exception:
            self._producer = None
            return False


_store: Store | None = None


def get_store() -> Store:
    global _store
    if _store is None:
        _store = Store()
    return _store
