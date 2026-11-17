#!/usr/bin/env python3
"""Metered architecture diagrams — strict spacing, labeled arrows, verified layout."""

from __future__ import annotations

import os
from pathlib import Path

os.environ.setdefault("MPLCONFIGDIR", "/tmp/mpl-metered")
os.environ.setdefault("XDG_CACHE_HOME", "/tmp")

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch, Rectangle
from matplotlib.offsetbox import AnnotationBbox, OffsetImage
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
DIAG = ROOT / "docs" / "diagrams"
ICON = DIAG / "icons"

C_BG = "#FFFFFF"
C_INK = "#202124"
C_MUTED = "#5F6368"
C_LINE = "#3C4043"
C_BORDER = "#DADCE0"
C_LANE = "#F8F9FA"
C_NAVY = "#174EA6"
C_TEAL = "#007B83"
C_GREEN = "#0D652D"
C_ORANGE = "#E37400"

CARD_W = 1.70
CARD_H = 1.35
ICON_ZOOM = 0.11
# Minimum clear gap between card edges (not centers)
EDGE_GAP = 0.45


def _img(name: str):
    path = ICON / f"{name}.png"
    if not path.exists():
        return None
    return Image.open(path).convert("RGBA")


def icon_node(ax, x, y, icon_name, title, subtitle=None, *, icon_zoom=ICON_ZOOM, box_w=CARD_W, box_h=CARD_H):
    left, bottom = x - box_w / 2, y - box_h / 2
    ax.add_patch(
        FancyBboxPatch(
            (left, bottom),
            box_w,
            box_h,
            boxstyle="round,pad=0.02,rounding_size=0.08",
            linewidth=1.2,
            edgecolor=C_BORDER,
            facecolor="#FFFFFF",
            zorder=3,
        )
    )
    if subtitle:
        icon_y = bottom + box_h * 0.68
        title_y = bottom + box_h * 0.32
        sub_y = bottom + box_h * 0.13
    else:
        icon_y = bottom + box_h * 0.62
        title_y = bottom + box_h * 0.22
        sub_y = None

    img = _img(icon_name)
    if img is not None:
        ax.add_artist(AnnotationBbox(OffsetImage(img, zoom=icon_zoom), (x, icon_y), frameon=False, zorder=4))
    else:
        ax.text(x, icon_y, "●", ha="center", va="center", fontsize=14, color=C_NAVY, zorder=4)

    ax.text(x, title_y, title, ha="center", va="center", fontsize=7.6, color=C_INK, fontweight="bold", zorder=4, clip_on=False)
    if subtitle:
        ax.text(x, sub_y, subtitle, ha="center", va="center", fontsize=6.2, color=C_MUTED, zorder=4, clip_on=False)

    return {
        "c": (x, y),
        "n": (x, bottom + box_h),
        "s": (x, bottom),
        "e": (left + box_w, y),
        "w": (left, y),
        "h": box_h,
        "w_": box_w,
    }


def lane(ax, x, y, w, h, title, color=C_NAVY):
    ax.add_patch(
        FancyBboxPatch(
            (x, y),
            w,
            h,
            boxstyle="round,pad=0.01,rounding_size=0.05",
            linewidth=1.4,
            edgecolor=color,
            facecolor=C_LANE,
            zorder=0,
        )
    )
    ax.text(
        x + 0.10,
        y + h + 0.18,
        title,
        ha="left",
        va="bottom",
        fontsize=8.5,
        color=color,
        fontweight="bold",
        zorder=5,
        clip_on=False,
        bbox=dict(boxstyle="round,pad=0.18", facecolor="white", edgecolor="none"),
    )


def _arrow(ax, a, b):
    """Always draw a visible filled arrowhead ABOVE cards."""
    x1, y1 = a
    x2, y2 = b
    dx, dy = x2 - x1, y2 - y1
    dist = (dx * dx + dy * dy) ** 0.5
    if dist < 0.06:
        return
    # Stop the tip in the gap (not under the destination card face)
    inset = min(0.12, max(0.08, dist * 0.15))
    ux, uy = dx / dist, dy / dist
    x2i, y2i = x2 - ux * inset, y2 - uy * inset
    # Draw shaft + explicit triangle head (more reliable than annotate styles)
    ax.plot([x1, x2i], [y1, y2i], color=C_LINE, lw=1.7, solid_capstyle="butt", zorder=5)
    # Triangle head in data coords
    head_len = min(0.16, dist * 0.28)
    head_w = head_len * 0.55
    # tip at (x2i,y2i), base back along the shaft
    bx, by = x2i - ux * head_len, y2i - uy * head_len
    px, py = -uy * head_w, ux * head_w  # perpendicular
    tri = plt.Polygon(
        [(x2i, y2i), (bx + px, by + py), (bx - px, by - py)],
        closed=True,
        facecolor=C_LINE,
        edgecolor=C_LINE,
        linewidth=0.5,
        zorder=6,
        clip_on=False,
    )
    ax.add_patch(tri)


