# Metered — Live links (public access only)

**Project:** Metered · **Region:** `asia-south1`  
**Note:** These are **public browser URLs**. There are **no GCP Console links** here — evaluators do not need a Google Cloud login.

Open the links below directly in a browser.

---

## 1. Actual application service (use this first)

This is the **real Metered web service** — the only public app users interact with for the ride flow.

| What | Link | Login |
|---|---|---|
| **Metered app (Ride Request BFF + UI)** | **http://34.49.108.248/** | None |

**What you can do on this link**

- Create rider / driver  
- Go online, request a ride, accept, board, finish  
- Open **Checklist**, **Trace**, **Ring** pages from the UI  

This is the assignment’s **public web service URL**.

---

## 2. Supporting live UIs (also public — not GCP Console)

These are separate LoadBalancer URLs used to **demonstrate** letters (demand, observability, GitOps). They are **not** the main ride app.

| What this link is for | Link | Login |
|---|---|---|
| **Demand page** (Flink 1-minute windows / letter **e**) | http://34.14.132.230/demand/page | None |
| **Grafana** (metrics dashboards / letter **h**) | http://8.231.70.2 | Username: `admin` · Password: `admin` |
| **Prometheus** (raw metrics backend / letter **h**) | http://35.200.197.156:9090 | None |
| **Argo CD** (GitOps sync status / letter **d**) | https://8.234.64.238 | Username: `admin` · Password: `X4mSyTYEmnTp3oNK` |

**Argo CD tip:** the browser may warn about the certificate (IP / self-signed). Choose Advanced → Proceed to continue.

---

## 3. What is intentionally not linked

| System | Why no public “console” link |
|---|---|
| GCP Console, Cloud SQL, Firestore, GCS, Pub/Sub, Dataproc, Cloud Logging UI | Requires project IAM — **not** for external evaluators |
| Rider / Driver / Matching / Dispatch pods | **Private** inside the VPC — reached only via the Ride Request app |
| Kafka brokers | Internal / VPC — not a browser demo surface |

Evidence for private pieces is shown **through the app** (Trace hops, Checklist) and the public links in sections 1–2.

---

## 4. Quick demo order using only these links

1. Open **section 1** → run one full ride (request → accept → board → finish).  
2. Stay on the app → open Trace / Checklist.  
3. Open **Demand page** (section 2).  
4. Open **Grafana** (section 2).  
5. Open **Argo CD** (section 2) → confirm Synced / Healthy.  
6. Optional: **Prometheus** (section 2).

---

## 5. Repo (code / IaC — not a runtime service)

| What | Link |
|---|---|
| GitHub repository | https://github.com/pratham-commits/metered |

Design doc, presentation, and task division are in this repository root (`design.md`, `presentation.pdf`, `task_division.txt`).
