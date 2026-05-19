#!/usr/bin/env python3
"""Attach play names to a team-playbook catalog from a play-screen vision pass.

`ingest_docx_playbooks.py` builds the formation catalog (formations + play
counts). This script enriches it with the actual play NAMES, read off the
play-diagram screens by a separate chunked vision pass.

Input: a cache directory of per-team chunk JSONs, one file per image-range
chunk, named ``<team>__chunkNN.json``. Each file is a list of per-image
records produced by a vision subagent:

    {"img": 3, "kind": "play_screen",
     "plays": [{"name": "Mesh", "type": "pass"}, ...]}
    {"img": 1, "kind": "formation_list", "family": "SINGLEBACK", ...}
    {"img": 5, "kind": "other"}

ESPN play screens additionally carry a "formation" field (the on-screen
header); Madden play screens do not.

Two association modes, picked automatically per team:

  header   - play screens name their own formation (ESPN). Group directly.
  segment  - play screens don't (Madden). They appear in formation order, so
             the ordered play stream is segmented by each formation's known
             play_count: a formation fills to its play_count, then the stream
             rolls forward to the next formation.

Only teams that have chunk files in the cache dir are touched; the rest of
the catalog is left as-is, so the pass can run incrementally.

Usage:
    python tools/ingest-research/extract_play_names.py \\
        --game madden-25-ps3 --cache-dir .docx-cache-m25-plays
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).parent))
from ingest_docx_playbooks import _write_yaml  # noqa: E402  (reuse catalog writer)

REPO_ROOT = Path(__file__).resolve().parents[2]

# Cap stand-in for a formation whose play_count is unknown (absorbs the tail).
_UNCOUNTED_CAP = 10 ** 6


def _load_team_sequence(cache_dir: Path, team: str) -> list[dict]:
    """Reassemble one team's chunk JSONs into a single image-ordered sequence."""
    seq: list[dict] = []
    for chunk_file in sorted(cache_dir.glob(f"{team}__chunk*.json")):
        seq.extend(json.loads(chunk_file.read_text()))
    seq.sort(key=lambda rec: rec.get("img", 0))
    return seq


def _teams_with_chunks(cache_dir: Path) -> set[str]:
    """Team names that have at least one chunk file in the cache dir."""
    return {f.name.split("__chunk")[0] for f in cache_dir.glob("*__chunk*.json")}


def _dedup_append(plays: list[dict], play: dict) -> None:
    """Append a play unless its name is already present (case-insensitive).

    Consecutive play screens overlap as the menu scrolls, so the same play is
    seen several times; within one formation a play name is unique.
    """
    name = (play.get("name") or "").strip()
    if not name or name.lower() in {p["name"].lower() for p in plays}:
        return
    play_type = play.get("type")
    plays.append({"name": name,
                  "type": play_type if play_type in ("run", "pass") else None})


def _cap(formation: dict) -> int:
    """A formation's play_count, or a large stand-in when it is unknown."""
    pc = formation.get("play_count")
    return pc if isinstance(pc, int) else _UNCOUNTED_CAP


def associate_by_play_count(seq: list[dict], formations: list[dict]) -> None:
    """Madden mode — segment the ordered play stream by each formation's count.

    Play screens are in formation order but do not name their formation; each
    formation fills to its play_count, then the stream rolls to the next.
    """
    for formation in formations:
        formation["plays"] = []
    cursor = 0
    for record in seq:
        if record.get("kind") != "play_screen":
            continue
        for play in record.get("plays", []):
            while (cursor < len(formations)
                   and len(formations[cursor]["plays"]) >= _cap(formations[cursor])):
                cursor += 1
            if cursor >= len(formations):
                return
            _dedup_append(formations[cursor]["plays"], play)


def associate_by_header(seq: list[dict], formations: list[dict]) -> None:
    """ESPN mode — each play screen names its own formation, so group directly."""
    by_name = {f["name"].lower(): f for f in formations}
    for formation in formations:
        formation["plays"] = []
    for record in seq:
        if record.get("kind") != "play_screen":
            continue
        target = by_name.get((record.get("formation") or "").strip().lower())
        if target is None:
            continue
        for play in record.get("plays", []):
            _dedup_append(target["plays"], play)


def main(argv: list[str]) -> None:
    parser = argparse.ArgumentParser(
        description="Attach play names to a team-playbook catalog.")
    parser.add_argument("--game", required=True, help="Game ID, e.g. 'madden-25-ps3'")
    parser.add_argument("--cache-dir", required=True,
                        help="Directory of <team>__chunkNN.json vision files")
    args = parser.parse_args(argv[1:])

    catalog_path = REPO_ROOT / "data" / "games" / args.game / "team-playbooks.yaml"
    if not catalog_path.exists():
        print(f"ERROR: catalog not found: {catalog_path}", file=sys.stderr)
        sys.exit(1)
    catalog = yaml.safe_load(catalog_path.read_text())

    cache_dir = Path(args.cache_dir)
    done = _teams_with_chunks(cache_dir)
    print(f"{len(done)} team(s) have play-screen chunks: {sorted(done)}\n")

    processed = 0
    for team in catalog["teams"]:
        if team["name"] not in done:
            continue
        seq = _load_team_sequence(cache_dir, team["name"])
        has_header = any(r.get("kind") == "play_screen" and r.get("formation")
                         for r in seq)
        if has_header:
            associate_by_header(seq, team["formations"])
        else:
            associate_by_play_count(seq, team["formations"])

        # Report extracted-vs-expected so under/over-fills are visible.
        clean = 0
        for f in team["formations"]:
            got, want = len(f.get("plays") or []), f.get("play_count")
            if isinstance(want, int) and abs(got - want) <= 2:
                clean += 1
        counted = sum(1 for f in team["formations"]
                      if isinstance(f.get("play_count"), int))
        total_plays = sum(len(f.get("plays") or []) for f in team["formations"])
        mode = "header" if has_header else "segment"
        print(f"  {team['name']:24} [{mode}]  {total_plays:4d} plays  "
              f"{clean}/{counted} formations within +/-2 of play_count")
        processed += 1

    _write_yaml(catalog, catalog_path)
    print(f"\nWrote {catalog_path}  ({processed} team(s) updated with play names)")


if __name__ == "__main__":
    main(sys.argv)
