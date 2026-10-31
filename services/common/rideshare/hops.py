import json


def record_hop(conn, ride_id: str, service: str, mechanism: str, store: str, detail: dict) -> None:
    if not ride_id:
        return
    conn.execute(
        """
        INSERT INTO ride_hops (ride_id, service, mechanism, store, detail)
        VALUES (%s, %s, %s, %s, %s::jsonb)
        """,
        (ride_id, service, mechanism, store, json.dumps(detail)),
    )
