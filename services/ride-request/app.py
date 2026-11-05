import json
import os
import uuid
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
import grpc
from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from psycopg.errors import UniqueViolation
from uuid import UUID
from ride.v1 import dispatch_pb2, dispatch_pb2_grpc
from rideshare.db import connection, ping
from rideshare.fare import quote_coordinates
from rideshare.hashring import HashRing, nodes_from_env
from rideshare.hops import record_hop
from rideshare.logging_setup import configure
from rideshare.store import get_store
from rideshare.web import install
from rideshare.zones import cells_around, resolution, zone_for

RIDER_URL = os.environ.get("RIDER_URL", "http://rider.rideshare.svc.cluster.local:8001")
DRIVER_HTTP = os.environ.get(
    "DRIVER_HTTP", "http://driver.rideshare.svc.cluster.local:8002"
)
TRIP_URL = os.environ.get(
    "TRIP_URL", "http://trip-tracking.rideshare.svc.cluster.local:8006"
)
DISPATCH_GRPC = os.environ.get(
    "DISPATCH_GRPC", "dispatch.rideshare.svc.cluster.local:9005"
)
FARE_ESTIMATE_URL = os.environ.get("FARE_ESTIMATE_URL", "").strip()
DEMO_TOKEN = os.environ.get("DEMO_TOKEN", "")
DEFAULT_PARTITIONS = "p0,p1,p2,p3"
STATIC_DIR = Path(__file__).resolve().parent / "static"

app = FastAPI()
install(app,"ride-request",ready_check=ping)
log = configure()

def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
def live_ring() -> HashRing:
    return HashRing(nodes_from_env(os.environ.get("HASH_NODES", DEFAULT_PARTITIONS)))


def http_json(method: str, url: str, body: dict | None = None) -> dict:
    data = None if body is None else json.dumps(body).encode("utf-8")
    request = urllib.request.Request(url, data=data, method=method)
    if body is not None:
        request.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            raw = response.read().decode("utf-8")
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise HTTPException(status_code=exc.code, detail=detail or exc.reason) from exc
    except urllib.error.URLError as exc:
        raise HTTPException(status_code=502, detail=str(exc.reason)) from exc


def ride_row(conn, ride_id: str) -> dict | None:
    row = conn.execute(
        """
        SELECT id::text, rider_id::text, pickup_zone, drop_zone,
               pickup_lat, pickup_lng, drop_lat, drop_lng, status,
               estimated_fare_cents, final_fare_cents, surge,
               assigned_driver_id::text, assigned_partition_id,
               idempotency_key, created_at, updated_at
        FROM ride_requests WHERE id = %s
        """,
        (ride_id,),
    ).fetchone()
    if row is None:
        return None
    return {
        "id": row[0],
        "rider_id": row[1],
        "pickup_zone": row[2],
        "drop_zone": row[3],
        "pickup_lat": row[4],
        "pickup_lng": row[5],
        "drop_lat": row[6],
        "drop_lng": row[7],
        "status": row[8],
        "estimated_fare_cents": row[9],
        "final_fare_cents": row[10],
        "surge": row[11],
        "assigned_driver_id": row[12],
        "assigned_partition_id": row[13],
        "idempotency_key": row[14],
        "created_at": row[15].astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "updated_at": row[16].astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }




class RideIn(BaseModel):
    rider_id: UUID
    pickup_lat: float = Field(ge=-90, le=90)
    pickup_lng: float = Field(ge=-180, le=180)
    drop_lat: float = Field(ge=-90, le=90)
    drop_lng: float = Field(ge=-180, le=180)
    idempotency_key: str | None = None


class RingPreviewIn(BaseModel):
    nodes: list[str]
    zones: list[str]


class ConflictIn(BaseModel):
    ride_id: UUID
    driver_id: str
    partition_id: str




@app.get("/")
def index():
    path = STATIC_DIR / "index.html"
    if not path.is_file():
        raise HTTPException(status_code=404, detail="ui missing")
    return FileResponse(path)


@app.get("/api/config")
def api_config():
    return {
        "h3_resolution": resolution(),
        "hash_nodes": nodes_from_env(os.environ.get("HASH_NODES", DEFAULT_PARTITIONS)),
        "kafka_topic_events": os.environ.get("KAFKA_TOPIC_EVENTS", "ride-events"),
        "kafka_topic_results": os.environ.get("KAFKA_TOPIC_RESULTS", "demand-results"),
        "match_topic": os.environ.get("MATCH_TOPIC", "rideshare-match-jobs"),
        "graph": {
            "rider": RIDER_URL,
            "driver": DRIVER_HTTP,
            "trip": TRIP_URL,
            "dispatch_grpc": DISPATCH_GRPC,
        },
    }


