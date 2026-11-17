# Metered — Presentation speaker notes (three solo blocks)

**Deck:** `docs/Metered-Cloud-Architecture.pptx` (19 slides)  
**Rule:** Three contiguous blocks. **No switching speakers inside a block.** Ved finishes his entire block, then Pratham, then Vidhu. The other two stay quiet unless faculty asks them a direct question.

| Block | Speaker | Slides | What the block covers |
|---|---|---|---|
| **1** | **Ved only** | **1 – 7** | Open, ownership, letters, his platform, his challenges |
| **2** | **Pratham only** | **8 – 13** | Match path, hashing, full system, demo plan, his challenges |
| **3** | **Vidhu only** | **14 – 19** | Fare + Flink, protocols, limitations, summary, thank you → demo |

Live URLs: `03-ui-and-demo.md`. After slide 19, open the app.

---

# How to practice

1. Read **Concept first** until you can teach it with the laptop closed.  
2. Say **Say this** out loud once (~45–90s per content slide).  
3. Know **If faculty asks** for your block only.  
4. On diagram slides: point; do not read every box.

---

# BLOCK 1 — VED ONLY (slides 1–7)

When Ved stands up, he owns the room until slide 7 is done. Then he sits / hands the clicker to Pratham.

---

## SLIDE 1 — Title (“Metered”)

### Concept first
Metered is cloud-native ride matching on Google Cloud (`asia-south1`). This talk is three solo blocks.

### Say this
> “Good morning. We are Ved, Pratham, and Vidhu. Our project is **Metered** — cloud-native ride matching on Google Cloud. We present in three blocks: I cover the platform foundation, Pratham covers the interactive path, Vidhu covers fare and stream analytics. I will start.”

### Do
- 2-second pause on the title. Do not dive into Pratham/Vidhu details.

---

## SLIDE 2 — Agenda

### Concept first
Agenda = three blocks, one speaker each, no handoffs mid-block.

### Say this
> “Block one is mine — task division, requirement letters, Terraform, GitOps, the three stores, Rider and Driver, and my challenges. Block two is Pratham — BFF, matching, hashing, full system, demo order. Block three is Vidhu — trip completion, Fare, Flink, limitations, and close. After the deck we demo on public URLs.”

---

## SLIDE 3 — Task division

### Concept first
Three people, eight services, eight letters. Assignment text assumes four members; we are three, so services are 3 / 3 / 2, but every letter has one owner.

### Say this
> “Here is ownership. The brief’s two-services-each line assumes four people. We are three, so the service split is three, three, and two — but every requirement letter still has a single owner.  
> I own Rider and Driver, plus letters **a**, **d**, and **g**.  
> Pratham owns Ride Request, Matching, and Dispatch — letters **c**, **f**, and **h**.  
> Vidhu owns Trip Tracking, Fare, and Demand Analytics — letters **b** and **e**.  
> I will now walk the letters, then my architecture.”

### If faculty asks
- **“Why not four people?”** → “Our enrolled group is three; letters are fully covered.”

---

## SLIDE 4 — Requirement letters a–h

### Concept first
Each letter maps to something concrete in Metered. You name the owner; you do not deep-dive Pratham/Vidhu yet.

### Say this
> “**a** — Infrastructure as code: Terraform — me.  
> **b** — Serverless plus REST, gRPC, queues — Vidhu.  
> **c** — GKE, HPA, k6 — Pratham.  
> **d** — GitOps with Argo CD — me.  
> **e** — Flink stream processing — Vidhu.  
> **f** — Consistent hashing — Pratham.  
> **g** — GCS, Cloud SQL, Firestore — me.  
> **h** — Prometheus, Grafana, Cloud Logging — Pratham.  
> Next I focus on **a**, **d**, and **g**.”

---

## SLIDE 5 — Ved — platform foundation (WORDS)

### Concept first
1. Terraform = letter **a**.  
2. Argo CD = letter **d**.  
3. GCS + Cloud SQL + Firestore = letter **g**.  
4. Rider → SQL; Driver → SQL + Firestore presence.

### Say this
> “My work is the platform foundation. I provision the project with Terraform — bootstrap, platform, and Kubernetes stacks: VPC, GKE, Cloud SQL, Firestore, GCS, Pub/Sub, Artifact Registry, IAM. I install Argo CD so rollouts are git-driven. On the app side I own Rider and Driver: Rider writes profiles to Cloud SQL; Driver also publishes live presence into Firestore so Matching can find online drivers. Letter **g** is deliberate: object storage in GCS, relational data in Cloud SQL, operational NoSQL in Firestore.”

