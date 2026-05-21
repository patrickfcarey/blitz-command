#!/usr/bin/env python3
"""Pure-Python detection of M25 play-diagram glyphs.

Replaces the bulk of the vision model's work with OpenCV. Detects:

- The C-square (white filled rectangle).
- All white-circle glyphs (OL, TE, WR, backfield) via blob detection.
- Classification by geometry:
    - OL = the 4 white circles closest to C on the LOS row.
    - TE = circles immediately adjacent to OL on the LOS row (no gap).
    - WR = circles on the LOS row separated from cluster by a gap.
    - backfield = circles below the LOS row.
- PS button glyphs (□ purple, △ green, ⊗ blue, ⊙ red) by color thresholds.
- Red arrow (ball-carrier path for runs OR primary route for passes).
- For runs: target_gap (A_left/A_right/B_left/B_right/C_left/C_right/
  D_left/D_right/straight) by intersecting the red-arrow endpoint
  with the OL x-coordinates.

The detector annotates the input crop with:
- Cyan horizontal LOS line.
- Magenta vertical LOS line through C.
- Yellow box around C.
- Numbered labels on every detected glyph.
- Green endpoints showing arrow start/end.

Output (per crop):
- <slug>__detected.jpg  (annotated visualization)
- <slug>__detected.json (structured detection result)

Run:
    .venv/bin/python tools/playbook-vision-pilot/detect_glyphs.py <crop.jpg> [--out DIR]
"""
from __future__ import annotations
import argparse
import json
from dataclasses import asdict, dataclass
from pathlib import Path

import cv2
import numpy as np


# ---------- shape detection ----------

@dataclass
class Glyph:
    x: int
    y: int
    radius: int
    role: str = "UNKNOWN"   # filled in by classifier


@dataclass
class Arrow:
    color: str
    start: tuple[int, int]
    end: tuple[int, int]


@dataclass
class DetectionResult:
    los_y: int
    c_square: tuple[int, int]
    ol_x: list[int]                  # 5 OL x-positions, left-to-right (incl. C)
    glyphs: list[dict]               # all detected glyphs (with role)
    button_glyphs: list[dict]        # colored PS-button glyphs
    arrows: list[dict]               # detected arrows
    target_gap: str | None           # A_left ... D_right or null


# ---------- C-square detection ----------

def detect_c_square(img: np.ndarray) -> tuple[int, int]:
    """Sliding-window scan for the densest patch of near-white pixels in the
    upper-middle region. This is the C-square — a small filled square that
    other OL/TE/WR glyphs (hollow circles + stubs) don't match. Same approach
    that proved reliable in crop_for_dispatch.py.
    """
    h, w = img.shape[:2]
    r, g, b = img[..., 2], img[..., 1], img[..., 0]
    white = ((r > 235) & (g > 235) & (b > 235)).astype(np.uint8)
    # WIDE crops put the LOS row in the upper-middle band; restrict the search
    # vertically to the LOS region (avoid backfield where stubs cluster).
    x0, x1 = int(w * 0.20), int(w * 0.80)
    y0, y1 = int(h * 0.20), int(h * 0.55)
    BOX = 40
    best = (0, 0, 0)
    for y in range(y0, y1 - BOX, 2):
        for x in range(x0, x1 - BOX, 2):
            d = int(white[y:y + BOX, x:x + BOX].sum())
            if d > best[2]:
                best = (x, y, d)
    if best[2] < 500:   # 500 of 1600 pixels = 31% density — generous floor
        raise RuntimeError(f"could not detect C-square (best density={best[2]})")
    return best[0] + BOX // 2, best[1] + BOX // 2


# ---------- circle detection ----------

