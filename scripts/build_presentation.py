#!/usr/bin/env python3
"""Assemble the Metered architecture PowerPoint from icon-based diagrams."""

from __future__ import annotations

import os
import sys
from pathlib import Path

os.environ.setdefault("MPLCONFIGDIR", "/tmp/mpl-metered")
os.environ.setdefault("XDG_CACHE_HOME", "/tmp")

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from diagrams_metered import build_all  # noqa: E402
from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.util import Inches, Pt, Emu

OUT = ROOT / "docs" / "Metered-Cloud-Architecture.pptx"
LEGACY = ROOT / "docs" / "Rideshare-Cloud-Architecture.pptx"

# Professional palette — deep navy, cool paper, steel accent (no green side bars)
NAVY = RGBColor(0x0B, 0x1F, 0x33)
INK = RGBColor(0x1A, 0x23, 0x2E)
MUTED = RGBColor(0x5C, 0x6B, 0x7A)
ACCENT = RGBColor(0x1D, 0x7A, 0xA2)  # steel blue
SOFT = RGBColor(0xF3, 0xF6, 0xF9)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)
CARD = RGBColor(0xFF, 0xFF, 0xFF)
LINE = RGBColor(0xD5, 0xDC, 0xE3)
SUB = RGBColor(0x8F, 0xA8, 0xBC)

FONT_DISPLAY = "Georgia"
FONT_BODY = "Calibri"


def set_run(run, size=14, bold=False, color=INK, *, font=FONT_BODY, italic=False):
    run.font.name = font
    run.font.size = Pt(size)
    run.font.bold = bold
    run.font.italic = italic
    run.font.color.rgb = color


def new_slide(prs):
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    bg = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(0), Inches(0), Inches(13.333), Inches(7.5))
    bg.fill.solid()
    bg.fill.fore_color.rgb = SOFT
    bg.line.fill.background()
    return slide


def header(slide, title, subtitle=None):
    bar = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(0), Inches(0), Inches(13.333), Inches(1.05))
    bar.fill.solid()
    bar.fill.fore_color.rgb = NAVY
    bar.line.fill.background()
    # Thin copper underline — no left vertical bars
    rule = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(0.55), Inches(1.05), Inches(1.4), Inches(0.045))
    rule.fill.solid()
    rule.fill.fore_color.rgb = ACCENT
    rule.line.fill.background()

    tb = slide.shapes.add_textbox(Inches(0.55), Inches(0.22), Inches(12.2), Inches(0.72))
    tf = tb.text_frame
    tf.word_wrap = True
    r = tf.paragraphs[0].add_run()
    r.text = title
    set_run(r, 26, True, WHITE, font=FONT_DISPLAY)
    if subtitle:
        p = tf.add_paragraph()
        r2 = p.add_run()
        r2.text = subtitle
        set_run(r2, 13, False, SUB, font=FONT_BODY)


FOOTER_TEAM = (
    "Ved Pahune  2026H1030056P   ·   Pratham Shah  2026H1030063P   ·   Vidhu Kant Sharma  2026H1030053P"
)


def footer(slide, n, total, *, dark=False):
    ink = SUB if dark else MUTED
    rule_c = RGBColor(0x3A, 0x4F, 0x63) if dark else LINE
    rule = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(0.45), Inches(7.05), Inches(12.4), Inches(0.015))
    rule.fill.solid()
    rule.fill.fore_color.rgb = rule_c
    rule.line.fill.background()
    tb = slide.shapes.add_textbox(Inches(0.45), Inches(7.14), Inches(11.0), Inches(0.28))
    r = tb.text_frame.paragraphs[0].add_run()
    r.text = FOOTER_TEAM
    set_run(r, 9, False, ink, font=FONT_BODY)
    num = slide.shapes.add_textbox(Inches(11.55), Inches(7.14), Inches(1.3), Inches(0.28))
    num.text_frame.paragraphs[0].alignment = PP_ALIGN.RIGHT
    r2 = num.text_frame.paragraphs[0].add_run()
    r2.text = f"{n}  /  {total}"
    set_run(r2, 9, False, ink, font=FONT_BODY)


def body(slide, left, top, width, height, texts, size=14):
    tb = slide.shapes.add_textbox(Inches(left), Inches(top), Inches(width), Inches(height))
    tf = tb.text_frame
    tf.word_wrap = True
    for i, t in enumerate(texts):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.space_after = Pt(10)
        r = p.add_run()
        r.text = t
        set_run(r, size, False, INK, font=FONT_BODY)


