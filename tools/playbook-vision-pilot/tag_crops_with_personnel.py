#!/usr/bin/env python3
"""Rename canonical crops to embed expected-personnel tag in the filename.

Each canonical crop gets a personnel tag inserted into its filename:
    old: <family>__<formation>__<play_type>__<play_name>__WIDE.jpg
    new: <family>__<formation>__r<R>f<F>t<T>w<W>__<play_type>__<play_name>__WIDE.jpg

Where r/f/t/w are the expected counts of RB/FB/TE/WR per
`formation_personnel.py`. The LLM reads this from the file path with no
extra prompt overhead.

Also updates _canonical_manifest.json with the renamed filename and a
new `expected_personnel` key per entry.

Idempotent: safe to re-run; only renames files that don't already have
a personnel tag.

Run:
    python3 tag_crops_with_personnel.py [--dir DIR]
"""
from __future__ import annotations
import argparse
import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "tools/playbook-vision-pilot"))
from formation_personnel import personnel_for  # noqa: E402

DEFAULT_DIR = REPO / "tools/playbook-vision-pilot/dedup-crops"


def _personnel_tag(p: dict) -> str:
    return f"r{p['RB']}f{p['FB']}t{p['TE']}w{p['WR']}"


# Match a filename that already has a personnel tag (e.g. r1f0t2w2)
_TAGGED_RE = re.compile(r"__r\d+f\d+t\d+w\d+__")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", type=Path, default=DEFAULT_DIR,
                    help="Directory with canonical crops + manifest.json")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    manifest_path = args.dir / "_canonical_manifest.json"
    if not manifest_path.exists():
        sys.exit(f"manifest missing: {manifest_path}")
    manifest = json.loads(manifest_path.read_text())

    renamed = 0
    skipped = 0
    new_manifest: dict[str, dict] = {}
    for old_filename, info in manifest.items():
        # Compute personnel for this formation.
        p = personnel_for(info["family"], info["formation"])
        tag = _personnel_tag(p)

        # If already tagged, skip rename but ensure manifest has personnel.
        if _TAGGED_RE.search(old_filename):
            skipped += 1
            new_filename = old_filename
        else:
            # Insert tag after the formation slug. Filename pattern:
            # <family-slug>__<formation-slug>__<play_type>__<play_name>__<team>__img<NN>p<P>__WIDE.jpg
            # Insert tag as a new __r#f#t#w#__ field after the formation slug,
            # before the play_type. The formation slug is at most 2 fields
            # (e.g. "singleback-ace-pair"), but the original separator was
            # the play_type field. We just insert `tag__` after the second
            # `__`, which lands it between formation and play_type.
            parts = old_filename.split("__")
            # Original format: parts = [fam-form, play_type, play_name, team, imgX, WIDE.jpg]
            # We insert the tag at position 1.
            new_parts = [parts[0], tag] + parts[1:]
            new_filename = "__".join(new_parts)

        old_path = args.dir / old_filename
        new_path = args.dir / new_filename

        if old_filename != new_filename:
            if not args.dry_run:
                if old_path.exists() and not new_path.exists():
                    old_path.rename(new_path)
                    renamed += 1
            else:
                renamed += 1   # would rename

        # Update manifest entry — keyed by NEW filename for downstream consumers.
        # Store both the renamed file and the personnel hint.
        new_info = {**info,
                    "filename": new_filename,
                    "expected_personnel": p}
        new_manifest[new_filename] = new_info

    if not args.dry_run:
        manifest_path.write_text(json.dumps(new_manifest, indent=2))

    print(f"renamed: {renamed}")
    print(f"already tagged (skipped): {skipped}")
    print(f"manifest entries: {len(new_manifest)}")
    if args.dry_run:
        print("(dry-run — no files touched)")


if __name__ == "__main__":
    main()
