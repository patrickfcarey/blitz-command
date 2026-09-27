#!/usr/bin/env python3
"""Attach play names to the NCAA Football 14 catalog from its Play Database.

Unlike the Madden/ESPN docx (one screenshot sequence per *team*), NCAA 14's
Play Database is one docx per *formation* — the docx filename IS the formation
name, and every screenshot in it shows three plays (play name in the panel
header, RUN/PASS in the corner). Plays therefore belong to a formation, and
every team whose playbook includes that formation shares them.

A chunked vision pass writes one cache file per formation:

    .docx-cache-ncaa14-plays/<Formation>.json
        {"formation": "Ace Bunch", "plays": [{"name": "Counter Y", "type": "run"}, ...]}

This script reads them, builds a formation -> plays map, and attaches a
`plays` list to every matching formation in
data/games/ncaa-14-ps3/team-playbooks.yaml.

The catalog is rewritten with a local writer (not the Madden/ESPN one) so the
quoted `team_id` values survive — NCAA 14 has numeric-looking slugs such as
"3_4_multiple" that a YAML loader would otherwise read back as integers.

Usage:
    python tools/ingest-research/extract_ncaa14_play_names.py \\
        [--cache-dir .docx-cache-ncaa14-plays]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
CATALOG = REPO_ROOT / "data" / "games" / "ncaa-14-ps3" / "team-playbooks.yaml"

_YAML_SPECIAL = (": ", "#", "[", "]", "{", "}", ",", "&", "*", "!", "'", '"', "\n")


def _yaml_str(value: str) -> str:
    """YAML-encode a scalar string, quoting only when necessary."""
    if not value:
        return '""'
    if any(ch in value for ch in _YAML_SPECIAL):
        return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'
    return value


def _load_formation_plays(cache_dir: Path) -> dict[str, list[dict]]:
    """Map formation-name (case-folded) -> deduplicated ordered play list."""
    by_formation: dict[str, list[dict]] = {}
    for cache_file in sorted(cache_dir.glob("*.json")):
        data = json.loads(cache_file.read_text())
        formation = (data.get("formation") or cache_file.stem).strip()
        plays: list[dict] = []
        seen: set[str] = set()
        for play in data.get("plays", []):
            name = (play.get("name") or "").strip()
            if not name or name.lower() in seen:
                continue
            seen.add(name.lower())
            ptype = play.get("type")
            plays.append({"name": name,
                          "type": ptype if ptype in ("run", "pass") else None})
        by_formation[formation.lower()] = plays
    return by_formation


def _write_catalog(catalog: dict, path: Path) -> None:
    """Write the team-playbook catalog, preserving every formation-entry field.

    team_id is always quoted (NCAA 14 slugs like "3_4_multiple" would otherwise
    parse back as integers); play entries are emitted when present.
    """
    lines: list[str] = []
    lines.append(f"game_id: {catalog['game_id']}")
    lines.append(f"source: {_yaml_str(catalog['source'])}")
    lines.append(f"verification_status: {catalog['verification_status']}")
    lines.append(f"generated_date: \"{catalog['generated_date']}\"")
    lines.append(f"notes: {_yaml_str(catalog['notes'])}")
    lines.append("teams:")
    for team in catalog["teams"]:
        lines.append(f'  - team_id: "{team["team_id"]}"')
        lines.append(f"    name: {_yaml_str(team['name'])}")
        style = team.get("playbook_style")
        lines.append(f"    playbook_style: {_yaml_str(style) if style else 'null'}")
        lines.append(f"    formation_count: {team['formation_count']}")
        lines.append("    formation_families:")
        for fam, count in (team.get("formation_families") or {}).items():
            lines.append(f"      {fam}: {count}")
        breakdown = team.get("personnel_breakdown")
        if breakdown:
            lines.append("    personnel_breakdown:")
            for code, count in breakdown.items():
                lines.append(f'      "{code}": {count}')
        else:
            lines.append("    personnel_breakdown: null")
        lines.append("    formations:")
        for formation in team["formations"]:
            lines.append(f"      - name: {_yaml_str(formation['name'])}")
            personnel = formation.get("personnel")
            if personnel is not None:
                lines.append(f'        personnel: "{personnel}"')
            for field in ("family",):
                if formation.get(field) is not None:
                    lines.append(f"        {field}: {formation[field]}")
            if formation.get("play_count") is not None:
                lines.append(f"        play_count: {formation['play_count']}")
            plays = formation.get("plays")
            if plays:
                lines.append("        plays:")
                for play in plays:
                    lines.append(f"          - name: {_yaml_str(play['name'])}")
                    ptype = play.get("type")
                    lines.append(f"            type: "
                                 f"{ptype if ptype in ('run', 'pass') else 'null'}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main(argv: list[str]) -> None:
    parser = argparse.ArgumentParser(
        description="Attach NCAA 14 Play Database play names to the catalog.")
    parser.add_argument("--cache-dir", default=".docx-cache-ncaa14-plays",
                        help="Directory of per-formation <Formation>.json files")
    args = parser.parse_args(argv[1:])

    cache_dir = Path(args.cache_dir)
    by_formation = _load_formation_plays(cache_dir)
    catalog = yaml.safe_load(CATALOG.read_text())

    matched = unmatched = 0
    unmatched_names: set[str] = set()
    for team in catalog["teams"]:
        for formation in team["formations"]:
            plays = by_formation.get(formation["name"].lower())
            if plays:
                formation["plays"] = plays
                matched += 1
            else:
                unmatched += 1
                unmatched_names.add(formation["name"])

    _write_catalog(catalog, CATALOG)
    print(f"{len(by_formation)} formations in cache.")
    print(f"  catalog formation-entries with plays: {matched}")
    print(f"  unmatched formation-entries: {unmatched} "
          f"({len(unmatched_names)} distinct names)")
    if unmatched_names:
        print(f"  sample unmatched: {sorted(unmatched_names)[:12]}")


if __name__ == "__main__":
    main(sys.argv)
