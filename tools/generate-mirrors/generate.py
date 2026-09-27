#!/usr/bin/env python3
"""Generate left-handed mirror files for every right-handed offensive formation.

For each formation in data/formations/ that isn't already a mirror and
isn't symmetric, creates a <stem>-left.yaml (or replaces 'Right' with
'Left' in the stem if the original name contains 'right') with:

  - x coordinates flipped (non-OL players only; OL labels stay symmetric)
  - strength_side flipped (right <-> left; balanced stays)
  - name updated ('Right' -> 'Left', else suffix ' Left')
  - source_notes appended with a 'mirror of <original>' breadcrumb

Symmetric formations (e.g. full-house) are skipped.

Run from the repo root:
    python tools/generate-mirrors/generate.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
FORMATIONS_DIR = REPO_ROOT / "data" / "formations"
INTERIOR_OL = {"LT", "LG", "C", "RG", "RT"}

# Symmetric — don't mirror
SKIP_SYMMETRIC = {"full-house"}

# Stems that already encode direction
DIRECTION_RENAMES = {
    "shotgun-trips-right": "shotgun-trips-left",
    "trey-right": "trey-left",
}


def main() -> int:
    created = 0
    skipped: list[str] = []
    for path in sorted(FORMATIONS_DIR.glob("*.yaml")):
        stem = path.stem
        if stem.endswith("-left"):
            continue
        if stem in SKIP_SYMMETRIC:
            skipped.append(f"{stem} (symmetric)")
            continue

        with open(path) as f:
            data = yaml.safe_load(f)

        if data.get("side") != "offense":
            skipped.append(f"{stem} (not offense)")
            continue

        # Flip strength_side
        ss = data.get("strength_side")
        if ss == "right":
            data["strength_side"] = "left"
        elif ss == "left":
            data["strength_side"] = "right"
        # 'balanced' stays

        # Flip x for non-OL players
        for p in data.get("players", []):
            if p["position"] not in INTERIOR_OL:
                p["x"] = -p["x"]

        # Update name
        name = data.get("name", "")
        if "Right" in name:
            data["name"] = name.replace("Right", "Left")
        elif "Left" not in name:
            data["name"] = name + " Left"

        # Add mirror breadcrumb to source_notes
        notes = data.setdefault("source_notes", [])
        notes.append(
            f"Mirror of {stem}.yaml — coordinates flipped horizontally on x; "
            f"strength_side flipped; OL labels (LT/LG/C/RG/RT) and centered "
            f"backfield positions (QB / centered FB or HB) unchanged. Notes "
            f"in this file may still describe the original right-handed look "
            f"in places — read coordinates as the source of truth."
        )

        # Determine output stem
        mirror_stem = DIRECTION_RENAMES.get(stem, f"{stem}-left")
        mirror_path = FORMATIONS_DIR / f"{mirror_stem}.yaml"

        # Don't overwrite — fail loudly if mirror already exists
        if mirror_path.exists():
            print(f"WARN: {mirror_path.name} already exists — skipping. "
                  f"Delete it first if you want to regenerate.", file=sys.stderr)
            continue

        with open(mirror_path, "w") as f:
            yaml.safe_dump(
                data,
                f,
                sort_keys=False,
                allow_unicode=True,
                default_flow_style=False,
                width=120,
            )

        print(f"generated {mirror_stem}.yaml from {stem}.yaml")
        created += 1

    print()
    print(f"Created {created} mirror formations.")
    if skipped:
        print("Skipped:")
        for s in skipped:
            print(f"  - {s}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
