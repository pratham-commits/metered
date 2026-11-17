# Metered — UI & live demo guide for teammates

**Audience:** Ved, Pratham, Vidhu  
**Goal:** Run the full viva demo using **only live public URLs**. No localhost. No deploy.  
**Presentation window:** keep stack live through **20 Nov**; destroy Dataproc after the talk.

---

## 1. Live URLs (bookmark these)

| Surface | URL | Login |
|---|---|---|
| **App (Ride Request UI)** | http://34.49.108.248 | none |
| **Grafana** | http://8.231.70.2 | `admin` / `admin` |
| **Argo CD** | https://8.234.64.238 | `admin` / `X4mSyTYEmnTp3oNK` |
| **Demand page** | http://34.14.132.230/demand/page | none |
| **Prometheus** | http://35.200.197.156:9090 | none |

If a link fails: wait 10s and refresh (free/idle quirks). Do **not** start inventing localhost URLs.

---

## 2. Demo order (recommended 8–10 minutes)

### Step A — Open the app (everyone watches)

1. Open **App** → you should see the Metered UI (checklist / ride flow).  
2. Say: *“This is Ride Request, our public BFF. The browser only talks here.”*

### Step B — Happy-path ride (core story)

Do this slowly so hops appear:

1. **Create a rider** (name/phone as shown in UI).  
2. **Create a driver** and set them **ONLINE** / available near the pickup area.  
3. **Request a ride** (pickup/drop as UI asks).  
4. Wait until a match/offer appears → **Accept**.  
5. Click **I'm in the car / Board** (IN_PROGRESS).  
6. Click **I've reached / Finish** (COMPLETED).  
7. Open **Trace / hops** for that ride → show the timeline (request → match → assign → trip → fare).  
8. Confirm **final fare** appeared (checklist or ride detail — `final_fare_cents`).

**What you are proving:** end-to-end path across SQL, Firestore, Pub/Sub, gRPC, GCS, Eventarc, Fare.

### Step C — Checklist page (proof board)

On the app checklist, walk the green checks:

- Health of services  
- Storage products in use  
- Hash-ring partitions (`p0..p3`)  
- Recent hops  
- HPA / replica evidence if shown  

Say: *“This checklist is our viva scorecard — same system faculty can refresh.”*

### Step D — Demand (Vidhu)

1. Open **Demand page** URL.  
2. Explain: Flink windows Kafka ride-events → demand-results → Firestore → this page.  
3. If windows look empty: say the job was submitted on Dataproc; generate a few rides and refresh (1-minute windows).

### Step E — Grafana (Pratham)

1. Open Grafana → login `admin`/`admin`.  
2. Open the rideshare / RPS dashboard if listed.  
3. Say: *“Prometheus scrapes `/metrics`; Grafana visualizes. Under k6 load we proved HPA scale-out.”*

### Step F — Argo CD (Ved)

1. Open Argo (accept TLS warning if browser complains — self-signed/IP).  
2. Login with credentials above.  
3. Show Application(s) **Synced / Healthy**.  
4. Say: *“Git is the source of truth. We don’t kubectl-set-image for normal deploys.”*

### Step G — Prometheus (optional 30s)

Open Prometheus → Status → Targets (or query `up`).  
Say: *“Raw metrics backend behind Grafana.”*

---

## 3. Who clicks what (divide the screen share)

| Segment | Who leads | What they open |
|---|---|---|
| Intro + architecture diagram | Anyone (or Ved) | PPT + maybe app home |
| Terraform / Argo / Rider-Driver | **Ved** | Argo UI; mention SQL+Firestore+GCS |
| Ride UI + matching + HPA + Grafana | **Pratham** | App ride flow, checklist, Grafana, (optional Prometheus) |
| Trip finish → Fare + Demand + Flink | **Vidhu** | Finish ride, fare on checklist/trace, Demand page |

---

## 4. Phrases that sound conceptually clear

Use these; they are accurate:

- “**BFF** — Backend for Frontend: Ride Request aggregates private services.”  
- “**Eventarc** watches GCS `completions/` and triggers Fare finalize.”  
- “**H3** cells are hex map zones; we hash them onto a **consistent hash ring** `p0–p3`.”  
- “**HPA** scales pods from Prometheus metrics; **k6** was our load generator.”  
- “**GitOps** — desired state in git; Argo reconciles the cluster.”  
- “**Dataproc** hosts **Flink**; Flink is the streaming job, not a separate cloud product icon.”

---

## 5. If something looks wrong (do not panic)

| Symptom | What to try | What to say |
|---|---|---|
| Match never comes | Ensure a driver is ONLINE near pickup; wait ~10–20s | “Matching is async via Pub/Sub.” |
| No final fare | Confirm Finish wrote completion; wait a few seconds; refresh checklist | “Eventarc is eventually consistent by a few seconds.” |
| Demand empty | Create 2–3 rides; wait ~1 min; refresh | “Flink uses tumbling 1-minute windows.” |
| Grafana blank | Refresh; check datasource; still show Prometheus targets | “Metrics still scrape even if a panel is empty.” |
| Argo TLS warning | Proceed / Advanced → continue | “IP cert, expected for demo LB.” |

Do **not** SSH, terraform apply, or rebuild images during the viva unless faculty asks and Pratham is available.

---

## 6. k6 / HPA proof (Pratham talking point)

We already ran load tests; results live under `loadtest/k6/results/` in the repo.

One-line claim: *“Under synthetic load, ride-request HPA scaled above the baseline replica count (we recorded ~6 vs target floor 5 in the successful run — cite the results file if asked).”*

You do **not** need to re-run k6 live unless there is spare time and the cluster is healthy.

---

## 7. After 20 Nov (cleanup reminder)

1. Finish presentation.  
2. Destroy **Dataproc** Flink cluster (biggest avoidable burn).  
3. Later: tear down remaining Terraform when the course allows.  

Stopping browser tabs does not stop billing.

---

## 8. Printable pre-flight (day of talk)

- [ ] App opens  
- [ ] Can create rider + online driver + ride + accept + board + finish  
- [ ] Trace shows hops; final fare present  
- [ ] Demand page loads  
- [ ] Grafana login works  
- [ ] Argo Synced/Healthy  
- [ ] Each person knows their 2–3 slides + which URL they open  
