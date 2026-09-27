#!/usr/bin/env python3
"""Attach play names to the Madden NFL 04 catalog from per-team docx vision.

Each docx is one team's playbook; vision subagents walk the screenshot
sequence and emit a per-team cache file:

    .docx-cache-m04-plays/<Team_With_Underscores>.json
        {"team": "Arizona Cardinals",
         "formations": [
             {"name": "Singleback-Big",
              "plays": [{"name": "Fitzgerald Option", "type": null}, ...]},
             ...
         ]}

This script reads them, matches formations into the catalog by tolerant
name comparison (M07 uses hyphens — "Singleback-Big" vs the catalog's
"Singleback Big"), and writes the result back. Reuses the NCAA 14 writer
which preserves every field and always quotes ``team_id``.
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
CATALOG = REPO_ROOT / "data" / "games" / "madden-04-ps2" / "team-playbooks.yaml"


def _normalize_formation_name(name: str) -> str:
    """Strip hyphens/whitespace/case and collapse Gun↔Shotgun.

    The xlsx-sourced catalog abbreviates "Shotgun" as "Gun"; the in-game
    screens spell it out. Without this normalization roughly a third of
    every team's formations would silently miss.
    """
    out = re.sub(r"[\s\-_]+", "", name).lower()
    if out.startswith("shotgun"):
        out = "gun" + out[len("shotgun"):]
    return out


def _load_cache(cache_dir: Path) -> dict[str, dict[str, list[dict]]]:
    """Map team-name -> {normalized-formation-name -> [plays]}."""
    by_team: dict[str, dict[str, list[dict]]] = {}
    for cache_file in sorted(cache_dir.glob("*.json")):
        data = json.loads(cache_file.read_text())
        team = (data.get("team") or "").strip()
        if not team:
            continue
        forms: dict[str, list[dict]] = {}
        for formation in data.get("formations", []):
            name = (formation.get("name") or "").strip()
            if not name:
                continue
            plays: list[dict] = []
            seen: set[str] = set()
            for play in formation.get("plays", []):
                pname = (play.get("name") or "").strip()
                if not pname or pname.lower() in seen:
                    continue
                seen.add(pname.lower())
                ptype = play.get("type")
                plays.append({"name": pname,
                              "type": ptype if ptype in ("run", "pass") else None})
            forms[_normalize_formation_name(name)] = plays
        by_team[team] = forms
    return by_team


def main(argv: list[str]) -> None:
    parser = argparse.ArgumentParser(
        description="Attach Madden 04 play names to the catalog.")
    parser.add_argument("--cache-dir", default=".docx-cache-m04-plays",
                        help="Directory of per-team <Team>.json files")
    args = parser.parse_args(argv[1:])

    cache_dir = Path(args.cache_dir)
    by_team = _load_cache(cache_dir)
    catalog = yaml.safe_load(CATALOG.read_text())

    matched_teams = matched_forms = unmatched_forms = unmatched_teams = 0
    unmatched_form_names: set[str] = set()
    for team in catalog["teams"]:
        team_cache = by_team.get(team["name"])
        if not team_cache:
            unmatched_teams += 1
            continue
        matched_teams += 1
        for formation in team["formations"]:
            plays = team_cache.get(_normalize_formation_name(formation["name"]))
            if plays:
                formation["plays"] = plays
                matched_forms += 1
            else:
                unmatched_forms += 1
                unmatched_form_names.add(formation["name"])

    _write_catalog(catalog, CATALOG)
    print(f"cached teams: {len(by_team)}")
    print(f"  catalog teams with plays attached: {matched_teams}")
    print(f"  catalog teams without cache yet:   {unmatched_teams}")
    print(f"  formation-entries with plays:      {matched_forms}")
    print(f"  formation-entries unmatched:       {unmatched_forms} "
          f"({len(unmatched_form_names)} distinct names)")
    if unmatched_form_names:
        print(f"  sample unmatched: {sorted(unmatched_form_names)[:10]}")


if __name__ == "__main__":
    main(sys.argv)