def _line(ax, a, b):
    """Plain connector segment (no head) — used only as elbow mid-runs."""
    x1, y1 = a
    x2, y2 = b
    ax.plot([x1, x2], [y1, y2], color=C_LINE, lw=1.7, solid_capstyle="round", zorder=5)


def elbow(ax, points, label="", label_at=0):
    """Orthogonal path: plain mid-segments, single arrowhead on the final hop only."""
    if len(points) < 2:
        return
    for i in range(len(points) - 2):
        _line(ax, points[i], points[i + 1])
    _arrow(ax, points[-2], points[-1])
    if label:
        i = min(max(label_at, 0), len(points) - 2)
        x1, y1 = points[i]
        x2, y2 = points[i + 1]
        mx, my = (x1 + x2) / 2, (y1 + y2) / 2
        if abs(x1 - x2) >= abs(y1 - y2):
            _label(ax, mx, my + 0.16, label)
        else:
            _label(ax, mx + 0.14, my, label, ha="left", va="center")


def _label(ax, tx, ty, text, ha="center", va="bottom"):
    ax.text(
        tx,
        ty,
        text,
        ha=ha,
        va=va,
        fontsize=6.5,
        color=C_INK,
        fontweight="bold",
        zorder=6,
        clip_on=False,
        bbox=dict(boxstyle="round,pad=0.22", facecolor="white", edgecolor=C_BORDER, linewidth=0.55, alpha=1.0),
    )


def edge(ax, p1, p2, label="", *, bend=None):
    """Connector with one final arrowhead. Bent paths use plain mid-run + headed last hop."""
    x1, y1 = p1
    x2, y2 = p2
    if abs(x1 - x2) < 0.08 or abs(y1 - y2) < 0.08:
        bend = None

    def place():
        if not label:
            return
        if bend is None:
            mx, my = (x1 + x2) / 2, (y1 + y2) / 2
            if abs(x1 - x2) >= abs(y1 - y2):
                _label(ax, mx, my + 0.18, label)
            else:
                _label(ax, mx + 0.16, my, label, ha="left", va="center")
        elif bend == "h":
            if abs(x1 - x2) >= abs(y1 - y2):
                _label(ax, (x1 + x2) / 2, y1 + 0.18, label)
            else:
                _label(ax, x2 + 0.16, (y1 + y2) / 2, label, ha="left", va="center")
        else:
            if abs(y1 - y2) >= abs(x1 - x2):
                _label(ax, x1 + 0.16, (y1 + y2) / 2, label, ha="left", va="center")
            else:
                _label(ax, (x1 + x2) / 2, y2 + 0.18, label)

    if bend is None:
        _arrow(ax, (x1, y1), (x2, y2))
        place()
        return

    if bend == "h":
        mid = (x2, y1)
        pts = [(x1, y1)]
        if abs(x1 - mid[0]) >= 0.08:
            pts.append(mid)
        pts.append((x2, y2))
        elbow(ax, pts, label=label, label_at=0 if abs(x1 - mid[0]) >= abs(mid[1] - y2) else 1)
    else:
        mid = (x1, y2)
        pts = [(x1, y1)]
        if abs(y1 - mid[1]) >= 0.08:
            pts.append(mid)
        pts.append((x2, y2))
        elbow(ax, pts, label=label, label_at=0 if abs(y1 - mid[1]) >= abs(mid[0] - x2) else 1)


def finish(fig, path: Path):
    fig.patch.set_facecolor(C_BG)
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=200, bbox_inches="tight", pad_inches=0.30, facecolor=C_BG, edgecolor="none")
    plt.close(fig)


def stack_ys(top: float, n: int, box_h: float = CARD_H, gap: float = EDGE_GAP) -> list[float]:
    """Centers for n stacked cards with guaranteed edge gaps."""
    step = box_h + gap
    return [top - i * step for i in range(n)]


