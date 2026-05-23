#!/usr/bin/env python3
"""Build red-route-clusters.html v2 — review gallery for the labeling pass.

Reads red_clusters.json (v2: pass-only, with per-member side L/R/C).
For each cluster:
  - render an exemplar (the red route, cropped tight, NO overlay drawn
    on top — your v1 feedback noted the magenta polyline was confusing)
  - call Haiku 4.5 with the route-shape guide + your v1 vocabulary to
    propose a label (single isolated route = the LLM's easy case)
  - show side dominance so post/corner/etc. can be judged
  - cumulative coverage so you can stop reviewing once the top covers
    enough.

Labelling ~200 templates is the whole job; every play's red route then
maps deterministically.
"""
from __future__ import annotations
import base64
import io
import json
import os
import sys
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import anthropic
import cv2
import numpy as np
from dotenv import load_dotenv

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "tools/playbook-vision-pilot"))
from cluster_red_routes import red_route_mask          # noqa: E402

CROPS = REPO / "tools/playbook-vision-pilot/dedup-crops"
CLUSTERS = REPO / "tools/playbook-vision-pilot/red_clusters.json"
OUT = REPO / "tools/playbook-vision-pilot/red-route-clusters.html"

LLM_MODEL = "claude-haiku-4-5-20251001"
LLM_WORKERS = 6

LABEL_PROMPT = """You are looking at one isolated red-arrow route from a
Madden 25 play diagram. The receiver runs from the green LOS line shown
in the image downfield (away from the bottom). The receiver is on the
{side_desc} side of the QB.

Identify the route. Pick exactly ONE name from this list:
streak, fade, seam, slant, quick_slants, drag, shallow_cross, hitch,
curl, comeback, in, dig, out, corner, post, wheel, flat, screen,
hb_texas, double_move, block_release_drag, swing, check_release

Route shapes (the visual signature):
- streak: perfectly straight vertical line, no bend
- fade: near-vertical, angling slightly toward the sideline near the end
- seam: straight, vertical, from an inner/slot receiver
- slant: immediate ~45 degree angle inward, shallow
- quick_slants: like slant but very short and quick
- drag / shallow_cross: shallow, mostly horizontal across the field
- hitch: short stem (~5yd) then stops and arrowhead points back to QB
- curl: medium stem (~10-12yd) then curls back to QB
- comeback: deep stem (~15yd) then breaks back to sideline-and-down
- in / dig: stem downfield, then 90deg break TOWARD THE MIDDLE
- out: stem downfield, then 90deg break TOWARD THE SIDELINE
- post: stem then 45deg break toward middle, continuing deep
- corner: stem then 45deg break toward sideline, continuing deep
- wheel: starts lateral toward sideline then turns and runs UP the sideline
- flat: quick shallow route to the sideline near the LOS
- screen: short, stays near or behind the LOS
- hb_texas: HB releases one way then breaks opposite at an angle
- double_move: a shake-and-go (e.g. slant-and-go, hitch-and-go)
- block_release_drag: blocks first then releases shallow across
- swing: lateral from the backfield toward the sideline behind LOS
- check_release: stays in to block, then releases short as a safety valve

The label depends on side: same shape on LEFT receiver = post (breaks to
middle); same shape on RIGHT receiver = corner. Read the visual + side.

Reply with ONLY the route name, lowercased, no explanation."""


_client = None
_client_lock = threading.Lock()


def _get_client():
    global _client
    with _client_lock:
        if _client is None:
            load_dotenv(REPO / ".env")
            _client = anthropic.Anthropic()
    return _client


def exemplar_image(crop_name: str) -> bytes | None:
    """Render a cluster exemplar: the red route, cropped tight, NO
    overlay. Adds a thin green line at the LOS row so the LLM (and the
    reviewer) has a reference for downfield direction."""
    img = cv2.imread(str(CROPS / crop_name))
    if img is None:
        return None
    mask = red_route_mask(img)
    if mask is None:
        return None
    try:
        from target_gap_python import _detect_c
        c = _detect_c(img)
    except Exception:
        c = None
    cy = c[1] if c is not None else int(img.shape[0] * 0.42)
    ys, xs = np.where(mask)
    M = 120
    x0, x1 = max(0, xs.min() - M), min(img.shape[1], xs.max() + M)
    y0, y1 = max(0, ys.min() - M), min(img.shape[0], ys.max() + M)
    view = img[y0:y1, x0:x1].copy()
    if y0 <= cy < y1:
        cv2.line(view, (0, cy - y0), (view.shape[1] - 1, cy - y0),
                 (90, 220, 90), 1)
    h, w = view.shape[:2]
    scale = min(440 / max(w, 1), 380 / max(h, 1), 2.5)
    view = cv2.resize(view, (int(w * scale), int(h * scale)))
    ok, buf = cv2.imencode(".jpg", view, [cv2.IMWRITE_JPEG_QUALITY, 88])
    return buf.tobytes() if ok else None


