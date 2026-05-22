#!/usr/bin/env python3
"""Build red-route-clusters.html — the route-template review gallery.

Reads red_clusters.json (produced by cluster_red_routes.py). For each
cluster — a distinct route shape the game renders identically — it
renders an exemplar image and a proposed route name, sorted by how many
plays use that shape, with a running coverage figure.

The user reviews/labels the templates here. Labelling ~200 templates
(not 7,300 plays) is the whole job: every red route in the dataset then
maps deterministically to a cluster, and the cluster carries the label.
"""
from __future__ import annotations
import base64
import json
import sys
from pathlib import Path

import cv2
import numpy as np

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "tools/playbook-vision-pilot"))
from cluster_red_routes import red_route_mask          # noqa: E402
from route_geometry import classify_route              # noqa: E402
from target_gap_python import _detect_c                # noqa: E402

CROPS = REPO / "tools/playbook-vision-pilot/dedup-crops"
CLUSTERS = REPO / "tools/playbook-vision-pilot/red_clusters.json"
OUT = REPO / "tools/playbook-vision-pilot/red-route-clusters.html"


def _longest_path(mask: np.ndarray) -> list | None:
    """Skeletonize one clean route mask, return its centerline polyline
    (double-BFS longest path). Fine here — a cluster exemplar is a single
    isolated route."""
    from collections import deque
    from skimage.morphology import skeletonize
    skel = skeletonize(mask > 0)
    ys, xs = np.where(skel)
    if len(xs) < 20:
        return None
    pts = set(zip(xs.tolist(), ys.tolist()))

    def bfs(start):
        seen = {start: None}
        q = deque([start])
        last = start
        while q:
            cur = q.popleft()
            last = cur
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    nb = (cur[0] + dx, cur[1] + dy)
                    if nb in pts and nb not in seen:
                        seen[nb] = cur
                        q.append(nb)
        return last, seen

    # largest component
    best: set = set()
    rem = set(pts)
    while rem:
        _, seen = bfs(next(iter(rem)))
        comp = set(seen)
        if len(comp) > len(best):
            best = comp
        rem -= comp
    pts = best
    f1, _ = bfs(next(iter(pts)))
    f2, par = bfs(f1)
    path = []
    n = f2
    while n is not None:
        path.append(n)
        n = par[n]
    return path


def exemplar(crop_name: str) -> tuple[bytes, str] | None:
    """Render a cluster exemplar: the red route cropped tight, plus a
    proposed route-name from classify_route."""
    img = cv2.imread(str(CROPS / crop_name))
    if img is None:
        return None
    mask = red_route_mask(img)
    if mask is None:
        return None
    c = _detect_c(img)
    cx, cy = c if c is not None else (img.shape[1] // 2,
                                      int(img.shape[0] * 0.42))
    poly = _longest_path(mask)
    label = "uncertain"
    if poly:
        cls = classify_route(poly, cy, cx)
        label = cls.get("route", "uncertain")
    ys, xs = np.where(mask)
    M = 110
    x0, x1 = max(0, xs.min() - M), min(img.shape[1], xs.max() + M)
    y0, y1 = max(0, ys.min() - M), min(img.shape[0], ys.max() + M)
    view = img[y0:y1, x0:x1].copy()
    if poly:
        sh = np.array([(x - x0, y - y0) for x, y in poly], np.int32)
        cv2.polylines(view, [sh.reshape(-1, 1, 2)], False, (255, 0, 255), 3)
    h, w = view.shape[:2]
    scale = min(420 / max(w, 1), 360 / max(h, 1), 2.5)
    view = cv2.resize(view, (int(w * scale), int(h * scale)))
    ok, buf = cv2.imencode(".jpg", view, [cv2.IMWRITE_JPEG_QUALITY, 86])
    return buf.tobytes(), label