@app.get("/api/zones")
def api_zones(lat: float, lng: float, k: int = 3):
    zones = cells_around(lat, lng, k)
    return {"lat": lat, "lng": lng, "k": k, "zones": zones}


@app.post("/api/riders")
async def api_riders(request: Request):
    body = await request.json()
    return http_json("POST", f"{RIDER_URL}/riders", body)


@app.post("/api/drivers")
async def api_drivers(request: Request):
    body = await request.json()
    return http_json("POST", f"{DRIVER_HTTP}/drivers", body)


@app.post("/api/drivers/{driver_id}/presence")
async def api_presence(driver_id: UUID, request: Request):
    body = await request.json()
    return http_json("POST", f"{DRIVER_HTTP}/drivers/{driver_id}/presence", body)


@app.post("/api/trips/{ride_id}/progress")
async def api_trip_progress(ride_id: UUID, request: Request):
    body = await request.json()
    return http_json("POST", f"{TRIP_URL}/trips/{ride_id}/progress", body)


@app.get("/api/demand")
def api_demand():
    return http_json("GET", f"{TRIP_URL}/demand")






@app.post("/api/ride-requests", status_code=201)
def create_ride(body: RideIn):
    pickup_zone = zone_for(body.pickup_lat, body.pickup_lng)
    drop_zone = zone_for(body.drop_lat, body.drop_lng)
    ride_id = str(uuid.uuid4())
    rider_id = str(body.rider_id)
    store = get_store()

    with connection() as conn:
        if body.idempotency_key:
            existing = conn.execute(
                "SELECT id::text FROM ride_requests WHERE idempotency_key = %s",
                (body.idempotency_key,),
            ).fetchone()
            if existing:
                return ride_row(conn, existing[0])

        try:
            conn.execute(
                """
                INSERT INTO ride_requests (
                  id, rider_id, pickup_zone, drop_zone,
                  pickup_lat, pickup_lng, drop_lat, drop_lng,
                  status, idempotency_key
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'REQUESTED', %s)
                """,
                (
                    ride_id,
                    rider_id,
                    pickup_zone,
                    drop_zone,
                    body.pickup_lat,
                    body.pickup_lng,
                    body.drop_lat,
                    body.drop_lng,
                    body.idempotency_key,
                ),
            )
        except UniqueViolation:
            row = conn.execute(
                "SELECT id::text FROM ride_requests WHERE idempotency_key = %s",
                (body.idempotency_key,),
            ).fetchone()
            if row:
                return ride_row(conn, row[0])
            raise

        record_hop(
            conn,
            ride_id,
            "ride-request",
            "REST",
            "SQL",
            {"action": "insert", "status": "REQUESTED"},
        )

    # Fare estimate
    fare_payload = {
        "pickup_zone": pickup_zone,
        "drop_zone": drop_zone,
        "pickup_lat": body.pickup_lat,
        "pickup_lng": body.pickup_lng,
        "drop_lat": body.drop_lat,
        "drop_lng": body.drop_lng,
    }
    if FARE_ESTIMATE_URL:
        quote = http_json("POST", FARE_ESTIMATE_URL, fare_payload)
        source = "fare-function"
    else:
        quote = quote_coordinates(
            body.pickup_lat,
            body.pickup_lng,
            body.drop_lat,
            body.drop_lng,
            imbalance=1.0,
        )
        quote["source"] = "local-fallback"
        source = "local-fallback"

    with connection() as conn:
        conn.execute(
            """
            UPDATE ride_requests
            SET estimated_fare_cents = %s, surge = %s, updated_at = now()
            WHERE id = %s
            """,
            (quote.get("amount_cents"), quote.get("surge"), ride_id),
        )
        record_hop(
            conn,
            ride_id,
            "ride-request",
            "REST",
            "NONE",
            {"action": "fare_estimate", "source": source, "quote": quote},
        )

    message_id = store.send_job(
        {
            "ride_id": ride_id,
            "rider_id": rider_id,
            "pickup_zone": pickup_zone,
            "drop_zone": drop_zone,
        }
    )
    with connection() as conn:
        record_hop(
            conn,
            ride_id,
            "ride-request",
            "QUEUE",
            "NONE",
            {"action": "match_job", "message_id": message_id},
        )

    published = store.publish(
        {
            "event_id": str(uuid.uuid4()),
            "event_type": "RIDE_REQUESTED",
            "event_time": utc_now(),
            "zone": pickup_zone,
            "ride_id": ride_id,
            "rider_id": rider_id,
            "driver_id": "",
            "payload": {"drop_zone": drop_zone},
        }
    )
    with connection() as conn:
        record_hop(
            conn,
            ride_id,
            "ride-request",
            "EVENT",
            "NONE",
            {"action": "RIDE_REQUESTED", "kafka": published},
        )
        return ride_row(conn, ride_id)


