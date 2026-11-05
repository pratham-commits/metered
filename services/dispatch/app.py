# Person 2. Dispatch Service. HTTP 8005 for health only. gRPC 9005 for Assign.
#
# Assign calls store.assign(partition_id, driver_id, ride_id) in a Firestore transaction.
# Record a GRPC/NOSQL hop on the ride id with assigned and reason.
# reason is "assigned" or "driver_not_available".
# Start the gRPC server on 0.0.0.0:9005 from the FastAPI startup hook.
# This service is what stops two rides taking the same driver.



import os
from concurrent import futures
from contextlib import asynccontextmanager
import grpc
from fastapi import FastAPI

from ride.v1 import dispatch_pb2, dispatch_pb2_grpc
from rideshare.db import connection, ping
from rideshare.hops import record_hop
from rideshare.logging_setup import configure
from rideshare.store import get_store
from rideshare.web import install

GRPC_ADDRESS = "0.0.0.0:9005"
GRPC_WORKERS = 8

@asynccontextmanager
async def lifespan(app:FastAPI):
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=GRPC_WORKERS))
    dispatch_pb2_grpc.add_DispatchServicer_to_server(DispatchServicer(), server)
    server.add_insecure_port(GRPC_ADDRESS)
    server.start()
    app.state.grpc = server
    try:
        yield
    finally:
        server.stop(grace=5).wait()

app = FastAPI(lifespan=lifespan)
install(app,"dispatch",ready_check=ping)
log = configure()

class DispatchServicer(dispatch_pb2_grpc.DispatchServicer):
    def Assign(self, request, context):
        ride_id = request.ride_id
        driver_id = request.driver_id
        partition_id = request.partition_id
        assigned = False
        reason = "driver_not_available"

        try:
            assigned = bool(
                get_store().assign(partition_id, driver_id, ride_id)
            )
            reason = "assigned" if assigned else reason
        except Exception:
            log.exception(
                f"Assigning ride {ride_id} to driver {driver_id} on partition {partition_id} failed",
                extra= {
                    "event": "dispatch_assign_failed",
                    "ride_id": ride_id,
                },
                )
            assigned = False
            reason = "driver_not_available"
        
        with connection() as conn:
            record_hop(
                conn,
                ride_id,
                "dispatch",
                "GRPC",
                "NOSQL",
                {
                    "rpc": "Assign",
                    "driver_id": driver_id,
                    "partition_id": partition_id,
                    "assigned": assigned,
                    "reason": reason,
                },
            )
        log.info(
            "assign",
            extra= {
                "event": "dispatch_assign_success",
                "ride_id":ride_id,
            },

        )
        return dispatch_pb2.AssignResponse(assigned=assigned, reason=reason)