def diagram_person1(path: Path):
    fig, ax = plt.subplots(figsize=(13.5, 7.8))
    ax.set_xlim(0, 13.5)
    ax.set_ylim(0, 7.8)
    ax.axis("off")

    lane(ax, 0.25, 3.05, 3.10, 4.25, "Terraform  ·  letter a", C_NAVY)
    lane(ax, 3.55, 3.05, 4.55, 4.25, "Identity services on GKE", C_TEAL)
    lane(ax, 8.30, 3.05, 4.90, 4.25, "Three stores  ·  letter g", C_GREEN)
    lane(ax, 0.25, 0.30, 12.95, 2.30, "GitOps  ·  letter d", C_ORANGE)

    # Wider vertical gap so short arrows keep visible heads
    ys = stack_ys(6.20, 2, CARD_H, 0.70)
    tf = icon_node(ax, 1.80, ys[0], "terraform", "Terraform", "bootstrap → platform → k8s", box_w=2.20)
    gke = icon_node(ax, 1.80, ys[1], "gke", "GKE cluster", "asia-south1-a", box_w=2.20)
    edge(ax, tf["s"], gke["n"], "provisions")

    rider = icon_node(ax, 4.90, ys[0], "pod", "Rider", "profiles")
    driver = icon_node(ax, 7.00, ys[0], "pod", "Driver", "presence")
    lib = icon_node(ax, 5.95, ys[1], "pod", "Shared library", "db · store · zones", box_w=2.20)
    edge(ax, gke["e"], rider["w"], "hosts")
    edge(ax, rider["e"], driver["w"], "co-located")
    lib_nl = (lib["c"][0] - 0.40, lib["n"][1])
    lib_nr = (lib["c"][0] + 0.40, lib["n"][1])
    elbow(ax, [rider["s"], (rider["c"][0], lib_nl[1]), lib_nl], "imports", label_at=0)
    elbow(ax, [driver["s"], (driver["c"][0], lib_nr[1]), lib_nr], "imports", label_at=0)

    sql = icon_node(ax, 9.40, ys[0], "sql", "Cloud SQL", "relational")
    fs = icon_node(ax, 11.60, ys[0], "firestore", "Firestore", "live / NoSQL")
    gcs = icon_node(ax, 10.50, ys[1], "gcs", "Cloud Storage", "objects + triggers", box_w=2.10)
    # Route SQL over the top (inside lane) so the line never cuts through Driver
    over = ys[0] + CARD_H / 2 + 0.32
    elbow(ax, [rider["n"], (rider["c"][0], over), (sql["c"][0], over), sql["n"]], "SQL", label_at=1)
    edge(ax, driver["e"], fs["w"], "NoSQL")
    edge(ax, lib["e"], gcs["w"], "objects")
    gcs_nl = (gcs["c"][0] - 0.30, gcs["n"][1])
    gcs_nr = (gcs["c"][0] + 0.30, gcs["n"][1])
    elbow(ax, [sql["s"], (sql["c"][0], gcs_nl[1]), gcs_nl], "letter g", label_at=0)
    elbow(ax, [fs["s"], (fs["c"][0], gcs_nr[1]), gcs_nr], "letter g", label_at=0)

    gh = icon_node(ax, 2.10, 1.30, "github", "GitHub main", "deploy/apps", box_w=2.00)
    argo = icon_node(ax, 5.00, 1.30, "cicd", "Argo CD", "tracks git SHA", box_w=2.00)
    dep = icon_node(ax, 7.90, 1.30, "pod", "Workload images", "git SHA tags", box_w=2.10)
    sync = icon_node(ax, 11.00, 1.30, "gke", "Roll out on GKE", "→ cluster above", box_w=2.20)
    edge(ax, gh["e"], argo["w"], "push")
    edge(ax, argo["e"], dep["w"], "sync")
    edge(ax, dep["e"], sync["w"], "apply")
    finish(fig, path)


