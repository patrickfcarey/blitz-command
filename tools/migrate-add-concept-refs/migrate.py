#!/usr/bin/env python3
"""Migration: add concept_ref fields to existing play files.

Infers run_concept_ref, pass_concept_ref, pass_protection_ref, and
philosophy_ref from existing tags, names, and philosophy fields.

Usage:
    python3 tools/migrate-add-concept-refs/migrate.py [--dry-run]

    --dry-run  Print what would change without writing files.

Acceptance criteria:
    >80% of run plays get run_concept_ref
    >80% of pass plays get pass_concept_ref
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
PLAYS_DIR = REPO_ROOT / "data" / "plays"
CONCEPTS_DIR = REPO_ROOT / "data" / "concepts"

# --- Inference maps ---

# Map of tag/name substrings → run_concept_ref
RUN_CONCEPT_HINTS: list[tuple[str, str]] = [
    # (substring to search in name.lower() + tags, concept_id)
    ("power-o", "power"),
    ("power o", "power"),
    ("power run", "power"),
    ("-power", "power"),
    ("power", "power"),
    ("counter trey", "counter-trey"),
    ("counter-trey", "counter-trey"),
    ("iso ", "iso"),
    ("-iso", "iso"),
    ("iso$", "iso"),
    ("inside zone", "inside-zone"),
    ("inside-zone", "inside-zone"),
    ("outside zone", "outside-zone"),
    ("outside-zone", "outside-zone"),
    ("stretch", "stretch"),
    ("trap", "trap"),
    ("draw", "draw"),
    ("lead toss", "lead-toss"),
    ("lead-toss", "lead-toss"),
    ("sweep", "sweep"),
    ("buck sweep", "sweep"),
    ("pin and pull", "pin-and-pull"),
    ("pin-and-pull", "pin-and-pull"),
    ("crack toss", "crack-toss"),
    ("crack-toss", "crack-toss"),
    ("triple option", "triple-option-veer"),
    ("triple-option", "triple-option-veer"),
    ("midline option", "midline-option"),
    ("midline-option", "midline-option"),
    ("wham", "wham"),
    ("fb dive", "iso"),
    ("fb-dive", "iso"),
    ("belly", "inside-zone"),
]

# Map for pass_concept_ref
PASS_CONCEPT_HINTS: list[tuple[str, str]] = [
    ("mesh", "mesh"),
    ("smash", "smash"),
    ("snag", "snag"),
    ("stick", "stick"),
    ("flood", "flood"),
    ("four verticals", "four-verticals"),
    ("four-verticals", "four-verticals"),
    ("4 verts", "four-verticals"),
    ("4-verts", "four-verticals"),
    ("drive", "drive"),
    ("hi-lo", "hi-lo"),
    ("hi lo", "hi-lo"),
    ("levels", "levels"),
    ("dagger", "dagger"),
    ("sail", "sail"),
    ("post corner", "post-corner"),
    ("post-corner", "post-corner"),
    ("slant flat", "slant-flat"),
    ("slant-flat", "slant-flat"),
    ("double slant", "double-slant"),
    ("double-slant", "double-slant"),
    ("switch", "switch"),
    ("y-cross", "drive"),
    ("pa cross", "drive"),
    ("pa-cross", "drive"),
    ("bootleg", "sail"),
    ("naked", "sail"),
    ("waggle", "sail"),
]

# Map for pass_protection_ref
PASS_PROTECTION_HINTS: list[tuple[str, str]] = [
    ("slide left", "full-slide-left"),
    ("slide-left", "full-slide-left"),
    ("slide right", "full-slide-right"),
    ("slide-right", "full-slide-right"),
    ("max protection", "max-protection-7-man"),
    ("max-protection", "max-protection-7-man"),
    ("boss", "boss-pickup"),
]

# Map for philosophy_ref (by philosophy string value)
PHILOSOPHY_REF_MAP: dict[str, str] = {
    "power-run": "power-run",
    "west-coast": "west-coast",
    "air-raid": "air-raid",
    "spread-option": "spread-option",
    "veer-option": "veer-option",
    "wing-t": "wing-t",
    "run-and-shoot": "run-and-shoot",
    "coryell": "coryell",
    "pro-style": "pro-style",
    "erhardt-perkins": "erhardt-perkins",
    "shanahan-zone": "shanahan-zone",
    "mcvay-rams": "mcvay-rams",
    "wildcat": "wildcat",
    "option-heavy": "option-heavy",
    "flexbone": "flexbone",
    "high-school-power": "high-school-power",
    "sec-power-run": "sec-power-run",
    "rpo-heavy": "rpo-heavy",
}

# Validate candidate refs exist on disk
_run_concept_ids: set[str] = {p.stem for p in (CONCEPTS_DIR / "run-concepts").glob("*.yaml")}
_pass_concept_ids: set[str] = {p.stem for p in (CONCEPTS_DIR / "pass-concepts").glob("*.yaml")}
_pass_prot_ids: set[str] = {p.stem for p in (CONCEPTS_DIR / "pass-protections").glob("*.yaml")}
_philosophy_ids: set[str] = {p.stem for p in (CONCEPTS_DIR / "philosophies").glob("*.yaml")}


def _infer(text: str, hints: list[tuple[str, str]], valid_ids: set[str]) -> str | None:
    """Return first matching concept id from hints list."""
    text_lower = text.lower()
    for hint, concept_id in hints:
        if hint in text_lower and concept_id in valid_ids:
            return concept_id
    return None


def _infer_refs(play: dict) -> dict[str, str | None]:
    """Return inferred concept refs for a play."""
    play_type = play.get("play_type", "")
    name = play.get("name", "")
    tags_str = " ".join(play.get("tags", []))
    aliases_str = " ".join(play.get("aliases", []))
    search_text = f"{name} {tags_str} {aliases_str}"

    refs: dict[str, str | None] = {
        "run_concept_ref": None,
        "pass_concept_ref": None,
        "pass_protection_ref": None,
        "philosophy_ref": None,
    }

    if play_type in ("run",):
        refs["run_concept_ref"] = _infer(search_text, RUN_CONCEPT_HINTS, _run_concept_ids)

    if play_type in ("pass", "rpo"):
        refs["pass_concept_ref"] = _infer(search_text, PASS_CONCEPT_HINTS, _pass_concept_ids)
        refs["pass_protection_ref"] = _infer(search_text, PASS_PROTECTION_HINTS, _pass_prot_ids)

    if play_type == "play-action":
        refs["run_concept_ref"] = _infer(search_text, RUN_CONCEPT_HINTS, _run_concept_ids)
        refs["pass_concept_ref"] = _infer(search_text, PASS_CONCEPT_HINTS, _pass_concept_ids)

    if play_type == "screen":
        refs["pass_protection_ref"] = _infer(search_text, PASS_PROTECTION_HINTS, _pass_prot_ids)

    phil = play.get("philosophy", "")
    if phil and phil in _philosophy_ids:
        refs["philosophy_ref"] = phil
    elif phil and phil in PHILOSOPHY_REF_MAP and PHILOSOPHY_REF_MAP[phil] in _philosophy_ids:
        refs["philosophy_ref"] = PHILOSOPHY_REF_MAP[phil]

    return refs


def _insert_refs_into_yaml(path: Path, refs: dict[str, str | None]) -> bool:
    """Read YAML, add non-null refs after the 'philosophy' field, write back. Returns True if changed."""
    with open(path) as f:
        content = f.read()

    data = yaml.safe_load(content)
    if not data:
        return False

    changed = False
    for key, val in refs.items():
        if val and key not in data:
            data[key] = val
            changed = True

    if not changed:
        return False

    # Rebuild YAML preserving field order: insert ref fields after 'philosophy'
    # We do a simple text injection rather than full yaml.dump to preserve style.
    lines = content.split("\n")
    insert_lines: list[str] = []
    for key, val in refs.items():
        if val and key not in content:
            insert_lines.append(f"{key}: {val}")

    if not insert_lines:
        return False

    # Find the line with 'philosophy:' and insert after it
    insert_after = None
    for i, line in enumerate(lines):
        if line.startswith("philosophy:"):
            insert_after = i
            break
    # Fallback: insert before 'era:'
    if insert_after is None:
        for i, line in enumerate(lines):
            if line.startswith("era:"):
                insert_after = i - 1
                break
    # Last resort: insert before 'tags:'
    if insert_after is None:
        for i, line in enumerate(lines):
            if line.startswith("tags:"):
                insert_after = i - 1
                break

    if insert_after is not None:
        for j, new_line in enumerate(insert_lines):
            lines.insert(insert_after + 1 + j, new_line)
        with open(path, "w") as f:
            f.write("\n".join(lines))
        return True

    return False


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="Print changes without writing")
    args = parser.parse_args()

    play_files = sorted(PLAYS_DIR.glob("*.yaml"))

    stats = {"total": 0, "run": 0, "run_got_ref": 0, "pass": 0, "pass_got_ref": 0, "changed": 0}

    for path in play_files:
        try:
            with open(path) as f:
                play = yaml.safe_load(f)
            if not play:
                continue
        except Exception as e:
            print(f"WARN: could not read {path.name}: {e}", file=sys.stderr)
            continue

        stats["total"] += 1
        play_type = play.get("play_type", "")
        if play_type == "run":
            stats["run"] += 1
        elif play_type in ("pass", "rpo"):
            stats["pass"] += 1

        refs = _infer_refs(play)
        new_refs = {k: v for k, v in refs.items() if v and k not in play}

        if not new_refs:
            continue

        if args.dry_run:
            print(f"  {path.name}: would add {new_refs}")
        else:
            changed = _insert_refs_into_yaml(path, new_refs)
            if changed:
                stats["changed"] += 1
                if play_type == "run" and new_refs.get("run_concept_ref"):
                    stats["run_got_ref"] += 1
                if play_type in ("pass", "rpo") and new_refs.get("pass_concept_ref"):
                    stats["pass_got_ref"] += 1

    # Report
    print(f"\nMigration complete:")
    print(f"  Total plays processed: {stats['total']}")
    if not args.dry_run:
        print(f"  Files modified: {stats['changed']}")
    print(f"  Run plays: {stats['run']}, got run_concept_ref: {stats['run_got_ref']}")
    print(f"  Pass plays: {stats['pass']}, got pass_concept_ref: {stats['pass_got_ref']}")

    if stats["run"] > 0:
        pct = stats["run_got_ref"] / stats["run"] * 100
        status = "PASS" if pct >= 80 else "FAIL"
        print(f"  Run coverage: {pct:.0f}% [{status}]")
    if stats["pass"] > 0:
        pct = stats["pass_got_ref"] / stats["pass"] * 100
        status = "PASS" if pct >= 80 else "FAIL"
        print(f"  Pass coverage: {pct:.0f}% [{status}]")


if __name__ == "__main__":
    main()
