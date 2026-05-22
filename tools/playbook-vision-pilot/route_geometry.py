#!/usr/bin/env python3
"""Deterministic route-geometry extraction for M25 play diagrams.

See ROUTE-GEOMETRY-DESIGN.md for the full rationale. In short: the LLM
cannot reliably trace thin overlapping route arrows from the screenshot,
so route shape is extracted in Python instead.

Build status — iteration 1: clean-crop generation + color isolation +
button/border filtering. Tracing (task #32) and classification
(task #33) come next.

This module works on CLEAN crops — the play panel with NO cyan/yellow
reference annotations drawn on it (those collide with route colors).
`clean_crop()` produces one straight from the source docx.
"""
from __future__ import annotations
import io
import math
import sys
import zipfile
from pathlib import Path

import cv2
import numpy as np

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "tools/ingest-research"))
from extract_docx_images import ordered_image_entries  # noqa: E402

PLAYBOOKS = REPO / "research_artifacts/PS3/Madden NFL 25 (2013)/Playbooks"
PLAY_AREA_LEFT, PLAY_AREA_RIGHT = 420, 1820

# Route colors in HSV (OpenCV: H 0-179). M25 draws each receiver's route
# in a distinct color (red = primary). Tuned against M25 play panels.
# NOTE iteration-1 finding: routes span more colors than first assumed —
# red, yellow, cyan, blue, green all appear as routes on a single play.
ROUTE_COLORS = {
    "red":    [((0, 110, 80), (10, 255, 255)),
               ((170, 110, 80), (180, 255, 255))],
    "yellow": [((20, 90, 90), (40, 255, 255))],
    "green":  [((42, 80, 80), (82, 255, 255))],
    "cyan":   [((84, 80, 90), (98, 255, 255))],
    "blue":   [((99, 90, 90), (125, 255, 255))],
}


def clean_crop(team: str, img_idx: int, panel: int) -> np.ndarray:
    """Full-res wide LOS-zoom crop of one play panel — NO annotations.

    Same geometry as the dispatch crops (panel → 3x → band 0.30-0.95 →
    2x) but without the cyan LOS line / yellow C-box, so route-color
    detection isn't polluted.
    """
    docx = PLAYBOOKS / f"{team}.docx"
    entries = ordered_image_entries(docx)
    with zipfile.ZipFile(docx) as z, z.open(entries[img_idx - 1]) as src:
        raw = src.read()
    # PIL for the LANCZOS resize chain, then hand to cv2 as BGR.
    from PIL import Image
    img = Image.open(io.BytesIO(raw)).convert("RGB")
    pw = (PLAY_AREA_RIGHT - PLAY_AREA_LEFT) / 3
    L = int(round(PLAY_AREA_LEFT + panel * pw))
    R = int(round(PLAY_AREA_LEFT + (panel + 1) * pw))
    panel_img = img.crop((L, 0, R, img.size[1]))
    w, h = panel_img.size
    up3 = panel_img.resize((w * 3, h * 3), Image.LANCZOS)
    w2, h2 = up3.size
    band = up3.crop((0, int(h2 * 0.30), w2, int(h2 * 0.95)))
    bw, bh = band.size
    wide = band.resize((bw * 2, bh * 2), Image.LANCZOS)
    arr = np.array(wide)            # RGB
    return cv2.cvtColor(arr, cv2.COLOR_RGB2BGR)


def _color_mask(img: np.ndarray, color: str) -> np.ndarray:
    """Binary mask of one route color, with border + banner zeroed out."""
    h, w = img.shape[:2]
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    mask = np.zeros((h, w), np.uint8)
    for lo, hi in ROUTE_COLORS[color]:
        mask |= cv2.inRange(hsv, np.array(lo), np.array(hi))
    # Kill the pink/magenta panel-border vignette.
    margin = int(w * 0.035)
    mask[:, :margin] = 0
    mask[:, w - margin:] = 0
    mask[:int(h * 0.04), :] = 0
    # Kill the bottom play-name banner + the pink panel-bottom border.
    # The play diagram sits above ~72% height; below that is banner/border.
    mask[int(h * 0.72):, :] = 0
    mask[int(h * 0.62):, :int(w * 0.42)] = 0   # bottom-left RUN/PASS text
    return mask