### If faculty asks
- **“Why Firestore and SQL?”** → “SQL is durable business records; Firestore is low-latency live presence.”  
- **“What is GitOps?”** → “Desired state in git; Argo reconciles the cluster.”

---

## SLIDE 6 — Ved — architecture (DIAGRAM)

### Concept first
Point Terraform → cluster → stores → Rider/Driver → Argo.

### Say this
> “This is my slice. Terraform defines the cloud resources. Inside the VPC we have GKE. Rider and Driver run as services. Profiles land in Cloud SQL; Driver live state in Firestore; objects in GCS. Argo CD watches GitHub and keeps the cluster synchronized — letter **d**. GCS, Cloud SQL, and Firestore together are letter **g**. Everything Pratham and Vidhu deploy assumes this foundation.”

### Do
- Cursor on the three stores when you say **g**.  
- Cursor on Argo when you say GitOps.

---

## SLIDE 7 — Ved — challenges

### Concept first
Honest migration story; then hand off cleanly.

### Say this
> “The hard part for the platform was migration. We had built on AWS until credits ran out, then re-homed the entire stack onto GCP — Terraform, networking, and managed services. EKS, MSK, SQS, RDS patterns became GKE, Strimzi Kafka, Pub/Sub, Cloud SQL, Firestore, and GCS. We kept GitOps as the normal deploy path, and we wired three storage products correctly for letter **g**. That closes my block. Pratham will take the interactive path.”

### Do
- Hand the clicker to Pratham. Stop talking.

---

# BLOCK 2 — PRATHAM ONLY (slides 8–13)

Pratham owns slides 8 through 13 alone. Ved and Vidhu stay quiet unless asked.

---

## SLIDE 8 — Pratham — interactive path (WORDS)

### Concept first
Browser → only Ride Request. Matching = Pub/Sub. Dispatch = gRPC. HPA+k6 = **c**. Hash ring = **f**. Prom/Grafana/Logging = **h**.

### Say this
> “I own the interactive path. The browser talks only to **Ride Request**, our BFF. It creates rides, proxies rider and driver calls, publishes match jobs on Pub/Sub, emits Kafka events, and serves Trace, Ring, and Checklist. **Matching** pulls those jobs and groups nearby H3 cells with consistent hashing. **Dispatch** assigns over gRPC with an atomic Firestore lock. Letter **c** is HPAs plus k6. Letter **h** is Prometheus, Grafana, and Cloud Logging.”

---

## SLIDE 9 — Pratham — request and match path (DIAGRAM)

### Say this
> “A rider hits Ride Request over HTTPS. We persist REQUESTED in Cloud SQL, publish a match job, and emit a Kafka event. Matching consumes the queue, finds candidates from Driver presence, and creates an offer. On accept, Ride Request calls Dispatch over gRPC; Dispatch locks the driver; the ride becomes ACCEPTED. One UI — behind it REST, a queue, and gRPC.”

---

## SLIDE 10 — Letter f — consistent hashing

### Concept first
Hash **H3 cells**, not driver IDs. Ring partitions `p0–p3`.

### Say this
> “Letter **f** is consistent hashing over geography. The map is H3 cells. Each cell hashes onto a ring partition — p0 through p3. Matching groups neighbour cells using that ring. With fixed membership, the same cell keeps the same partition. The Ring page can preview extra nodes without changing the live HASH_NODES Matching uses.”

---

## SLIDE 11 — Full system architecture

### Say this
> “This is Metered end to end in asia-south1. Public ingress lands on Ride Request. Inside the VPC: Rider, Driver, Matching, Dispatch, Trip Tracking, Kafka, demand sink. Around them: Cloud SQL, Firestore, GCS, Pub/Sub, Cloud Functions, Dataproc. Observability and Argo sit beside the apps. Ved’s foundation underpins this; Vidhu’s fare and Flink sit on the completion and analytics edges — he will detail those in the next block. My focus here is the interactive spine you just saw.”

---

## SLIDE 12 — How we demonstrate

### Say this
> “Demo order: open Checklist; create rider and online drivers; show H3 cell and partition; request a ride; open Trace for REST, queue, gRPC, SQL, NoSQL, EVENT hops; accept via Dispatch; show Ring; show HPA/Grafana evidence; query Cloud Logging by ride_id; show Argo for the git SHA. All URLs are public load balancers — no localhost. Vidhu will demo finish → fare and the Demand page in his block / live demo.”

