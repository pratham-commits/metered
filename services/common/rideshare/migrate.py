from rideshare.db import connection

SQL = """
CREATE TABLE IF NOT EXISTS riders (
  id UUID PRIMARY KEY,
  name TEXT NOT NULL,
  phone TEXT NOT NULL UNIQUE,
  email TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS drivers (
  id UUID PRIMARY KEY,
  name TEXT NOT NULL,
  phone TEXT NOT NULL UNIQUE,
  vehicle_number TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS ride_requests (
  id UUID PRIMARY KEY,
  rider_id UUID NOT NULL REFERENCES riders(id),
  pickup_zone TEXT NOT NULL,
  drop_zone TEXT NOT NULL,
  pickup_lat DOUBLE PRECISION NOT NULL,
  pickup_lng DOUBLE PRECISION NOT NULL,
  drop_lat DOUBLE PRECISION NOT NULL,
  drop_lng DOUBLE PRECISION NOT NULL,
  status TEXT NOT NULL,
  estimated_fare_cents INTEGER,
  final_fare_cents INTEGER,
  surge DOUBLE PRECISION,
  assigned_driver_id UUID,
  assigned_partition_id TEXT,
  idempotency_key TEXT UNIQUE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS trips (
  ride_id UUID PRIMARY KEY REFERENCES ride_requests(id),
  driver_id UUID,
  status TEXT NOT NULL,
  distance_km NUMERIC,
  duration_sec INTEGER,
  started_at TIMESTAMPTZ,
  completed_at TIMESTAMPTZ,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS fare_quotes (
  id UUID PRIMARY KEY,
  ride_id UUID,
  kind TEXT NOT NULL,
  amount_cents INTEGER NOT NULL,
  surge DOUBLE PRECISION NOT NULL,
  distance_km NUMERIC,
  breakdown JSONB NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS ride_hops (
  id BIGSERIAL PRIMARY KEY,
  ride_id UUID NOT NULL,
  service TEXT NOT NULL,
  mechanism TEXT NOT NULL,
  store TEXT NOT NULL,
  detail JSONB NOT NULL DEFAULT '{}',
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ride_hops_ride_id_idx ON ride_hops (ride_id, id);
"""


def main() -> None:
    with connection() as conn:
        conn.execute(SQL)
    print("schema ready")


if __name__ == "__main__":
    main()
