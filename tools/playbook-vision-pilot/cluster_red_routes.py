#!/usr/bin/env python3
"""Proof-of-concept: do M25 routes collapse to a small template set?

The game RENDERS play diagrams — the same route is drawn pixel-identical
every time. So routes should cluster: extract every play's RED primary
route, normalize out its on-field position, fingerprint it, and count
the distinct shapes. If 7,300 plays collapse to a few hundred clusters,
the deterministic path is: cluster -> label each cluster once -> every
route maps by cluster membership. No per-play hand-labeling.

Uses the existing dedup-crops (cyan/yellow annotations don't touch RED).
"""
from __future__ import annotations
import sys
from pathlib import Path

import cv2
import numpy as np

REPO = Path(__file__).resolve().parents[2]
CROPS = REPO / "tools/playbook-vision-pilot/dedup-crops"

CANVAS = 900          # normalized canvas before downsampling
FP = 40               # fingerprint grid (FP x FP cells)
DILATE = 11           # thicken routes pre-fingerprint to absorb edge jitter
MATCH_TOL = 0.055     # mean per-cell abs diff (0-1) below which = same route
SHIFTS = range(-3, 4)  # small translations tried when matching


def detect_red_route_side(img: np.ndarray, c_xy: tuple[int, int] | None
                          ) -> str:
    """Side (L/R/C) of the receiver running the red route — i.e. which
    side of the QB they lined up on, NOT where the route's centroid
    ended up. The red ⊙ button glyph (when visible) marks the receiver
    exactly; otherwise we fall back to the route's bottommost pixel
    (closest to / below the LOS = origin)."""
    if c_xy is None:
        return "C"
    cx, _ = c_xy
    h, w = img.shape[:2]
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    mask = (cv2.inRange(hsv, np.array((0, 110, 80)), np.array((10, 255, 255)))
            | cv2.inRange(hsv, np.array((170, 110, 80)),
                          np.array((180, 255, 255))))
    m = int(w * 0.045)
    mask[:, :m] = 0
    mask[:, w - m:] = 0
    mask[:int(h * 0.05), :] = 0
    mask[int(h * 0.72):, :] = 0
    n, _lbl, stats, _ = cv2.connectedComponentsWithStats(mask, 8)
    # Look for the red ⊙ button: compact, squarish. Else fall back to the
    # bottommost route component (largest bbox bottom-edge y). Using stats
    # only — np.where(labels==i) on a 4M-px image is far too slow.
    button_x = None
    route_anchor_x = None
    route_bottom_y = -1
    for i in range(1, n):
        a = stats[i, cv2.CC_STAT_AREA]
        if a < 250:
            continue
        bw = stats[i, cv2.CC_STAT_WIDTH]
        bh = stats[i, cv2.CC_STAT_HEIGHT]
        bx = stats[i, cv2.CC_STAT_LEFT]
        by = stats[i, cv2.CC_STAT_TOP]
        span = max(bw, bh)
        aspect = max(bw, bh) / max(min(bw, bh), 1)
        if span <= 95 and aspect < 1.7:
            button_x = bx + bw // 2
        else:
            bottom_y = by + bh - 1
            if bottom_y > route_bottom_y:
                route_bottom_y = bottom_y
                route_anchor_x = bx + bw // 2
    anchor = button_x if button_x is not None else route_anchor_x
    if anchor is None:
        return "C"
    dx = anchor - cx
    return "L" if dx < -50 else "R" if dx > 50 else "C"


def red_route_mask(img: np.ndarray) -> np.ndarray | None:
    """Binary mask of the red route pixels, border + button removed."""
    h, w = img.shape[:2]
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    mask = (cv2.inRange(hsv, np.array((0, 110, 80)), np.array((10, 255, 255)))
            | cv2.inRange(hsv, np.array((170, 110, 80)),
                          np.array((180, 255, 255))))
    m = int(w * 0.045)
    mask[:, :m] = 0
    mask[:, w - m:] = 0
    mask[:int(h * 0.05), :] = 0
    mask[int(h * 0.72):, :] = 0
    # Drop compact button glyphs (the red ⊙); keep elongated route bits.
    n, lbl, stats, _ = cv2.connectedComponentsWithStats(mask, 8)
    out = np.zeros_like(mask)
    for i in range(1, n):
        a = stats[i, cv2.CC_STAT_AREA]
        bw, bh = stats[i, cv2.CC_STAT_WIDTH], stats[i, cv2.CC_STAT_HEIGHT]
        if a < 250:
            continue
        span = max(bw, bh)
        aspect = max(bw, bh) / max(min(bw, bh), 1)
        if span <= 95 and aspect < 1.7:      # compact => button glyph
            continue
        out[lbl == i] = 255
    return out if out.any() else None