def detect_white_circles(img: np.ndarray) -> list[Glyph]:
    """Find all near-white circle glyphs (OL/TE/WR/backfield head circles)."""
    h, w = img.shape[:2]
    r, g, b = img[..., 2], img[..., 1], img[..., 0]
    white = ((r > 220) & (g > 220) & (b > 220)).astype(np.uint8) * 255

    contours, _ = cv2.findContours(white, cv2.RETR_EXTERNAL,
                                   cv2.CHAIN_APPROX_SIMPLE)
    glyphs: list[Glyph] = []
    for c in contours:
        area = cv2.contourArea(c)
        if area < 100 or area > 4000:   # too small / too big
            continue
        (cx, cy), radius = cv2.minEnclosingCircle(c)
        radius = int(radius)
        if radius < 10 or radius > 40:
            continue
        # Filter "square-shape" out — circularity = 4πA / P²; circles ~1, squares ~0.78
        perim = cv2.arcLength(c, True)
        if perim == 0:
            continue
        circularity = 4 * np.pi * area / (perim * perim)
        if circularity < 0.65:   # very generous; the body+stub combo lowers this
            continue
        glyphs.append(Glyph(int(cx), int(cy), radius))
    return glyphs


# ---------- colored button glyphs ----------

BUTTON_RANGES = {
    # OpenCV HSV: H in 0..179, S 0..255, V 0..255
    "Square":   ((130, 80, 80), (170, 255, 255)),    # purple/magenta
    "Triangle": ((40, 80, 80),  (85, 255, 255)),     # green
    "Cross":    ((95, 80, 80),  (130, 255, 255)),    # blue
    "Circle":   ((0, 120, 80),  (15, 255, 255)),     # red (low hue)
}


def detect_buttons(img: np.ndarray) -> list[dict]:
    """Detect PS-button-colored glyphs on the panel."""
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    results = []
    for name, (lo, hi) in BUTTON_RANGES.items():
        mask = cv2.inRange(hsv, np.array(lo), np.array(hi))
        # Special: red wraps around 0; also catch the high-hue red.
        if name == "Circle":
            mask2 = cv2.inRange(hsv, np.array((170, 120, 80)),
                                np.array((180, 255, 255)))
            mask = cv2.bitwise_or(mask, mask2)
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL,
                                       cv2.CHAIN_APPROX_SIMPLE)
        for c in contours:
            area = cv2.contourArea(c)
            if area < 200 or area > 3000:
                continue
            x, y, cw, ch = cv2.boundingRect(c)
            results.append({
                "button": name,
                "x": x + cw // 2,
                "y": y + ch // 2,
                "area": int(area),
            })
    return results


# ---------- red arrow ----------

def detect_red_arrow(img: np.ndarray) -> dict | None:
    """Find the red ball-carrier / primary route arrow.
    Returns the endpoints of the largest red blob's bounding box, sorted
    so 'start' is the y closer to LOS-y if known, 'end' is the other.
    Caller may swap based on play_type.
    """
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    # Red wraps around hue 0; combine two ranges.
    m1 = cv2.inRange(hsv, np.array((0, 110, 80)), np.array((10, 255, 255)))
    m2 = cv2.inRange(hsv, np.array((170, 110, 80)), np.array((180, 255, 255)))
    mask = cv2.bitwise_or(m1, m2)

    # Filter out the "RUN" / "PASS" label text in the corner — it's red but
    # we can mask the bottom 20% of the image since arrows are above that.
    h = img.shape[0]
    mask[int(h * 0.80):, :] = 0

    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL,
                                   cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return None
    # Take the largest contour by area (the arrow).
    c = max(contours, key=cv2.contourArea)
    if cv2.contourArea(c) < 80:
        return None
    # Use min/max y points of the contour to find vertical extent.
    pts = c.reshape(-1, 2)
    ymin_idx = np.argmin(pts[:, 1])
    ymax_idx = np.argmax(pts[:, 1])
    top = tuple(int(v) for v in pts[ymin_idx])
    bottom = tuple(int(v) for v in pts[ymax_idx])
    return {"color": "red", "top": top, "bottom": bottom}


# ---------- classification ----------