def bullets(slide, left, top, width, height, items, size=13):
    tb = slide.shapes.add_textbox(Inches(left), Inches(top), Inches(width), Inches(height))
    tf = tb.text_frame
    tf.word_wrap = True
    for i, t in enumerate(items):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.space_after = Pt(9)
        r = p.add_run()
        r.text = "–  " + t
        set_run(r, size, False, INK, font=FONT_BODY)


def card(slide, left, top, width, height):
    shape = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(left), Inches(top), Inches(width), Inches(height))
    shape.fill.solid()
    shape.fill.fore_color.rgb = CARD
    shape.line.color.rgb = LINE
    shape.line.width = Pt(1.0)
    shape.adjustments[0] = 0.08
    return shape


def picture(slide, path: Path, *, top=1.25, bottom=6.95, max_width=12.2):
    from PIL import Image as PILImage

    img = PILImage.open(path)
    iw, ih = img.size
    aspect = iw / ih
    avail_h = bottom - top
    avail_w = max_width
    width = avail_w
    height = width / aspect
    if height > avail_h:
        height = avail_h
        width = height * aspect
    left = (13.333 - width) / 2
    slide.shapes.add_picture(str(path), Inches(left), Inches(top), width=Inches(width), height=Inches(height))


def build():
    paths = build_all()
    prs = Presentation()
    prs.slide_width = Inches(13.333)
    prs.slide_height = Inches(7.5)
    slides = []

    def S():
        s = new_slide(prs)
        slides.append(s)
        return s

    # ── Title ──
    s = S()
    hero = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(0), Inches(0), Inches(13.333), Inches(7.5))
    hero.fill.solid()
    hero.fill.fore_color.rgb = NAVY
    hero.line.fill.background()
    # Soft copper mark under brand — no left bar
    mark = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(0.9), Inches(3.55), Inches(1.8), Inches(0.05))
    mark.fill.solid()
    mark.fill.fore_color.rgb = ACCENT
    mark.line.fill.background()

    tb = s.shapes.add_textbox(Inches(0.9), Inches(2.0), Inches(11.5), Inches(1.5))
    tf = tb.text_frame
    r = tf.paragraphs[0].add_run()
    r.text = "Metered"
    set_run(r, 60, True, WHITE, font=FONT_DISPLAY)

    tb = s.shapes.add_textbox(Inches(0.9), Inches(3.75), Inches(11.5), Inches(1.4))
    tf = tb.text_frame
    tf.word_wrap = True
    r = tf.paragraphs[0].add_run()
    r.text = "Cloud-native ride matching on Google Cloud"
    set_run(r, 22, False, RGBColor(0xD5, 0xE0, 0xEA), font=FONT_BODY)
    p = tf.add_paragraph()
    p.space_before = Pt(8)
    r = p.add_run()
    r.text = "Three contiguous blocks  ·  One speaker per block  ·  No mid-deck handoffs"
    set_run(r, 14, False, SUB, font=FONT_BODY)

    # ── Agenda ──
    s = S()
    header(s, "Agenda", "Three blocks — one person owns each block start to finish")
    body(
        s,
        0.55,
        1.35,
        12.2,
        0.7,
        [
            "We do not bounce between speakers. Ved presents his full block, then Pratham presents his, then Vidhu presents his. Each block covers that person’s services, letters, diagram, and the closing slides that belong to them."
        ],
        15,
    )
    bullets(
        s,
        0.7,
        2.3,
        12,
        4.3,
        [
            "Block 1 — Ved: task division, letters, Terraform / GitOps / three stores, Rider & Driver, his challenges.",
            "Block 2 — Pratham: BFF / Matching / Dispatch, hashing, full system, demo order, his challenges.",
            "Block 3 — Vidhu: Trip Tracking, Fare, Flink demand, communication mechanisms, limitations, summary.",
            "After the three blocks: live demo on public URLs (no localhost).",
        ],
        15,
    )

    # ── Division ──
    s = S()
    header(s, "Task division", "Three people  ·  Eight services  ·  Eight letters")
    body(
        s,
        0.55,
        1.3,
        12.2,
        0.55,
        [
            "The assignment’s “two services each” line assumes four members. With three people every service and every letter still has a single owner. The service count is 3 / 3 / 2 on purpose."
        ],
        14,
    )
    cols = [
        (
            0.45,
            "Ved",
            "Platform + identity",
            [
                "Services: Rider, Driver",
                "a — Terraform for all infrastructure",
                "d — Argo CD GitOps",
                "g — GCS, Cloud SQL, Firestore",
                "Also: VPC, GKE, Kafka, Pub/Sub, IAM, shared library",
            ],
        ),
        (
            4.55,
            "Pratham",
            "Match path + observability",
            [
                "Services: Ride Request, Matching, Dispatch",
                "c — GKE apps, HPA, k6",
                "f — Consistent hashing on H3 cells",
                "h — Prometheus, Grafana, Cloud Logging",
                "Also: public UI, Trace, Ring, Checklist",
            ],
        ),
        (
            8.65,
            "Vidhu",
            "Fare + stream analytics",
            [
                "Services: Trip Tracking, Fare, Demand Analytics",
                "b — Cloud Run Fare + REST/gRPC/queues",
                "e — Flink on Dataproc (1-minute windows)",
                "Also: demand sink and demand page",
                "GCS completions → Eventarc → final_fare",
            ],
        ),
    ]
    for x, title, sid, items in cols:
        card(s, x, 2.05, 3.95, 4.55)
        tb = s.shapes.add_textbox(Inches(x + 0.22), Inches(2.25), Inches(3.5), Inches(4.15))
        tf = tb.text_frame
        tf.word_wrap = True
        r = tf.paragraphs[0].add_run()
        r.text = title
        set_run(r, 16, True, NAVY, font=FONT_DISPLAY)
        p = tf.add_paragraph()
        p.space_before = Pt(4)
        r = p.add_run()
        r.text = sid
        set_run(r, 11, False, ACCENT, font=FONT_BODY)
        for item in items:
            p = tf.add_paragraph()
            p.space_before = Pt(10)
            r = p.add_run()
            r.text = item
            set_run(r, 12, False, INK, font=FONT_BODY)

    # ── Letters ──
    s = S()
    header(s, "Requirement letters and owners", "What each letter means in Metered")
    rows = [
        ("a", "IaC — networks, cluster, databases, storage, IAM via Terraform", "Ved"),
        ("b", "One serverless service; path uses REST, gRPC, and message queues", "Vidhu"),
        ("c", "GKE for stateless services; HPAs on two services; k6 proves scale-out", "Pratham"),
        ("d", "GitOps controller tracks git; no kubectl apply for service deploys", "Ved"),
        ("e", "Flink stream job: Kafka → 1-minute stateful window → results topic", "Vidhu"),
        ("f", "Declared concept applied to the domain and shown live", "Pratham"),
        ("g", "Object store + managed SQL + managed NoSQL", "Ved"),
        ("h", "Prometheus/Grafana metrics plus centralized logging", "Pratham"),
    ]
    y = 1.3
    for letter, text, owner in rows:
        badge = s.shapes.add_shape(MSO_SHAPE.OVAL, Inches(0.55), Inches(y + 0.02), Inches(0.42), Inches(0.42))
        badge.fill.solid()
        badge.fill.fore_color.rgb = NAVY
        badge.line.fill.background()
        tb = s.shapes.add_textbox(Inches(0.55), Inches(y + 0.05), Inches(0.42), Inches(0.38))
        tb.text_frame.paragraphs[0].alignment = PP_ALIGN.CENTER
        r = tb.text_frame.paragraphs[0].add_run()
        r.text = letter
        set_run(r, 14, True, WHITE, font=FONT_DISPLAY)

        tb = s.shapes.add_textbox(Inches(1.2), Inches(y), Inches(9.5), Inches(0.48))
        r = tb.text_frame.paragraphs[0].add_run()
        r.text = text
        set_run(r, 13, False, INK, font=FONT_BODY)

        tb = s.shapes.add_textbox(Inches(10.9), Inches(y), Inches(1.9), Inches(0.48))
        r = tb.text_frame.paragraphs[0].add_run()
        r.text = owner
        set_run(r, 13, True, ACCENT, font=FONT_BODY)
        y += 0.62

    # ── Ved ──
    s = S()
    header(s, "Ved — platform foundation", "Terraform, identity services, GitOps, three stores")
    body(
        s,
        0.55,
        1.3,
        12.2,
        0.95,
        [
            "Ved provisions the Google Cloud project with Terraform and installs Argo CD so later service changes are git-driven. He implements Rider and Driver, and owns the three storage products required by letter g.",
        ],
        14,
    )
    bullets(
        s,
        0.7,
        2.4,
        12,
        4.2,
        [
            "Stacks: bootstrap, platform (VPC, GKE, SQL, Firestore, GCS, Pub/Sub, Artifact Registry, IAM), k8s (Argo CD, Strimzi Kafka, secrets).",
            "Rider writes relational profiles; Driver writes profiles to SQL and live presence to Firestore under a hashed partition.",
            "Deploy rule: images tagged with a git SHA and rolled by Argo CD. Direct kubectl set image is not used.",
        ],
        14,
    )

    s = S()
    header(s, "Ved — architecture", "IaC, identity services, three stores, GitOps")
    picture(s, paths["p1"])

    s = S()
    header(s, "Ved — challenges", "Platform migration and foundation hard parts")
    bullets(
        s,
        0.65,
        1.35,
        12.1,
        5.4,
        [
            "AWS → GCP mid-project: usable credits ran out, so the entire stack and Terraform had to be re-homed onto Google Cloud.",
            "Provider rewrite cost: EKS/MSK/SQS/RDS patterns became GKE, Strimzi Kafka, Pub/Sub, Cloud SQL, Firestore, and GCS — same product shape, different control planes.",
            "GitOps discipline from day one on GCP: images tagged with a git SHA and synced by Argo CD — no kubectl set image as the normal path.",
            "Three-store wiring for letter g: getting GCS, Cloud SQL, and Firestore into one VPC story with correct IAM and private connectivity.",
        ],
        14,
    )

    # ── BLOCK 2: Pratham (solo) ──
    s = S()
    header(s, "Pratham — interactive path", "Matching, scale-out, hashing, observability")
    body(
        s,
        0.55,
        1.3,
        12.2,
        0.9,
        [
            "Pratham owns the services a user touches. The browser talks only to Ride Request. Matching and Dispatch sit on the private network. The UI pages make letters c, f, and h visible without opening every console.",
        ],
        14,
    )
    bullets(
        s,
        0.7,
        2.35,
        12,
        4.2,
        [
            "Ride Request is the BFF: create rides, proxy rider/driver calls, publish Pub/Sub jobs, emit Kafka events, serve Trace/Ring/Checklist.",
            "Matching pulls Pub/Sub, groups H3 neighbours by consistent-hash owner, and calls Driver GetCandidates over gRPC.",
            "When a driver accepts in the UI, Ride Request calls Dispatch Assign (gRPC) and updates Firestore / Cloud SQL.",
            "HPAs on Ride Request and Matching; k6 proves scale-out. Grafana and Cloud Logging prove metrics and ride_id logs.",
        ],
        14,
    )

    s = S()
    header(s, "Pratham — request and match path", "HTTPS into the BFF, then queue + gRPC inside the VPC")
    picture(s, paths["p2"])

    s = S()
    header(s, "Letter f — consistent hashing in Metered", "H3 cells on a hash ring, not driver ids")
    picture(s, paths["hash"])

    s = S()
    header(s, "Full system architecture — Metered on Google Cloud", "Region asia-south1")
    picture(s, paths["full"])

    s = S()
    header(s, "How we demonstrate Metered end to end", "Checklist first, then deepen into each letter")
    bullets(
        s,
        0.65,
        1.35,
        12.1,
        5.4,
        [
            "Open Checklist and state which rows are proven versus show-yourself screens.",
            "Create a rider and drivers; go online; show H3 cell and partition.",
            "Request a ride; open Trace and read REST, QUEUE, gRPC, SQL, NOSQL, EVENT hops.",
            "Have a driver accept; show Dispatch Assign from Ride Request (not Matching).",
            "Open Ring; preview adding p4; read stayed versus moved.",
            "Run k6; watch both HPAs rise above 2; keep Grafana RPS visible.",
            "Query Cloud Logging with jsonPayload.ride_id across at least two services.",
            "Show Argo CD (git SHA) for GitOps, then hand the deck to Vidhu’s block for fare and Flink.",
        ],
        14,
    )

    s = S()
    header(s, "Pratham — challenges", "Scale, hashing, and proving letters c / f / h live")
    bullets(
        s,
        0.65,
        1.35,
        12.1,
        5.4,
        [
            "Networking boundary: browser stays on Ride Request only; Matching and Dispatch stay private (Ingress, ClusterIP, gRPC).",
            "Dual messaging: Pub/Sub for match jobs plus Kafka for domain events — two failure modes and careful hop tracing in the UI.",
            "Consistent hashing on H3 cells: partitions stay stable while Ring can preview p4 without breaking live HASH_NODES.",
            "HPA + k6: prove Ride Request and Matching scale under load without starving the BFF.",
            "Assign-on-accept: Matching never assigns; Ride Request → Dispatch Assign is the only live assignment write path.",
            "Observability glue: one ride_id across REST, QUEUE, gRPC, SQL, NoSQL, and EVENT hops.",
        ],
        14,
    )

    # ── BLOCK 3: Vidhu (solo) ──
    s = S()
    header(s, "Vidhu — completion and analytics", "Trip Tracking, serverless fare, Flink demand")
    body(
        s,
        0.55,
        1.3,
        12.2,
        0.9,
        [
            "Vidhu owns the post-assign path and letters b and e: Trip Tracking, serverless Fare, Dataproc Flink demand windows, and the demand sink.",
        ],
        14,
    )
    bullets(
        s,
        0.7,
        2.35,
        12,
        4.2,
        [
            "Trip Tracking: progress updates, write completions/{ride_id}.json, then release the driver.",
            "Fare: HTTP estimate; Eventarc finalize on GCS object finalize → Cloud SQL final_fare.",
            "Flink on Dataproc: consume ride-events, 1-minute H3 windows, emit demand-results.",
            "Demand sink: copy window results into Firestore for the demand UI.",
        ],
        14,
    )

    s = S()
    header(s, "Vidhu — fare trigger and Flink pipeline", "Trip → GCS → Fare → Cloud SQL  ·  Kafka → Flink → demand")
    picture(s, paths["p3"])

    s = S()
    header(s, "Communication mechanisms on one ride", "REST, gRPC, and queues are all present")
    picture(s, paths["comms"])

    s = S()
    header(s, "Limitations and what we would improve", "Honest gaps after the migration and the demo path")
    bullets(
        s,
        0.65,
        1.35,
        12.1,
        5.4,
        [
            "Live demo vs physical ride: we can show the full software path, but we cannot stage a real car start-to-end in class — continuous GPS movement for an in-progress trip is not practical inside a classroom or building.",
            "Single region (asia-south1): no multi-region failover or active-active matching yet.",
            "Credit / quota ceiling: load tests stay demo-sized; we cannot soak-test peak city traffic on free or student budgets.",
            "Stream analytics cost: Dataproc Flink is heavy for a course demo — we’d prefer a lighter managed stream job or scheduled batch windows.",
            "Security hardening: add mTLS between pods, tighter IAM per service account, and secret rotation beyond the current Terraform bootstrap.",
            "Resilience: chaos drills, stronger Pub/Sub DLQ dashboards, and automated canary / Rolling Releases before production-like traffic.",
            "Product depth: richer fare models, better demand UI, and end-to-end trip progress without manual hops between pages.",
        ],
        14,
    )

    s = S()
    header(s, "Summary", "One product, three owners, eight letters")
    body(
        s,
        0.55,
        1.4,
        12.2,
        1.1,
        [
            "Metered is one application presented in three blocks. Ved built the cloud foundation. Pratham built the interactive path, scale-out, hashing, and observability. Vidhu owns serverless fare and the Flink demand pipeline."
        ],
        16,
    )
    bullets(
        s,
        0.7,
        2.8,
        12,
        3.5,
        [
            "Ved — letters a, d, g (Terraform, GitOps, three stores).",
            "Pratham — letters c, f, h (match/accept path, hashing, observability).",
            "Vidhu — letters b, e (Fare trigger, Flink demand analytics).",
        ],
        15,
    )

    # ── Thanks ──
    s = S()
    hero = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(0), Inches(0), Inches(13.333), Inches(7.5))
    hero.fill.solid()
    hero.fill.fore_color.rgb = NAVY
    hero.line.fill.background()
    mark = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(5.75), Inches(3.55), Inches(1.8), Inches(0.05))
    mark.fill.solid()
    mark.fill.fore_color.rgb = ACCENT
    mark.line.fill.background()

    tb = s.shapes.add_textbox(Inches(0.8), Inches(2.35), Inches(11.7), Inches(1.2))
    tf = tb.text_frame
    tf.paragraphs[0].alignment = PP_ALIGN.CENTER
    r = tf.paragraphs[0].add_run()
    r.text = "Thank you"
    set_run(r, 56, True, WHITE, font=FONT_DISPLAY)

    tb = s.shapes.add_textbox(Inches(0.8), Inches(3.85), Inches(11.7), Inches(0.7))
    tf = tb.text_frame
    tf.paragraphs[0].alignment = PP_ALIGN.CENTER
    r = tf.paragraphs[0].add_run()
    r.text = "Any questions?  ·  Can we move to the demo now?"
    set_run(r, 22, False, RGBColor(0xD5, 0xE0, 0xEA), font=FONT_BODY)

    total = len(slides)
    for i, slide in enumerate(slides):
        dark = i in (0, total - 1)
        footer(slide, i + 1, total, dark=dark)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    prs.save(OUT)
    prs.save(LEGACY)
    print(f"Wrote {OUT}")


if __name__ == "__main__":
    build()