# ---------------------------------------------------------------------------
# Route tracing — junction-aware directional walk (tasks #32 / #35 / #36).
#
# Connected-components cannot separate routes: it both over-segments one
# route (fragmentation) and over-merges touching routes. Instead, each
# route is WALKED from its receiver origin: at a junction the walk takes
# the straightest branch (routes cross, they don't turn 90° onto each
# other), and at a fragmentation gap it leaps forward along its heading.
# ---------------------------------------------------------------------------

# 8-connected neighbour offsets.
_NBR8 = [(-1, -1), (0, -1), (1, -1), (-1, 0), (1, 0), (-1, 1), (0, 1), (1, 1)]

# A SMALL close only bridges anti-aliasing gaps; larger fragmentation
# gaps (a detached arrowhead) are bridged by the walk's gap-jump — so the
# kernel stays small and does NOT fuse routes that merely pass close.
SKEL_CLOSE = 13
GAP_JUMP_MAX = 85       # px the walk may leap across a fragmentation gap


def _skeleton(mask: np.ndarray) -> set:
    """Light CLOSE, skeletonize, return the set of skeleton pixels."""
    from skimage.morphology import skeletonize
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE,
                                       (SKEL_CLOSE, SKEL_CLOSE))
    closed = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
    skel = skeletonize(closed > 0)
    ys, xs = np.where(skel)
    return set(zip(xs.tolist(), ys.tolist()))


def _degree(pts: set, p: tuple) -> int:
    x, y = p
    return sum((x + dx, y + dy) in pts for dx, dy in _NBR8)


def _prune_spurs(pts: set, max_spur: int = 34) -> set:
    """Remove short dead-end branches (skeletonization barbs). A spur is
    an endpoint whose path to the nearest junction is <= max_spur px.
    Without this, every barb is a false route origin."""
    pts = set(pts)
    for _ in range(5):
        endpoints = [p for p in pts if _degree(pts, p) == 1]
        remove: set = set()
        for ep in endpoints:
            branch = [ep]
            cur, prev = ep, None
            while True:
                nbrs = [(cur[0] + dx, cur[1] + dy) for dx, dy in _NBR8
                        if (cur[0] + dx, cur[1] + dy) in pts
                        and (cur[0] + dx, cur[1] + dy) != prev]
                if len(nbrs) != 1:
                    break               # hit a junction or dead end
                prev, cur = cur, nbrs[0]
                branch.append(cur)
                if len(branch) > max_spur:
                    break
            if len(branch) <= max_spur and _degree(pts, cur) >= 3:
                remove.update(branch[:-1])   # drop the spur, keep junction
        if not remove:
            break
        pts -= remove
    return pts


def _unit(dx: float, dy: float) -> tuple:
    n = math.hypot(dx, dy) or 1.0
    return (dx / n, dy / n)


def _branch_heading(pts, frm, first, blocked, depth=18):
    """Heading of the branch leaving `frm` via `first`, peeked ~depth px —
    used to choose the straightest branch at a junction."""
    vis = set(blocked)
    vis.add(frm)
    cur = first
    vis.add(cur)
    last = first
    for _ in range(depth):
        nxt = [(cur[0] + dx, cur[1] + dy) for dx, dy in _NBR8
               if (cur[0] + dx, cur[1] + dy) in pts
               and (cur[0] + dx, cur[1] + dy) not in vis]
        if len(nxt) != 1:
            break
        cur = nxt[0]
        vis.add(cur)
        last = cur
    return _unit(last[0] - frm[0], last[1] - frm[1])


