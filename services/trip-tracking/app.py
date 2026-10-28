# Person 3. Trip Tracking Service. Port 8006.
#
# POST /trips/{ride_id}/progress {status, lat, lng, distance_km, duration_sec}.
# status is ARRIVING, IN_PROGRESS, or COMPLETED.
# COMPLETED requires distance_km and duration_sec.
# Upsert trips, update ride_requests.status, record a REST/SQL hop.
# Put a GPS sample at gps/{ride_id}/{timestamp}.json.
# Publish TRIP_UPDATED. payload.status is the trip status. zone is the pickup zone.
# On COMPLETED, also put completions/{ride_id}.json with ride, rider, driver, partition,
# pickup zone, drop zone, distance, duration, and completed_at.
# Then release the driver back to AVAILABLE.
# Record an EVENT/OBJECT hop with both S3 keys.
# GET /demand returns {topic: demand-results, windows: latest window per zone}.