def fingerprint(mask: np.ndarray) -> np.ndarray | None:
    """Position-normalized, jitter-tolerant fingerprint of a route mask.

    DILATE the route so 1-2px edge jitter (JPEG / anti-aliasing / HSV
    threshold wobble) is absorbed, translate the centroid to canvas
    centre (receiver alignment doesn't matter), keep scale (route depth
    is meaningful), downsample to an FP x FP grayscale grid in [0,1].
    """
    ys, xs = np.where(mask)
    if len(xs) < 60:
        return None
    cx, cy = int(xs.mean()), int(ys.mean())
    canvas = np.zeros((CANVAS, CANVAS), np.uint8)
    nx = xs - cx + CANVAS // 2
    ny = ys - cy + CANVAS // 2
    keep = (nx >= 0) & (nx < CANVAS) & (ny >= 0) & (ny < CANVAS)
    canvas[ny[keep], nx[keep]] = 255
    k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (DILATE, DILATE))
    canvas = cv2.dilate(canvas, k)
    small = cv2.resize(canvas, (FP, FP), interpolation=cv2.INTER_AREA)
    return small.astype(np.float32) / 255.0


def _distance(a: np.ndarray, b: np.ndarray) -> float:
    """Min mean-abs-difference over small translations — shift-tolerant
    so centroid-normalization jitter doesn't split identical routes."""
    best = 1.0
    for sx in SHIFTS:
        for sy in SHIFTS:
            shifted = np.roll(np.roll(b, sy, axis=0), sx, axis=1)
            d = float(np.abs(a - shifted).mean())
            if d < best:
                best = d
    return best


def main() -> None:
    import json
    sys.path.insert(0, str(REPO / "tools/playbook-vision-pilot"))
    from target_gap_python import _detect_c   # noqa: E402

    # PASS plays only — on RUN plays red is the ball-carrier path, not a
    # route (already captured by target_gap), so it shouldn't be clustered
    # alongside pass primaries (user feedback v1, clusters #4 #23).
    manifest_path = REPO / "tools/playbook-vision-pilot/dedup-crops/_canonical_manifest.json"
    manifest = json.loads(manifest_path.read_text())
    pass_files = {name for name, info in manifest.items()
                  if info.get("play_type") == "pass"}

    limit = int(sys.argv[1]) if len(sys.argv) > 1 else 1500
    crops = [f for f in sorted(CROPS.glob("*.jpg"))
             if f.name in pass_files][:limit]
    print(f"Fingerprinting RED primary routes for {len(crops)} PASS plays...")
    items = []          # list of dicts: name, fp, side ("L"/"R"/"C")
    for i, f in enumerate(crops):
        img = cv2.imread(str(f))
        if img is None:
            continue
        mask = red_route_mask(img)
        if mask is None:
            continue
        fp = fingerprint(mask)
        if fp is None:
            continue
        c = _detect_c(img)
        side = detect_red_route_side(img, c)
        items.append({"name": f.name, "fp": fp, "side": side})
        if (i + 1) % 400 == 0:
            print(f"  {i + 1}/{len(crops)}")

    print(f"\n{len(items)} red routes fingerprinted. Clustering...")
    # each cluster: {"members": [{name, side}, ...], "fp": centroid fingerprint}
    clusters: list[dict] = []
    for it in items:
        placed = False
        for cl in clusters:
            if _distance(cl["fp"], it["fp"]) <= MATCH_TOL:
                cl["members"].append({"name": it["name"], "side": it["side"]})
                placed = True
                break
        if not placed:
            clusters.append({"members": [{"name": it["name"],
                                          "side": it["side"]}],
                             "fp": it["fp"]})

    clusters.sort(key=lambda c: len(c["members"]), reverse=True)
    out_clusters = []
    for i, c in enumerate(clusters):
        sides = [m["side"] for m in c["members"]]
        side_counts = {s: sides.count(s) for s in set(sides)}
        dominant = max(side_counts, key=side_counts.get)
        out_clusters.append({"id": i, "size": len(c["members"]),
                             "side": dominant, "side_counts": side_counts,
                             "members": c["members"]})
    out = {"play_type": "pass", "route_count": len(items),
           "clusters": out_clusters}
    dest = REPO / "tools/playbook-vision-pilot/red_clusters.json"
    dest.write_text(json.dumps(out, indent=1))
    print(f"  wrote {dest}")

    sizes = sorted((len(c["members"]) for c in clusters), reverse=True)
    print(f"\n=== RESULT ===")
    print(f"  routes:   {len(items)}")
    print(f"  clusters: {len(clusters)}")
    print(f"  ratio:    {len(items) / max(len(clusters), 1):.1f} routes per cluster")
    print(f"  top cluster sizes: {sizes[:15]}")
    singletons = sum(1 for s in sizes if s == 1)
    print(f"  singletons: {singletons} ({100*singletons/max(len(clusters),1):.0f}% of clusters)")
    covered = sum(s for s in sizes if s >= 3)
    print(f"  routes in clusters of >=3: {covered} "
          f"({100*covered/max(len(items),1):.0f}%)")


if __name__ == "__main__":
    main()