def llm_label(jpeg: bytes, side: str) -> str:
    side_desc = {"L": "LEFT", "R": "RIGHT",
                 "C": "CENTER / inner"}.get(side, "unknown")
    prompt = LABEL_PROMPT.format(side_desc=side_desc)
    b64 = base64.standard_b64encode(jpeg).decode()
    try:
        resp = _get_client().messages.create(
            model=LLM_MODEL, max_tokens=24,
            messages=[{"role": "user", "content": [
                {"type": "image", "source": {"type": "base64",
                                             "media_type": "image/jpeg",
                                             "data": b64}},
                {"type": "text", "text": prompt}]}])
        txt = "".join(b.text for b in resp.content if b.type == "text")
        return txt.strip().lower().replace(" ", "_")
    except Exception as exc:        # noqa: BLE001
        return f"err:{type(exc).__name__}"


CSS = """
body{font-family:system-ui,sans-serif;max-width:1500px;margin:0 auto;
padding:18px;background:#1b1b1b;color:#eee}
h1{color:#fff} .sub{color:#999;font-size:14px}
.grid{display:grid;grid-template-columns:repeat(3,1fr);gap:14px;margin-top:14px}
.card{background:#262626;border:1px solid #3a3a3a;border-radius:7px;padding:10px}
.card.done{border-color:#4a7a4a}
.card img{width:100%;border:1px solid #444;border-radius:3px;background:#111}
.hd{font-size:13px;color:#999;margin:6px 0 2px}
.side{color:#7ad;font-weight:bold}
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
  out.push({cluster_id:+c.dataset.id,size:+c.dataset.size,side:c.dataset.side,
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
    print(f"{len(clusters)} pass-play clusters covering {total} routes — "
          f"rendering exemplars + LLM-labelling...")

    # First pass: render exemplar images (sequential, fast).
    exemplars: dict[int, bytes] = {}
    for cl in clusters:
        for m in cl["members"][:5]:
            ex = exemplar_image(m["name"])
            if ex is not None:
                exemplars[cl["id"]] = ex
                break

    # Second pass: LLM-label each cluster's exemplar in parallel.
    labels: dict[int, str] = {}

    def _label_one(cl):
        ex = exemplars.get(cl["id"])
        if ex is None:
            return cl["id"], "uncertain"
        return cl["id"], llm_label(ex, cl["side"])

    with ThreadPoolExecutor(max_workers=LLM_WORKERS) as ex_pool:
        futures = {ex_pool.submit(_label_one, cl): cl for cl in clusters}
        done = 0
        for fut in as_completed(futures):
            cid, lbl = fut.result()
            labels[cid] = lbl
            done += 1
            if done % 25 == 0:
                print(f"  labelled {done}/{len(clusters)}")

    # Render gallery.
    cards = []
    cumulative = 0
    for cl in clusters:
        ex = exemplars.get(cl["id"])
        if ex is None:
            continue
        b64 = base64.standard_b64encode(ex).decode()
        cumulative += cl["size"]
        cov = 100 * cumulative / total
        proposed = labels.get(cl["id"], "uncertain")
        side_counts = cl.get("side_counts", {})
        side_str = ", ".join(f"{s}:{n}" for s, n in
                             sorted(side_counts.items(),
                                    key=lambda kv: -kv[1]))
        cards.append(f'''
<div class="card" data-id="{cl['id']}" data-size="{cl['size']}"
     data-side="{cl['side']}" data-prop="{proposed}">
  <img src="data:image/jpeg;base64,{b64}">
  <div class="hd">cluster {cl['id']} &middot; {cl['size']} plays
    &middot; coverage {cov:.1f}% &middot;
    side <span class="side">{cl['side']}</span> ({side_str})</div>
  <div class="prop">LLM says: <b>{proposed}</b></div>
  <input type="text" placeholder="correct route name (blank = accept LLM)">
</div>''')

    html = f'''<!DOCTYPE html><html><head><meta charset="utf-8">
<title>Red route clusters v2</title><style>{CSS}</style></head><body>
<h1>Red primary-route templates (PASS plays only)</h1>
<div class="sub">{len(cards)} distinct route shapes across {total}
pass plays. The game renders these pixel-identically — label the template
once and every play that uses it maps deterministically.</div>
<div class="topnote">Each card shows ONLY the real red route (no
overlay). The thin green line is the LOS for reference; downfield is up.
Side L/R is which side of the QB the receiver lined up on — important for
post (left + inward break) vs corner (right + inward break) etc.<br>
If "LLM says" matches the shape, leave the input blank. If wrong, type
the correct route name. Sorted by frequency — top cards cover most
plays.</div>
<div class="grid">{"".join(cards)}</div>
<div class="bar"><button onclick="save()">Save &rarr; red_cluster_labels.json</button></div>
<script>{JS}</script></body></html>'''
    OUT.write_text(html)
    print(f"\nwrote {OUT}  ({len(cards)} cards)")


if __name__ == "__main__":
    main()
