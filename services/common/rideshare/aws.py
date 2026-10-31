import json
import os
import threading
from datetime import datetime, timezone

import boto3
from botocore.exceptions import ClientError

from rideshare.zones import all_zones


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _client(name: str):
    kwargs = {"region_name": os.environ.get("AWS_REGION", "ap-south-1")}
    endpoint = os.environ.get("AWS_ENDPOINT_URL")
    if endpoint:
        kwargs["endpoint_url"] = endpoint
    return boto3.client(name, **kwargs)


def _driver(item: dict) -> dict:
    return {
        "partition_id": item["partition_id"]["S"],
        "driver_id": item["driver_id"]["S"],
        "status": item["status"]["S"],
        "zone": item["zone"]["S"],
        "lat": float(item["lat"]["N"]),
        "lng": float(item["lng"]["N"]),
        "updated_at": item["updated_at"]["S"],
        "assigned_ride_id": item.get("assigned_ride_id", {}).get("S", ""),
    }


def _encode_driver(item: dict) -> dict:
    """Encode the live-driver schema consistently for writes and transactions."""
    encoded = {
        field: {"S": item[field]}
        for field in ("partition_id", "driver_id", "status", "zone", "updated_at")
    }
    encoded.update({field: {"N": str(item[field])} for field in ("lat", "lng")})
    encoded["assigned_ride_id"] = {"S": item.get("assigned_ride_id", "")}
    return encoded


