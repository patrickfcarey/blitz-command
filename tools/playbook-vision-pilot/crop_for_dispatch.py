#!/usr/bin/env python3
"""Crop a play panel at wide LOS-zoom (7.5x) with C-anchored cyan line,
output as JPEG q=85 with a verbose filename that encodes play context.

Verbose filename format (subagent reads this from the file path):
  <formation-slug>__<play-type>__<play-slug>__<team-slug>__img<NN>p<P>__WIDE.jpg

Usage:
    python3 crop_for_dispatch.py <team> <img_idx> <panel> <formation_slug> \
                                 <play_type> <play_name>

Example:
    python3 crop_for_dispatch.py "Baltimore Ravens" 45 1 iform-pro run "HB Blast"
"""
from __future__ import annotations
import io
import re
import sys
import zipfile
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "tools/ingest-research"))
from extract_docx_images import ordered_image_entries  # noqa: E402

PLAYBOOKS = REPO / "research_artifacts/PS3/Madden NFL 25 (2013)/Playbooks"
OUT_DIR = REPO / "tools/playbook-vision-pilot/dispatch-crops"
PLAY_AREA_LEFT, PLAY_AREA_RIGHT = 420, 1820


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def _crop_panel(raw: bytes, panel: int) -> Image.Image:
    img = Image.open(io.BytesIO(raw)).convert("RGB")
    pw = (PLAY_AREA_RIGHT - PLAY_AREA_LEFT) / 3
    L = int(round(PLAY_AREA_LEFT + panel * pw))
    R = int(round(PLAY_AREA_LEFT + (panel + 1) * pw))
    return img.crop((L, 0, R, img.size[1]))


def _wide_zoom(panel_img: Image.Image) -> Image.Image:
    w, h = panel_img.size
    up3 = panel_img.resize((w * 3, h * 3), Image.LANCZOS)
    w2, h2 = up3.size
    band = up3.crop((0, int(h2 * 0.30), w2, int(h2 * 0.95)))
    bw, bh = band.size
    return band.resize((bw * 2, bh * 2), Image.LANCZOS)


def _detect_c(img: Image.Image) -> tuple[int, int]:
    arr = np.array(img)
    h, w, _ = arr.shape
    r, g, b = arr[..., 0], arr[..., 1], arr[..., 2]
    white = (r > 235) & (g > 235) & (b > 235)
    x0, x1 = int(w * 0.25), int(w * 0.75)
    y0, y1 = int(h * 0.05), int(h * 0.50)
    BOX = 40
    best = (0, 0, 0)
    for y in range(y0, y1 - BOX, 2):
        for x in range(x0, x1 - BOX, 2):
            d = int(white[y:y + BOX, x:x + BOX].sum())
            if d > best[2]:
                best = (x, y, d)
    return best[0] + BOX // 2, best[1] + BOX // 2


def _mark_los(img: Image.Image) -> Image.Image:
    cx, cy = _detect_c(img)
    out = img.copy()
    draw = ImageDraw.Draw(out)
    draw.line([(0, cy), (img.size[0] - 1, cy)], fill=(0, 255, 255), width=2)
    draw.rectangle([(cx - 20, cy - 20), (cx + 20, cy + 20)],
                   outline=(255, 255, 0), width=2)
    return out


def crop(team: str, img_idx: int, panel: int, formation_slug: str,
         play_type: str, play_name: str, *, quality: int = 85) -> Path:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    docx = PLAYBOOKS / f"{team}.docx"
    entries = ordered_image_entries(docx)
    with zipfile.ZipFile(docx) as z, z.open(entries[img_idx - 1]) as src:
        raw = src.read()
    panel_img = _crop_panel(raw, panel)
    zoomed = _wide_zoom(panel_img)
    marked = _mark_los(zoomed)
    name = (f"{_slug(formation_slug)}__{_slug(play_type)}__{_slug(play_name)}"
            f"__{_slug(team)}__img{img_idx:02d}p{panel}__WIDE.jpg")
    out = OUT_DIR / name
    marked.save(out, "JPEG", quality=quality, optimize=True)
    return out


def main() -> None:
    if len(sys.argv) != 7:
        print(__doc__)
        sys.exit(2)
    team, img_idx, panel, formation_slug, play_type, play_name = sys.argv[1:]
    out = crop(team, int(img_idx), int(panel), formation_slug,
               play_type, play_name)
    print(f"wrote {out} ({out.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main()
