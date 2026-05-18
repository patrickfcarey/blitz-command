#!/usr/bin/env python3
"""Install schedule for an authored playbook.

Groups a playbook's plays into install phases (Day 1, Day 2, Week 1, Week 2,
mid-season) from each play entry's `install_order`, in teaching order. This is
the install table the playbook's front_matter.install_notes points at: the
Day-1 / Week-1 plays are the spine, Week-2 and mid-season adds layer disguise
depth, and each play is annotated with its formation and disguise family so a
companion play is never installed before its base.

Shared module — imported by tools/print-playbook-detailed/ and exposed by the
`playbook_install_schedule` tool on playbook-generation-mcp.

As a module:
    from schedule import compute_install_schedule
    phases = compute_install_schedule(playbook_path)

As a CLI (prints the schedule as JSON, like the other shared playbook tools):
    python3 tools/playbook-install-schedule/schedule.py data/playbooks/hs-base.yaml
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

# Install-order codes in teaching order, each with its display label. The
# codes match the play_entry_install_order enum in schemas/playbook.schema.json.
INSTALL_PHASES: list[tuple[str, str]] = [
    ("install-day-1", "Install — Day 1"),
    ("install-day-2", "Install — Day 2"),
    ("install-week-1", "Install — Week 1"),
    ("install-week-2", "Install — Week 2"),
    ("mid-season-add", "Mid-Season Add"),
]


def _load_yaml(path: Path) -> dict[str, Any]:
    """Parse a YAML file to a dict (empty dict for an empty file)."""
    with open(path) as handle:
        return yaml.safe_load(handle) or {}


def _play_to_family_name() -> dict[str, str]:
    """Map each play_id to its disguise family's display name.

    A play belongs to a family if it is that family's base play or one of its
    companions. Plays in no family are simply absent from the map.
    """
    mapping: dict[str, str] = {}
    if not FAMILIES_DIR.exists():
        return mapping
    for path in sorted(FAMILIES_DIR.glob("*.yaml")):
        family = _load_yaml(path)
        family_name = family.get("name") or family.get("family_id") or path.stem
        member_ids = [family.get("base_play_id")]
        member_ids.extend(family.get("companion_play_ids") or [])
        for play_id in member_ids:
            if play_id:
                mapping[play_id] = family_name
    return mapping


def _play_display_name(play_id: str) -> str:
    """Return a play's display name, falling back to a title-cased id."""
    play_path = PLAYS_DIR / f"{play_id}.yaml"
    if play_path.exists():
        name = _load_yaml(play_path).get("name")
        if name:
            return str(name)
    return play_id.replace("-", " ").title()


def compute_install_schedule(playbook_path: str | Path) -> list[dict[str, Any]]:
    """Return a playbook's install schedule — its plays grouped into install
    phases, in teaching order.

    Returns one object per non-empty install phase:
        {
          "install_order": "install-day-1",
          "label":         "Install — Day 1",
          "play_count":    6,
          "plays": [
            {"play_id", "name", "section_id", "section_name",
             "family_name", "role", "share_of_section_pct"}, ...
          ],
        }
    Plays within a phase are ordered by formation section, then by descending
    share of that section's calls — the base play of a section leads.
    """
    playbook = _load_yaml(Path(playbook_path))
    play_to_family = _play_to_family_name()

    plays_by_phase: dict[str, list[dict[str, Any]]] = {}
    for section in playbook.get("formation_sections") or []:
        section_id = section.get("section_id", "")
        section_name = section.get("name") or section_id
        for entry in section.get("plays") or []:
            play_id = entry.get("play_id", "")
            install_order = entry.get("install_order") or "unscheduled"
            plays_by_phase.setdefault(install_order, []).append({
                "play_id": play_id,
                "name": _play_display_name(play_id),
                "section_id": section_id,
                "section_name": section_name,
                "family_name": play_to_family.get(play_id),
                "role": entry.get("role"),
                "share_of_section_pct": entry.get("share_of_section_pct", 0),
            })

    # Known phases in teaching order, then any unexpected codes alphabetically.
    known_codes = [code for code, _ in INSTALL_PHASES]
    ordered_codes = [code for code in known_codes if code in plays_by_phase]
    ordered_codes += sorted(c for c in plays_by_phase if c not in known_codes)
    labels = dict(INSTALL_PHASES)

    schedule: list[dict[str, Any]] = []
    for code in ordered_codes:
        plays = plays_by_phase[code]
        plays.sort(key=lambda play: (play["section_name"],
                                     -play["share_of_section_pct"]))
        schedule.append({
            "install_order": code,
            "label": labels.get(code, code.replace("-", " ").title()),
            "play_count": len(plays),
            "plays": plays,
        })
    return schedule


def main(argv: list[str]) -> None:
    """CLI: print the install schedule as JSON for the given playbook path."""
    if len(argv) != 2:
        print("usage: schedule.py <playbook.yaml>", file=sys.stderr)
        sys.exit(1)
    print(json.dumps(compute_install_schedule(argv[1]), indent=2))


if __name__ == "__main__":
    main(sys.argv)