def diagram_person2(path: Path):
    """Three self-contained lanes — no lines cross lane borders."""
    fig, ax = plt.subplots(figsize=(14.0, 9.6))
    ax.set_xlim(0, 14.0)
    ax.set_ylim(0, 9.6)
    ax.axis("off")

    # ── 1 Match path (fully inside navy lane) ──
    lane(ax, 0.25, 7.15, 13.50, 2.05, "1 · Match path (GetCandidates only)", C_NAVY)
    top = 8.05
    xs = [1.20, 3.60, 6.00, 8.40, 10.90]
    user = icon_node(ax, xs[0], top, "user", "Browser")
    rr = icon_node(ax, xs[1], top, "pod", "Ride Request", "Metered BFF", box_w=1.85)
    pub = icon_node(ax, xs[2], top, "pubsub", "Pub/Sub", "match job")
    match = icon_node(ax, xs[3], top, "pod", "Matching", "H3 · HPA")
    drv = icon_node(ax, xs[4], top, "pod", "Driver", "GetCandidates", box_w=1.85)
    edge(ax, user["e"], rr["w"], "HTTPS")
    edge(ax, rr["e"], pub["w"], "QUEUE")
    edge(ax, pub["e"], match["w"], "pull")
    edge(ax, match["e"], drv["w"], "gRPC")

    # ── 2 Accept + side effects (two rows with real edge gap inside teal lane) ──
    lane(ax, 0.25, 3.15, 13.50, 3.65, "2 · Accept path + BFF side effects", C_TEAL)
    ay = 5.70
    acc = icon_node(ax, 1.55, ay, "pod", "Ride Request", "accept API", box_w=1.80)
    disp = icon_node(ax, 4.35, ay, "pod", "Dispatch", "Assign on accept", box_w=1.90)
    fs = icon_node(ax, 7.25, ay, "firestore", "Firestore", "live assign", box_w=1.80)
    sql2 = icon_node(ax, 10.15, ay, "sql", "Cloud SQL", "ASSIGNED", box_w=1.80)
    edge(ax, acc["e"], disp["w"], "accept")
    edge(ax, disp["e"], fs["w"], "NoSQL")
    edge(ax, fs["e"], sql2["w"], "SQL")

    # Wider vertical gap so the BFF-also arrowhead is unmistakable
    by = 3.85
    rd = icon_node(ax, 1.55, by, "pod", "Rider / Driver", "REST proxies", box_w=1.80)
    sql1 = icon_node(ax, 4.35, by, "sql", "Cloud SQL", "ride row + hops", box_w=1.80)
    kaf = icon_node(ax, 7.25, by, "kafka", "Kafka", "RIDE_REQUESTED", box_w=1.80)
    edge(ax, acc["s"], rd["n"], "BFF also")
    edge(ax, rd["e"], sql1["w"], "SQL")
    edge(ax, sql1["e"], kaf["w"], "EVENT")

    # ── 3 Evidence (fully inside navy lane) — wide gaps so every head is obvious ──
    lane(ax, 0.25, 0.20, 13.50, 2.60, "3 · Evidence for letters c, f, h", C_NAVY)
    ev = 1.45
    k6 = icon_node(ax, 1.25, ev, "monitoring", "k6 load", "HPAs above 2", box_w=1.50)
    check = icon_node(ax, 3.95, ev, "pod", "Checklist", "live HPA counts", box_w=1.50)
    ring = icon_node(ax, 6.65, ev, "gke", "Ring page", "H3 · add p4", box_w=1.50)
    graf = icon_node(ax, 9.35, ev, "grafana", "Grafana", "RPS · errors", box_w=1.50)
    log = icon_node(ax, 12.15, ev, "logging", "Logging", "ride_id", box_w=1.50)
    edge(ax, k6["e"], check["w"], "scale-out")
    edge(ax, check["e"], ring["w"], "hash UI")
    edge(ax, ring["e"], graf["w"], "metrics")
    edge(ax, graf["e"], log["w"], "ride_id")
    finish(fig, path)


def diagram_hashing(path: Path):
    fig, ax = plt.subplots(figsize=(12.8, 5.6))
    ax.set_xlim(0, 12.8)
    ax.set_ylim(0, 5.6)
    ax.axis("off")
    ax.text(6.4, 5.30, "Consistent hashing on live H3 cells", ha="center", fontsize=12, fontweight="bold", color=C_INK)

    a = icon_node(ax, 1.70, 3.55, "user", "lat, lng", "live GPS", box_w=2.00)
    b = icon_node(ax, 4.55, 3.55, "gke", "H3 cell", "resolution 8", box_w=2.00)
    c = icon_node(ax, 7.40, 3.55, "pod", "Hash ring", "MD5 · 100 vnodes", box_w=2.00)
    d = icon_node(ax, 10.25, 3.55, "firestore", "Partition", "p0 – p3", box_w=2.00)
    edge(ax, a["e"], b["w"], "geo index")
    edge(ax, b["e"], c["w"], "hash")
    edge(ax, c["e"], d["w"], "owner")

    lane(ax, 0.45, 0.35, 11.90, 1.80, "Why Metered hashes the cell, not the driver id", C_TEAL)
    ax.text(
        6.4,
        1.10,
        "Driver online writes presence under partition_id. Matching groups neighbour cells by the same owner\n"
        "and calls GetCandidates once per partition. The Ring page previews adding p4 without changing live HASH_NODES.",
        ha="center",
        va="center",
        fontsize=8.8,
        color=C_INK,
        linespacing=1.45,
        clip_on=False,
    )
    finish(fig, path)


