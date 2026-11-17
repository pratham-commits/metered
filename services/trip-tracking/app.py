import json
import uuid
from datetime import datetime, timezone
from typing import Literal
from uuid import UUID

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from rideshare.db import connection, ping
from rideshare.hops import record_hop
from rideshare.logging_setup import configure
from rideshare.store import get_store
from rideshare.web import install
from rideshare.zones import zone_for


app = FastAPI()
install(app, "trip-tracking", ready_check=ping)
log = configure()


class ProgressIn(BaseModel):
    status: Literal["ARRIVING", "IN_PROGRESS", "COMPLETED"]
    lat: float = Field(ge=-90, le=90, allow_inf_nan=False)
    lng: float = Field(ge=-180, le=180, allow_inf_nan=False)
    distance_km: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    duration_sec: int | None = Field(default=None, ge=0)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def iso_utc(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _demand_page() -> str:
    return """<!doctype html>
<html lang=\"en\"><head><meta charset=\"utf-8\"><meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">
<title>Ride demand</title><style>
body{font:15px system-ui,sans-serif;margin:2rem;background:#101522;color:#eef2ff}h1{margin-bottom:.25rem}
small{color:#aab4cc}table{border-collapse:collapse;width:100%;margin-top:1.5rem;background:#1b2435}
th,td{padding:.7rem;text-align:left;border-bottom:1px solid #35415a}th{color:#b9c7e8}code{color:#a8e6cf}
#error{color:#ff9d9d}button{padding:.5rem .8rem;margin-top:1rem}
</style></head><body><h1>Demand windows</h1><small>Kafka topic: <code id=\"topic\">demand-results</code></small>
<p id=\"status\">Loading latest windows…</p><p id=\"error\"></p><button onclick=\"load()\">Refresh</button>
<table><thead><tr><th>Zone</th><th>Riders</th><th>Requests</th><th>Assigned</th><th>Online drivers</th><th>Queue</th><th>Imbalance</th><th>Window start</th><th>Window end</th></tr></thead>
<tbody id=\"rows\"></tbody></table><script>
async function load(){const status=document.getElementById('status'),error=document.getElementById('error'),rows=document.getElementById('rows');
error.textContent='';try{const r=await fetch('/demand');if(!r.ok)throw new Error('HTTP '+r.status);const d=await r.json();document.getElementById('topic').textContent=d.topic;
rows.replaceChildren();for(const w of d.windows){const tr=document.createElement('tr');for(const k of ['zone','unique_riders','request_count','assigned_count','online_drivers','queue_length','imbalance','window_start','window_end']){const td=document.createElement('td');td.textContent=w[k]??'';tr.appendChild(td)}rows.appendChild(tr)}
status.textContent=d.windows.length+' zone window(s) loaded';}catch(e){error.textContent=e.message;status.textContent='Could not load demand windows'}}load();
</script></body></html>"""


@app.post("/trips/{ride_id}/progress")
def update_progress(ride_id: UUID, body: ProgressIn):
    if body.status == "COMPLETED" and (body.distance_km is None or body.duration_sec is None):
        raise HTTPException(status_code=422, detail="COMPLETED requires distance_km and duration_sec")

    ride_id_text = str(ride_id)
    now = utc_now()
    completed_at = iso_utc(now)
    timestamp = now.strftime("%Y%m%dT%H%M%S.%fZ")
    gps_key = f"gps/{ride_id_text}/{timestamp}.json"
    pickup_zone = None
    driver_id = None
    partition_id = None

    # Lock the ride row so simultaneous progress updates cannot race its state.
    with connection() as conn:
        ride = conn.execute(
            """
            SELECT id::text, rider_id::text, assigned_driver_id::text,
                   assigned_partition_id, pickup_zone, drop_zone,
                   pickup_lat, pickup_lng, drop_lat, drop_lng
            FROM ride_requests WHERE id = %s FOR UPDATE
            """,
            (ride_id_text,),
        ).fetchone()
        if ride is None:
            raise HTTPException(status_code=404, detail="ride not found")

        (
            _ride_id, rider_id, driver_id, partition_id, pickup_zone, drop_zone,
            pickup_lat, pickup_lng, drop_lat, drop_lng,
        ) = ride
        if not driver_id or not partition_id:
            raise HTTPException(status_code=409, detail="ride has no assigned driver")

        conn.execute(
            """
            INSERT INTO trips (ride_id, driver_id, status, distance_km, duration_sec,
                               started_at, completed_at, updated_at)
            VALUES (%s, %s, %s, %s, %s,
                    CASE WHEN %s = 'IN_PROGRESS' THEN now() ELSE NULL END,
                    CASE WHEN %s = 'COMPLETED' THEN now() ELSE NULL END,
                    now())
            ON CONFLICT (ride_id) DO UPDATE SET
                driver_id = EXCLUDED.driver_id,
                status = EXCLUDED.status,
                distance_km = COALESCE(EXCLUDED.distance_km, trips.distance_km),
                duration_sec = COALESCE(EXCLUDED.duration_sec, trips.duration_sec),
                started_at = CASE WHEN EXCLUDED.status = 'IN_PROGRESS'
                                   THEN COALESCE(trips.started_at, now()) ELSE trips.started_at END,
                completed_at = CASE WHEN EXCLUDED.status = 'COMPLETED'
                                    THEN now() ELSE trips.completed_at END,
                updated_at = now()
            """,
            (ride_id_text, driver_id, body.status, body.distance_km, body.duration_sec,
             body.status, body.status),
        )
        conn.execute(
            "UPDATE ride_requests SET status = %s, updated_at = now() WHERE id = %s",
            (body.status, ride_id_text),
        )
        record_hop(
            conn, ride_id_text, "trip-tracking", "REST", "SQL",
            {"action": "progress", "status": body.status},
        )

    store = get_store()
    gps_sample = {
        "ride_id": ride_id_text,
        "driver_id": driver_id,
        "status": body.status,
        "lat": body.lat,
        "lng": body.lng,
        "event_time": completed_at,
    }
    store.put_object(gps_key, json.dumps(gps_sample).encode("utf-8"))

    event = {
        "event_id": str(uuid.uuid4()),
        "event_type": "TRIP_UPDATED",
        "event_time": completed_at,
        "zone": pickup_zone,
        "ride_id": ride_id_text,
        "rider_id": rider_id,
        "driver_id": driver_id,
        "payload": {
            "status": body.status,
            "lat": body.lat,
            "lng": body.lng,
            "distance_km": body.distance_km,
            "duration_sec": body.duration_sec,
        },
    }
    kafka_published = store.publish(event)

    completion_key = None
    if body.status == "COMPLETED":
        completion_key = f"completions/{ride_id_text}.json"
        completion = {
            "ride_id": ride_id_text,
            "rider_id": rider_id,
            "driver_id": driver_id,
            "partition_id": partition_id,
            "pickup_zone": pickup_zone,
            "drop_zone": drop_zone,
            "pickup_lat": float(pickup_lat),
            "pickup_lng": float(pickup_lng),
            "drop_lat": float(drop_lat),
            "drop_lng": float(drop_lng),
            "distance_km": body.distance_km,
            "duration_sec": body.duration_sec,
            "completed_at": completed_at,
        }
        store.put_object(completion_key, json.dumps(completion).encode("utf-8"))
        with connection() as conn:
            record_hop(
                conn, ride_id_text, "trip-tracking", "EVENT", "OBJECT",
                {"gps_key": gps_key, "completion_key": completion_key},
            )
        store.release(partition_id, driver_id)

    log.info(
        "trip progress updated",
        extra={"event": "trip_updated", "ride_id": ride_id_text},
    )
    return {
        "ride_id": ride_id_text,
        "status": body.status,
        "gps_key": gps_key,
        "completion_key": completion_key,
        "kafka_published": kafka_published,
    }


@app.get("/demand")
def demand():
    return {"topic": "demand-results", "windows": get_store().latest_all()}


@app.get("/demand/page", response_class=HTMLResponse)
def demand_page():
    return HTMLResponse(_demand_page())