def classify_glyphs(glyphs: list[Glyph], c_xy: tuple[int, int],
                    los_band: int = 35) -> tuple[list[int], list[Glyph]]:
    """Identify which glyphs are OL/TE/WR (LOS row) vs backfield.

    Returns:
        ol_x: list of 5 OL x-positions sorted left-to-right (LT, LG, C, RG, RT)
        glyphs: input list with .role updated.
    """
    cx, cy = c_xy
    # LOS-row glyphs: y close to cy.
    on_los = [g for g in glyphs if abs(g.y - cy) <= los_band]
    backfield = [g for g in glyphs if g.y > cy + los_band]
    on_los.sort(key=lambda g: g.x)

    if not on_los:
        return [cx], glyphs

    # Find the 4 OL closest to C (by absolute x distance), then sort with C.
    by_dist = sorted(on_los, key=lambda g: abs(g.x - cx))[:4]
    ol_glyphs_xs = sorted([g.x for g in by_dist] + [cx])

    ol_xs_set = set(ol_glyphs_xs)
    # Tag roles.
    # Find OL boundaries (leftmost and rightmost OL x).
    ol_left = ol_glyphs_xs[0]
    ol_right = ol_glyphs_xs[-1]
    # Sort all LOS-row glyphs left-to-right; iterate to identify TE/WR by gaps.
    sorted_los = sorted(on_los, key=lambda g: g.x)
    # Add a virtual C glyph if not already in sorted_los (the C is a square, not
    # detected by white-circle detector).
    for g in sorted_los:
        if g.x in ol_xs_set:
            g.role = "OL"   # one of LT/LG/RG/RT (refined below)

    # Refine: of the 4 OL flanking C, name them by left-to-right order.
    ol_cands = sorted([g for g in sorted_los if g.role == "OL"],
                      key=lambda g: g.x)
    role_seq = ["LT", "LG", "RG", "RT"]
    # If we found fewer/more than 4 around C, just label by order.
    for i, g in enumerate(ol_cands[:4]):
        g.role = role_seq[i] if i < len(role_seq) else f"OL_{i}"

    # Identify TEs and WRs: any LOS-row glyph not labeled OL,
    # check gap to the nearest OL.
    GAP_THRESHOLD = 80  # px; less than this = attached = TE; more = WR
    for g in sorted_los:
        if g.role == "OL" or g.role in role_seq:
            continue
        if g.x < ol_left:
            dist = ol_left - g.x
            g.role = "TE_L" if dist < GAP_THRESHOLD else "WR_X"
        else:
            dist = g.x - ol_right
            g.role = "TE_R" if dist < GAP_THRESHOLD else "WR_Z"

    # Backfield labeling — stacked column behind C vs offset.
    backfield.sort(key=lambda g: g.y)
    for i, g in enumerate(backfield):
        g.role = f"BACK_{i}"   # caller can refine via formation context

    return ol_glyphs_xs, glyphs


# ---------- target gap ----------

def compute_target_gap(arrow: dict | None, ol_x: list[int],
                       c_x: int, los_y: int) -> str | None:
    """Given the red-arrow endpoints + OL x-positions, classify target gap.
    For a run, the relevant point is the END of the arrow (where the ball
    carrier is going) — typically the y MINIMUM (further upfield = lower y).
    """
    if not arrow or len(ol_x) < 5:
        return None
    top = arrow["top"]    # (x, y) — usually the upfield endpoint
    end_x = top[0]
    # ol_x is sorted left-to-right: [LT, LG, C, RG, RT]
    lt, lg, c, rg, rt = ol_x
    # Define gap midpoints (gap is the space BETWEEN two players).
    gaps = [
        ("D_left", -float("inf"), lt - 30),
        ("C_left", lt - 30, lt + 30),         # outside LT
        # within OL — the named gaps:
        ("B_left", lt + 30, lg + 5),          # between LT and LG = B_left
        ("A_left", lg + 5, c),                # between LG and C = A_left
        ("A_right", c, rg - 5),
        ("B_right", rg - 5, rt - 30),
        ("C_right", rt - 30, rt + 30),
        ("D_right", rt + 30, float("inf")),
    ]
    for name, lo, hi in gaps:
        if lo <= end_x < hi:
            return name
    return "straight"


# ---------- annotation ----------

