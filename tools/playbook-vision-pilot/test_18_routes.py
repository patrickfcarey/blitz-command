#!/usr/bin/env python3
"""Re-extract the 18 hand-reviewed plays with the route-shape-teaching
prompt at FULL resolution, and print results next to the user's notes.

This is the validation gate before committing to a full re-run: if the
route-shape prompt + full-res visibly improves the route calls, the
cheap fix worked. If not, we know the hard Python-geometry build is
needed.

No Python route-geometry yet — this isolates the effect of the prompt
rewrite + resolution. Annotations recolored to gray so they neither
pollute nor get mistaken for routes.
"""
from __future__ import annotations
import base64
import io
import json
import re
import sys
import zipfile
from pathlib import Path

import anthropic
import numpy as np
from dotenv import load_dotenv
from PIL import Image, ImageDraw

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "tools/ingest-research"))
sys.path.insert(0, str(REPO / "tools/playbook-vision-pilot"))
from extract_docx_images import ordered_image_entries  # noqa: E402
from target_gap_python import compute_target_gap_for_crop, _detect_c  # noqa: E402
from play_concepts import classify as classify_play  # noqa: E402

PROMPT = REPO / "tools/playbook-vision-pilot/subagent-prompt.md"
MANIFEST = REPO / "tools/playbook-vision-pilot/dedup-crops/_canonical_manifest.json"
PLAYBOOKS = REPO / "research_artifacts/PS3/Madden NFL 25 (2013)/Playbooks"
TRUTH = Path("/mnt/c/Users/root/Downloads/hand_review_results.json")
OUT_DIR = Path("/tmp/pilot-work/route-test-18")
MODEL = "claude-haiku-4-5-20251001"
PLAY_AREA_LEFT, PLAY_AREA_RIGHT = 420, 1820


def _crop_fullres_gray(team: str, img_idx: int, panel: int) -> Image.Image:
    """Full-res wide LOS-zoom crop with GRAY annotations (non-route color)."""
    docx = PLAYBOOKS / f"{team}.docx"
    entries = ordered_image_entries(docx)
    with zipfile.ZipFile(docx) as z, z.open(entries[img_idx - 1]) as src:
        raw = src.read()
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
    # Detect C, draw GRAY annotations (128,128,128 — not red/yellow/cyan).
    arr = np.array(wide)
    r, g, b = arr[..., 0], arr[..., 1], arr[..., 2]
    white = (r > 235) & (g > 235) & (b > 235)
    hh, ww, _ = arr.shape
    BOX = 40
    best = (0, 0, 0)
    for y in range(int(hh * 0.20), int(hh * 0.55) - BOX, 2):
        for x in range(int(ww * 0.25), int(ww * 0.75) - BOX, 2):
            d = int(white[y:y + BOX, x:x + BOX].sum())
            if d > best[2]:
                best = (x, y, d)
    cx, cy = best[0] + BOX // 2, best[1] + BOX // 2
    draw = ImageDraw.Draw(wide)
    draw.line([(0, cy), (wide.size[0] - 1, cy)], fill=(128, 128, 128), width=2)
    draw.rectangle([(cx - 20, cy - 20), (cx + 20, cy + 20)],
                   outline=(160, 160, 160), width=2)
    return wide


def _load_rules() -> str:
    text = PROMPT.read_text()
    start = text.index("## SYSTEM PROMPT")
    start = text.index("\n", start) + 1
    end = text.index("## USER MESSAGE template")
    return text[start:end].strip()


def main() -> None:
    load_dotenv(REPO / ".env")
    client = anthropic.Anthropic()
    rules = _load_rules()
    manifest = json.loads(MANIFEST.read_text())
    truth = json.loads(TRUTH.read_text())
    reviewed = [p for p in truth["plays"] if p["verdict"] != "unreviewed"]
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    print(f"Re-extracting {len(reviewed)} hand-reviewed plays "
          f"(full-res, route-shape prompt)\n")

    for tp in reviewed:
        slug = tp["slug"]
        fname = f"{slug}.jpg"
        info = manifest.get(fname)
        if not info:
            print(f"  ?? {slug} — not in manifest")
            continue
        crop = _crop_fullres_gray(info["canonical_team"],
                                  info["canonical_img"],
                                  info["canonical_panel"])
        buf = io.BytesIO()
        crop.save(buf, "JPEG", quality=90)
        crop_path = OUT_DIR / fname
        crop.save(crop_path, "JPEG", quality=90)
        img_b64 = base64.standard_b64encode(buf.getvalue()).decode()

        py = compute_target_gap_for_crop(crop_path, info["play_type"])
        concept = classify_play(info["play_name"], info["play_type"])
        cl = (f"py_concept: {concept['concept']} (family={concept['concept_family']})\n"
              if concept["concept"] != "unknown" else "")
        bh = ("This is a standard run — blockers implicit; empty routes ok.\n"
              if concept.get("blockers_implicit") else "")
        context = (f"play_id: {slug}\n"
                   f"formation: {info['family']} {info['formation']}\n"
                   f"play_name: {info['play_name']}\n"
                   f"play_type: {info['play_type']}\n"
                   f"py_target_gap: {py.get('target_gap')}\n{cl}\n"
                   "Filename encodes personnel as r#f#t#w#. Classify each "
                   "route by its SHAPE per the route-shape guide. Do NOT "
                   "default to streak. Emit only the JSON object.\n" + bh)
        resp = client.messages.create(
            model=MODEL, max_tokens=2048,
            system=[{"type": "text", "text": rules,
                     "cache_control": {"type": "ephemeral"}}],
            messages=[{"role": "user", "content": [
                {"type": "image",
                 "source": {"type": "base64", "media_type": "image/jpeg",
                            "data": img_b64}},
                {"type": "text", "text": context}]}])
        out = "".join(b.text for b in resp.content if b.type == "text")
        m = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", out, re.DOTALL)
        obj = json.loads(m.group(1)) if m else {}
        (OUT_DIR / f"{slug}.json").write_text(json.dumps(obj, indent=2))

        routes = obj.get("routes")
        print(f"  {slug}")
        print(f"    verdict was: {tp['verdict']}  wrong: {tp.get('wrong_fields')}")
        if tp.get("notes"):
            print(f"    your note: {tp['notes'][:160]}")
        print(f"    NEW routes: {routes}")
        print(f"    NEW concept={obj.get('concept')}  bc={obj.get('ball_carrier')}  "
              f"pt={obj.get('primary_target')}")
        print()


if __name__ == "__main__":
    main()
