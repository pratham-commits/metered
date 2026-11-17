# Person 3. Fare Service. Cloud Run functions (2nd gen). Two entry points, one source tree.
#
# estimate(request): HTTP entry point. request is a Flask request.
#   GET /health returns {ok, service: fare}.
#   POST body {pickup_zone, drop_zone, pickup_lat, pickup_lng, drop_lat, drop_lng}.
#   Read the latest imbalance from Firestore (rideshare_demand_windows) for the
#   pickup zone, default 1.0. Use quote_coordinates when coordinates are present,
#   otherwise quote_between. Return the quote as JSON.
# finalize(cloud_event): CloudEvent entry point for
#   google.cloud.storage.object.v1.finalized. Ignore objects that are not
#   completions/*.json. Read the completion JSON from GCS and compute the fare with
#   quote_coordinates on the stored pickup/drop coordinates.
#   Insert fare_quotes kind FINAL. Update ride_requests.final_fare_cents and surge.
#   Insert a ride_hops row: service fare, mechanism EVENT, store SQL.
#   Print a JSON log line with event final_fare, ride_id, and amount_cents.
# The database URL comes from Secret Manager secret rideshare-database, field "url".
# Do not copy the fare formula into this file. Import rideshare.fare.
#
# infra/functions only deploys when this file defines both `def estimate(` and
# `def finalize(`. Keep the stubs as comments until those functions exist.


import json
import os
import uuid

from google.cloud import secretmanager, storage
from rideshare.db import connection
from rideshare.fare import quote_between, quote_coordinates
from rideshare.hops import record_hop
from rideshare.store import get_store


def _response(payload: dict, status: int = 200):
    return (
        json.dumps(payload),
        status,
        {"Content-Type": "application/json"},
    )


def _database_url() -> str:
    existing = os.environ.get("DATABASE_URL")
    if existing:
        return existing

    project = os.environ.get("GCP_PROJECT") or os.environ.get(
        "GOOGLE_CLOUD_PROJECT"
    )
    secret_id = os.environ.get("DATABASE_SECRET", "rideshare-database")

    if not project:
        raise RuntimeError("GCP_PROJECT or GOOGLE_CLOUD_PROJECT must be set")

    client = secretmanager.SecretManagerServiceClient()
    name = (
        f"projects/{project}/secrets/{secret_id}/versions/latest"
    )
    result = client.access_secret_version(request={"name": name})
    secret = json.loads(result.payload.data.decode("utf-8"))

    url = secret.get("url")
    if not url:
        raise RuntimeError("Database secret does not contain a url field")

    os.environ["DATABASE_URL"] = url
    return url


def _imbalance(zone: str) -> float:
    if not zone:
        return 1.0

    demand = get_store().latest_demand(zone)
    if not demand:
        return 1.0

    return float(demand.get("imbalance", 1.0))


def estimate(request):
    if request.method == "GET":
        return _response({"ok": True, "service": "fare"})

    if request.method != "POST":
        return _response({"error": "Method not allowed"}, 405)

    body = request.get_json(silent=True)
    if not isinstance(body, dict):
        return _response({"error": "Expected a JSON object"}, 400)

    zone_a = body.get("pickup_zone")
    zone_b = body.get("drop_zone")

    coordinate_fields = (
        "pickup_lat",
        "pickup_lng",
        "drop_lat",
        "drop_lng",
    )
    supplied_coordinates = [field in body for field in coordinate_fields]

    try:
        imbalance = _imbalance(zone_a)

        if all(supplied_coordinates):
            quote = quote_coordinates(
                float(body["pickup_lat"]),
                float(body["pickup_lng"]),
                float(body["drop_lat"]),
                float(body["drop_lng"]),
                imbalance,
            )
        elif any(supplied_coordinates):
            return _response(
                {"error": "Provide all four pickup/drop coordinates"}, 400
            )
        elif zone_a and zone_b:
            quote = quote_between(zone_a, zone_b, imbalance)
        else:
            return _response(
                {
                    "error": (
                        "Provide all four coordinates or pickup_zone and drop_zone"
                    )
                },
                400,
            )

        quote["imbalance"] = imbalance
        return _response(quote)

    except (TypeError, ValueError) as exc:
        return _response({"error": str(exc)}, 400)


def finalize(cloud_event):
    data = cloud_event.data or {}
    object_name = data.get("name", "")
    bucket_name = data.get("bucket", "")

    # Ignore GPS uploads and all other objects.
    if not object_name.startswith("completions/") or not object_name.endswith(
        ".json"
    ):
        print(json.dumps({"event": "ignored", "object": object_name}))
        return

    if not bucket_name:
        raise ValueError("Cloud Storage event is missing its bucket")

    project = os.environ.get("GCP_PROJECT") or os.environ.get(
        "GOOGLE_CLOUD_PROJECT"
    )
    client = storage.Client(project=project)
    blob = client.bucket(bucket_name).blob(object_name)
    completion = json.loads(blob.download_as_bytes().decode("utf-8"))

    ride_id = completion.get("ride_id")
    if not ride_id:
        raise ValueError("Completion object is missing ride_id")

    required = (
        "pickup_lat",
        "pickup_lng",
        "drop_lat",
        "drop_lng",
    )
    if any(field not in completion for field in required):
        raise ValueError("Completion object is missing pickup/drop coordinates")

    imbalance = _imbalance(completion.get("pickup_zone", ""))

    quote = quote_coordinates(
        float(completion["pickup_lat"]),
        float(completion["pickup_lng"]),
        float(completion["drop_lat"]),
        float(completion["drop_lng"]),
        imbalance,
    )

    amount_cents = quote["amount_cents"]
    surge = quote["surge"]

    breakdown = {
        **quote,
        "imbalance": imbalance,
        "actual_duration_sec": completion.get("duration_sec"),
        "completion_object": object_name,
    }

    # Fetch credentials before opening the shared SQL connection pool.
    _database_url()

    with connection() as conn:
        # Serialize finalization attempts for the same ride.
        ride = conn.execute(
            """
            SELECT final_fare_cents
            FROM ride_requests
            WHERE id = %s
            FOR UPDATE
            """,
            (ride_id,),
        ).fetchone()

        if ride is None:
            raise ValueError(f"Ride {ride_id} does not exist")

        # Eventarc may redeliver the same event. Do not insert twice.
        if ride[0] is not None:
            print(
                json.dumps(
                    {
                        "event": "final_fare",
                        "ride_id": str(ride_id),
                        "amount_cents": ride[0],
                        "duplicate": True,
                    }
                )
            )
            return

        conn.execute(
            """
            INSERT INTO fare_quotes (
                id, ride_id, kind, amount_cents, surge,
                distance_km, breakdown
            )
            VALUES (%s, %s, 'FINAL', %s, %s, %s, %s::jsonb)
            """,
            (
                str(uuid.uuid4()),
                ride_id,
                amount_cents,
                surge,
                quote["distance_km"],
                json.dumps(breakdown),
            ),
        )

        conn.execute(
            """
            UPDATE ride_requests
            SET final_fare_cents = %s,
                surge = %s,
                updated_at = now()
            WHERE id = %s
            """,
            (amount_cents, surge, ride_id),
        )

        record_hop(
            conn,
            str(ride_id),
            "fare",
            "EVENT",
            "SQL",
            {
                "action": "finalize",
                "amount_cents": amount_cents,
                "surge": surge,
                "imbalance": imbalance,
                "completion_object": object_name,
            },
        )

    print(
        json.dumps(
            {
                "event": "final_fare",
                "ride_id": str(ride_id),
                "amount_cents": amount_cents,
            }
        )
    )
