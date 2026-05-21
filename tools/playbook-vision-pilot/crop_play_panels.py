#!/usr/bin/env python3
"""Crop the play panel for each sampled pilot play.

Reads ``/tmp/pilot-work/pilot-sample.json`` and writes one JPEG per play to
``/tmp/pilot-work/crops/<id>.jpg``. Each Madden 25 play-screen image in the
per-team docx is a 1865x374 strip with exactly 3 horizontal panels; the
sample's ``panel`` field (0/1/2) picks which third.

The source images are extracted from the per-team docx via the same
document-order resolver used by `extract_docx_images.py`.
"""
from __future__ import annotations

import io
import json
import sys
import zipfile
from collections import defaultdict
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SAMPLE = Path("/tmp/pilot-work/pilot-sample.json")
CROPS_DIR = Path("/tmp/pilot-work/crops")
PLAYBOOKS = REPO_ROOT / "research_artifacts/PS3/Madden NFL 25 (2013)/Playbooks"

PANEL_COUNT = 3  # M25 play-screen images are 3 panels wide.
# Every M25 play-screen image is 1865x374 with a team-logo strip on the left
# (~420px) and a UI strip on the right (~45px). The play diagrams occupy
# x=420..1820 (1400px), split into three equal 467px panels. Boundaries
# verified visually against annotated overlays on multiple images.
PLAY_AREA_LEFT = 420
PLAY_AREA_RIGHT = 1820
# Every M25 play-screen image carries a team-logo strip on the left, then
# three equal-width play panels. Empirically (verified against annotated
# overlays on Arizona Cardinals 0002/0003/0050/0100) the logo strip is ~420px
# wide; the remaining 1445px split into three ~482px panels.
LOGO_WIDTH = 420

sys.path.insert(0, str(REPO_ROOT / "tools/ingest-research"))
from extract_docx_images import ordered_image_entries  # noqa: E402

from PIL import Image  # noqa: E402


def _docx_path(docx_stem: str) -> Path:
    # cache stem is "Arizona Cardinals" with spaces preserved in the actual
    # file; sampler swapped spaces to underscores for the slug — undo that.
    name = docx_stem.replace("_", " ")
    return PLAYBOOKS / f"{name}.docx"


def _crop_panel(image_bytes: bytes, panel: int) -> Image.Image:
    image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    _, height = image.size
    play_area = PLAY_AREA_RIGHT - PLAY_AREA_LEFT
    panel_width = play_area / PANEL_COUNT
    left = int(round(PLAY_AREA_LEFT + panel * panel_width))
    right = int(round(PLAY_AREA_LEFT + (panel + 1) * panel_width))
    return image.crop((left, 0, right, height))


def main() -> None:
    CROPS_DIR.mkdir(parents=True, exist_ok=True)
    sample = json.loads(SAMPLE.read_text())

    by_docx: dict[str, list[dict]] = defaultdict(list)
    for play in sample:
        by_docx[play["docx_stem"]].append(play)

    written = 0
    for docx_stem, plays in sorted(by_docx.items()):
        path = _docx_path(docx_stem)
        if not path.exists():
            print(f"!! missing docx: {path}", file=sys.stderr)
            continue
        entries = ordered_image_entries(path)
        wanted_imgs = {play["image"] for play in plays}
        with zipfile.ZipFile(path) as document:
            cache: dict[int, bytes] = {}
            for img_idx in wanted_imgs:
                # img is 1-based in the cache; entries is 0-based.
                entry = entries[img_idx - 1]
                with document.open(entry) as source:
                    cache[img_idx] = source.read()
            for play in plays:
                panel_image = _crop_panel(cache[play["image"]], play["panel"])
                out = CROPS_DIR / f"{play['id']}.jpg"
                panel_image.save(out, "JPEG", quality=90)
                written += 1
        print(f"  {docx_stem:<32} {len(plays):>2} plays cropped")

    print(f"\nwrote {written} crops to {CROPS_DIR}")


if __name__ == "__main__":
    main()
