#!/usr/bin/env python3
"""Backfill `flip_reads` onto every directional run play.

`flip_reads` (schema sibling of `defensive_counters`) are pre-snap alignment
reads that tell the QB to FLIP the run — `mirror-play` flips the play to the
other side, `mirror-formation` flips the whole formation. They were authored
by hand on three exemplar run plays; this script fills in the rest.

The content of a flip_read is side-agnostic ("the called side", "the
formation's strength") and `flip_to` is an enum, not a play reference — so a
base play and its `-left` mirror get IDENTICAL flip_reads.

Plays are bucketed by run scheme (inside gap / perimeter / zone / option /
RPO); each bucket gets a two-read template — one front-based `mirror-play`
read and one strength-declare `mirror-formation` read. Pure non-directional
runs (QB sneak) are skipped.

Idempotent: a play that already has `flip_reads` is left untouched.

Run from the repo root:
    python3 tools/backfill-flip-reads/backfill.py
"""
from __future__ import annotations

from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
PLAYS_DIR = REPO_ROOT / "data" / "plays"

MIRROR_SUFFIX = "-left"                      # a left-mirror play is "<base>-left"
RUN_PLAY_TYPES = ("run", "rpo", "option")    # play_types this script gives flip_reads

INSIDE_GAP_TEMPLATE = [
    {
        "flip_id": "front-overshift-callside",
        "pre_snap_look": "Defensive front slid toward the called side — an extra down "
        "lineman or a walked-up linebacker puts +1 in the called-side box.",
        "qb_key": "Count the box side to side — the called side has one more hat than "
        "the backside.",
        "read_category": "box-count",
        "flip_to": "mirror-play",
        "why": "Running a gap scheme into the overshift is into the teeth; flipping the "
        "play attacks the lighter box with the same blocking math.",
        "typical_against": ["over-front", "shifted 4-3"],
    },
    {
        "flip_id": "strength-declared-to-formation",
        "pre_snap_look": "Defense has fully declared to the formation's strength — an "
        "extra box defender to the strong side and a safety rolled down over it.",
        "qb_key": "Check the strength side — both the box count and the safety roll are "
        "committed to it.",
        "read_category": "safety-shell",
        "flip_to": "mirror-formation",
        "why": "When the defense keys the formation's strength, flipping the whole "
        "formation forces a re-declare and the run hits the side they vacated.",
        "typical_against": ["cover-3 with strong roll", "8-man fronts"],
    },
]

PERIMETER_TEMPLATE = [
    {
        "flip_id": "force-set-callside",
        "pre_snap_look": "The playside force defender (corner or outside linebacker) is "
        "aligned tight and downhill with run support set hard to the called side.",
        "qb_key": "Check the playside edge — force defender squatted and downhill, no "
        "cushion.",
        "read_category": "cb-leverage",
        "flip_to": "mirror-play",
        "why": "A perimeter run into a set force defender has no edge; flipping to the "
        "side with a soft, depth-aligned corner gives the play the room it needs.",
        "typical_against": ["cover-2 with hard corners", "cloud support"],
    },
    {
        "flip_id": "alley-stacked-formation",
        "pre_snap_look": "Defense has stacked the alley to the formation's strength — an "
        "extra defender plus a rolled safety filling the strong-side perimeter.",
        "qb_key": "Check the strong-side alley — it is stacked while the backside alley "
        "is open.",
        "read_category": "box-count",
        "flip_to": "mirror-formation",
        "why": "Flipping the formation relocates the strength and the run target away "
        "from the stacked alley, forcing the defense to re-rotate or surrender the edge.",
        "typical_against": ["quarters with strong roll", "8-man fronts"],
    },
]

ZONE_TEMPLATE = [
    {
        "flip_id": "three-tech-callside",
        "pre_snap_look": "The 3-technique tackle and the playside linebacker are both "
        "set to the called side, loading the front-side gaps the zone is aiming for.",
        "qb_key": "Find the 3-technique — it is aligned to the called side, in the "
        "zone's path.",
        "read_category": "dl-alignment",
        "flip_to": "mirror-play",
        "why": "Zone run into the 3-technique blocks the penetrator head-on; flipping "
        "the zone away runs at the lighter shade and a cleaner front-side double.",
        "typical_against": ["over-front", "shifted 4-3"],
    },
    {
        "flip_id": "strength-declared-to-formation",
        "pre_snap_look": "Defense has declared to the formation's strength — an extra "
        "box defender to the strong side with a safety rolled down to support it.",
        "qb_key": "Check the strength side — the box count and the safety roll are both "
        "committed to it.",
        "read_category": "safety-shell",
        "flip_to": "mirror-formation",
        "why": "Flipping the whole formation re-locates the strength call; a defense "
        "slow to re-set leaves the front-side gaps the zone wants unfilled.",
        "typical_against": ["cover-3 with strong roll", "quarters with strong roll"],
    },
]

