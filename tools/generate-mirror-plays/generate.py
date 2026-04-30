#!/usr/bin/env python3
"""Generate left-handed mirror plays for every right-handed play.

For each play in data/plays/ that isn't already a mirror and whose mirror
formation exists, creates a <stem>-left.yaml (or replaces '-right-' with
'-left-' in the stem) with:

- formation reference flipped to the mirror formation (e.g. i-formation -> i-formation-left)
- play_id stem flipped
- name updated ('Right' -> 'Left', or appended)
- All path and alt_paths waypoints negated on x
- All motion end_positions negated on x
- A breadcrumb appended to source_notes

Routes are NOT touched — the drawing tool already mirrors them automatically
based on the receiver's x position.

Skips plays whose target mirror already exists, or where the mirror
formation isn't built yet.

Run from repo root:
    python3.11 tools/generate-mirror-plays/generate.py
"""
from __future__ import annotations

import copy
import sys
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
PLAYS_DIR = REPO_ROOT / "data" / "plays"
FORMATIONS_DIR = REPO_ROOT / "data" / "formations"


def mirror_stem(stem: str) -> str | None:
    """Return the left-mirror stem, or None if `stem` is already a mirror."""
    if "-right-" in stem:
        return stem.replace("-right-", "-left-")
    if stem.endswith("-left") or "-left-" in stem:
        return None
    return f"{stem}-left"


def mirror_formation_id(fid: str) -> str:
    """Return the mirror formation id."""
    if "-right" in fid:
        return fid.replace("-right", "-left")
    if fid.endswith("-left"):
        return fid
    return f"{fid}-left"


def mirror_play(play: dict, original_stem: str) -> dict:
    new = copy.deepcopy(play)

    # play_id
    new["play_id"] = mirror_stem(original_stem) or new.get("play_id", original_stem)

    # formation reference
    fid = new.get("formation")
    if fid:
        new["formation"] = mirror_formation_id(fid)

    # name
    name = new.get("name", "")
    if "Right" in name:
        new["name"] = name.replace("Right", "Left")
    elif "(Mirror" not in name and "Left" not in name:
        new["name"] = f"{name} (Mirror Left)"

    # motions
    for motion in new.get("motions", []):
        ep = motion.get("end_position")
        if ep and "x" in ep:
            ep["x"] = -ep["x"]

    # assignments — paths and alt_paths
    for assignment in new.get("assignments", []):
        if "path" in assignment:
            assignment["path"] = [[-wp[0], wp[1]] for wp in assignment["path"]]
        for alt in assignment.get("alt_paths", []):
            alt["path"] = [[-wp[0], wp[1]] for wp in alt["path"]]

    # source_notes breadcrumb
    notes = new.setdefault("source_notes", [])
    notes.append(
        f"Mirror of {original_stem}.yaml — path waypoints flipped on x; "
        f"formation reference points to the mirror formation. Routes auto-mirror "
        f"in the drawing tool based on receiver side. Narrative notes may still "
        f"describe the original right-handed look — coordinates and paths are "
        f"the source of truth."
    )

    return new


def main() -> int:
    created = 0
    skipped: list[str] = []
    for path in sorted(PLAYS_DIR.glob("*.yaml")):
        stem = path.stem
        new_stem = mirror_stem(stem)
        if new_stem is None:
            continue  # already a mirror

        target_path = PLAYS_DIR / f"{new_stem}.yaml"
        if target_path.exists():
            skipped.append(f"{new_stem} (already exists)")
            continue

        with open(path) as f:
            play = yaml.safe_load(f)

        fid = play.get("formation")
        if fid:
            mirror_fid = mirror_formation_id(fid)
            mirror_form_path = FORMATIONS_DIR / f"{mirror_fid}.yaml"
            if not mirror_form_path.exists():
                skipped.append(f"{new_stem} (mirror formation '{mirror_fid}' missing)")
                continue

        new_play = mirror_play(play, stem)

        with open(target_path, "w") as f:
            yaml.safe_dump(
                new_play,
                f,
                sort_keys=False,
                default_flow_style=False,
                width=120,
                allow_unicode=True,
            )

        print(f"generated {new_stem}.yaml from {stem}.yaml")
        created += 1

    print()
    print(f"Created {created} mirror plays.")
    if skipped:
        print("Skipped:")
        for s in skipped[:30]:
            print(f"  - {s}")
        if len(skipped) > 30:
            print(f"  ... and {len(skipped) - 30} more")
    return 0


if __name__ == "__main__":
    sys.exit(main())
