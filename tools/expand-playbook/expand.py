#!/usr/bin/env python3
"""Expand data/playbooks/hs-base.yaml into the full master playbook.

Folds in EVERY play that belongs to a disguise family — taking the playbook
from its hand-authored core to a ~90-play master/reference book. It is meant
to be re-run whenever the families change; it is deterministic and safely
idempotent (re-running on its own output reproduces that output).

Rules:
  - Every base + companion play of every family in data/play-families/ is
    included, plus any play already in the playbook.
  - Existing play entries keep their hand-authored counter_responses, role,
    install_order, notes. Only their share_of_section_pct is recomputed.
  - New plays get counter_responses generated from their defensive_counters
    via a read_category -> audible-slot heuristic, and a derived role.
  - Section shares are role-weighted, normalised to 100, and re-sorted.
  - audibles, audible_mode, situational_sections, and all other top-level
    fields are preserved as-is.

Run from the repo root:
    python3 tools/expand-playbook/expand.py
"""
from __future__ import annotations

from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
PLAYBOOK_PATH = REPO_ROOT / "data" / "playbooks" / "hs-base.yaml"
FAMILIES_DIR = REPO_ROOT / "data" / "play-families"
PLAYS_DIR = REPO_ROOT / "data" / "plays"

# formation_id -> the playbook section that formation's plays belong in.
SECTION_BY_FORMATION = {
    "i-formation": "i-formation",
    "i-formation-twins-weak": "i-formation",
    "singleback-ace": "singleback",
    "singleback-trio": "singleback",
    "shotgun-2x2": "shotgun",
    "shotgun-trips-left": "shotgun",
    "shotgun-trips-right": "shotgun",
    "goal-line": "goal-line",
    "double-slot": "double-slot",
}
SECTION_ORDER = ["i-formation", "singleback", "shotgun", "double-slot", "goal-line"]
SECTION_DISPLAY_NAME = {
    "i-formation": "I-Formation",
    "singleback": "Singleback",
    "shotgun": "Shotgun",
    "double-slot": "Double Slot",
    "goal-line": "Goal Line",
}
SECTION_TARGET_SNAP_SHARE = {
    "i-formation": 33, "singleback": 25, "shotgun": 27,
    "double-slot": 9, "goal-line": 6,
}

# A new play's defensive_counters read_category -> which of the five hs-base
# audible slots the QB should check to when that pre-snap look shows.
AUDIBLE_SLOT_BY_READ_CATEGORY = {
    "box-count": 3,      # BLUE 80 — loaded box, throw the quick game
    "dl-alignment": 2,   # WIDE 28 — DL movement, hit the perimeter
    "lb-depth": 5,       # WHITE BOOT — LB tells, boot away
    "safety-shell": 1,   # RED 22 — coverage shell, run Power
    "cb-leverage": 1,    # RED 22 — corner leverage, run Power
}
AUDIBLE_CALL_BY_SLOT = {
    1: "RED 22", 2: "WIDE 28", 3: "BLUE 80", 4: "KILL POWER", 5: "WHITE BOOT",
}

# Relative weight each play role contributes when dividing a section's 100%
# of call share. A base play is called far more often than an answer play.
CALL_SHARE_WEIGHT_BY_ROLE = {
    "base": 4, "counter": 2, "complement": 2, "constraint": 2,
    "misdirection": 2, "package": 2, "answer": 1, "opener": 1,
    "tempo": 1, "trick": 1,
}

# Defaults applied when a value cannot be derived from the play data.
DEFAULT_INSTALL_ORDER = "install-week-2"  # install week for a newly folded-in play
DEFAULT_AUDIBLE_SLOT = 1   # unmapped read_category falls back to slot 1 (RED 22)
DEFAULT_ROLE_WEIGHT = 1    # call-share weight for an unrecognised play role
MIN_PLAY_SHARE_PCT = 1     # every play keeps at least this much of its section


def _derive_role(play_id: str, play: dict, is_family_base: bool) -> str:
    """Infer a playbook role for a play not already entered by hand.

    A family's base play is the section workhorse ("base"); counters and
    screens get their own roles; anything else is a "complement".
    """
    if is_family_base:
        return "base"
    if "counter" in play_id:
        return "counter"
    if "screen" in play_id or play.get("play_type") == "screen":
        return "answer"
    return "complement"


def _generate_counter_responses(play: dict) -> list[dict]:
    """Build counter_responses for a new play from its defensive_counters.

    Each defensive_counter is mapped — via its read_category — to one of the
    playbook's five audible slots. The first counter becomes the primary
    response; the rest are secondary.
    """
    counter_responses = []
    for counter_index, counter in enumerate(play.get("defensive_counters") or []):
        audible_slot = AUDIBLE_SLOT_BY_READ_CATEGORY.get(
            counter.get("read_category"), DEFAULT_AUDIBLE_SLOT
        )
        counter_responses.append({
            "counter_ref": counter["counter_id"],
            "priority": "primary" if counter_index == 0 else "secondary",
            "response": {
                "audible_slot": audible_slot,
                "notes": f"{counter.get('qb_key', 'Read the look')} — "
                         f"check to {AUDIBLE_CALL_BY_SLOT[audible_slot]}.",
            },
        })
    return counter_responses


