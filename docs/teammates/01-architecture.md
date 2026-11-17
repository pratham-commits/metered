# Metered — Architecture guide for teammates

**Audience:** Ved, Pratham, Vidhu (not faculty)  
**Goal:** After reading this, you can explain what Metered is, what every major piece does, and how a ride moves through the system — without deploying anything.

**Project:** `metered-513804` · **Region:** `asia-south1` (Mumbai)

---

## 1. What is Metered in one paragraph?

Metered is a **cloud ride-matching demo**. A rider requests a ride in a browser. The system finds a nearby online driver, assigns them, tracks the trip, writes a completion file, calculates a final fare, and can also compute **demand** (how busy each map cell is) using a streaming job. Everything important for the viva is **already live** in Google Cloud. You open links and show — you do not run Terraform on demo day (except you leave Dataproc/Flink running until after the 20 Nov presentation, then destroy it).

---

## 2. The big picture (who talks to whom)

```text
Browser
   │  HTTPS/HTTP
   ▼
Ride Request  (public BFF — the ONLY service the browser calls)
   │
   ├──► Rider service        → Cloud SQL (rider profiles)
   ├──► Driver service       → Cloud SQL + Firestore (live location)
   ├──► Matching             → Pub/Sub jobs + Firestore candidates
   ├──► Dispatch (gRPC)      → Firestore assign lock
   ├──► Trip Tracking        → Cloud SQL trips + GCS files + Kafka events
   ├──► Fare estimate URL    → Cloud Function / Cloud Run (HTTP)
   └──► Checklist / UI pages → also reads Prometheus replica counts, Grafana URL

When trip completes:
   Trip Tracking writes GCS completions/{ride}.json
        │
        ▼ Eventarc
   Fare finalize (Cloud Function) → Cloud SQL final_fare_cents

Meanwhile (streaming):
   Kafka ride-events → Flink on Dataproc → Kafka demand-results
        → demand-sink pod → Firestore demand windows
        → Demand page reads Firestore via Trip Tracking
```

**Remember this sentence for viva:**  
*“The browser only talks to Ride Request. Everything else is private inside the VPC / Google APIs.”*

---

## 3. The eight “letters” (assignment requirements)

| Letter | Plain English | Owner | Where it lives in Metered |
|---|---|---|---|
| **a** | Infrastructure as code | Ved | Terraform under `infra/` |
| **b** | Serverless + REST/gRPC/queues | Vidhu | Fare Cloud Functions; ride path uses REST, gRPC, Pub/Sub, Kafka |
| **c** | Kubernetes + autoscaling + load test | Pratham | GKE Deployments, HPAs, k6 |
| **d** | GitOps | Ved | Argo CD watches GitHub `main` |
| **e** | Stream processing | Vidhu | Flink on Dataproc |
| **f** | Consistent hashing | Pratham | H3 cells on a hash ring (`p0..p3`) |
| **g** | Object + SQL + NoSQL | Ved | GCS + Cloud SQL + Firestore |
| **h** | Metrics + logging | Pratham | Prometheus, Grafana, Cloud Logging |

---

## 4. Every service (the “flying entities”)

### 4.1 Services that run as pods on GKE (Kubernetes)

| Service | Port | What it does | Owner |
|---|---|---|---|
| **Ride Request** | 8003 | Public API + web UI (BFF). Creates rides, proxies rider/driver, accept/board/finish, checklist | Pratham |
| **Rider** | 8001 | Creates/stores rider profiles | Ved |
| **Driver** | 8002 (+ gRPC 9002) | Driver profiles + presence (ONLINE) into Firestore | Ved |
| **Matching** | 8004 | Consumes Pub/Sub match jobs, finds candidates, offers | Pratham |
| **Dispatch** | 8005 (+ gRPC 9005) | Assigns a driver atomically in Firestore | Pratham |
| **Trip Tracking** | 8006 | Trip progress, GPS objects, completion JSON, demand page | Vidhu |
| **Demand sink** | 8010 | Reads Kafka `demand-results`, writes Firestore | Vidhu |
| **Kafka (Strimzi)** | 9094/9095 | Message bus for ride events and demand results | Platform (Ved) |
| **Prometheus** | 9090 | Scrapes `/metrics` from pods | Pratham |
| **Grafana** | 80 | Dashboards (RPS, etc.) | Pratham |
| **Argo CD** | 443 | Syncs Git → cluster | Ved |

### 4.2 Serverless (not pods)

| Name | Type | What it does |
|---|---|---|
| **rideshare-fare-estimate** | Cloud Function (HTTP) → Cloud Run | Quote before/during request (`amount_cents`, surge) |
| **rideshare-fare-final** | Cloud Function (Eventarc on GCS) | When `completions/*.json` is created, writes `final_fare_cents` |

### 4.3 Dataproc / Flink (streaming)

| Name | What it is |
|---|---|
| **rideshare-flink** | Dataproc cluster (VMs) with Flink installed |
| **DemandJob** | Flink JAR job: reads Kafka `ride-events`, 1-minute windows per H3 zone, writes `demand-results` |