def annotate(img: np.ndarray, result: DetectionResult) -> np.ndarray:
    out = img.copy()
    h, w = out.shape[:2]
    cx, cy = result.c_square
    # Cyan horizontal LOS line
    cv2.line(out, (0, result.los_y), (w - 1, result.los_y), (255, 255, 0), 2)
    # Magenta vertical line through C
    cv2.line(out, (cx, 0), (cx, h - 1), (255, 0, 255), 2)
    # Yellow box around C
    cv2.rectangle(out, (cx - 22, cy - 22), (cx + 22, cy + 22),
                  (0, 255, 255), 2)
    # Numbered glyph labels
    for i, g in enumerate(result.glyphs):
        x, y = g["x"], g["y"]
        cv2.circle(out, (x, y), 6, (0, 255, 0), 2)
        label = f"{g.get('role', '?')}"
        cv2.putText(out, label, (x - 22, y - 14),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 255, 0), 1,
                    cv2.LINE_AA)
    # Button glyphs
    for b in result.button_glyphs:
        cv2.rectangle(out, (b["x"] - 15, b["y"] - 15),
                      (b["x"] + 15, b["y"] + 15), (255, 255, 255), 1)
        cv2.putText(out, b["button"], (b["x"] - 30, b["y"] + 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 255, 255), 1,
                    cv2.LINE_AA)
    # Arrows
    for a in result.arrows:
        cv2.circle(out, tuple(a["top"]), 8, (0, 0, 255), 2)
        cv2.circle(out, tuple(a["bottom"]), 8, (0, 165, 255), 2)
    # Target gap label
    if result.target_gap:
        cv2.putText(out, f"gap: {result.target_gap}", (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2,
                    cv2.LINE_AA)
    return out


# ---------- top-level ----------

def detect(image_path: Path) -> tuple[DetectionResult, np.ndarray]:
    img = cv2.imread(str(image_path))
    if img is None:
        raise RuntimeError(f"can't read {image_path}")
    c_xy = detect_c_square(img)
    los_y = c_xy[1]
    glyphs = detect_white_circles(img)
    ol_x, glyphs = classify_glyphs(glyphs, c_xy)
    buttons = detect_buttons(img)
    arrow = detect_red_arrow(img)
    target_gap = compute_target_gap(arrow, ol_x, c_xy[0], los_y)
    result = DetectionResult(
        los_y=los_y,
        c_square=c_xy,
        ol_x=ol_x,
        glyphs=[asdict(g) for g in glyphs],
        button_glyphs=buttons,
        arrows=[arrow] if arrow else [],
        target_gap=target_gap,
    )
    return result, img


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("crop_path")
    ap.add_argument("--out", default=None,
                    help="output directory (defaults to alongside the crop)")
    args = ap.parse_args()

    crop = Path(args.crop_path)
    out_dir = Path(args.out) if args.out else crop.parent
    out_dir.mkdir(parents=True, exist_ok=True)

    result, img = detect(crop)
    json_out = out_dir / f"{crop.stem}__detected.json"
    img_out = out_dir / f"{crop.stem}__detected.jpg"
    json_out.write_text(json.dumps(asdict(result), indent=2))
    annotated = annotate(img, result)
    cv2.imwrite(str(img_out), annotated, [cv2.IMWRITE_JPEG_QUALITY, 90])
    print(f"wrote {json_out}")
    print(f"wrote {img_out}")
    print()
    print(f"  C-square at:     {result.c_square}")
    print(f"  LOS y:           {result.los_y}")
    print(f"  OL x positions:  {result.ol_x}")
    print(f"  glyphs:          {len(result.glyphs)}")
    for g in result.glyphs:
        print(f"    {g['role']:<8} at ({g['x']:>4}, {g['y']:>4})")
    print(f"  buttons:         {len(result.button_glyphs)}")
    for b in result.button_glyphs:
        print(f"    {b['button']:<10} at ({b['x']:>4}, {b['y']:>4})")
    print(f"  red arrow:       {result.arrows}")
    print(f"  target_gap:      {result.target_gap}")


if __name__ == "__main__":
    main()
