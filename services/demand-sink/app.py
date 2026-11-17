import json
import logging
import os
import threading

from fastapi import FastAPI, HTTPException
from kafka import KafkaConsumer
from kafka.errors import KafkaError
from prometheus_client import Counter

from rideshare.store import get_store
from rideshare.web import install

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("demand-sink")

app = FastAPI()

CONSUMED = Counter(
    "demand_sink_records_total",
    "Demand records consumed and persisted",
)
FAILED = Counter(
    "demand_sink_errors_total",
    "Demand sink processing errors",
)

REQUIRED_FIELDS = (
    "zone",
    "window_start",
    "window_end",
    "unique_riders",
    "request_count",
    "assigned_count",
    "online_drivers",
    "queue_length",
    "imbalance",
)

ready = threading.Event()
stop_event = threading.Event()


def ready_check():
    if not ready.is_set():
        raise HTTPException(
            status_code=503,
            detail="Kafka consumer is not ready",
        )


install(app, "demand-sink", ready_check=ready_check)


def _consumer_config():
    brokers = os.environ.get("KAFKA_BOOTSTRAP", "kafka:9092")
    protocol = os.environ.get("KAFKA_SECURITY_PROTOCOL", "SSL")

    config = {
        "bootstrap_servers": [
            item.strip() for item in brokers.split(",") if item.strip()
        ],
        "group_id": "demand-sink",
        "auto_offset_reset": "earliest",
        "enable_auto_commit": False,
        "security_protocol": protocol,
        "request_timeout_ms": 30000,
        "api_version_auto_timeout_ms": 10000,
    }

    if protocol == "SSL":
        ca_file = os.environ.get("KAFKA_SSL_CA_FILE")
        if ca_file:
            config["ssl_cafile"] = ca_file

        config["ssl_check_hostname"] = (
            os.environ.get("KAFKA_SSL_CHECK_HOSTNAME", "false").lower()
            == "true"
        )

    return config


def _persist(value: bytes, topic: str):
    payload = json.loads(value.decode("utf-8"))

    if not isinstance(payload, dict):
        raise ValueError("Demand message must be a JSON object")

    missing = [field for field in REQUIRED_FIELDS if field not in payload]
    if missing:
        raise ValueError(f"Demand message missing fields: {missing}")

    item = {field: payload[field] for field in REQUIRED_FIELDS}
    item["topic"] = topic

    get_store().put_demand(item)
    CONSUMED.inc()

    log.info(
        "Demand window persisted",
        extra={"zone": item["zone"], "window_start": item["window_start"]},
    )


def consume_forever():
    topic = os.environ.get("KAFKA_TOPIC_RESULTS", "demand-results")

    while not stop_event.is_set():
        consumer = None

        try:
            log.info("Connecting to Kafka topic %s", topic)

            consumer = KafkaConsumer(**_consumer_config())

            # Don't declare readiness until the topic actually exists.
            if topic not in consumer.topics():
                raise RuntimeError(f"Kafka topic {topic!r} does not exist")

            consumer.subscribe([topic])
            ready.set()
            log.info("Consuming topic %s", topic)

            while not stop_event.is_set():
                records = consumer.poll(timeout_ms=1000, max_records=1)

                for messages in records.values():
                    for message in messages:
                        try:
                            _persist(message.value, topic)
                        except (ValueError, UnicodeDecodeError, json.JSONDecodeError) as exc:
                            # Skip malformed messages rather than getting stuck
                            # forever on the same Kafka offset.
                            FAILED.inc()
                            log.exception("Invalid demand message: %s", exc)

                        # Acknowledge only after persistence (or invalid-message
                        # handling) has completed.
                        consumer.commit()

        except Exception:
            ready.clear()
            FAILED.inc()
            log.exception("Demand consumer unavailable; retrying in 5 seconds")

        finally:
            ready.clear()
            if consumer is not None:
                try:
                    consumer.close(autocommit=False)
                except Exception:
                    log.exception("Error closing Kafka consumer")

        stop_event.wait(5)


@app.on_event("startup")
def start_consumer():
    thread = threading.Thread(
        target=consume_forever,
        name="demand-consumer",
        daemon=True,
    )
    thread.start()


@app.on_event("shutdown")
def stop_consumer():
    stop_event.set()
