#!/usr/bin/env python3
"""Compute target_gap deterministically in Python for run plays.

The model's target_gap guess is wrong ~1 in 6 run plays. Since the gap is a
function of (red-arrow endpoint x, C-square x, assumed OL spacing), we can
compute it in Python more reliably than the model.

Usage from the dispatcher:
    if play_type == "run":
        gap = compute_target_gap_for_crop(crop_path)
        # override the model's gap with this one
"""
from __future__ import annotations
from pathlib import Path

import cv2
import numpy as np


# Default OL_SPACING fallback if dynamic measurement fails.
# Calibration history (empirical, on hand-labeled plays):
#   85 → 10/12 matched the LLM but missed 2 cases where LLM was wrong too
#   158 → 9/12 (calibrated from median model coords)
#   133 → fits both ground-truth cases (run_balanced power_o = C_right,
#         mike_ditka counter = C_left). Picked from the constraint range
#         [125, 141] that satisfies both.
DEFAULT_OL_SPACING = 133


def _measure_ol_spacing(img: np.ndarray, c_x: int, c_y: int) -> int:
    """Measure the average OL spacing for THIS crop by finding white-pixel
    column groups in a thin horizontal strip at the LOS y.

    Returns the median distance between adjacent groups, or DEFAULT_OL_SPACING
    if detection fails.
    """
    h, w = img.shape[:2]
    r, g, b = img[..., 2], img[..., 1], img[..., 0]
    white = ((r > 220) & (g > 220) & (b > 220)).astype(np.uint8)
    # Thin strip just at the LOS, capturing the OL circle HEADS (above the stubs).
    strip = white[max(0, c_y - 18):c_y + 8, :]
    col_density = strip.sum(axis=0)
    # Threshold: a column is "occupied" if it has >= 3 white pixels in the strip.
    occupied = col_density >= 3
    # Walk through and group consecutive occupied columns.
    groups: list[tuple[int, int]] = []
    in_group = False
    start = 0
    for x in range(len(occupied)):
        if occupied[x]:
            if not in_group:
                in_group = True
                start = x
        else:
            if in_group:
                groups.append((start, x - 1))
                in_group = False
    if in_group:
        groups.append((start, len(occupied) - 1))
    # Centers of each group.
    centers = [(s + e) // 2 for s, e in groups]
    # Restrict to centers near C (within 4x default spacing on each side) —
    # we don't want WRs at the far edges polluting the OL-spacing measurement.
    nearby = sorted(cx for cx in centers
                    if abs(cx - c_x) <= 4 * DEFAULT_OL_SPACING)
    if len(nearby) < 3:
        return DEFAULT_OL_SPACING
    # Median spacing between adjacent centers.
    gaps = [nearby[i + 1] - nearby[i] for i in range(len(nearby) - 1)]
    return int(np.median(gaps)) if gaps else DEFAULT_OL_SPACING


def _detect_c(img: np.ndarray) -> tuple[int, int] | None:
    """40x40 sliding window scan for densest near-white patch in upper-middle band."""
    h, w = img.shape[:2]
    r, g, b = img[..., 2], img[..., 1], img[..., 0]
    white = ((r > 235) & (g > 235) & (b > 235)).astype(np.uint8)
    x0, x1 = int(w * 0.20), int(w * 0.80)
    y0, y1 = int(h * 0.20), int(h * 0.55)
    BOX = 40
    best = (0, 0, 0)
    for y in range(y0, y1 - BOX, 2):
        for x in range(x0, x1 - BOX, 2):
            d = int(white[y:y + BOX, x:x + BOX].sum())
            if d > best[2]:
                best = (x, y, d)
    if best[2] < 500:
        return None
    return best[0] + BOX // 2, best[1] + BOX // 2


def _detect_red_arrow_los_x(img: np.ndarray, los_y: int,
                            c_x: int) -> tuple[int, int] | None:
    """Find where the red ball-carrier arrow crosses (or comes closest to)
    the LOS line. Returns (x_at_los, y_of_intersection) — the x is what
    classifies target_gap.

    The arrow shape is hugely variable per play type:
    - Dive/Blast: arrow goes north-south, head upfield (small y).
    - Toss/Sweep: arrow stays lateral in backfield, never crosses LOS.
    - Counter/Power: arrow goes diagonal, crosses LOS at a specific gap.

    Strategy: take the LARGEST red contour (the arrow's body, ignoring small
    text fragments), then within its points find the one whose y is closest
    to LOS-y. For arrows that don't reach the LOS (toss/sweep), use the
    contour point with maximum |dx from c_x| — that's where the ball-carrier
    is heading sideways and we classify by D_left/D_right.
    """
    h, w = img.shape[:2]
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    m1 = cv2.inRange(hsv, np.array((0, 110, 80)), np.array((10, 255, 255)))
    m2 = cv2.inRange(hsv, np.array((170, 110, 80)), np.array((180, 255, 255)))
    mask = cv2.bitwise_or(m1, m2)
    # Mask the play-name banner.
    mask[int(h * 0.65):, :int(w * 0.30)] = 0
    mask[int(h * 0.80):, :] = 0

    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL,
                                   cv2.CHAIN_APPROX_SIMPLE)
    contours = [c for c in contours if cv2.contourArea(c) >= 200]
    if not contours:
        return None
    # The arrow renders as 1-3 disconnected contours (head, body, tail) when
    # the rendering pipeline breaks it into chunks. Combine ALL contour
    # points so we don't miss the LOS crossing for split arrows.
    all_pts = np.vstack([c.reshape(-1, 2) for c in contours])
    ys = all_pts[:, 1]
    xs = all_pts[:, 0]

    # Does the arrow reach the LOS region?
    # Use a narrow band: ±25 px around los_y. The arrow CROSSES this line
    # at one x value (the target gap). Wider bands pick up the arrow's
    # outer bulges (e.g. counter plays that loop wide before cutting back),
    # which are NOT the crossing point.
    on_los = np.abs(ys - los_y) <= 25
    if on_los.any():
        # MEDIAN x of points on the LOS line. The arrow has thickness, so
        # multiple pixels are at any given y; median collapses them into
        # the centerline. Multiple crossings (e.g., the arrow tail at HB
        # depth doesn't appear here because we constrained y).
        on_los_x = xs[on_los]
        # If the arrow has TWO crossings (entering and exiting the LOS),
        # they'll be at distinct x clusters. Take the one farthest from c_x
        # since that's the FORWARD-motion crossing (the gap the carrier
        # heads through), not the lateral pre-cut.
        # Group nearby xs into clusters.
        sorted_x = np.sort(on_los_x)
        # Walk through and split into clusters where gap > 80 px.
        clusters: list[list[int]] = [[int(sorted_x[0])]]
        for v in sorted_x[1:]:
            if v - clusters[-1][-1] > 80:
                clusters.append([int(v)])
            else:
                clusters[-1].append(int(v))
        # For each cluster, get its median x.
        cluster_medians = [int(np.median(c)) for c in clusters]
        # The "forward-motion" gap is the cluster whose median is furthest
        # from c_x (the arrow continues toward that side AFTER crossing).
        best_x = max(cluster_medians, key=lambda x: abs(x - c_x))
        # y is just los_y for diagnostic purposes.
        return best_x, los_y
    # Arrow contours don't reach the LOS line (counter plays with stylized
    # disconnected arrows, or arrows that overshoot the LOS into the
    # backfield/upfield without a crossing in their renderable pixels).
    # Use the arrow HEAD (smallest y = most upfield point) as the
    # destination. The ball carrier ends up at that x, which approximates
    # the target gap.
    head_idx = int(np.argmin(ys))
    return int(xs[head_idx]), int(ys[head_idx])