def diagram_person3(path: Path):
    fig, ax = plt.subplots(figsize=(13.2, 6.8))
    ax.set_xlim(0, 13.2)
    ax.set_ylim(0, 6.8)
    ax.axis("off")

    lane(ax, 0.25, 4.15, 12.70, 2.20, "Letter b — serverless fare trigger", C_TEAL)
    trip = icon_node(ax, 1.70, 5.15, "pod", "Trip Tracking", box_w=2.00)
    gcs = icon_node(ax, 4.55, 5.15, "gcs", "Cloud Storage", "completions/*.json", box_w=2.10)
    fare = icon_node(ax, 7.55, 5.15, "run", "Cloud Run Fare", "Eventarc finalize", box_w=2.10)
    sql = icon_node(ax, 10.65, 5.15, "sql", "Cloud SQL", "final_fare + hop", box_w=2.10)
    edge(ax, trip["e"], gcs["w"], "PUT")
    edge(ax, gcs["e"], fare["w"], "Eventarc")
    edge(ax, fare["e"], sql["w"], "write")

    lane(ax, 0.25, 1.35, 12.70, 2.20, "Letter e — stream analytics", C_NAVY)
    kaf_in = icon_node(ax, 1.70, 2.35, "kafka", "events topic", "Kafka input", box_w=2.00)
    flink = icon_node(ax, 4.80, 2.35, "dataproc", "Dataproc Flink", "1-minute windows", box_w=2.20)
    kaf_out = icon_node(ax, 8.05, 2.35, "kafka", "results topic", "demand-results", box_w=2.10)
    sink = icon_node(ax, 11.15, 2.35, "firestore", "Demand sink", "Firestore windows", box_w=2.10)
    edge(ax, kaf_in["e"], flink["w"], "consume")
    edge(ax, flink["e"], kaf_out["w"], "emit")
    edge(ax, kaf_out["e"], sink["w"], "copy")

    finish(fig, path)