def _gap_jump(pts, cur, heading, visited):
    """The walk dead-ended mid-route (a fragmentation gap). Find the
    nearest unvisited skeleton pixel that continues the heading."""
    best = None
    for p in pts:
        if p in visited:
            continue
        dx, dy = p[0] - cur[0], p[1] - cur[1]
        dist = math.hypot(dx, dy)
        if dist < 5 or dist > GAP_JUMP_MAX:
            continue
        align = heading[0] * (dx / dist) + heading[1] * (dy / dist)
        if align < 0.55:                 # must roughly continue forward
            continue
        score = align - 0.25 * dist / GAP_JUMP_MAX
        if best is None or score > best[0]:
            best = (score, p)
    return best[1] if best else None


def _walk(pts: set, origin: tuple, max_steps: int = 6000) -> list:
    """Directional greedy walk from a route origin to its arrowhead.

    At a junction (a route crossing/touching another) it continues in the
    straightest direction — that is what keeps two routes apart. At a
    fragmentation gap it leaps forward via `_gap_jump`."""
    nbrs = [(origin[0] + dx, origin[1] + dy) for dx, dy in _NBR8
            if (origin[0] + dx, origin[1] + dy) in pts]
    if not nbrs:
        return [origin]
    visited = {origin}
    cur = nbrs[0]
    visited.add(cur)
    path = [origin, cur]
    heading = _unit(cur[0] - origin[0], cur[1] - origin[1])
    jumps = 0
    for _ in range(max_steps):
        nbrs = [(cur[0] + dx, cur[1] + dy) for dx, dy in _NBR8
                if (cur[0] + dx, cur[1] + dy) in pts
                and (cur[0] + dx, cur[1] + dy) not in visited]
        if not nbrs:
            if jumps >= 6:
                break
            jp = _gap_jump(pts, cur, heading, visited)
            if jp is None:
                break
            jumps += 1
            nxt = jp
        elif len(nbrs) == 1:
            nxt = nbrs[0]
        else:
            best = None
            for nb in nbrs:
                bh = _branch_heading(pts, cur, nb, visited)
                score = heading[0] * bh[0] + heading[1] * bh[1]
                if best is None or score > best[0]:
                    best = (score, nb)
            nxt = best[1]
        visited.add(nxt)
        path.append(nxt)
        cur = nxt
        if len(path) >= 14:
            a = path[-14]
            heading = _unit(cur[0] - a[0], cur[1] - a[1])
    return path


def _same_route(a: list, b: list, tol: int = 30, frac: float = 0.62) -> bool:
    """True if polyline `a` overlaps `b` enough to be the same route —
    fraction of a's sampled points lying within `tol` of a b point.
    Endpoint-proximity dedupe fails for bunch formations (distinct
    receivers, near-identical origins); path overlap is what matters."""
    sample = a[::10] or a
    probe = b[::5] or b
    hits = sum(any(abs(p[0] - q[0]) <= tol and abs(p[1] - q[1]) <= tol
                   for q in probe)
               for p in sample)
    return hits / max(len(sample), 1) >= frac


def routes_for_color(mask: np.ndarray, los_y: int,
                     one_route: bool = False) -> list:
    """Trace every route in one color mask. Each route is walked from its
    receiver origin — a skeleton endpoint on/near the LOS row. Spurs are
    pruned first so barbs don't become false origins. `one_route=True`
    (used for RED) keeps only the single longest walk."""
    pts = _prune_spurs(_skeleton(mask))
    if len(pts) < 40:
        return []
    endpoints = [p for p in pts if _degree(pts, p) == 1]
    # Origins: every pruned endpoint on/near the receiver line (+ a
    # backfield band for RB routes). NOT deduped by proximity — bunch
    # formations put distinct receivers within a few px of each other.
    origins = [p for p in endpoints
               if los_y - 150 <= p[1] <= los_y + 360]
    routes = []
    for o in origins:
        poly = _walk(pts, o)
        if len(poly) >= 22:
            routes.append(poly)
    # Dedupe by PATH OVERLAP — the same route walked from its origin and
    # from a near-LOS arrowhead, or two origins onto one route. Keep the
    # longer of any overlapping pair.
    routes.sort(key=len, reverse=True)
    unique: list = []
    for r in routes:
        if not any(_same_route(r, u) for u in unique):
            unique.append(r)
    # RED is exactly one route (the primary) — keep the longest walk.
    if one_route and len(unique) > 1:
        unique = [unique[0]]
    return unique