**Clarification:** *Dataproc* = the cluster of machines. *Flink* = the streaming program that runs on that cluster. Starting Dataproc without submitting the job is incomplete; we submit `DemandJob` so the demand page can fill.

---

## 5. Every place data is stored

| Store | Product | What we put there | Why |
|---|---|---|---|
| **Cloud SQL** `rideshare-pg` | PostgreSQL 16 | Riders, drivers, rides, trips, hops, fare quotes | Durable relational truth |
| **Firestore** | Native NoSQL | `rideshare_driver_live` (who is online where), `rideshare_demand_windows` | Fast lookups for matching / demand |
| **GCS** trip bucket | Object storage | `gps/...`, `completions/{ride_id}.json`, Flink JAR | Files + Eventarc trigger |
| **Pub/Sub** | Queue | `rideshare-match-jobs` (+ DLQ) | Async match work |
| **Kafka** | Log/stream | `ride-events`, `demand-results` | Events for Flink + sink |
| **Secret Manager** | Secrets | DB URL, demo token | Not in git |
| **Artifact Registry** | Docker images | All service images tagged by git SHA | What GKE pulls |

**Letter g talking point:** “We use **GCS** (object), **Cloud SQL** (SQL), and **Firestore** (NoSQL) — three storage products.”

---

## 6. One complete ride (memorize this story)

1. **Create rider** → Ride Request → Rider → row in Cloud SQL.  
2. **Create driver + Go online** → Driver writes **Firestore** presence (`AVAILABLE`) with an **H3 cell** (map hex). That cell is hashed onto ring partitions `p0,p1,p2,p3` (letter **f**).  
3. **Request ride** → Ride Request inserts `REQUESTED` in SQL, may call **Fare estimate**, publishes **Pub/Sub** match job + Kafka `RIDE_REQUESTED`, records hops.  
4. **Matching** pulls Pub/Sub, asks Driver/Firestore for candidates, writes offer.  
5. **Accept** → Ride Request calls **Dispatch gRPC Assign** → driver locked in Firestore → ride `ACCEPTED` → Kafka `RIDE_ASSIGNED`.  
6. **Board (I'm in the car)** → Ride Request calls **Trip Tracking** `IN_PROGRESS` → trip row + GPS object + Kafka `TRIP_UPDATED`.  
7. **Finish (I've reached)** → Ride Request calls Trip Tracking `COMPLETED` → writes **`completions/{id}.json`** to GCS → releases driver.  
8. **Eventarc** sees the GCS object → **Fare finalize** → `final_fare_cents` in Cloud SQL + hop `fare / EVENT / SQL`.  
9. **Flink** (if running) windows Kafka events → **demand-results** → **demand-sink** → Firestore → **Demand page**.

---

## 7. Networking (simple)

- **VPC** `rideshare-vpc`: private network for GKE nodes, Kafka, Dataproc, Cloud SQL private IP.  
- **Cloud NAT**: private nodes can reach Google APIs / pull images.  
- **Ingress + static IP** `rideshare-ip` = public app (`34.49.108.248`).  
- **Separate LoadBalancers** for Grafana, Argo, Demand (Trip Tracking), Prometheus — each has its own IP.  
- Browser **never** talks to Matching/Dispatch/SQL directly.

---

## 8. How deploys work (GitOps)

1. Code is pushed to GitHub `pratham-commits/metered` on `main`.  
2. Images are built and pushed to Artifact Registry with a git SHA tag.  
3. Deployment YAML pins that SHA.  
4. **Argo CD** sees git change and rolls pods.  
5. We do **not** `kubectl set image` for normal deploys (letter **d**).

---

## 9. Observability (letter h)

| Tool | Purpose | How you open it |
|---|---|---|
| **Grafana** | Graphs (RPS, etc.) | Public HTTP link |
| **Prometheus** | Raw metrics scrape | Public link |
| **Cloud Logging** | Every pod’s stdout; `ride_id` in JSON | GCP Console |
| **Checklist page** in the app | Proves health, hops, ring, HPA | Inside the app UI |
| **Trace page** in the app | Shows hop timeline for a ride | Inside the app UI |

There is **no Fluent Bit**. GKE ships container logs to Cloud Logging automatically.

---

## 10. What stays up vs what costs money

| Keep until after 20 Nov | Notes |
|---|---|
| GKE + app + Kafka + SQL + Firestore + GCS + Functions + Grafana + Argo + Demand LB + Prometheus LB | Standing cost |
| **Dataproc `rideshare-flink` + Flink job** | Extra cost (~tens of USD over a few days). Destroy **after** the presentation |

Stopping pods does **not** stop billing. Destroy Terraform / Dataproc when done.

---

## 11. Owners cheat-sheet

| Person | Say this in one line |
|---|---|
| **Ved** | “I built the cloud foundation with Terraform, GitOps with Argo, Rider/Driver, and the three stores.” |
| **Pratham** | “I built the public BFF and UI, matching/dispatch, hashing, HPAs/k6, and Prometheus/Grafana/Logging.” |
| **Vidhu** | “I built trip completion, serverless fare on GCS Eventarc, and Flink demand analytics into Firestore.” |