def diagram_full_system(path: Path):
    """Full system: column lanes, neighbor-only hops, no lines through cards."""
    fig, ax = plt.subplots(figsize=(15.0, 10.0))
    ax.set_xlim(0, 15.0)
    ax.set_ylim(0, 10.0)
    ax.axis("off")
    ax.set_title("Metered — full system on Google Cloud (asia-south1)", fontsize=13, fontweight="bold", color=C_INK, pad=10)

    bh = 1.05
    gap = 0.50
    # Bottom card clears platform (platform top ≈ 2.05); leave room for under-route
    ys = stack_ys(8.55, 4, bh, gap)  # ys[3] ≈ 3.90 → card bottom ≈ 3.37

    col_b = 2.45
    col_t = ys[0] + bh / 2 + 0.30
    lanes = [
        (0.20, 1.70, C_ORANGE, "Edge"),
        (2.10, 3.40, C_NAVY, "Request + match"),
        (5.70, 2.70, C_NAVY, "Workloads on GKE"),
        (8.60, 2.55, C_GREEN, "Managed data"),
        (11.35, 3.40, C_TEAL, "Async (b, e)"),
    ]
    for x, w, color, title in lanes:
        ax.add_patch(
            FancyBboxPatch(
                (x, col_b),
                w,
                col_t - col_b,
                boxstyle="round,pad=0.01,rounding_size=0.05",
                linewidth=1.35,
                edgecolor=color,
                facecolor=C_LANE,
                zorder=0,
            )
        )
        ax.text(
            x + w / 2,
            col_t + 0.18,
            title,
            ha="center",
            fontsize=8.5,
            color=color,
            fontweight="bold",
            clip_on=False,
            bbox=dict(boxstyle="round,pad=0.14", facecolor="white", edgecolor="none"),
        )

    z = 0.09
    user = icon_node(ax, 1.05, ys[0], "user", "Browser", box_w=1.40, box_h=bh, icon_zoom=z)
    ing = icon_node(ax, 1.05, ys[1], "ing", "Ingress", "HTTPS LB", box_w=1.40, box_h=bh, icon_zoom=z)

    # Subtitles carry accept/SQL facts so we never draw long gutters that look like orphans
    rr = icon_node(ax, 3.75, ys[0], "pod", "Ride Request", "BFF · SQL hops", box_w=1.55, box_h=bh, icon_zoom=z)
    pub = icon_node(ax, 3.75, ys[1], "pubsub", "Pub/Sub", "match jobs", box_w=1.55, box_h=bh, icon_zoom=z)
    match = icon_node(ax, 3.75, ys[2], "pod", "Matching", "H3 · HPA", box_w=1.55, box_h=bh, icon_zoom=z)
    disp = icon_node(ax, 3.75, ys[3], "pod", "Dispatch", "← accept from BFF", box_w=1.55, box_h=bh, icon_zoom=z)

    gke = icon_node(ax, 7.05, ys[0], "gke", "GKE cluster", "asia-south1-a", box_w=1.55, box_h=bh, icon_zoom=z)
    apps = icon_node(ax, 7.05, ys[1], "pod", "Rider / Driver", "REST + gRPC", box_w=1.55, box_h=bh, icon_zoom=z)
    trip = icon_node(ax, 7.05, ys[2], "pod", "Trip Tracking", "completions", box_w=1.55, box_h=bh, icon_zoom=z)
    kaf = icon_node(ax, 7.05, ys[3], "kafka", "Kafka", "ride-events", box_w=1.55, box_h=bh, icon_zoom=z)

    sql = icon_node(ax, 9.85, ys[0], "sql", "Cloud SQL", "BFF + fare", box_w=1.55, box_h=bh, icon_zoom=z)
    gcs = icon_node(ax, 9.85, ys[1], "gcs", "Cloud Storage", "completions", box_w=1.55, box_h=bh, icon_zoom=z)
    fs = icon_node(ax, 9.85, ys[3], "firestore", "Firestore", "live assign", box_w=1.55, box_h=bh, icon_zoom=z)

    fare = icon_node(ax, 13.00, ys[1], "run", "Cloud Run Fare", "letter b", box_w=1.65, box_h=bh, icon_zoom=z)
    flink = icon_node(ax, 13.00, ys[2], "dataproc", "Dataproc Flink", "letter e", box_w=1.65, box_h=bh, icon_zoom=z)
    demand = icon_node(ax, 13.00, ys[3], "firestore", "Demand sink", "1-min windows", box_w=1.65, box_h=bh, icon_zoom=z)

    # Only short, local edges — every segment ends on a card with an arrowhead
    edge(ax, user["s"], ing["n"], "HTTPS")
    edge(ax, ing["e"], rr["w"], "to BFF")
    edge(ax, rr["s"], pub["n"], "publish")
    edge(ax, pub["s"], match["n"], "pull")
    edge(ax, match["e"], apps["w"], "GetCandidates")
    edge(ax, rr["e"], gke["w"], "REST")
    edge(ax, gke["s"], apps["n"], "hosts")
    edge(ax, apps["s"], trip["n"], "next")
    edge(ax, trip["s"], kaf["n"], "events")
    edge(ax, gke["e"], sql["w"], "SQL")
    # Assign under the bottom row so it never cuts through Kafka (stay inside column lane)
    under = col_b + 0.14
    elbow(ax, [disp["s"], (disp["c"][0], under), (fs["c"][0], under), fs["s"]], "assign", label_at=1)
    edge(ax, trip["e"], gcs["w"], "PUT")
    edge(ax, gcs["e"], fare["w"], "Eventarc")
    edge(ax, kaf["e"], flink["w"], "consume")
    edge(ax, flink["s"], demand["n"], "emit")
    ax.text(
        13.00,
        ys[0],
        "Fare → Cloud SQL\n(final_fare)",
        ha="center",
        va="center",
        fontsize=6.5,
        color=C_MUTED,
        clip_on=False,
        bbox=dict(boxstyle="round,pad=0.2", facecolor="white", edgecolor=C_BORDER, linewidth=0.5),
    )

    # Platform strip — single sequential chain (no overlapping long arrows)
    plat_y = 1.05
    lane(ax, 0.20, 0.20, 14.60, 1.85, "Platform + ops", C_MUTED)
    tf = icon_node(ax, 1.55, plat_y, "terraform", "Terraform", "provisions GKE", box_w=1.65, box_h=1.10, icon_zoom=z)
    argo = icon_node(ax, 4.20, plat_y, "cicd", "Argo CD", "deploys to GKE", box_w=1.65, box_h=1.10, icon_zoom=z)
    graf = icon_node(ax, 6.90, plat_y, "grafana", "Grafana", "scrapes Matching", box_w=1.65, box_h=1.10, icon_zoom=z)
    logs = icon_node(ax, 9.70, plat_y, "logging", "Cloud Logging", "ride_id from BFF", box_w=1.75, box_h=1.10, icon_zoom=0.07)
    tip = icon_node(ax, 12.70, plat_y, "gke", "Same GKE", "asia-south1-a", box_w=1.75, box_h=1.10, icon_zoom=z)
    edge(ax, tf["e"], argo["w"], "IaC")
    edge(ax, argo["e"], graf["w"], "GitOps")
    edge(ax, graf["e"], logs["w"], "metrics")
    edge(ax, logs["e"], tip["w"], "logs")
    finish(fig, path)