class Store:
    def __init__(self):
        self.ddb = _client("dynamodb")
        self.s3 = _client("s3")
        self.sqs = _client("sqs")
        self.driver_table = os.environ["DRIVER_TABLE"]
        self.demand_table = os.environ["DEMAND_TABLE"]
        self.bucket = os.environ.get("TRIP_BUCKET", "")
        self.queue_url = os.environ.get("MATCH_QUEUE_URL", "")
        self._producer = None
        self._lock = threading.Lock()

    def put_driver(self, item: dict) -> None:
        self.ddb.put_item(TableName=self.driver_table, Item=_encode_driver(item))

    def set_presence(self, item: dict, partitions: list[str]) -> None:
        # Caller holds the SQL profile lock. Never reset an assigned driver's status.
        target = item["partition_id"]
        operations = []
        for partition in set(partitions) | {target}:
            if partition == target:
                continue
            key = {"partition_id": {"S": partition}, "driver_id": {"S": item["driver_id"]}}
            old = self.ddb.get_item(TableName=self.driver_table, Key=key, ConsistentRead=True).get("Item")
            if old:
                operations.append({"Delete": {
                    "TableName": self.driver_table, "Key": key,
                    "ConditionExpression": "#s <> :assigned",
                    "ExpressionAttributeNames": {"#s": "status"},
                    "ExpressionAttributeValues": {":assigned": {"S": "ASSIGNED"}},
                }})
        encoded = _encode_driver(item)
        operations.append({"Put": {
            "TableName": self.driver_table, "Item": encoded,
            "ConditionExpression": "attribute_not_exists(partition_id) OR #s <> :assigned",
            "ExpressionAttributeNames": {"#s": "status"},
            "ExpressionAttributeValues": {":assigned": {"S": "ASSIGNED"}},
        }})
        try:
            self.ddb.transact_write_items(TransactItems=operations)
        except ClientError as exc:
            if exc.response["Error"]["Code"] == "TransactionCanceledException" and any(
                reason.get("Code") == "ConditionalCheckFailed"
                for reason in exc.response.get("CancellationReasons", [])
            ):
                raise ValueError("driver is assigned; complete the trip before changing presence") from exc
            raise

    def query_available(self, partition_id: str, zones: list[str]) -> list[dict]:
        wanted = set(zones)
        found = []
        kwargs = dict(
            TableName=self.driver_table,
            KeyConditionExpression="partition_id = :p",
            ExpressionAttributeValues={":p": {"S": partition_id}},
            ConsistentRead=True,
        )
        while True:
            resp = self.ddb.query(**kwargs)
            for raw in resp.get("Items", []):
                item = _driver(raw)
                if item["status"] == "AVAILABLE" and item["zone"] in wanted:
                    found.append(item)
            if not resp.get("LastEvaluatedKey"):
                return found
            kwargs["ExclusiveStartKey"] = resp["LastEvaluatedKey"]

    def assign(self, partition_id: str, driver_id: str, ride_id: str) -> bool:
        try:
            self.ddb.update_item(
                TableName=self.driver_table,
                Key={"partition_id": {"S": partition_id}, "driver_id": {"S": driver_id}},
                UpdateExpression="SET #s = :assigned, assigned_ride_id = :ride, updated_at = :now",
                ConditionExpression=(
                    "attribute_exists(partition_id) AND "
                    "(#s = :available OR (#s = :assigned AND assigned_ride_id = :ride))"
                ),
                ExpressionAttributeNames={"#s": "status"},
                ExpressionAttributeValues={
                    ":assigned": {"S": "ASSIGNED"},
                    ":available": {"S": "AVAILABLE"},
                    ":ride": {"S": ride_id},
                    ":now": {"S": _now()},
                },
            )
            return True
        except ClientError as exc:
            if exc.response["Error"]["Code"] == "ConditionalCheckFailedException":
                return False
            raise

    def release(self, partition_id: str, driver_id: str) -> None:
        self.ddb.update_item(
            TableName=self.driver_table,
            Key={"partition_id": {"S": partition_id}, "driver_id": {"S": driver_id}},
            UpdateExpression="SET #s = :available, assigned_ride_id = :empty, updated_at = :now",
            ConditionExpression="attribute_exists(partition_id)",
            ExpressionAttributeNames={"#s": "status"},
            ExpressionAttributeValues={
                ":available": {"S": "AVAILABLE"},
                ":empty": {"S": ""},
                ":now": {"S": _now()},
            },
        )

    def put_object(self, key: str, body: bytes) -> None:
        self.s3.put_object(Bucket=self.bucket, Key=key, Body=body, ContentType="application/json")

    def send_job(self, body: dict) -> str:
        resp = self.sqs.send_message(QueueUrl=self.queue_url, MessageBody=json.dumps(body))
        return resp["MessageId"]

    def receive_jobs(self, limit: int = 5) -> list[tuple[str, dict]]:
        resp = self.sqs.receive_message(
            QueueUrl=self.queue_url,
            MaxNumberOfMessages=limit,
            WaitTimeSeconds=20,
            VisibilityTimeout=60,
        )
        out = []
        for message in resp.get("Messages", []):
            out.append((message["ReceiptHandle"], json.loads(message["Body"])))
        return out

    def delete_job(self, receipt: str) -> None:
        self.sqs.delete_message(QueueUrl=self.queue_url, ReceiptHandle=receipt)

    def latest_demand(self, zone: str) -> dict | None:
        resp = self.ddb.query(
            TableName=self.demand_table,
            KeyConditionExpression="#z = :z",
            ExpressionAttributeNames={"#z": "zone"},
            ExpressionAttributeValues={":z": {"S": zone}},
            ScanIndexForward=False,
            Limit=1,
        )
        items = resp.get("Items", [])
        if not items:
            return None
        return {key: value["S"] for key, value in items[0].items()}

    def latest_all(self) -> list[dict]:
        rows = []
        for zone in all_zones():
            row = self.latest_demand(zone)
            if row:
                rows.append(row)
        return rows

    def put_demand(self, item: dict) -> None:
        self.ddb.put_item(
            TableName=self.demand_table,
            Item={key: {"S": "" if value is None else str(value)} for key, value in item.items()},
        )

    def publish(self, event: dict) -> bool:
        topic = os.environ.get("KAFKA_TOPIC_EVENTS", "ride-events")
        return self._publish(topic, event)

    def publish_topic(self, topic: str, event: dict) -> bool:
        return self._publish(topic, event)

    def _get_producer(self, brokers: str):
        if self._producer is not None:
            return self._producer
        from kafka import KafkaProducer

        self._producer = KafkaProducer(
            bootstrap_servers=[part.strip() for part in brokers.split(",") if part.strip()],
            security_protocol=os.environ.get("KAFKA_SECURITY_PROTOCOL", "SSL"),
            value_serializer=lambda value: json.dumps(value).encode("utf-8"),
            retries=3,
            request_timeout_ms=10000,
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
