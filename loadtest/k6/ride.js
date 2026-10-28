// Person 2. Letter c. Sustained traffic against the public ALB.
//
// stages: 1 minute to 20 VUs, 3 minutes at 40, 1 minute back to 0.
// setup() POSTs /api/riders once and returns the rider id.
// default() POSTs /api/ride-requests with pickup 17.40,78.40 and drop 17.45,78.45
// and a unique idempotency key per iteration. Check for HTTP 201. sleep 0.2s.
// Run: k6 run -e BASE_URL=http://<alb-host> loadtest/k6/ride.js
// Watch the checklist replica row while this runs.