def diagram_comms(path: Path):
    fig, ax = plt.subplots(figsize=(12.8, 6.8))
    ax.set_xlim(0, 12.8)
    ax.set_ylim(0, 6.8)
    ax.axis("off")
    ax.set_title("Communication mechanisms on one Metered ride", fontsize=12, fontweight="bold", color=C_INK, pad=12)

    rows = [
        (5.60, "ing", "REST", "Browser → Ride Request → Rider / Driver / Trip; Fare estimate over HTTP"),
        (4.35, "pod", "gRPC", "Matching → Driver GetCandidates; Ride Request → Dispatch Assign on accept"),
        (3.10, "pubsub", "Pub/Sub", "Ride Request publishes match jobs; Matching pulls; DLQ after 5 attempts"),
        (1.85, "kafka", "Kafka", "Domain events on ride-events; Flink output on demand-results"),
        (0.60, "sql", "Stores", "SQL hops · Firestore live docs · GCS objects · Eventarc trigger"),
    ]
    for y, icon, title, body in rows:
        left, bottom, bw, bh = 0.35, y - 0.42, 2.35, 0.84
        ax.add_patch(
            FancyBboxPatch(
                (left, bottom),
                bw,
                bh,
                boxstyle="round,pad=0.02,rounding_size=0.06",
                linewidth=1.1,
                edgecolor=C_BORDER,
                facecolor="#FFFFFF",
                zorder=2,
            )
        )
        img = _img(icon)
        if img is not None:
            ax.add_artist(AnnotationBbox(OffsetImage(img, zoom=0.09), (left + 0.40, y), frameon=False, zorder=3))
        ax.text(left + 1.40, y, title, ha="left", va="center", fontsize=9.2, fontweight="bold", color=C_INK, zorder=3)
        ax.add_patch(
            FancyBboxPatch(
                (3.00, y - 0.38),
                9.40,
                0.76,
                boxstyle="round,pad=0.02,rounding_size=0.05",
                linewidth=1.0,
                edgecolor=C_BORDER,
                facecolor="#FFFFFF",
                zorder=2,
            )
        )
        ax.text(3.30, y, body, ha="left", va="center", fontsize=9.0, color=C_INK, zorder=3, clip_on=False)
    finish(fig, path)


def build_all():
    DIAG.mkdir(parents=True, exist_ok=True)
    cicd = ICON / "cicd.png"
    if not cicd.exists() and (ICON / "github.png").exists():
        cicd.write_bytes((ICON / "github.png").read_bytes())

    outs = {
        "full": DIAG / "full_system.png",
        "p1": DIAG / "person1.png",
        "p2": DIAG / "person2.png",
        "hash": DIAG / "hashing.png",
        "p3": DIAG / "person3.png",
        "comms": DIAG / "comms.png",
    }
    diagram_full_system(outs["full"])
    diagram_person1(outs["p1"])
    diagram_person2(outs["p2"])
    diagram_hashing(outs["hash"])
    diagram_person3(outs["p3"])
    diagram_comms(outs["comms"])
    return outs


if __name__ == "__main__":
    build_all()
    print("wrote", DIAG)