def extract_routes(img: np.ndarray) -> dict:
    """Top-level: trace + classify every route on a play crop.

    Returns {"c_xy": (cx, cy), "routes": [{color, polyline, route, ...}]}.
    """
    try:
        from target_gap_python import _detect_c
        c = _detect_c(img)
    except Exception:       # noqa: BLE001 — fall back to a geometric guess
        c = None
    if c is None:
        cx, cy = img.shape[1] // 2, int(img.shape[0] * 0.42)
    else:
        cx, cy = c
    routes = []
    for color in ROUTE_COLORS:
        mask = _color_mask(img, color)
        for poly in routes_for_color(mask, cy, one_route=(color == "red")):
            cls = classify_route(poly, cy, cx)
            if cls.get("route") == "not_a_route":
                continue
            routes.append({"color": color, "polyline": poly, **cls})
    return {"c_xy": (cx, cy), "routes": routes}


def annotate_debug(img: np.ndarray, extracted: dict) -> np.ndarray:
    """Draw every traced route polyline + its label for visual QA."""
    out = img.copy()
    cx, cy = extracted["c_xy"]
    cv2.line(out, (0, cy), (out.shape[1] - 1, cy), (130, 130, 130), 1)
    for r in extracted["routes"]:
        poly = r["polyline"]
        pts = np.array(poly, np.int32).reshape(-1, 1, 2)
        cv2.polylines(out, [pts], False, (255, 0, 255), 3)
        tail = poly[0] if abs(poly[0][1] - cy) < abs(poly[-1][1] - cy) else poly[-1]
        tip = poly[-1] if tail is poly[0] else poly[0]
        cv2.circle(out, tail, 13, (0, 255, 0), 3)
        cv2.circle(out, tip, 13, (0, 0, 255), 3)
        cv2.putText(out, r["route"], (tip[0] + 6, tip[1]),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 0, 255), 2)
    return out


def _simplify(polyline: list, epsilon: float = 12.0) -> list:
    """Douglas-Peucker simplification — collapse the polyline to its
    defining vertices (stem ends, break points, tip)."""
    if len(polyline) < 3:
        return polyline
    arr = np.array(polyline, dtype=np.int32).reshape(-1, 1, 2)
    simplified = cv2.approxPolyDP(arr, epsilon, False)
    return [tuple(p[0]) for p in simplified]


# ---------------------------------------------------------------------------
# Route classification (task #33) — polyline geometry → route-tree name.
# ---------------------------------------------------------------------------