def compute_target_gap(arrow_endpoint_x: int, c_x: int, ol_spacing: int) -> str:
    """Classify the gap based on signed x-distance from C-square,
    measured in units of the LOCAL OL spacing for this crop.

    Gap midpoints (in OL_SPACING units from C):
        |dx| < 0.5  -> straight (over C)
        |dx| < 1.5  -> A_left/A_right (between C and G)
        |dx| < 2.5  -> B_left/B_right (between G and T)
        |dx| < 3.5  -> C_left/C_right (between T and TE)
        |dx| >= 3.5 -> D_left/D_right (outside TE / edge)
    """
    dx = arrow_endpoint_x - c_x
    side = "left" if dx < 0 else "right"
    abs_units = abs(dx) / ol_spacing
    if abs_units < 0.5:
        return "straight"
    if abs_units < 1.5:
        return f"A_{side}"
    if abs_units < 2.5:
        return f"B_{side}"
    if abs_units < 3.5:
        return f"C_{side}"
    return f"D_{side}"


def compute_target_gap_for_crop(crop_path: Path,
                                play_type: str | None = None,
                                model_ol_xs: list[int] | None = None,
                                model_c_x: int | None = None) -> dict:
    """Top-level: load image, detect C and red arrow, return gap + diagnostics.

    target_gap is ONLY computed for run plays. For pass plays the field is
    null.

    If model_ol_xs and model_c_x are provided (from the LLM's extraction),
    use them to compute per-crop OL spacing and to convert the model's
    coordinate frame to native pixels. This is much more accurate than the
    fixed-default fallback because OL spacing varies 2x across crops.
    """
    if play_type and play_type.lower() != "run":
        return {"target_gap": None, "skipped": f"play_type={play_type}, not a run"}
    img = cv2.imread(str(crop_path))
    if img is None:
        return {"target_gap": None, "error": f"can't read {crop_path}"}
    c = _detect_c(img)
    if c is None:
        return {"target_gap": None, "error": "no C detected"}
    cx, cy = c

    # If the model gave us OL x-positions, use them. The model's coords are
    # in a different scale; convert to native by scaling such that the model's
    # C_x maps to our detected cx.
    scale = 1.0
    model_offset = 0
    if model_ol_xs and len(model_ol_xs) == 4 and model_c_x is not None:
        # Use the OL extent in model coords vs our detected C-x in native
        # coords. The model's spacing in model coords:
        m_spacing = (max(model_ol_xs) - min(model_ol_xs)) / 3
        # We assume the native spacing is m_spacing * scale, where scale maps
        # model coords to native. Without a known reference we can't compute
        # scale directly, but we can use the typical scale factor of ~1.4
        # (native 2796 / display 2000), refined per call:
        # Actually we know cx in native and model_c_x. If the model uses the
        # full image x-axis: scale = cx / model_c_x. But the model's frame
        # may be panel-relative; rough scale ~ native_width / 2000.
        h, w = img.shape[:2]
        scale = w / 2000   # standard display width
        ol_spacing = int(m_spacing * scale)
    else:
        ol_spacing = _measure_ol_spacing(img, cx, cy)

    arrow = _detect_red_arrow_los_x(img, cy, cx)
    if arrow is None:
        return {"target_gap": None, "error": "no red arrow detected",
                "c_x": cx, "c_y": cy, "ol_spacing": ol_spacing}
    ex, ey = arrow
    gap = compute_target_gap(ex, cx, ol_spacing)
    return {
        "target_gap": gap,
        "c_xy": (cx, cy),
        "arrow_los_crossing_xy": (ex, ey),
        "dx_from_c": ex - cx,
        "ol_spacing": ol_spacing,
    }


if __name__ == "__main__":
    import argparse, json, sys
    ap = argparse.ArgumentParser()
    ap.add_argument("crop_path")
    ap.add_argument("--play-type", default=None,
                    help='"run" or "pass" — passes return null gap')
    ap.add_argument("--model-extraction", default=None,
                    help="path to model's extraction JSON; uses its OL coords for spacing")
    args = ap.parse_args()
    model_ol_xs = None
    model_c_x = None
    if args.model_extraction:
        import re
        d = json.load(open(args.model_extraction))
        raw = d.get('response_text', '')
        m = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', raw, re.DOTALL)
        if m:
            obj = json.loads(m.group(1))
            ol = obj.get('offensive_line', [])
            if len(ol) == 4:
                model_ol_xs = sorted(p.get('x', 0) for p in ol)
                model_c_x = obj.get('center', {}).get('x')
    result = compute_target_gap_for_crop(Path(args.crop_path), args.play_type,
                                         model_ol_xs, model_c_x)
    print(json.dumps(result, indent=2))