OPTION_TEMPLATE = [
    {
        "flip_id": "keys-set-callside",
        "pre_snap_look": "The dive key and the pitch key (first two defenders outside "
        "the tackle) are both aligned hard and downhill to the called side.",
        "qb_key": "Scan the called-side edge — both option keys are squatted and "
        "committed, no width left to read.",
        "read_category": "dl-alignment",
        "flip_to": "mirror-play",
        "why": "An option into keys that are already set gives the QB no honest read; "
        "flipping the option attacks the side where the keys still have to choose.",
        "typical_against": ["over-front", "cover-1 with edge pressure"],
    },
    {
        "flip_id": "strength-declared-to-formation",
        "pre_snap_look": "Defense has declared to the formation's strength — an extra "
        "perimeter defender and a safety rolled down to the strong side.",
        "qb_key": "Check the strength side — the extra hat and the safety roll are "
        "committed to it.",
        "read_category": "safety-shell",
        "flip_to": "mirror-formation",
        "why": "Flipping the formation moves the option away from the loaded perimeter "
        "and forces the defense to re-declare its keys.",
        "typical_against": ["cover-3 with strong roll", "8-man fronts"],
    },
]

RPO_TEMPLATE = [
    {
        "flip_id": "box-overload-callside",
        "pre_snap_look": "The box is overloaded to the run side — the defense has +1 to "
        "the run side while leaving the conflict defender's grass open.",
        "qb_key": "Count the box to the run side — it is heavy, the give is no longer "
        "the answer.",
        "read_category": "box-count",
        "flip_to": "mirror-play",
        "why": "Flipping the run portion away from the overload keeps the box count "
        "honest, so the give stays a live answer instead of a forced throw.",
        "typical_against": ["over-front", "8-man fronts"],
    },
    {
        "flip_id": "strength-declared-to-formation",
        "pre_snap_look": "Defense has declared fully to the formation's strength — an "
        "extra box defender and a safety rolled down over the passing strength.",
        "qb_key": "Check the strength side — both the box count and the safety roll are "
        "set to it.",
        "read_category": "safety-shell",
        "flip_to": "mirror-formation",
        "why": "Flipping the formation re-sets the defense's strength call and "
        "rebalances the RPO conflict so both the run and the throw stay viable.",
        "typical_against": ["cover-3 with strong roll", "quarters with strong roll"],
    },
]


def _flip_read_template(base_play_id: str, play_type: str) -> list | None:
    """Pick the flip_read template for a run play, keyed on its scheme.

    Returns None for non-directional runs (a QB sneak or kneel), which have
    no 'flip the play' decision to make. Scheme is detected from tokens in
    the base play_id. The `counter` check deliberately precedes the
    perimeter and zone checks: a toss-counter or a zone-counter is a
    gap-scheme counter, not a perimeter toss or a zone run.
    """
    if "sneak" in base_play_id or "kneel" in base_play_id:
        return None
    if play_type == "rpo":
        return RPO_TEMPLATE
    option_tokens = ("triple-option", "speed-option", "-option",
                     "veer", "midline", "-read", "counter-keep")
    if any(token in base_play_id for token in option_tokens):
        return OPTION_TEMPLATE
    if "counter" in base_play_id:
        return INSIDE_GAP_TEMPLATE
    perimeter_tokens = ("toss", "sweep", "reverse", "jet", "stretch")
    if any(token in base_play_id for token in perimeter_tokens):
        return PERIMETER_TEMPLATE
    if "zone" in base_play_id:
        return ZONE_TEMPLATE
    return INSIDE_GAP_TEMPLATE


def main() -> None:
    """Add flip_reads to every directional run play that lacks them."""
    plays_updated: list[str] = []
    plays_skipped_existing: list[str] = []
    plays_skipped_nondirectional: list[str] = []
    for play_file in sorted(PLAYS_DIR.glob("*.yaml")):
        play = yaml.safe_load(play_file.read_text())
        if not play or play.get("play_type") not in RUN_PLAY_TYPES:
            continue
        play_id = play["play_id"]
        if play.get("flip_reads"):
            plays_skipped_existing.append(play_id)
            continue
        base_play_id = play_id.removesuffix(MIRROR_SUFFIX)
        flip_read_template = _flip_read_template(base_play_id, play.get("play_type"))
        if flip_read_template is None:
            plays_skipped_nondirectional.append(play_id)
            continue
        flip_reads_yaml_block = yaml.dump(
            {"flip_reads": flip_read_template}, sort_keys=False,
            default_flow_style=False, allow_unicode=True, width=92,
        )
        original_text = play_file.read_text()
        if not original_text.endswith("\n"):
            original_text += "\n"
        updated_text = original_text + flip_reads_yaml_block
        # Re-parse the result before writing so a malformed append can never
        # land on disk.
        if not yaml.safe_load(updated_text).get("flip_reads"):
            raise SystemExit(f"parse check failed for {play_id}")
        play_file.write_text(updated_text)
        plays_updated.append(play_id)

    print(f"flip_reads added to {len(plays_updated)} plays")
    print(f"already had flip_reads (skipped): {len(plays_skipped_existing)} -> "
          f"{sorted(plays_skipped_existing)}")
    print(f"non-directional (skipped): {len(plays_skipped_nondirectional)} -> "
          f"{sorted(plays_skipped_nondirectional)}")


if __name__ == "__main__":
    main()
