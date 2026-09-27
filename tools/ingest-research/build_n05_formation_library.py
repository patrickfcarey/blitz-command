#!/usr/bin/env python3
"""Build a formation-library YAML for NCAA Football 05.

NCAA 05 has no per-team playbook-database xlsx (unlike NCAA 04/06/07/14), so
we can't produce the per-team team-playbooks.yaml shape. What we *can* extract
is the master Offensive Plays.docx, which groups every offensive formation in
the game and its full play list. That's still a useful artifact — a
formation-level reference — so we emit it as a distinct schema rather than
faking a single-team catalog.

Output: ``data/games/ncaa-05-ps2/formation-library.yaml``
    game_id: ncaa-05-ps2
    source: in-game Offensive Plays.docx
    generated_date: <ISO>
    formation_count: <int>
    formations:
      - name: Ace Big Twins
        plays:
          - {name: All Hook, type: null}
          - ...
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import date
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
OUTPUT = REPO_ROOT / "data" / "games" / "ncaa-05-ps2" / "formation-library.yaml"

# Reuse the YAML scalar quoter from the NCAA 14 attacher (already battle-tested
# against play names with apostrophes, ampersands, and colons).
from extract_ncaa14_play_names import _yaml_str  # type: ignore


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
    """Map formation-name -> ordered-deduped play list."""
    by_formation: dict[str, list[dict]] = {}
    seen_per_formation: dict[str, set[str]] = {}
    for obs in images:
        idx = obs.get("i")
        formation = image_to_formation.get(idx)
        if not formation:
            continue
        plays = by_formation.setdefault(formation, [])
        seen = seen_per_formation.setdefault(formation, set())
        for raw_name in obs.get("plays", []) or []:
            cleaned = (raw_name or "").strip()
            if not cleaned or cleaned.lower() in seen:
                continue
            seen.add(cleaned.lower())
            ptype = None  # NCAA 05 strips don't reliably surface run/pass
            plays.append({"name": cleaned, "type": ptype})
    return by_formation


def _write_library(by_formation: dict[str, list[dict]], path: Path) -> None:
    lines: list[str] = []
    lines.append("game_id: ncaa-05-ps2")
    lines.append("source: in-game Offensive Plays.docx")
    lines.append(f'generated_date: "{date.today().isoformat()}"')
    lines.append("verification_status: unverified")
    lines.append(f"formation_count: {len(by_formation)}")
    lines.append("formations:")
    for name in sorted(by_formation.keys()):
        plays = by_formation[name]
        lines.append(f"  - name: {_yaml_str(name)}")
        if not plays:
            lines.append("    plays: []")
            continue
        lines.append("    plays:")
        for play in plays:
            lines.append(f"      - name: {_yaml_str(play['name'])}")
            ptype = play.get("type")
            lines.append(f"        type: "
                         f"{ptype if ptype in ('run', 'pass') else 'null'}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main(argv: list[str]) -> None:
    parser = argparse.ArgumentParser(
        description="Build NCAA Football 05 formation library.")
    parser.add_argument("--cache-dir", default=".docx-cache-n05-plays-rerun",
                        help="Per-image observation chunks (chunkNN.json)")
    parser.add_argument("--image-map", default="/tmp/n05-work/image_to_formation.json",
                        help="image-index -> formation-name JSON")
    args = parser.parse_args(argv[1:])

    image_to_formation = _load_image_to_formation(Path(args.image_map))
    images = _load_chunks(Path(args.cache_dir))
    by_formation = _build_formation_plays(images, image_to_formation)

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    _write_library(by_formation, OUTPUT)

    play_total = sum(len(p) for p in by_formation.values())
    print(f"observations: {len(images)}")
    print(f"formations:   {len(by_formation)}")
    print(f"total plays:  {play_total}")
    print(f"wrote -> {OUTPUT}")


if __name__ == "__main__":
    main(sys.argv)
