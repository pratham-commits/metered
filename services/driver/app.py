# Person 1. Driver Service. HTTP 8002, gRPC 9002.
#
# POST /drivers creates the SQL profile. 409 on a duplicate phone.
# GET /drivers/{id} returns the profile.
# POST /drivers/{id}/presence {status ONLINE|OFFLINE, lat, lng, optional zone}.
# zone_for(lat, lng) must match the optional zone or the call returns 400.
# partition_id = HashRing(HASH_NODES).owner(zone).
# ONLINE is stored as DynamoDB status AVAILABLE. OFFLINE is stored as OFFLINE.
# Publish DRIVER_STATUS to ride-events. payload.status is ONLINE or OFFLINE.
# Return driver_id, zone, partition_id, status, neighbors, and whether Kafka accepted the event.
# gRPC DriverLookup.GetCandidates queries AVAILABLE drivers in that partition and the neighbor zones.
# Start the gRPC server on 0.0.0.0:9002 from the FastAPI startup hook.
