#!/usr/bin/env python3
"""Compile a playbook's glossary from the plays it contains.

A playbook's glossary is the set of routes and concepts its plays reference,
each paired with the `description` from its own data file — plus any
playbook-specific terms authored in front_matter.glossary_additions.

The glossary is never stored: it is compiled on demand (here) so it can never
drift from the plays. This module is shared — the playbook-generation MCP
exposes it as the `playbook_glossary` tool, and the detailed print tool
imports it to build the glossary pages of the PDF.

Routes and run/pass concepts resolve cleanly to a data file with a
`description`. Other terms a reader needs (blocking techniques, coverage
terms, audible call names) have no single data file and belong in the
authored front_matter.glossary_additions instead.

CLI — prints the compiled glossary as JSON:
    python3 tools/compile-glossary/compile_glossary.py data/playbooks/hs-base.yaml
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
PLAYS_DIR = REPO_ROOT / "data" / "plays"
ROUTES_DIR = REPO_ROOT / "data" / "routes"
RUN_CONCEPTS_DIR = REPO_ROOT / "data" / "concepts" / "run-concepts"
PASS_CONCEPTS_DIR = REPO_ROOT / "data" / "concepts" / "pass-concepts"

# Glossary category -> (data directory, human-readable label). Each of these
# data files is known to carry a `name` and a `description` field.
TERM_SOURCE_BY_CATEGORY = {
    "route": (ROUTES_DIR, "Route"),
    "run-concept": (RUN_CONCEPTS_DIR, "Run concept"),
    "pass-concept": (PASS_CONCEPTS_DIR, "Pass concept"),
}
ADDITIONS_SOURCE_LABEL = "front_matter.glossary_additions"
DEFAULT_ADDITION_CATEGORY = "other"


def _load_yaml(path: Path) -> dict:
    """Parse a YAML file into a dict (an empty file yields None)."""
    with open(path, encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def _collect_terms_from_play(play: dict) -> dict[str, set[str]]:
    """Return {category: set of term ids} for one play's routes and concepts."""
    route_ids: set[str] = set()
    run_concept_ids: set[str] = set()
    pass_concept_ids: set[str] = set()

    for assignment in play.get("assignments", []) or []:
        route_name = assignment.get("route_name")
        if route_name:
            route_ids.add(route_name)

    if play.get("run_concept_ref"):
        run_concept_ids.add(play["run_concept_ref"])
    if play.get("pass_concept_ref"):
        pass_concept_ids.add(play["pass_concept_ref"])

    for concept in play.get("concepts", []) or []:
        concept_ref = concept.get("concept_ref")
        if not concept_ref:
            continue
        if concept.get("concept_type") == "run":
            run_concept_ids.add(concept_ref)
        else:
            pass_concept_ids.add(concept_ref)

    return {
        "route": route_ids,
        "run-concept": run_concept_ids,
        "pass-concept": pass_concept_ids,
    }


def compile_glossary(playbook_path: Path) -> list[dict]:
    """Compile the glossary for the playbook at `playbook_path`.

    Walks every play in the playbook's formation_sections, collects the
    routes and concepts they use, resolves each to the `description` in its
    data file, and merges any front_matter.glossary_additions. Returns a list
    of {term, definition, category, source} dicts sorted by category then
    term. Terms that do not resolve to a data file are skipped.
    """
    playbook = _load_yaml(Path(playbook_path))

    # Collect the unique term ids per category across every play installed in
    # the playbook's formation_sections (its play spine).
    term_ids_by_category: dict[str, set[str]] = {
        category: set() for category in TERM_SOURCE_BY_CATEGORY
    }
    for section in playbook.get("formation_sections", []):
        for play_entry in section.get("plays", []):
            play_path = PLAYS_DIR / f"{play_entry['play_id']}.yaml"
            if not play_path.exists():
                continue
            play = _load_yaml(play_path)
            if not play:
                continue
            for category, term_ids in _collect_terms_from_play(play).items():
                term_ids_by_category[category].update(term_ids)

    # Resolve each collected term to its data-file name + description.
    glossary: list[dict] = []
    for category, term_ids in term_ids_by_category.items():
        data_dir, _label = TERM_SOURCE_BY_CATEGORY[category]
        for term_id in term_ids:
            term_path = data_dir / f"{term_id}.yaml"
            if not term_path.exists():
                continue
            term_data = _load_yaml(term_path) or {}
            glossary.append({
                "term": term_data.get("name", term_id),
                "definition": (term_data.get("description") or "").strip(),
                "category": category,
                "source": str(term_path.relative_to(REPO_ROOT)),
            })

    # Merge the authored, playbook-specific terms.
    front_matter = playbook.get("front_matter") or {}
    for addition in front_matter.get("glossary_additions") or []:
        glossary.append({
            "term": addition["term"],
            "definition": (addition.get("definition") or "").strip(),
            "category": addition.get("category", DEFAULT_ADDITION_CATEGORY),
            "source": ADDITIONS_SOURCE_LABEL,
        })

    glossary.sort(key=lambda entry: (entry["category"], entry["term"].lower()))
    return glossary


def main() -> int:
    """CLI entry point: print the compiled glossary for a playbook as JSON."""
    if len(sys.argv) != 2:
        print("usage: compile_glossary.py <playbook.yaml>", file=sys.stderr)
        return 2
    playbook_path = Path(sys.argv[1])
    if not playbook_path.exists():
        print(f"error: {playbook_path} not found", file=sys.stderr)
        return 2
    print(json.dumps(compile_glossary(playbook_path), indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
