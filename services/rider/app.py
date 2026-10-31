import uuid
from datetime import timezone

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from uuid import UUID
from psycopg.errors import UniqueViolation

from rideshare.db import connection, ping
from rideshare.web import install

app = FastAPI()
install(app, "rider", ready_check=ping)


class RiderIn(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    phone: str = Field(min_length=8, max_length=20)
    email: str | None = None


@app.post("/riders", status_code=201)
def create_rider(body: RiderIn):
    rider_id = str(uuid.uuid4())
    try:
        with connection() as conn:
            row = conn.execute("SELECT id::text FROM riders WHERE phone = %s", (body.phone,)).fetchone()
            if row:
                raise HTTPException(status_code=409, detail="phone already registered")
            conn.execute(
                "INSERT INTO riders (id, name, phone, email) VALUES (%s, %s, %s, %s)",
                (rider_id, body.name, body.phone, body.email),
            )
    except UniqueViolation:
        raise HTTPException(status_code=409, detail="phone already registered") from None
    return {"id": rider_id, "name": body.name, "phone": body.phone, "email": body.email}


@app.get("/riders/{rider_id}")
def get_rider(rider_id: UUID):
    with connection() as conn:
        row = conn.execute(
            "SELECT id::text, name, phone, email, created_at FROM riders WHERE id = %s",
            (rider_id,),
        ).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="rider not found")
    return {
        "id": row[0],
        "name": row[1],
        "phone": row[2],
        "email": row[3],
        "created_at": row[4].astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
