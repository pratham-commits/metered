# Metered — Codebase walkthrough for teammates

**Audience:** Ved, Pratham, Vidhu  
**Goal:** Know *where* the important code lives so you can open a file and speak about it confidently. You do **not** need to memorize every line.

**Repo:** `https://github.com/pratham-commits/metered` (branch `main`)

---

## 1. Top-level layout (mental map)

```text
metered/
├── apps/                    ← application source (Python FastAPI services + UI)
│   ├── ride_request/        ← public BFF + web UI (Pratham)
│   ├── rider/               ← rider profiles (Ved)
│   ├── driver/              ← driver + presence (Ved)
│   ├── matching/            ← match workers (Pratham)
│   ├── dispatch/            ← assign lock gRPC (Pratham)
│   ├── trip_tracking/       ← trips, GCS, demand page (Vidhu)
│   ├── demand_sink/         ← Kafka → Firestore (Vidhu)
│   └── fare/                ← Cloud Functions estimate + finalize (Vidhu)
├── flink/                   ← Flink DemandJob (Java) (Vidhu)
├── infra/                   ← Terraform (Ved) + k8s YAML (all)
│   ├── terraform/           ← GCP resources
│   └── k8s/                 ← Deployments, Services, HPAs, Argo, Prometheus…
├── loadtest/k6/             ← HPA proof scripts + results (Pratham)
├── scripts/                 ← helper shell scripts (deploy, flink, smoke)
├── docs/                    ← reports, architecture, teammates guides
├── task_division.txt        ← who owns a–h (submit this)
└── README.md
```

**Rule of thumb:**  
- Business logic → `apps/`  
- Cloud resources → `infra/terraform/`  
- How pods run → `infra/k8s/`  
- Streaming analytics → `flink/`

---

## 2. How a service is structured (pattern)

Most services look like:

```text
apps/<name>/
├── main.py          ← FastAPI app, HTTP routes
├── requirements.txt
├── Dockerfile
└── (sometimes) *.proto / gRPC generated code
```

Common ideas you can say out loud:

- **FastAPI** = Python web framework (REST).  
- **Dockerfile** = how the container image is built.  
- **Environment variables** (DB URL, bucket, topics) come from Kubernetes Secrets / ConfigMaps, not hard-coded secrets in git.

---

## 3. File-by-file: what each owner should open

### Ved (a, d, g + Rider/Driver)

| Open this | Why / what to say |
|---|---|
| `infra/terraform/` (esp. `main.tf`, modules for GKE, SQL, GCS, Firestore) | “This is infrastructure as code — we declare VPC, GKE, Cloud SQL, buckets, IAM.” |
| `infra/k8s/argocd/` or Argo Application manifests | “Argo CD watches GitHub `main` and syncs the cluster — GitOps.” |
| `apps/rider/main.py` | “Rider profiles go to Cloud SQL.” |
| `apps/driver/main.py` | “Drivers go online into Firestore with H3 cells.” |
| GCS / SQL / Firestore resource names in terraform | Letter **g**: object + SQL + NoSQL. |

**Viva sentence:** *“Terraform defines the cloud; Argo keeps Kubernetes matching git; Rider and Driver write SQL and Firestore.”*

---

### Pratham (c, f, h + Ride Request / Matching / Dispatch)

| Open this | Why / what to say |
|---|---|
| `apps/ride_request/main.py` | BFF: create ride, accept, board, finish, checklist APIs. |
| `apps/ride_request/static/` or templates (UI) | The browser UI you demo. |
| `apps/matching/` | Pub/Sub consumer + candidate search. |
| `apps/dispatch/` | gRPC Assign — atomic assignment. |
| Hash-ring / H3 helpers (search `h3`, `partition`, `p0`) under ride_request or matching | Letter **f**: consistent hashing of cells onto `p0..p3`. |
| `infra/k8s/` HPAs for ride-request / matching | Letter **c**: autoscaling. |
| `loadtest/k6/` + `results/` | Proof we scaled under load. |
| Prometheus / Grafana manifests under `infra/k8s/` | Letter **h**. |

**Viva sentence:** *“Ride Request is the only public surface; Matching and Dispatch do assignment; H3 cells sit on a hash ring; HPAs + k6 prove scale; Prometheus/Grafana/Logging prove observability.”*

---

### Vidhu (b, e + Trip Tracking / Fare / Flink)

| Open this | Why / what to say |
|---|---|
| `apps/trip_tracking/main.py` | Board/finish → trip states; writes `completions/*.json`; demand page. |
| `apps/fare/` (estimate + finalize handlers) | Serverless fare: HTTP estimate + Eventarc finalize. |
| `apps/demand_sink/` | Consumes Kafka `demand-results` → Firestore. |
| `flink/` (Java `DemandJob`) | Letter **e**: stream windows on Kafka. |
| Eventarc / Function terraform or deploy scripts | Letter **b**: serverless + event trigger. |

**Viva sentence:** *“Trip Tracking writes completion objects; Eventarc triggers Fare finalize; Flink windows ride-events into demand; the sink stores windows in Firestore for the Demand page.”*

---

## 4. Important flows mapped to code (conceptual)

### Create ride
`ride_request` → SQL insert `REQUESTED` → Pub/Sub match job → Kafka `RIDE_REQUESTED` → hops recorded.

### Accept
`ride_request` → `dispatch` gRPC Assign → Firestore lock → SQL `ACCEPTED` → Kafka `RIDE_ASSIGNED`.

### Board / Finish
`ride_request` → `trip_tracking` → SQL trip + GCS GPS/completion → Kafka `TRIP_UPDATED` → (finish) Eventarc → fare finalize.

### Demand
Kafka `ride-events` → Flink `DemandJob` → Kafka `demand-results` → `demand_sink` → Firestore → Trip Tracking demand page.

---

## 5. Kubernetes YAML — what to glance at

| Path pattern | Meaning |
|---|---|
| `infra/k8s/*/deployment.yaml` | How many replicas, image, env |
| `infra/k8s/*/service.yaml` | ClusterIP vs LoadBalancer |
| `infra/k8s/*/hpa.yaml` | CPU/RPS-based autoscaling |
| `infra/k8s/ingress*` | Public app hostname/IP |
| `infra/k8s/monitoring/` | Prometheus, Grafana, ServiceMonitors |

You do **not** need to edit these for the presentation. Pointing at them shows you know GitOps + k8s structure.

---

## 6. Scripts you might hear about (do not run casually)

| Script | Purpose |
|---|---|
| `scripts/run-flink.sh` | Submit DemandJob to Dataproc |
| `scripts/smoke*.sh` | End-to-end ride checks |
| Deploy / image push scripts | CI-style builds |

**For demo day:** open the **running** system via links in the UI guide. Do not re-deploy unless Pratham says so.

---

## 7. What “good” looks like when browsing code

1. Find the service folder for your letter.  
2. Open `main.py` (or Flink Java main).  
3. Find the function that matches the story (create ride, assign, complete, finalize, window).  
4. Say: “This function does X; it writes to Y; the next hop is Z.”

That is enough for a faculty “show me the code” moment.

---

## 8. Ownership reminder

| Letters | Person | Primary folders |
|---|---|---|
| a, d, g | Ved | `infra/terraform`, Argo, `apps/rider`, `apps/driver` |
| c, f, h | Pratham | `apps/ride_request`, `apps/matching`, `apps/dispatch`, HPA, k6, monitoring |
| b, e | Vidhu | `apps/fare`, `apps/trip_tracking`, `apps/demand_sink`, `flink/` |

Full roster with IDs: see repo root `task_division.txt`.
