#!/usr/bin/env python3
"""Generate route-check.html — verify route_geometry.py's classification.

Picks a few individual routes, crops tight around each so the route
fills the card, overlays the traced polyline, and states what
route_geometry classified it as. The user marks each correct / wrong.
Saves route_check_results.json.
"""
from __future__ import annotations
import base64
import io
import sys
from pathlib import Path

import cv2
import numpy as np

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "tools/playbook-vision-pilot"))
from route_geometry import (clean_crop, isolate_routes, trace_route,  # noqa
                            classify_route)
from target_gap_python import _detect_c  # noqa: E402

OUT = REPO / "tools/playbook-vision-pilot/route-check.html"

# (label, team, img, panel, which classification to pick for the card)
TARGETS = [
    ("Zona Curls",  "Arizona Cardinals", 15,  0, "curl"),
    ("Inside Dig",  "Arizona Cardinals", 96,  0, "in"),
    ("WR Deep In",  "Arizona Cardinals", 90,  2, "streak"),
]


def _route_card_image(team, img_idx, panel, want) -> tuple[bytes, str] | None:
    """Return (jpeg_bytes, classified_route) for one route on a play —
    cropped tight around the route with the traced polyline overlaid."""
    img = clean_crop(team, img_idx, panel)
    cx, cy = _detect_c(img)
    iso = isolate_routes(img)
    chosen = None
    for color, masks in iso.items():
        for m in masks:
            poly = trace_route(m)
            if poly is None:
                continue
            cls = classify_route(poly, cy, cx)
            if cls["route"] == "not_a_route":
                continue
            if cls["route"] == want and chosen is None:
                chosen = (poly, cls)
    if chosen is None:
        # fall back to any classified route
        for color, masks in iso.items():
            for m in masks:
                poly = trace_route(m)
                if poly is None:
                    continue
                cls = classify_route(poly, cy, cx)
                if cls["route"] != "not_a_route":
                    chosen = (poly, cls)
                    break
            if chosen:
                break
    if chosen is None:
        return None
    poly, cls = chosen

    # Tight crop around the route + margin.
    xs = [p[0] for p in poly]
    ys = [p[1] for p in poly]
    M = 130
    x0, x1 = max(0, min(xs) - M), min(img.shape[1], max(xs) + M)
    y0, y1 = max(0, min(ys) - M), min(img.shape[0], max(ys) + M)
    view = img[y0:y1, x0:x1].copy()
    # Overlay the traced polyline + origin/tip markers.
    shifted = np.array([(x - x0, y - y0) for x, y in poly], np.int32)
    cv2.polylines(view, [shifted.reshape(-1, 1, 2)], False, (255, 0, 255), 4)
    o = poly[0] if abs(poly[0][1] - cy) < abs(poly[-1][1] - cy) else poly[-1]
    t = poly[-1] if o is poly[0] else poly[0]
    cv2.circle(view, (o[0] - x0, o[1] - y0), 16, (0, 255, 0), 3)   # origin
    cv2.circle(view, (t[0] - x0, t[1] - y0), 16, (0, 0, 255), 3)   # tip
    # Scale so the card is a comfortable size.
    h, w = view.shape[:2]
    scale = min(900 / max(w, 1), 620 / max(h, 1), 3.0)
    view = cv2.resize(view, (int(w * scale), int(h * scale)))
    ok, buf = cv2.imencode(".jpg", view, [cv2.IMWRITE_JPEG_QUALITY, 90])
    return buf.tobytes(), cls["route"]


CSS = """
body{font-family:system-ui,-apple-system,sans-serif;max-width:1050px;
margin:0 auto;padding:20px;background:#1b1b1b;color:#eee}
h1{color:#fff}
.card{background:#262626;border:1px solid #3a3a3a;border-radius:8px;
padding:18px;margin-bottom:22px}
.card.done{border-color:#4a7a4a}
.card img{width:100%;border:1px solid #444;border-radius:4px}
.label{font-size:20px;margin:12px 0 6px}
.label b{color:#ffd060}
.legend{color:#999;font-size:13px;margin-bottom:8px}
.vrow{display:flex;gap:22px;align-items:center;margin:10px 0;flex-wrap:wrap}
.vrow label{cursor:pointer;font-size:16px}
input[type=radio]{transform:scale(1.4);margin-right:6px}
textarea{width:100%;box-sizing:border-box;background:#1a1a1a;color:#eee;
border:1px solid #444;border-radius:3px;padding:8px;min-height:46px;
font-family:inherit;margin-top:6px}
button{background:#4a8a4a;color:#fff;border:0;padding:13px 34px;
font-size:16px;border-radius:4px;cursor:pointer}
.bar{position:sticky;bottom:0;background:#1b1b1b;border-top:2px solid #444;
padding:14px;text-align:center;margin-top:18px}
"""

JS = """
function mark(i){
 document.getElementById('c'+i).classList.add('done');
}
function save(){
 const cards=document.querySelectorAll('.card');
 const routes=[];
 cards.forEach((c,i)=>{
  const v=c.querySelector('input[name="v'+i+'"]:checked');
  const corrected=c.querySelector('textarea').value||'';
  routes.push({slug:c.dataset.slug,
   classified_as:c.dataset.cls,
   verdict:v?v.value:'unreviewed',
   correct_route:corrected});
 });
 const blob=new Blob([JSON.stringify({routes:routes},null,2)],
  {type:'application/json'});
 const a=document.createElement('a');
 a.href=URL.createObjectURL(blob);
 a.download='route_check_results.json';a.click();
 alert('Saved route_check_results.json — send it back to Claude.');
}
"""


def main() -> None:
    cards = []
    for i, (label, team, img_idx, panel, want) in enumerate(TARGETS):
        res = _route_card_image(team, img_idx, panel, want)
        if res is None:
            print(f"  skip {label} — no route traced")
            continue
        jpeg, classified = res
        b64 = base64.standard_b64encode(jpeg).decode()
        cards.append(f'''
<div class="card" id="c{i}" data-slug="{label}" data-cls="{classified}">
  <img src="data:image/jpeg;base64,{b64}">
  <div class="legend">Magenta line = the route route_geometry traced.
   Green dot = where it starts (the receiver). Red dot = the arrowhead.</div>
  <div class="label">route_geometry identified this as:
   <b>{classified}</b> &nbsp;<span style="color:#888;font-size:14px">
   ({label})</span></div>
  <div class="vrow">
    <label><input type="radio" name="v{i}" value="correct"
      onchange="mark({i})"> Correct</label>
    <label><input type="radio" name="v{i}" value="wrong"
      onchange="mark({i})"> Wrong</label>
  </div>
  <textarea placeholder="if wrong: what route is it actually?"></textarea>
</div>''')
        print(f"  {label}: traced a route, classified '{classified}'")

    html = f'''<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>Route check</title>
<style>{CSS}</style></head><body>
<h1>Route geometry — spot check</h1>
<p style="color:#999">For each route below: the magenta line is the path
route_geometry traced from the play diagram. Does the label match the
shape you see? Mark Correct or Wrong, then Save.</p>
{"".join(cards)}
<div class="bar"><button onclick="save()">Save &rarr; route_check_results.json</button></div>
<script>{JS}</script>
</body></html>'''
    OUT.write_text(html)
    print(f"\nwrote {OUT}")


if __name__ == "__main__":
    main()
