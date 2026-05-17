#!/usr/bin/env python3
"""Compute a playbook's tendency profile from its call shares.

A playbook's tendency profile is the coach's-eye summary of what the playbook
*does*: its run/pass balance, and how its snaps split across play types,
formations, and personnel groupings. Every figure is derived from the call
shares already stored in the playbook — each section's target_snap_share_pct
and each play's share_of_section_pct — so the profile can never drift from
the playbook.

Shared module: the playbook-generation MCP exposes it as the
`playbook_tendency_profile` tool, and the detailed print tool imports it for
the tendency-profile page of the PDF.

CLI — prints the profile as JSON:
    python3 tools/playbook-profile/profile.py data/playbooks/hs-base.yaml
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
PLAYS_DIR = REPO_ROOT / "data" / "plays"
FORMATIONS_DIR = REPO_ROOT / "data" / "formations"

# play_type -> run/pass family, for the headline run-pass balance.
RUN_PASS_FAMILY = {
    "run": "run", "rpo": "run", "option": "run",
    "pass": "pass", "play-action": "pass", "screen": "pass",
    "trick": "other", "special": "other",
}


def _load_yaml(path: Path) -> dict:
    """Parse a YAML file into a dict."""
    with open(path, encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def _sorted_shares(share_by_key: dict[str, float]) -> dict[str, float]:
    """Round each share to one decimal, ordered by share descending."""
    return {
        key: round(value, 1)
        for key, value in sorted(share_by_key.items(), key=lambda item: -item[1])
    }


def compute_tendency_profile(playbook_path: Path) -> dict:
    """Compute the tendency profile for the playbook at `playbook_path`.

    For every play, total snap share = the section's target_snap_share_pct
    times the play's share_of_section_pct / 100. Those shares are rolled up
    by run/pass family, play type, formation, and personnel grouping.
    """
    playbook = _load_yaml(Path(playbook_path))

    personnel_by_formation: dict[str, str] = {}
    run_pass: dict[str, float] = {}
    by_play_type: dict[str, float] = {}
    by_formation: dict[str, float] = {}
    by_personnel: dict[str, float] = {}
    total_share = 0.0
    unresolved_plays: list[str] = []

    for section in playbook.get("formation_sections", []):
        section_share = section.get("target_snap_share_pct")
        if section_share is None:
            continue
        for play_entry in section.get("plays", []):
            play_share = play_entry.get("share_of_section_pct")
            if play_share is None:
                continue
            snap_share = section_share * play_share / 100.0
            play_path = PLAYS_DIR / f"{play_entry['play_id']}.yaml"
            if not play_path.exists():
                unresolved_plays.append(play_entry["play_id"])
                continue
            play = _load_yaml(play_path)
            play_type = play.get("play_type", "unknown")
            formation_id = play.get("formation", "unknown")

            total_share += snap_share
            by_play_type[play_type] = by_play_type.get(play_type, 0.0) + snap_share
            by_formation[formation_id] = by_formation.get(formation_id, 0.0) + snap_share
            family = RUN_PASS_FAMILY.get(play_type, "other")
            run_pass[family] = run_pass.get(family, 0.0) + snap_share

            if formation_id not in personnel_by_formation:
                formation_path = FORMATIONS_DIR / f"{formation_id}.yaml"
                formation = _load_yaml(formation_path) if formation_path.exists() else {}
                personnel_by_formation[formation_id] = formation.get("personnel", "unknown")
            personnel = personnel_by_formation[formation_id]
            by_personnel[personnel] = by_personnel.get(personnel, 0.0) + snap_share

    return {
        "playbook_id": playbook.get("playbook_id"),
        "total_snap_share_pct": round(total_share, 1),
        "run_pass_split": _sorted_shares(run_pass),
        "by_play_type": _sorted_shares(by_play_type),
        "by_formation": _sorted_shares(by_formation),
        "by_personnel": _sorted_shares(by_personnel),
        "unresolved_plays": sorted(unresolved_plays),
    }


def main() -> int:
    """CLI entry point: print the playbook's tendency profile as JSON."""
    if len(sys.argv) != 2:
        print("usage: profile.py <playbook.yaml>", file=sys.stderr)
        return 2
    playbook_path = Path(sys.argv[1])
    if not playbook_path.exists():
        print(f"error: {playbook_path} not found", file=sys.stderr)
        return 2
    print(json.dumps(compute_tendency_profile(playbook_path), indent=2,
                     ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