@app.get("/api/ride-requests/{ride_id}")
def get_ride(ride_id: UUID):
    with connection() as conn:
        ride = ride_row(conn, str(ride_id))
        if ride is None:
            raise HTTPException(status_code=404, detail="ride not found")
        hops = conn.execute(
            """
            SELECT id, service, mechanism, store, detail, created_at
            FROM ride_hops WHERE ride_id = %s ORDER BY id
            """,
            (str(ride_id),),
        ).fetchall()
    return {
        "ride": ride,
        "hops": [
            {
                "id": h[0],
                "service": h[1],
                "mechanism": h[2],
                "store": h[3],
                "detail": h[4],
                "created_at": h[5]
                .astimezone(timezone.utc)
                .strftime("%Y-%m-%dT%H:%M:%SZ"),
            }
            for h in hops
        ],
    }


@app.get("/api/ring")
def api_ring(lat: float, lng: float, k: int = 3):
    zones = cells_around(lat, lng, k)
    ownership = live_ring().ownership(zones)
    return {"lat": lat, "lng": lng, "k": k, "zones": zones, "ownership": ownership}


@app.post("/api/ring/preview")
def api_ring_preview(body: RingPreviewIn):
    before = live_ring().ownership(body.zones)
    after = HashRing(body.nodes).ownership(body.zones)
    moved = [z for z in body.zones if before.get(z) != after.get(z)]
    stayed = [z for z in body.zones if before.get(z) == after.get(z)]
    total = len(body.zones) or 1
    return {
        "before": before,
        "after": after,
        "moved": moved,
        "stayed": stayed,
        "moved_fraction": len(moved) / total,
    }


@app.post("/api/demo/conflict")
def api_conflict(
    body: ConflictIn,
    x_demo_token: str | None = Header(default=None, alias="X-Demo-Token"),
):
    if not DEMO_TOKEN or x_demo_token != DEMO_TOKEN:
        raise HTTPException(status_code=401, detail="invalid demo token")
    probe_ride_id = str(uuid.uuid4())
    channel = grpc.insecure_channel(DISPATCH_GRPC)
    try:
        stub = dispatch_pb2_grpc.DispatchStub(channel)
        response = stub.Assign(
            dispatch_pb2.AssignRequest(
                ride_id=probe_ride_id,
                driver_id=body.driver_id,
                partition_id=body.partition_id,
            ),
            timeout=10,
        )
    finally:
        channel.close()

    with connection() as conn:
        record_hop(
            conn,
            str(body.ride_id),
            "ride-request",
            "GRPC",
            "NOSQL",
            {
                "rpc": "Assign",
                "demo": "conflict",
                "probe_ride_id": probe_ride_id,
                "driver_id": body.driver_id,
                "partition_id": body.partition_id,
                "assigned": bool(response.assigned),
                "reason": response.reason,
            },
        )
    return {
        "assigned": bool(response.assigned),
        "reason": response.reason,
        "probe_ride_id": probe_ride_id,
    }


@app.get("/api/checklist")
def api_checklist():
    targets = {
        "rider": f"{RIDER_URL}/healthz",
        "driver": f"{DRIVER_HTTP}/healthz",
        "matching": "http://matching.rideshare.svc.cluster.local:8004/healthz",
        "dispatch": "http://dispatch.rideshare.svc.cluster.local:8005/healthz",
        "trip": f"{TRIP_URL}/healthz",
        "sink": "http://demand-sink.rideshare.svc.cluster.local:8010/healthz",
    }
    health = {}
    for name, url in targets.items():
        try:
            http_json("GET", url)
            health[name] = "ok"
        except HTTPException:
            health[name] = "down"

    rows = [
        {"id": "health", "title": "Service health", "status": "proven" if all(v == "ok" for v in health.values()) else "todo", "evidence": health},
        {"id": "terraform", "title": "Terraform platform", "status": "show", "evidence": "terraform -chdir=infra/platform state list"},
        {"id": "argocd", "title": "Argo CD GitOps", "status": "show", "evidence": "kubectl -n argocd get app"},
        {"id": "grafana", "title": "Grafana dashboards", "status": "show", "evidence": "kubectl -n monitoring port-forward svc/kube-prometheus-stack-grafana 3000:80"},
        {"id": "logging", "title": "Cloud Logging", "status": "show", "evidence": 'resource.type="k8s_container"'},
        {"id": "hpa", "title": "HPA replicas > 2 under k6", "status": "todo", "evidence": "open checklist while k6 runs"},
        {"id": "ring", "title": "Ring preview stayed cells", "status": "todo", "evidence": "use /api/ring/preview"},
        {"id": "demand", "title": "Demand window < 15m", "status": "todo", "evidence": "Person 3 Flink + sink"},
    ]
    return {"rows": rows, "health": health}