#!/usr/bin/env python3
"""Test route_geometry.py on plays with known route shapes.

Runs the full pipeline (clean_crop → isolate_routes → trace_route →
classify_route) on plays whose names tell us what routes to expect, and
prints the per-route classification + a debug image. The validation
target: correctly identify isolated routes like curls and in/dig routes.
"""
from __future__ import annotations
import sys
from pathlib import Path

import cv2
import numpy as np

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "tools/playbook-vision-pilot"))
from route_geometry import (clean_crop, isolate_routes, trace_route,  # noqa
                            classify_route, _simplify)
from target_gap_python import _detect_c  # noqa: E402

# (label, team, img, panel, expected route-family present)
TEST_PLAYS = [
    ("Zona Curls",   "Arizona Cardinals", 15, 0, "curl"),
    ("Zona Dbl Curls", "Arizona Cardinals", 33, 2, "curl"),
    ("Inside Dig",   "Arizona Cardinals", 96, 0, "in"),
    ("WR Deep In",   "Arizona Cardinals", 90, 2, "in"),
    ("Deep X Dig",   "Arizona Cardinals", 138, 1, "in"),
]


def main() -> None:
    for label, team, img_idx, panel, expect in TEST_PLAYS:
        img = clean_crop(team, img_idx, panel)
        cx, cy = _detect_c(img)
        iso = isolate_routes(img)
        print(f"\n=== {label}  (expect: {expect})  C=({cx},{cy}) ===")
        dbg = img.copy()
        cv2.line(dbg, (0, cy), (img.shape[1] - 1, cy), (128, 128, 128), 1)
        found_routes = []
        for color, masks in iso.items():
            for m in masks:
                poly = trace_route(m)
                if poly is None:
                    continue
                cls = classify_route(poly, cy, cx)
                if cls["route"] == "not_a_route":
                    continue
                found_routes.append((color, cls))
                # Draw the traced polyline + label
                pts = np.array(poly, np.int32).reshape(-1, 1, 2)
                cv2.polylines(dbg, [pts], False, (0, 255, 0), 2)
                tip = poly[-1] if abs(poly[0][1] - cy) < abs(poly[-1][1] - cy) else poly[0]
                cv2.putText(dbg, cls["route"], (tip[0], tip[1]),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
                print(f"  [{color}] route={cls['route']:<10} conf={cls.get('confidence')} "
                      f"maxdepth={cls.get('max_depth_px')} cameback={cls.get('came_back_px')} "
                      f"breaks={cls.get('n_breaks')}")
        # Did we find the expected route?
        names = [c["route"] for _, c in found_routes]
        hit = expect in names
        print(f"  --> routes found: {names}")
        print(f"  --> {'PASS' if hit else 'MISS'} (expected '{expect}')")
        cv2.imwrite(f"/tmp/rg_test_{label.replace(' ','_')}.jpg", dbg)


if __name__ == "__main__":
    main()