def _rebalance_shares_to_100(shares: list[int]) -> list[int]:
    """Nudge a list of integer percentages so they sum to exactly 100.

    Any rounding remainder is added to (or removed from) the largest shares
    first. Assumes a modestly sized section — shares never drop below 1, and
    the playbook's sections are small enough that the adjustable values are
    never exhausted.
    """
    remainder = 100 - sum(shares)
    indices_largest_first = sorted(
        range(len(shares)), key=lambda share_index: -shares[share_index]
    )
    cursor = 0
    while remainder != 0 and indices_largest_first:
        index = indices_largest_first[cursor % len(indices_largest_first)]
        if remainder > 0:
            shares[index] += 1
            remainder -= 1
        elif shares[index] > MIN_PLAY_SHARE_PCT:
            shares[index] -= 1
            remainder += 1
        cursor += 1
    return shares


def main() -> None:
    """Regenerate hs-base.yaml as the master playbook and write it back."""
    playbook = yaml.safe_load(PLAYBOOK_PATH.read_text())

    existing_entries = {
        entry["play_id"]: entry
        for section in playbook["formation_sections"]
        for entry in section["plays"]
    }

    family_base_play_ids: set[str] = set()
    family_member_play_ids: set[str] = set()
    for family_path in sorted(FAMILIES_DIR.glob("*.yaml")):
        family = yaml.safe_load(family_path.read_text())
        family_base_play_ids.add(family["base_play_id"])
        family_member_play_ids.add(family["base_play_id"])
        family_member_play_ids.update(family.get("companion_play_ids") or [])

    play_ids_to_include = set(existing_entries) | family_member_play_ids

    # Group every included play into its formation section. Each list holds
    # (playbook entry, full play dict) pairs.
    entries_by_section: dict[str, list[tuple[dict, dict]]] = {
        section_id: [] for section_id in SECTION_ORDER
    }
    skipped_play_ids = []
    for play_id in sorted(play_ids_to_include):
        play_path = PLAYS_DIR / f"{play_id}.yaml"
        if not play_path.exists():
            skipped_play_ids.append(play_id)
            continue
        play = yaml.safe_load(play_path.read_text())
        section_id = SECTION_BY_FORMATION.get(play.get("formation"))
        if section_id is None:
            skipped_play_ids.append(play_id)
            continue
        if play_id in existing_entries:
            entry = dict(existing_entries[play_id])
        else:
            entry = {
                "play_id": play_id,
                "role": _derive_role(play_id, play, play_id in family_base_play_ids),
                "install_order": DEFAULT_INSTALL_ORDER,
                "counter_responses": _generate_counter_responses(play),
            }
        entries_by_section[section_id].append((entry, play))

    # Build each section: assign role-weighted shares, sort by share, and
    # roll up the per-formation usage split.
    formation_sections = []
    total_play_count = 0
    for section_id in SECTION_ORDER:
        section_entries = entries_by_section[section_id]
        if not section_entries:
            continue
        role_weights = [
            CALL_SHARE_WEIGHT_BY_ROLE.get(entry.get("role"), DEFAULT_ROLE_WEIGHT)
            for entry, _play in section_entries
        ]
        total_weight = sum(role_weights) or 1
        shares = _rebalance_shares_to_100(
            [max(MIN_PLAY_SHARE_PCT, round(weight / total_weight * 100))
             for weight in role_weights]
        )
        for (entry, _play), share in zip(section_entries, shares):
            entry["share_of_section_pct"] = share
        section_entries.sort(
            key=lambda entry_and_play: -entry_and_play[0]["share_of_section_pct"]
        )

        share_by_formation: dict[str, int] = {}
        for entry, play in section_entries:
            formation_id = play["formation"]
            share_by_formation[formation_id] = (
                share_by_formation.get(formation_id, 0) + entry["share_of_section_pct"]
            )
        section = {
            "section_id": section_id,
            "name": SECTION_DISPLAY_NAME[section_id],
            "formations": sorted(share_by_formation),
            "target_snap_share_pct": SECTION_TARGET_SNAP_SHARE[section_id],
        }
        if len(share_by_formation) > 1:
            section["formation_usage_split"] = dict(sorted(share_by_formation.items()))
        section["plays"] = [entry for entry, _play in section_entries]
        formation_sections.append(section)
        total_play_count += len(section_entries)

    playbook["formation_sections"] = formation_sections
    playbook["notes"] = (
        "MASTER / REFERENCE playbook — every play from every disguise family is "
        "folded in (regenerate with tools/expand-playbook/expand.py). This is a "
        "library, not a game-day install; cut it down per opponent. Section "
        "shares are role-weighted approximations.\n"
    )

    header_comment = (
        "# GENERATED by tools/expand-playbook/expand.py — do not hand-edit.\n"
        "# Master playbook: every disguise-family play folded in.\n"
    )
    PLAYBOOK_PATH.write_text(
        header_comment
        + yaml.dump(playbook, sort_keys=False, default_flow_style=False,
                    allow_unicode=True, width=100)
    )
    print(f"Wrote {PLAYBOOK_PATH.relative_to(REPO_ROOT)} — {total_play_count} plays "
          f"across {len(formation_sections)} sections.")
    if skipped_play_ids:
        print(f"Skipped (no file / unmapped formation): {skipped_play_ids}")


if __name__ == "__main__":
    main()
