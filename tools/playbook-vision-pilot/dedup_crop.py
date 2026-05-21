#!/usr/bin/env python3
"""De-duplicate Madden 25 play diagrams.

Walks every team's docx-cache to build a unique-play index keyed by
(family, formation, play_name). For each unique combo, picks a canonical
(team, img, panel) and crops it once. Outputs:

    tools/playbook-vision-pilot/dedup-crops/<family>__<formation>__<play-type>__<play-name>.jpg
    tools/playbook-vision-pilot/dedup-crops/_canonical_manifest.json

The manifest maps each unique play to its source (canonical team) AND the
list of all teams whose playbooks include the play, so a single extraction
can later be replicated across all owning teams.

Spot-check confirmed (3-team comparison): the play diagram is identical
across teams for the same (family, formation, play_name) — only the field
background tint differs. Dedup is safe for extraction.
"""
from __future__ import annotations
import io
import json
import re
import sys
import zipfile
from collections import defaultdict
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "tools/ingest-research"))
from extract_docx_images import ordered_image_entries  # noqa: E402

CACHE = REPO / ".docx-cache-m25-plays"
PLAYBOOKS = REPO / "research_artifacts/PS3/Madden NFL 25 (2013)/Playbooks"
OUT = REPO / "tools/playbook-vision-pilot/dedup-crops"
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
    arr = np.array(img); h, w, _ = arr.shape
    r, g, b = arr[..., 0], arr[..., 1], arr[..., 2]
    white = (r > 235) & (g > 235) & (b > 235)
    x0, x1 = int(w * 0.25), int(w * 0.75)
    y0, y1 = int(h * 0.05), int(h * 0.50)
    BOX = 40; best = (0, 0, 0)
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


def _build_index() -> tuple[dict, dict]:
    """Returns:
        canonical: {(family, formation, play_name, type):
                     (team_part, img, panel)}  -- pick first occurrence
        owners:    {(family, formation, play_name, type): [team_part, ...]}
    """
    canonical: dict[tuple, tuple] = {}
    owners: dict[tuple, list[str]] = defaultdict(list)
    for cache_file in sorted(CACHE.glob("*__chunk*.json")):
        team_part = cache_file.stem.split("__")[0]
        current = None
        for entry in json.loads(cache_file.read_text()):
            kind = entry.get("kind")
            if kind == "formation_list":
                current = (entry.get("family"), entry.get("highlighted"))
            elif kind == "play_screen" and current:
                family, formation = current
                for pi, p in enumerate(entry.get("plays", [])):
                    name = (p.get("name") or "").strip()
                    if not name:
                        continue
                    ptype = p.get("type") or "unknown"
                    key = (family, formation, name, ptype)
                    if key not in canonical:
                        canonical[key] = (team_part, entry["img"], pi)
                    owners[key].append(team_part)
    return canonical, owners


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    print("indexing playbooks...")
    canonical, owners = _build_index()
    n_unique = len(canonical)
    n_total = sum(len(v) for v in owners.values())
    print(f"  total entries: {n_total:,}")
    print(f"  unique combos: {n_unique:,}")
    print(f"  dedup ratio:   {n_unique / n_total:.2f}")
    print(f"  estimated extraction cost @ $0.022/call: ${n_unique * 0.022:.0f}")

    # Group canonicals by team for efficient zipfile access.
    by_team: dict[str, list[tuple]] = defaultdict(list)
    for key, (team_part, img_idx, panel) in canonical.items():
        by_team[team_part].append((key, img_idx, panel))

    manifest: dict[str, dict] = {}
    written = 0
    for team_part in sorted(by_team.keys()):
        docx = PLAYBOOKS / f"{team_part}.docx"
        if not docx.exists():
            print(f"  !! missing docx: {docx}", file=sys.stderr)
            continue
        entries = ordered_image_entries(docx)
        items = by_team[team_part]
        # Cache image bytes per img_idx so we don't re-read the same image.
        wanted_imgs = {img_idx for _, img_idx, _ in items}
        cache: dict[int, bytes] = {}
        with zipfile.ZipFile(docx) as z:
            for img_idx in wanted_imgs:
                with z.open(entries[img_idx - 1]) as src:
                    cache[img_idx] = src.read()
        for key, img_idx, panel in items:
            family, formation, name, ptype = key
            panel_img = _crop_panel(cache[img_idx], panel)
            zoomed = _wide_zoom(panel_img)
            marked = _mark_los(zoomed)
            slug_name = (f"{_slug(family)}__{_slug(formation)}"
                         f"__{_slug(ptype)}__{_slug(name)}.jpg")
            out = OUT / slug_name
            marked.save(out, "JPEG", quality=85, optimize=True)
            manifest[slug_name] = {
                "family": family,
                "formation": formation,
                "play_name": name,
                "play_type": ptype,
                "canonical_team": team_part,
                "canonical_img": img_idx,
                "canonical_panel": panel,
                "owner_teams": sorted(set(owners[key])),
                "owner_count": len(set(owners[key])),
            }
            written += 1
            if written % 500 == 0:
                print(f"  cropped {written}/{n_unique}")

    (OUT / "_canonical_manifest.json").write_text(json.dumps(manifest, indent=2))
    print(f"\nwrote {written} canonical crops + manifest to {OUT}")


if __name__ == "__main__":
    main()
