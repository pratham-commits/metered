# Person 1. Rider Service. Port 8001.
#
# install(app, "rider", ready_check=ping).
# POST /riders {name, phone, email} -> 201 with a new UUID. 409 if the phone exists.
# GET /riders/{id} -> the profile, or 404.
# This service has no ride id yet, so it does not write ride_hops.
# Ride Request writes the REST/SQL hop when it proxies the create call.
