#!/usr/bin/env python3
"""Attach play names to the NCAA Football 06 catalog from the master
``Offensive Plays.docx`` (one docx, formation-grouped by Heading 1 paragraphs).

Pipeline:
1. ``map_images_to_formations.py`` (sibling script) walks the docx body and
   records each image's enclosing Heading-1 formation -> ``/tmp/n06-work/image_to_formation.json``.
2. Vision subagents read the extracted .png strips and emit per-chunk JSON:
       .docx-cache-n06-plays-rerun/chunkNN.json
       {"first_image": 1, "last_image": 41,
        "images": [{"i": 1, "plays": ["All Hook", "HB Dive", "PA Deep Post"]}, ...]}
3. This script combines the chunks, groups plays by formation, deduplicates,
   and attaches the resulting formation -> plays map to every catalog entry
   whose formation name matches (tolerant of dashes/spaces/case).
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

import yaml

from extract_ncaa14_play_names import _write_catalog  # type: ignore

REPO_ROOT = Path(__file__).resolve().parents[2]
CATALOG = REPO_ROOT / "data" / "games" / "ncaa-06-ps2" / "team-playbooks.yaml"


def _normalize(name: str) -> str:
    """Tolerant key for cross-source formation matching.

    The xlsx catalog abbreviates "Shotgun" as "Gun" and uses "5-Wide" / "5 Wide"
    inconsistently; the docx spells out "Shotgun" and uses "5 Wide". Collapse
    whitespace/dashes/case and rewrite the Shotgun prefix.
    """
    out = re.sub(r"[\s\-_]+", "", name).lower()
    if out.startswith("shotgun"):
        out = "gun" + out[len("shotgun"):]
    return out


def _load_image_to_formation(path: Path) -> dict[int, str]:
    raw = json.loads(path.read_text())
    return {int(k): v for k, v in raw.items()}


def _load_chunks(cache_dir: Path) -> list[dict]:
    images: list[dict] = []
    for chunk in sorted(cache_dir.glob("chunk*.json")):
        data = json.loads(chunk.read_text())
        images.extend(data.get("images", []))
    return images


def _build_formation_plays(
    images: list[dict],
    image_to_formation: dict[int, str],
) -> dict[str, list[dict]]:
    """Map normalized-formation -> ordered-deduped play list."""
    by_formation: dict[str, list[dict]] = {}
    seen_per_formation: dict[str, set[str]] = {}
    for obs in images:
        idx = obs.get("i")
        formation = image_to_formation.get(idx)
        if not formation:
            continue
        key = _normalize(formation)
        plays = by_formation.setdefault(key, [])
        seen = seen_per_formation.setdefault(key, set())
        for raw_name in obs.get("plays", []):
            cleaned = (raw_name or "").strip()
            if not cleaned or cleaned.lower() in seen:
                continue
            seen.add(cleaned.lower())
            plays.append({"name": cleaned, "type": None})
    return by_formation


def main(argv: list[str]) -> None:
    parser = argparse.ArgumentParser(
        description="Attach NCAA 06 Offensive Plays.docx play names to the catalog.")
    parser.add_argument("--cache-dir", default=".docx-cache-n06-plays-rerun",
                        help="Directory of chunkNN.json per-image observation files")
    parser.add_argument("--image-map",
                        default="/tmp/n06-work/image_to_formation.json",
                        help="JSON of image-index -> formation-name from map_images_to_formations.py")
    args = parser.parse_args(argv[1:])

    image_to_formation = _load_image_to_formation(Path(args.image_map))
    images = _load_chunks(Path(args.cache_dir))
    by_formation = _build_formation_plays(images, image_to_formation)

    catalog = yaml.safe_load(CATALOG.read_text())
    matched = unmatched = 0
    unmatched_names: set[str] = set()
    for team in catalog["teams"]:
        for formation in team["formations"]:
            plays = by_formation.get(_normalize(formation["name"]))
            if plays:
                formation["plays"] = plays
                matched += 1
            else:
                unmatched += 1
                unmatched_names.add(formation["name"])

    _write_catalog(catalog, CATALOG)
    print(f"chunks: {len(images)} image observations")
    print(f"  distinct formations seen in docx: {len(by_formation)}")
    print(f"  catalog formation-entries with plays: {matched}")
    print(f"  unmatched formation-entries: {unmatched} "
          f"({len(unmatched_names)} distinct names)")
    if unmatched_names:
        print(f"  sample unmatched: {sorted(unmatched_names)[:10]}")


if __name__ == "__main__":
    main(sys.argv)
