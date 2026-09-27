#!/usr/bin/env python3
"""One-time migration: add a `depth` field to every pass-concept file.

`depth` (quick / medium / deep) is the route-depth axis added to
pass-concept.schema.json. `category` already classifies a concept by route
mechanic; `depth` is the orthogonal "how far downfield" axis. This script
inserts `depth` directly after the `category:` line of each pass-concept
file, preserving all existing formatting and comments.

Idempotent: a file that already has a `depth` field is left untouched.

Run from the repo root:
    python3 tools/migrate-add-pass-depth/migrate.py
"""
from __future__ import annotations

from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
PASS_CONCEPTS_DIR = REPO_ROOT / "data" / "concepts" / "pass-concepts"

# Primary route-depth bucket per pass concept: quick = rhythm game (breaks at
# ~6 yd or less), medium = intermediate (~7-15 yd), deep = shot plays (16+ yd).
DEPTH_BY_CONCEPT = {
    "dagger": "deep",
    "double-slant": "quick",
    "drive": "medium",
    "flood": "medium",
    "four-verticals": "deep",
    "hi-lo": "medium",
    "levels": "medium",
    "mesh": "quick",
    "post-corner": "deep",
    "sail": "medium",
    "slant-flat": "quick",
    "smash": "medium",
    "snag": "quick",
    "spacing": "quick",
    "stick": "quick",
    "switch": "deep",
}


def main() -> None:
    """Insert `depth` after the `category:` line of each pass-concept file."""
    updated, skipped_existing, unmapped = [], [], []
    for concept_path in sorted(PASS_CONCEPTS_DIR.glob("*.yaml")):
        concept = yaml.safe_load(concept_path.read_text())
        concept_id = concept["concept_id"]
        if "depth" in concept:
            skipped_existing.append(concept_id)
            continue
        depth = DEPTH_BY_CONCEPT.get(concept_id)
        if depth is None:
            unmapped.append(concept_id)
            continue
        lines = concept_path.read_text().splitlines(keepends=True)
        for line_index, line in enumerate(lines):
            if line.startswith("category:"):
                lines.insert(line_index + 1, f"depth: {depth}\n")
                concept_path.write_text("".join(lines))
                updated.append(concept_id)
                break
        else:
            unmapped.append(concept_id)

    print(f"depth added to {len(updated)} pass concepts: {sorted(updated)}")
    if skipped_existing:
        print(f"already had depth (skipped): {sorted(skipped_existing)}")
    if unmapped:
        print(f"WARNING: unmapped / no category line: {sorted(unmapped)}")


if __name__ == "__main__":
    main()
