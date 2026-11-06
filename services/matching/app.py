import os
import threading
import uuid
from collections import defaultdict
from contextlib import asynccontextmanager
from datetime import datetime, timezone

import grpc
from fastapi import FastAPI

from ride.v1 import dispatch_pb2, dispatch_pb2_grpc, driver_pb2, driver_pb2_grpc
from rideshare.db import connection, ping
from rideshare.hashring import HashRing, nodes_from_env
from rideshare.hops import record_hop
from rideshare.logging_setup import configure
from rideshare.store import get_store
from rideshare.web import install
from rideshare.zones import neighbors

DEFAULT_PARTITIONS = "p0,p1,p2,p3"
DEFAULT_CANDIDATES = 5
POLL_IDLE_SEC = 1.0
DRIVER_GRPC = os.environ.get(
    "DRIVER_GRPC", "driver.rideshare.svc.cluster.local:9002"
)
DISPATCH_GRPC = os.environ.get(
    "DISPATCH_GRPC", "dispatch.rideshare.svc.cluster.local:9005"
)

log = configure()


def ring() -> HashRing:
    return HashRing(nodes_from_env(os.environ.get("HASH_NODES", DEFAULT_PARTITIONS)))


def group_zones_by_partition(zones: list[str], hash_ring: HashRing) -> dict[str, list[str]]:
    grouped: dict[str, list[str]] = defaultdict(list)
    for zone in zones:
        grouped[hash_ring.owner(zone)].append(zone)
    return dict(grouped)


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def driver_stub():
    channel = grpc.insecure_channel(DRIVER_GRPC)
    return driver_pb2_grpc.DriverLookupStub(channel), channel


def dispatch_stub():
    channel = grpc.insecure_channel(DISPATCH_GRPC)
    return dispatch_pb2_grpc.DispatchStub(channel), channel


def handle_job(job: dict) -> None:
    ride_id = job["ride_id"]
    pickup_zone = job["pickup_zone"]
    hash_ring = ring()
    neighbor_zones = neighbors(pickup_zone)
    by_partition = group_zones_by_partition(neighbor_zones, hash_ring)

    stub, channel = driver_stub()
    try:
        merged: list[driver_pb2.Candidate] = []
        seen: set[str] = set()
        for partition_id, zones in by_partition.items():
            response = stub.GetCandidates(
                driver_pb2.CandidateRequest(
                    partition_id=partition_id,
                    pickup_zone=pickup_zone,
                    neighbor_zones=zones,
                    limit=DEFAULT_CANDIDATES,
                ),
                timeout=10,
            )
            for candidate in response.candidates:
                if candidate.driver_id in seen:
                    continue
                seen.add(candidate.driver_id)
                merged.append(candidate)
    finally:
        channel.close()

    with connection() as conn:
        record_hop(
            conn,
            ride_id,
            "matching",
            "GRPC",
            "NOSQL",
            {
                "rpc": "GetCandidates",
                "candidate_count": len(merged),
                "neighbor_count": len(neighbor_zones),
                "partition_count": len(by_partition),
            },
        )

    # The ride stays open until a driver accepts, even if nobody is online yet.
    with connection() as conn:
        record_hop(
            conn,
            ride_id,
            "matching",
            "EVENT",
            "SQL",
            {"action": "offer", "candidate_count": len(merged), "status": "REQUESTED"},
        )
        conn.execute(
            """
            UPDATE ride_requests
            SET status = %s, updated_at = now()
            WHERE id = %s AND status = 'REQUESTED'
            """,
            ("REQUESTED", ride_id),
        )


def poll_loop(stop: threading.Event) -> None:
    store = get_store()

    while not stop.is_set():
        try:
            jobs = store.receive_jobs(5)
            if not jobs:
                stop.wait(POLL_IDLE_SEC)
                continue
            for ack_id, job in jobs:
                if stop.is_set():
                    break
                handle_job(job)
                store.delete_job(ack_id)
        except Exception:
            log.exception("match poll failed", extra={"event": "match_poll_error", "ride_id": ""})
            stop.wait(POLL_IDLE_SEC)


@asynccontextmanager
async def lifespan(app: FastAPI):
    stop = threading.Event()
    thread = threading.Thread(target=poll_loop, args=(stop,), daemon=True)
    thread.start()
    app.state.match_stop = stop
    app.state.match_thread = thread
    try:
        yield
    finally:
        stop.set()
        thread.join(timeout=10)


app = FastAPI(lifespan=lifespan)
install(app, "matching", ready_check=ping)