CSS = """
body{font-family:system-ui,sans-serif;max-width:1500px;margin:0 auto;
padding:18px;background:#1b1b1b;color:#eee}
h1{color:#fff} .sub{color:#999;font-size:14px}
.grid{display:grid;grid-template-columns:repeat(3,1fr);gap:14px;margin-top:14px}
.card{background:#262626;border:1px solid #3a3a3a;border-radius:7px;padding:10px}
.card.done{border-color:#4a7a4a}
.card img{width:100%;border:1px solid #444;border-radius:3px;background:#111}
.hd{font-size:13px;color:#999;margin:6px 0 2px}
.prop{font-size:16px;margin:4px 0}
.prop b{color:#ffd060}
input[type=text]{width:100%;box-sizing:border-box;background:#1a1a1a;color:#eee;
border:1px solid #444;border-radius:3px;padding:6px;margin-top:5px}
.bar{position:sticky;bottom:0;background:#1b1b1b;border-top:2px solid #444;
padding:12px;text-align:center;margin-top:16px}
button{background:#4a8a4a;color:#fff;border:0;padding:12px 30px;font-size:15px;
border-radius:4px;cursor:pointer}
.topnote{background:#222;border-left:3px solid #4a8a4a;padding:10px 14px;
font-size:14px;margin:12px 0}
"""

JS = """
function save(){
 const cards=document.querySelectorAll('.card');
 const out=[];
 cards.forEach(c=>{
  out.push({cluster_id:+c.dataset.id,size:+c.dataset.size,
   proposed:c.dataset.prop,
   label:(c.querySelector('input').value||'').trim()||c.dataset.prop});
 });
 const b=new Blob([JSON.stringify({clusters:out},null,1)],
  {type:'application/json'});
 const a=document.createElement('a');
 a.href=URL.createObjectURL(b);a.download='red_cluster_labels.json';a.click();
 alert('Saved red_cluster_labels.json — send it back to Claude.');
}
"""


def main() -> None:
    data = json.loads(CLUSTERS.read_text())
    clusters = data["clusters"]
    total = data["route_count"]
    print(f"{len(clusters)} clusters, {total} routes — rendering exemplars...")

    cards = []
    cumulative = 0
    for cl in clusters:
        ex = None
        for member in cl["members"][:5]:        # try a few in case one fails
            ex = exemplar(member)
            if ex:
                break
        if ex is None:
            continue
        jpeg, proposed = ex
        b64 = base64.standard_b64encode(jpeg).decode()
        cumulative += cl["size"]
        cov = 100 * cumulative / total
        cards.append(f'''
<div class="card" data-id="{cl['id']}" data-size="{cl['size']}"
     data-prop="{proposed}">
  <img src="data:image/jpeg;base64,{b64}">
  <div class="hd">cluster {cl['id']} &middot; {cl['size']} plays
    &middot; running coverage {cov:.1f}%</div>
  <div class="prop">proposed: <b>{proposed}</b></div>
  <input type="text" placeholder="correct route name (blank = accept proposed)">
</div>''')

    html = f'''<!DOCTYPE html><html><head><meta charset="utf-8">
<title>Red route clusters</title><style>{CSS}</style></head><body>
<h1>Red primary-route templates</h1>
<div class="sub">{len(cards)} distinct route shapes across {total}
plays. Game-rendered, so each shape is pixel-identical wherever it
appears — label the template once and every play that uses it is mapped.
Sorted by frequency; the magenta line is the traced centerline.</div>
<div class="topnote">Review top-down — the first ~40-60 clusters already
cover most plays. For each: if "proposed" matches the shape, leave the
box blank; if not, type the correct route name.</div>
<div class="grid">{"".join(cards)}</div>
<div class="bar"><button onclick="save()">Save &rarr; red_cluster_labels.json</button></div>
<script>{JS}</script></body></html>'''
    OUT.write_text(html)
    print(f"wrote {OUT}  ({len(cards)} cards)")


if __name__ == "__main__":
    main()
