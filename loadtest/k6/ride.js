// Person 2. Letter c. Sustained traffic against the public GKE Ingress (HTTPS).
//
// stages: 1 minute to 20 VUs, 3 minutes at 40, 1 minute back to 0.
// setup():
//   - POST /api/riders once and keep the rider id
//   - optionally create a driver and set presence with live-style coordinates
// default():
//   - POST /api/ride-requests with a unique idempotency key
//   - use real lat/lng near the demo city (not fixed z11/z22 cells)
//   - check for HTTP 201, then sleep 0.2s
// The load must keep Ride Request and Matching CPU high enough for both HPAs
// to climb above 2 replicas.
//
// Run:
//   k6 run -e BASE_URL=https://YOUR_HOST loadtest/k6/ride.js
// Keep the checklist replica row open while this runs.
