import http from "k6/http";
import { check, sleep } from "k6";
import { uuidv4 } from "https://jslib.k6.io/k6-utils/1.4.0/index.js";

const BASE = __ENV.BASE_URL || "http://127.0.0.1:8003";

export const options = {
  stages: [
    { duration: "30s", target: 40 },
    { duration: "4m", target: 120 },
    { duration: "30s", target: 0 },
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
  const jitter = Math.random() * 0.08;
  const body = {
    rider_id: data.riderId,
    pickup_lat: 23.03 + jitter,
    pickup_lng: 72.54 + jitter,
    drop_lat: 23.05 + jitter,
    drop_lng: 72.58 + jitter,
    idempotency_key: uuidv4(),
  };
  const res = http.post(`${BASE}/api/ride-requests`, JSON.stringify(body), {
    headers: { "Content-Type": "application/json" },
  });
  check(res, { "ride accepted": (r) => r.status === 201 });
  sleep(0.05);
}
