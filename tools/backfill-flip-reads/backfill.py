#!/usr/bin/env python3
"""Backfill `flip_reads` onto every directional run play.

`flip_reads` (schema sibling of `defensive_counters`) are pre-snap alignment
reads that tell the QB to FLIP the run — `mirror-play` flips the play to the
other side, `mirror-formation` flips the whole formation. They were authored
by hand on three exemplar plays in Phase; this fills in the rest.

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

REPO = Path(__file__).resolve().parents[2]
PLAYS_DIR = REPO / "data" / "plays"

INSIDE_GAP = [
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

PERIMETER = [
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

ZONE = [
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

OPTION = [
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

RPO = [
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


def _bucket(base_id: str, play_type: str) -> list | None:
    """Return the flip_read template for a play, or None to skip it."""
    pid = base_id
    if "sneak" in pid or "kneel" in pid:
        return None
    if play_type == "rpo":
        return RPO
    if any(t in pid for t in ("triple-option", "speed-option", "-option",
                              "veer", "midline", "-read", "counter-keep")):
        return OPTION
    if "counter" in pid:
        return INSIDE_GAP
    if any(t in pid for t in ("toss", "sweep", "reverse", "jet", "stretch")):
        return PERIMETER
    if "zone" in pid:
        return ZONE
    return INSIDE_GAP


def main() -> None:
    added, skipped_existing, skipped_nondir, untouched = [], [], [], []
    for pf in sorted(PLAYS_DIR.glob("*.yaml")):
        play = yaml.safe_load(pf.read_text())
        if not play or play.get("play_type") not in ("run", "rpo", "option"):
            continue
        pid = play["play_id"]
        if play.get("flip_reads"):
            skipped_existing.append(pid)
            continue
        base = pid[:-5] if pid.endswith("-left") else pid
        template = _bucket(base, play.get("play_type"))
        if template is None:
            skipped_nondir.append(pid)
            continue
        block = yaml.dump({"flip_reads": template}, sort_keys=False,
                          default_flow_style=False, allow_unicode=True, width=92)
        text = pf.read_text()
        if not text.endswith("\n"):
            text += "\n"
        new_text = text + block
        # parse-check before writing
        parsed = yaml.safe_load(new_text)
        if not parsed.get("flip_reads"):
            raise SystemExit(f"parse check failed for {pid}")
        pf.write_text(new_text)
        added.append(pid)

    print(f"flip_reads added to {len(added)} plays")
    print(f"already had flip_reads (skipped): {len(skipped_existing)} -> "
          f"{sorted(skipped_existing)}")
    print(f"non-directional (skipped): {len(skipped_nondir)} -> {sorted(skipped_nondir)}")


if __name__ == "__main__":
    main()
