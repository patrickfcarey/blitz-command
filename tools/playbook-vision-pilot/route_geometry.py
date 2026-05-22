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


# De-fragmentation tuning (task #35). M25 renders a route as a colored
# arrow, but the color mask of one route comes back in 2-3 pieces (anti-
# aliasing gaps, the arrowhead detaching from the stem, the line passing
# behind a player glyph). A morphological CLOSE bridges those intra-route
# gaps; connected-components then separates genuinely distinct routes.
CLOSE_KERNEL = 41        # ellipse diameter — bridges intra-route gaps
# RED is always exactly one route (the primary), so it can be closed far
# more aggressively — there is no second red route to wrongly merge into.
# This bridges the larger stem↔arrowhead gaps that split the red route.
CLOSE_KERNEL_RED = 81
ROUTE_MIN_AREA = 1800    # min component area to count as a route (post-close)


def _is_button_component(mask_component: np.ndarray) -> bool:
    """A PS-button receiver glyph is a COMPACT, roughly-square blob
    (~50-95px span, aspect ~1). A route is elongated. True = it's a
    button, not a route."""
    ys, xs = np.where(mask_component)
    if len(xs) == 0:
        return False
    w = xs.max() - xs.min() + 1
    h = ys.max() - ys.min() + 1
    span = max(w, h)
    aspect = max(w, h) / max(min(w, h), 1)
    return span <= 95 and aspect < 1.7


def isolate_routes(img: np.ndarray) -> dict:
    """Return {color: [route_mask, ...]} — ONE mask per detected route.

    De-fragmentation (task #35): a morphological CLOSE bridges the gaps
    that split one route into multiple color blobs; connected-components
    then yields one component per genuinely distinct route. RED collapses
    to a single route — M25 draws exactly one red (primary) route.
    """
    out = {}
    for color in ROUTE_COLORS:
        mask = _color_mask(img, color)
        k = CLOSE_KERNEL_RED if color == "red" else CLOSE_KERNEL
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (k, k))
        closed = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
        n, labels, stats, _ = cv2.connectedComponentsWithStats(closed, 8)
        routes = []
        for i in range(1, n):
            if stats[i, cv2.CC_STAT_AREA] < ROUTE_MIN_AREA:
                continue
            comp = (labels == i).astype(np.uint8) * 255
            if _is_button_component(comp):
                continue            # compact glyph, not a route
            routes.append(comp)
        out[color] = routes
    # RED is exactly one route (the primary). If the close left >1 red
    # component, merge them all — every red pixel belongs to that route.
    if len(out.get("red", [])) > 1:
        merged = np.zeros_like(out["red"][0])
        for m in out["red"]:
            merged = cv2.bitwise_or(merged, m)
        out["red"] = [merged]
    return out


def annotate_debug(img: np.ndarray, isolated: dict) -> np.ndarray:
    """Draw the isolated route masks over the crop for visual QA."""
    out = img.copy()
    colors = {"red": (0, 0, 255), "yellow": (0, 255, 255),
              "green": (0, 255, 0), "cyan": (255, 200, 0),
              "blue": (255, 0, 0)}
    for color, masks in isolated.items():
        for i, m in enumerate(masks):
            cnts, _ = cv2.findContours(m, cv2.RETR_EXTERNAL,
                                       cv2.CHAIN_APPROX_SIMPLE)
            cv2.drawContours(out, cnts, -1, colors[color], 2)
    return out


# ---------------------------------------------------------------------------
# Route tracing (task #32) — skeletonize a route mask and trace the polyline.
# ---------------------------------------------------------------------------

def _skeleton_endpoints(skel: np.ndarray) -> list[tuple[int, int]]:
    """Skeleton pixels (x, y) with exactly one 8-connected neighbor."""
    ys, xs = np.where(skel)
    pts = set(zip(xs.tolist(), ys.tolist()))
    endpoints = []
    for x, y in pts:
        n = sum(((x + dx, y + dy) in pts)
                for dx in (-1, 0, 1) for dy in (-1, 0, 1)
                if not (dx == 0 and dy == 0))
        if n == 1:
            endpoints.append((x, y))
    return endpoints


def _bfs_farthest(pts: set, start: tuple) -> tuple:
    """BFS over the skeleton point-set; return (farthest_point, parent_map)."""
    from collections import deque
    seen = {start: None}
    q = deque([start])
    last = start
    while q:
        cur = q.popleft()
        last = cur
        cx, cy = cur
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                if dx == 0 and dy == 0:
                    continue
                nb = (cx + dx, cy + dy)
                if nb in pts and nb not in seen:
                    seen[nb] = cur
                    q.append(nb)
    return last, seen


def _longest_path(comp: set) -> list:
    """Double-BFS longest path through one connected skeleton component."""
    start = next(iter(comp))
    far1, _ = _bfs_farthest(comp, start)
    far2, parents = _bfs_farthest(comp, far1)
    path = []
    node = far2
    while node is not None:
        path.append(node)
        node = parents[node]
    path.reverse()
    return path


def trace_route(mask: np.ndarray) -> list[tuple[int, int]] | None:
    """Skeletonize a route mask and return its centerline polyline.

    The mask is ONE route (post de-fragmentation). If the skeleton still
    has disconnected pieces, the LARGEST is traced — a stable choice that
    avoids the zigzag a naive stitch produces. (Bridging genuine intra-
    route gaps is handled upstream by the morphological close.)"""
    from skimage.morphology import skeletonize
    if mask.sum() < 200 * 255:
        return None
    skel = skeletonize(mask > 0)
    ys, xs = np.where(skel)
    if len(xs) < 15:
        return None
    pts = set(zip(xs.tolist(), ys.tolist()))

    # Trace the largest connected component of the skeleton.
    best_component: set = set()
    remaining = set(pts)
    while remaining:
        seed = next(iter(remaining))
        _, seen = _bfs_farthest(remaining, seed)
        comp = set(seen.keys())
        if len(comp) > len(best_component):
            best_component = comp
        remaining -= comp
    if len(best_component) < 15:
        return None
    return _longest_path(best_component)


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
    import json
    if len(sys.argv) >= 4:
        team, img_idx, panel = sys.argv[1], int(sys.argv[2]), int(sys.argv[3])
        img = clean_crop(team, img_idx, panel)
        iso = isolate_routes(img)
        for color, masks in iso.items():
            print(f"{color}: {len(masks)} route(s)")
        dbg = annotate_debug(img, iso)
        cv2.imwrite("/tmp/route_geom_debug.jpg", dbg)
        print("wrote /tmp/route_geom_debug.jpg")
    else:
        print("usage: route_geometry.py <team> <img_idx> <panel>")
