# Person 1. Build context is the repository root.
#
# python:3.12-slim. Create uid 65532 appuser.
# Copy proto, services/common, and services/rider.
# pip install the common requirements.
# Generate gRPC stubs from proto/ride/v1 into /app and fix bare imports to ride.v1.
# Copy the rideshare package onto PYTHONPATH=/app.
# USER 65532. EXPOSE 8001.
# CMD uvicorn service.app:app --host 0.0.0.0 --port 8001.
