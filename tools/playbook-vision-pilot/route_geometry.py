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
    # Kill the bottom play-name banner. The "RUN"/"PASS" label + the
    # play-name text + the PS-button icon sit in the bottom band; the
    # label specifically reaches up into the bottom-LEFT quadrant.
    mask[int(h * 0.80):, :] = 0
    mask[int(h * 0.62):, :int(w * 0.42)] = 0   # bottom-left RUN/PASS text
    return mask


def _is_button_glyph(contour) -> bool:
    """A PS-button receiver glyph is a COMPACT, fairly-filled blob
    (~40-70px square, fill density > 0.45). A route is a thin line
    (low fill density). True = drop it as a button, not a route.
    """
    area = cv2.contourArea(contour)
    x, y, w, h = cv2.boundingRect(contour)
    if w == 0 or h == 0:
        return False
    bbox_area = w * h
    density = area / bbox_area
    span = max(w, h)
    aspect = max(w, h) / min(w, h)
    # Compact + squarish + reasonably filled → button glyph.
    return (25 <= span <= 80 and aspect < 1.8 and density > 0.45)


def isolate_routes(img: np.ndarray) -> dict:
    """Return per-color route masks with buttons + border removed.

    Output: {color: {"mask": ndarray, "contours": [contour, ...]}}
    Each contour is a candidate route (may still be 2+ fused routes —
    that's the tracing step's problem, task #32).
    """
    out = {}
    for color in ROUTE_COLORS:
        mask = _color_mask(img, color)
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL,
                                       cv2.CHAIN_APPROX_SIMPLE)
        route_contours = []
        clean = np.zeros_like(mask)
        for c in contours:
            if cv2.contourArea(c) < 200:
                continue
            if _is_button_glyph(c):
                continue
            route_contours.append(c)
            cv2.drawContours(clean, [c], -1, 255, -1)
        out[color] = {"mask": clean, "contours": route_contours}
    return out


def annotate_debug(img: np.ndarray, isolated: dict) -> np.ndarray:
    """Draw the isolated route contours over the crop for visual QA."""
    out = img.copy()
    colors = {"red": (0, 0, 255), "yellow": (0, 255, 255),
              "green": (0, 255, 0), "cyan": (255, 200, 0),
              "blue": (255, 0, 0)}
    for color, data in isolated.items():
        for c in data["contours"]:
            cv2.drawContours(out, [c], -1, colors[color], 2)
            x, y, w, h = cv2.boundingRect(c)
            cv2.putText(out, color[:1].upper(), (x, y - 4),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, colors[color], 1)
    return out


if __name__ == "__main__":
    import json
    if len(sys.argv) >= 4:
        team, img_idx, panel = sys.argv[1], int(sys.argv[2]), int(sys.argv[3])
        img = clean_crop(team, img_idx, panel)
        iso = isolate_routes(img)
        for color, d in iso.items():
            print(f"{color}: {len(d['contours'])} route contour(s)")
        dbg = annotate_debug(img, iso)
        cv2.imwrite("/tmp/route_geom_debug.jpg", dbg)
        print("wrote /tmp/route_geom_debug.jpg")
    else:
        print("usage: route_geometry.py <team> <img_idx> <panel>")