def classify_route(polyline: list, los_y: int, c_x: int) -> dict:
    """Classify a traced route polyline into a route-tree name.

    Coordinate frame: y increases DOWNWARD; downfield = up = smaller y.
    The route starts at a receiver near los_y and extends downfield.
    """
    if not polyline or len(polyline) < 2:
        return {"route": "uncertain", "confidence": "low", "reason": "no polyline"}

    # Orient the polyline tail→tip so the TAIL is the endpoint nearest LOS.
    a, b = polyline[0], polyline[-1]
    if abs(a[1] - los_y) > abs(b[1] - los_y):
        polyline = polyline[::-1]
    origin = polyline[0]
    tip = polyline[-1]
    simp = _simplify(polyline)

    # Depth metrics (yards-agnostic; in pixels).
    min_y = min(p[1] for p in polyline)        # deepest point (smallest y)
    max_depth = los_y - min_y                  # how far upfield the route got
    tip_depth = los_y - tip[1]                 # depth of the arrowhead
    came_back = max_depth - tip_depth           # how much it returned toward LOS

    # NOISE GUARD: a real route runs downfield (above the LOS). A traced
    # polyline that never gets meaningfully upfield is a fragment, the
    # panel border, or a backfield artifact — not a route.
    if max_depth < 40:
        return {"route": "not_a_route", "confidence": "low",
                "reason": f"max_depth {int(max_depth)}px — never goes downfield",
                "max_depth_px": int(max_depth)}

    # Net horizontal travel of the LAST segment (the defining break).
    if len(simp) >= 2:
        seg = (simp[-1][0] - simp[-2][0], simp[-1][1] - simp[-2][1])
    else:
        seg = (tip[0] - origin[0], tip[1] - origin[1])
    last_dx, last_dy = seg
    # Toward middle = toward c_x.
    toward_middle = (last_dx > 0) == (origin[0] < c_x)

    # A scale for "shallow vs deep": OL spacing is ~130px (see target_gap);
    # ~3 OL spacings ≈ a deep route.
    SHALLOW = 130
    DEEP = 360

    def _depth_band(d):
        return "shallow" if d < SHALLOW else ("deep" if d > DEEP else "intermediate")

    n_breaks = max(0, len(simp) - 2)
    total_dx = tip[0] - origin[0]
    total_dy = origin[1] - tip[1]   # positive = went upfield

    # --- classification ladder ---
    result = {"max_depth_px": int(max_depth), "tip_depth_px": int(tip_depth),
              "came_back_px": int(came_back), "n_breaks": n_breaks,
              "n_vertices": len(simp)}

    # Mostly-horizontal, shallow → drag.
    if max_depth < SHALLOW and abs(total_dx) > 1.6 * max(max_depth, 1):
        result.update(route="drag", confidence="high")
        return result

    # Came back toward the LOS at the end → hitch / curl / comeback.
    # Depth bands (px): hitch ~shallow stem, curl ~intermediate, comeback
    # ~very deep stem. Curl is the broad middle band.
    if came_back > 0.30 * max(max_depth, 1) and came_back > 40:
        if max_depth < SHALLOW + 50:
            result.update(route="hitch", confidence="high")
        elif max_depth > 520:
            result.update(route="comeback", confidence="medium")
        else:
            result.update(route="curl", confidence="high")
        return result

    # No meaningful break → streak/seam.
    if n_breaks == 0 or abs(total_dx) < 60:
        result.update(route=("streak" if abs(total_dx) < 90 else "seam"),
                      confidence="high")
        return result

    # There IS a break and the route did not come back. Look at the break:
    # the last segment's slope tells in/out (≈horizontal) vs post/corner (diag).
    seg_len = (last_dx ** 2 + last_dy ** 2) ** 0.5
    horiz_ratio = abs(last_dx) / max(seg_len, 1)   # 1.0 = fully horizontal

    if horiz_ratio > 0.80:
        # Sharp ~90° break, stays at depth → in/dig or out.
        result.update(route=("in" if toward_middle else "out"),
                      confidence="high")
    else:
        # ~45° break continuing downfield → post or corner.
        result.update(route=("post" if toward_middle else "corner"),
                      confidence="high")
    result["depth_band"] = _depth_band(max_depth)
    return result


if __name__ == "__main__":
    if len(sys.argv) >= 4:
        team, img_idx, panel = sys.argv[1], int(sys.argv[2]), int(sys.argv[3])
        img = clean_crop(team, img_idx, panel)
        extracted = extract_routes(img)
        for r in extracted["routes"]:
            print(f"  [{r['color']:6s}] {r['route']:9s} conf={r.get('confidence')} "
                  f"maxdepth={r.get('max_depth_px')} cameback={r.get('came_back_px')}")
        dbg = annotate_debug(img, extracted)
        cv2.imwrite("/tmp/route_geom_debug.jpg", dbg)
        print(f"  {len(extracted['routes'])} routes — wrote /tmp/route_geom_debug.jpg")
    else:
        print("usage: route_geometry.py <team> <img_idx> <panel>")
