#!/usr/bin/env python3
"""Crop all 50 plays from pilot-sample.json at wide LOS-zoom with C-anchored
cyan line and yellow C-box, output as JPEG q=85 with verbose filenames.

For each sample play, walks the team's docx-cache chunks to find the
formation context (family + name) preceding that play_screen image, then
emits a JPEG named:

    <formation-slug>__<play-type>__<play-slug>__<team-slug>__img<NN>p<P>__WIDE.jpg

into tools/playbook-vision-pilot/dispatch-crops/.

Inputs:
    /tmp/pilot-work/pilot-sample.json
    .docx-cache-m25-plays/<Team>__chunk*.json (for formation context)
    research_artifacts/PS3/Madden NFL 25 (2013)/Playbooks/<Team>.docx

Output:
    tools/playbook-vision-pilot/dispatch-crops/*.jpg (50 files)
    Plus dispatch-crops/_manifest.json mapping play_id -> filename + formation.
"""
from __future__ import annotations
import glob
import json
from pathlib import Path

from crop_for_dispatch import crop, _slug

REPO = Path(__file__).resolve().parents[2]
SAMPLE = Path("/tmp/pilot-work/pilot-sample.json")
CACHE_DIR = REPO / ".docx-cache-m25-plays"
OUT_DIR = REPO / "tools/playbook-vision-pilot/dispatch-crops"


def _formation_index(team_part: str) -> dict[int, tuple[str, str]]:
    """Map image_index -> (family, formation) for a team, by walking the
    formation_list entries that precede each play_screen in the cache."""
    out: dict[int, tuple[str, str]] = {}
    current: tuple[str, str] | None = None
    chunk_files = sorted(CACHE_DIR.glob(f"{team_part}__chunk*.json"))
    for f in chunk_files:
        for entry in json.loads(f.read_text()):
            if entry.get("kind") == "formation_list":
                current = (entry.get("family"), entry.get("highlighted"))
            elif entry.get("kind") == "play_screen" and current:
                out[entry["img"]] = current
    return out


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    sample = json.loads(SAMPLE.read_text())
    manifest: dict[str, dict] = {}
    indices: dict[str, dict[int, tuple[str, str]]] = {}

    for i, play in enumerate(sample):
        team = play["team"]
        team_part = team  # team_part in cache matches play["team"]
        if team_part not in indices:
            indices[team_part] = _formation_index(team_part)
        formation_tuple = indices[team_part].get(play["image"])
        if formation_tuple:
            family, formation = formation_tuple
            formation_slug = f"{family.lower()}-{_slug(formation)}"
        else:
            formation_slug = "unknown"

        out = crop(team=team,
                   img_idx=play["image"],
                   panel=play["panel"],
                   formation_slug=formation_slug,
                   play_type=play["play_type"] or "unknown",
                   play_name=play["play_name"])
        manifest[play["id"]] = {
            "filename": out.name,
            "team": team,
            "formation": (f"{family} {formation}" if formation_tuple
                          else "unknown"),
            "play_name": play["play_name"],
            "play_type": play["play_type"],
            "image": play["image"],
            "panel": play["panel"],
            "stratum": play["stratum"],
        }
        print(f"[{i+1:>2}/{len(sample)}] {out.name}")

    (OUT_DIR / "_manifest.json").write_text(json.dumps(manifest, indent=2))
    print(f"\nwrote {len(manifest)} crops + _manifest.json to {OUT_DIR}")


if __name__ == "__main__":
    main()
