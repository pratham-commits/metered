import os
import uuid
from concurrent import futures
from contextlib import asynccontextmanager
from datetime import datetime, timezone

import grpc
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from uuid import UUID
from psycopg.errors import UniqueViolation

from ride.v1 import driver_pb2, driver_pb2_grpc
from rideshare.aws import get_store
from rideshare.db import connection, ping
from rideshare.hashring import HashRing, nodes_from_env
from rideshare.logging_setup import configure
from rideshare.web import install
from rideshare.zones import neighbors, zone_for

GRPC_ADDRESS = "0.0.0.0:9002"
GRPC_WORKERS = 8
MAX_CANDIDATES = 100
DEFAULT_CANDIDATES = 5
DEFAULT_PARTITIONS = "p0,p1,p2,p3"


@asynccontextmanager
async def lifespan(app: FastAPI):
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=GRPC_WORKERS))
    driver_pb2_grpc.add_DriverLookupServicer_to_server(Lookup(), server)
    server.add_insecure_port(GRPC_ADDRESS)
    server.start()
    app.state.grpc = server
    try:
        yield
    finally:
        server.stop(grace=5).wait()


app = FastAPI(lifespan=lifespan)
install(app, "driver", ready_check=ping)
log = configure()


def ring() -> HashRing:
    return HashRing(configured_partitions())


def configured_partitions() -> list[str]:
    return nodes_from_env(os.environ.get("HASH_NODES", DEFAULT_PARTITIONS))


class DriverIn(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    phone: str = Field(min_length=8, max_length=20)
    vehicle_number: str | None = None


class PresenceIn(BaseModel):
    status: str
    lat: float = Field(ge=-90, le=90, allow_inf_nan=False)
    lng: float = Field(ge=-180, le=180, allow_inf_nan=False)
    zone: str | None = None


@app.post("/drivers", status_code=201)
def create_driver(body: DriverIn):
    driver_id = str(uuid.uuid4())
    try:
        with connection() as conn:
            row = conn.execute("SELECT id::text FROM drivers WHERE phone = %s", (body.phone,)).fetchone()
            if row:
                raise HTTPException(status_code=409, detail="phone already registered")
            conn.execute(
                "INSERT INTO drivers (id, name, phone, vehicle_number) VALUES (%s, %s, %s, %s)",
                (driver_id, body.name, body.phone, body.vehicle_number),
            )
    except UniqueViolation:
        raise HTTPException(status_code=409, detail="phone already registered") from None
    return {"id": driver_id, "name": body.name, "phone": body.phone}


@app.get("/drivers/{driver_id}")
def get_driver(driver_id: UUID):
    with connection() as conn:
        row = conn.execute(
            "SELECT id::text, name, phone, vehicle_number FROM drivers WHERE id = %s",
            (driver_id,),
        ).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="driver not found")
    return {"id": row[0], "name": row[1], "phone": row[2], "vehicle_number": row[3]}


@app.post("/drivers/{driver_id}/presence")
def presence(driver_id: UUID, body: PresenceIn):
    driver_id = str(driver_id)
    if body.status not in {"ONLINE", "OFFLINE"}:
        raise HTTPException(status_code=400, detail="status must be ONLINE or OFFLINE")
    zone = zone_for(body.lat, body.lng)
    if body.zone and body.zone != zone:
        raise HTTPException(status_code=400, detail=f"coordinates are in {zone}, not {body.zone}")
    partition_id = ring().owner(zone)
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    status = "AVAILABLE" if body.status == "ONLINE" else "OFFLINE"
    store = get_store()
    # Serialize presence moves per profile; DynamoDB conditions arbitrate dispatch races.
    with connection() as conn:
        exists = conn.execute("SELECT id FROM drivers WHERE id = %s FOR UPDATE", (driver_id,)).fetchone()
        if not exists:
            raise HTTPException(status_code=404, detail="driver not found")
        try:
            store.set_presence(
                {
                    "partition_id": partition_id,
                    "driver_id": driver_id,
                    "status": status,
                    "zone": zone,
                    "lat": body.lat,
                    "lng": body.lng,
                    "updated_at": now,
                    "assigned_ride_id": "",
                }, configured_partitions()
            )
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
    published = store.publish(
        {
            "event_id": str(uuid.uuid4()),
            "event_type": "DRIVER_STATUS",
            "event_time": now,
            "zone": zone,
            "ride_id": "",
            "rider_id": "",
            "driver_id": driver_id,
            "payload": {"status": body.status},
        }
    )
    log.info("presence", extra={"event": "driver_presence", "ride_id": ""})
    return {
        "driver_id": driver_id,
        "zone": zone,
        "partition_id": partition_id,
        "status": status,
        "neighbors": neighbors(zone),
        "kafka": published,
    }


class Lookup(driver_pb2_grpc.DriverLookupServicer):
    def GetCandidates(self, request, context):
        zones = list(request.neighbor_zones) or [request.pickup_zone]
        rows = get_store().query_available(request.partition_id, zones)
        limit = max(1, min(request.limit or DEFAULT_CANDIDATES, MAX_CANDIDATES))
        candidates = [
            driver_pb2.Candidate(
                driver_id=row["driver_id"],
                zone=row["zone"],
                partition_id=row["partition_id"],
                lat=row["lat"],
                lng=row["lng"],
            )
            for row in rows[:limit]
        ]
        return driver_pb2.CandidateResponse(candidates=candidates)