---

## SLIDE 13 — Pratham — challenges

### Say this
> “My hard parts: keep Matching and Dispatch private while the browser only sees Ride Request; run Pub/Sub and Kafka without losing hop visibility; keep the hash ring stable while Ring can preview p4; prove HPA with k6; make sure Matching never assigns — only Dispatch Assign writes live assignment; stitch one ride_id across every hop for logging and Grafana. That closes my block. Vidhu takes fare and streaming.”

### Do
- Hand the clicker to Vidhu. Stop.

---

# BLOCK 3 — VIDHU ONLY (slides 14–19)

Vidhu owns 14 through 19 alone, then leads into the live demo.

---

## SLIDE 14 — Vidhu — completion and analytics (WORDS)

### Concept first
Trip Tracking → GCS completions → Eventarc → Fare finalize. Flink on Dataproc → demand. Fare ≠ Flink.

### Say this
> “I own the post-assign path and letters **b** and **e**. **Trip Tracking** records progress. On finish we write `completions/{ride_id}.json` to GCS and release the driver. Eventarc triggers **Fare** finalize, which writes `final_fare_cents` to Cloud SQL — that is our serverless piece. In parallel, Kafka ride-events feed **Flink** on **Dataproc** for one-minute demand windows; the demand sink stores them in Firestore for the Demand page.”

### If faculty asks
- **“Dataproc vs Flink?”** → “Dataproc is the VM cluster; Flink is the engine; DemandJob is our program.”  
- **“Does Flink compute fare?”** → “No. Flink is demand analytics. Fare is the Cloud Function path.”

---

## SLIDE 15 — Vidhu — fare trigger and Flink pipeline (DIAGRAM)

### Say this
> “Two pipelines. Left: Trip Tracking writes the completion object; Eventarc calls Fare finalize; Cloud SQL gets the final fare. Right: Kafka into Flink; windows out to demand-results; sink into Firestore; Demand page reads it. Same product, two concerns — billing completion versus city demand.”

---

## SLIDE 16 — Communication mechanisms

### Say this
> “On one ride we use REST, gRPC, and message queues together. REST into Ride Request and across many HTTP services. gRPC for Dispatch Assign. Queues: Pub/Sub for match jobs, Kafka for events into Flink. Letter **b** is the serverless Fare service on a path that already exercises all three styles.”

---

## SLIDE 17 — Limitations

### Say this
> “Honest gaps: we can demo the full software path, not a physical car with continuous classroom GPS. We are single-region. Load tests are demo-sized. Dataproc Flink is heavy for a course demo — destroy it after the talk. We would harden mTLS, IAM, DLQs, and deepen fare and demand UX for production.”

---

## SLIDE 18 — Summary

### Say this
> “Metered is one product, three solo blocks. Ved — letters a, d, g. Pratham — letters c, f, h. Vidhu — letters b, e. Eight letters, eight services, each demoable on the live system.”

---

## SLIDE 19 — Thank you

### Say this
> “Thank you. Questions — or we can move to the live demo now.”

### Do
- App tab already loaded. You drive demo for fare/demand; Pratham can take the ride UI if you agreed beforehand — but that is **after** the deck, not mid-slides.

---

# Printable cheat cards

## Ved — Block 1 (slides 1–7)
You alone. Open → ownership → letters → platform words → diagram → your challenges → **hand to Pratham**.

Spine: Terraform **a**, Argo **d**, GCS+SQL+Firestore **g**, Rider/Driver.

## Pratham — Block 2 (slides 8–13)
You alone. Interactive path → match diagram → hashing → full system → demo plan → your challenges → **hand to Vidhu**.

Spine: BFF only; Pub/Sub + gRPC; H3 ring **f**; HPA/k6 **c**; Prom/Grafana/Logging **h**.

## Vidhu — Block 3 (slides 14–19)
You alone. Completion words → fare/Flink diagram → protocols → limitations → summary → thank you → **demo**.

Spine: completions → Eventarc → Fare; Flink demand; Fare ≠ Flink; letter **b** + **e**.

---

# Night-before checklist

- [ ] Each person can run their **entire block** without the others speaking.  
- [ ] Clicker handoff only at end of slide 7 and end of slide 13.  
- [ ] No “I’ll let X explain this box” inside your block.  
- [ ] IDs match `task_division.txt`.  
- [ ] No localhost in any sentence.
