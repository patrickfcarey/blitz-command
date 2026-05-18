#!/usr/bin/env python3
"""Per-formation play-call breakdown for an authored playbook.

For each formation section of a playbook, groups the section's plays by their
disguise family and reports each play's share of that formation's calls — the
"before every formation, list the plays and their call %" view. Grouping by
disguise family makes the install structure and the disguise design visible.

Shared module — imported by tools/print-playbook-detailed/ and exposed by the
`playbook_call_breakdown` tool on playbook-generation-mcp.

As a module:
    from breakdown import compute_call_breakdown
    sections = compute_call_breakdown(playbook_path)

As a CLI (prints the breakdown as JSON, like the other shared playbook tools):
    python3 tools/playbook-call-breakdown/breakdown.py data/playbooks/hs-base.yaml
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
PLAYS_DIR = REPO_ROOT / "data" / "plays"
FAMILIES_DIR = REPO_ROOT / "data" / "play-families"

# Heading for the group of plays that belong to no disguise family.
UNFAMILIED_LABEL = "Standalone plays (no disguise family)"


def _load_yaml(path: Path) -> dict[str, Any]:
    """Parse a YAML file to a dict (empty dict for an empty file)."""
    with open(path) as handle:
        return yaml.safe_load(handle) or {}


def _play_to_family() -> dict[str, dict[str, str]]:
    """Map each play_id to its disguise family ({family_id, family_name}).

    A play belongs to a family if it is that family's base play or one of its
    companions. Plays in no family are simply absent from the map.
    """
    mapping: dict[str, dict[str, str]] = {}
    if not FAMILIES_DIR.exists():
        return mapping
    for path in sorted(FAMILIES_DIR.glob("*.yaml")):
        family = _load_yaml(path)
        family_id = family.get("family_id") or path.stem
        family_name = family.get("name") or family_id
        member_ids = [family.get("base_play_id")]
        member_ids.extend(family.get("companion_play_ids") or [])
        for play_id in member_ids:
            if play_id:
                mapping[play_id] = {"family_id": family_id,
                                    "family_name": family_name}
    return mapping


def _play_display_name(play_id: str) -> str:
    """Return a play's display name, falling back to a title-cased id."""
    play_path = PLAYS_DIR / f"{play_id}.yaml"
    if play_path.exists():
        name = _load_yaml(play_path).get("name")
        if name:
            return str(name)
    return play_id.replace("-", " ").title()


def compute_call_breakdown(playbook_path: str | Path) -> list[dict[str, Any]]:
    """Return the per-formation-section play-call breakdown for a playbook.

    Each section's plays are grouped by disguise family; families are ordered
    by descending share of the formation's calls, with standalone plays last.

    Returns one object per formation section:
        {
          "section_id":            "i-formation",
          "section_name":          "I-Formation",
          "target_snap_share_pct": 33,
          "formations":            ["i-formation", ...],
          "play_count":            13,
          "families": [
            {
              "family_id":        "i-formation-power-family" | None,
              "family_name":      "I-Formation Power Family",
              "family_share_pct": 32,
              "plays": [
                {"play_id", "name", "role", "share_of_section_pct"}, ...
              ],
            }, ...
          ],
        }
    """
    playbook = _load_yaml(Path(playbook_path))
    play_to_family = _play_to_family()
    sections: list[dict[str, Any]] = []

    for section in playbook.get("formation_sections") or []:
        # Bucket the section's plays by disguise family (None = standalone).
        buckets: dict[Any, dict[str, Any]] = {}
        for entry in section.get("plays") or []:
            play_id = entry.get("play_id", "")
            family = play_to_family.get(play_id)
            family_id = family["family_id"] if family else None
            family_name = family["family_name"] if family else UNFAMILIED_LABEL
            bucket = buckets.setdefault(
                family_id,
                {"family_id": family_id, "family_name": family_name,
                 "plays": []},
            )
            bucket["plays"].append({
                "play_id": play_id,
                "name": _play_display_name(play_id),
                "role": entry.get("role"),
                "share_of_section_pct": entry.get("share_of_section_pct", 0),
            })

        families: list[dict[str, Any]] = []
        for bucket in buckets.values():
            bucket["plays"].sort(
                key=lambda play: play["share_of_section_pct"], reverse=True)
            bucket["family_share_pct"] = sum(
                play["share_of_section_pct"] for play in bucket["plays"])
            families.append(bucket)
        # Real families first, by descending call share; standalone bucket last.
        families.sort(
            key=lambda fam: (fam["family_id"] is None, -fam["family_share_pct"]))

        sections.append({
            "section_id": section.get("section_id", ""),
            "section_name": section.get("name") or section.get("section_id", ""),
            "target_snap_share_pct": section.get("target_snap_share_pct"),
            "formations": section.get("formations") or [],
            "play_count": sum(len(fam["plays"]) for fam in families),
            "families": families,
        })
    return sections


def main(argv: list[str]) -> None:
    """CLI: print the breakdown as JSON for the given playbook path."""
    if len(argv) != 2:
        print("usage: breakdown.py <playbook.yaml>", file=sys.stderr)
        sys.exit(1)
    print(json.dumps(compute_call_breakdown(argv[1]), indent=2))


if __name__ == "__main__":
    main(sys.argv)
