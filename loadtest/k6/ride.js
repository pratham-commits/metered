import http from "k6/http";
import { check, sleep } from "k6";
import { uuidv4 } from "https://jslib.k6.io/k6-utils/1.4.0/index.js";

const BASE = __ENV.BASE_URL || "http://127.0.0.1:8003";

export const options = {
  stages: [
    { duration: "1m", target: 20 },
    { duration: "3m", target: 40 },
    { duration: "1m", target: 0 },
  ],
};

export function setup() {
  const rider = http.post(
    `${BASE}/api/riders`,
    JSON.stringify({ name: "Load Rider", phone: `+9198${Date.now().toString().slice(-8)}` }),
    { headers: { "Content-Type": "application/json" } }
  );
  check(rider, { "rider created": (r) => r.status === 200 || r.status === 201 });
  return { riderId: rider.json("id") };
}

export default function (data) {
  const jitter = Math.random() * 0.02;
  const body = {
    rider_id: data.riderId,
    pickup_lat: 12.9716 + jitter,
    pickup_lng: 77.5946 + jitter,
    drop_lat: 12.9352 + jitter,
    drop_lng: 77.6245 + jitter,
    idempotency_key: uuidv4(),
  };
  const res = http.post(`${BASE}/api/ride-requests`, JSON.stringify(body), {
    headers: { "Content-Type": "application/json" },
  });
  check(res, { "ride accepted": (r) => r.status === 201 });
  sleep(0.2);
}