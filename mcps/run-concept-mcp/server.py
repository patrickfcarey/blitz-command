#!/usr/bin/env python3
"""Run Concept Library MCP server.

Exposes blitz-command's run concept library (data/concepts/run-concepts/)
to AI agents over the Model Context Protocol.

Requires Python 3.10+.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import yaml
from jsonschema import ValidationError, validate
from mcp.server.fastmcp import FastMCP

REPO_ROOT = Path(__file__).resolve().parents[2]
CONCEPTS_DIR = REPO_ROOT / "data" / "concepts" / "run-concepts"
SCHEMA_PATH = REPO_ROOT / "schemas" / "run-concept.schema.json"

_SCHEMA_CACHE: dict | None = None


def _load_schema() -> dict:
    global _SCHEMA_CACHE
    if _SCHEMA_CACHE is None:
        with open(SCHEMA_PATH) as f:
            _SCHEMA_CACHE = json.load(f)
    return _SCHEMA_CACHE


_CACHE: dict[str, dict[str, Any]] | None = None
_CACHE_MTIME: float = 0.0


def _load_all() -> dict[str, dict[str, Any]]:
    global _CACHE, _CACHE_MTIME
    current_mtime = CONCEPTS_DIR.stat().st_mtime if CONCEPTS_DIR.exists() else 0.0
    if _CACHE is not None and current_mtime == _CACHE_MTIME:
        return _CACHE
    schema = _load_schema()
    concepts: dict[str, dict[str, Any]] = {}
    for path in sorted(CONCEPTS_DIR.glob("*.yaml")):
        try:
            with open(path) as f:
                data = yaml.safe_load(f)
            if not data:
                continue
            validate(data, schema)
            concepts[path.stem] = data
        except (ValidationError, yaml.YAMLError) as e:
            print(f"WARN: skipping {path.name}: {e}", file=sys.stderr)
    _CACHE = concepts
    _CACHE_MTIME = current_mtime
    return concepts


mcp = FastMCP("run-concept-library")


def _paginate(items: list, cursor: str | None, limit: int) -> dict[str, Any]:
    offset = int(cursor) if cursor else 0
    page = items[offset: offset + limit]
    next_offset = offset + len(page)
    return {
        "items": page,
        "next_cursor": str(next_offset) if next_offset < len(items) else None,
    }


@mcp.tool()
def list_run_concepts(cursor: str | None = None, limit: int = 50) -> dict[str, Any]:
    """List every run concept with brief metadata.

    Returns:
        {
          "items":       [{...}, ...],
          "next_cursor": str | null,
        }

    Item shape:
        {
          "id":       "power",
          "name":     "Power",
          "category": "gap-scheme" | "zone-scheme" | "option" | "man-blocking-scheme" | "misdirection",
          "aim_point": "Off-tackle gap, between playside RT and TE",
          "tags":     ["run", "gap-scheme", "any-level", ...],
        }

    Args:
        cursor: opaque pagination token from the previous call's next_cursor.
        limit: max items per page (default 50).

    Example:
        >>> page = list_run_concepts()
        >>> [c['id'] for c in page['items'] if c['category'] == 'zone-scheme']
        ['inside-zone', 'outside-zone', 'pin-and-pull', 'stretch']
    """
    all_items = [
        {
            "id": cid,
            "name": c.get("name"),
            "category": c.get("category"),
            "aim_point": c.get("aim_point"),
            "tags": c.get("tags", []),
        }
        for cid, c in _load_all().items()
    ]
    return _paginate(all_items, cursor, limit)


@mcp.tool()
def get_run_concept(concept_id: str) -> dict[str, Any]:
    """Get the full run concept definition.

    Returns: concept_id, name, category, description, aim_point, read_tree
    (phase-by-phase defender/decision), blocking_scheme_ref, pulls_required,
    lead_blocker, pairs_with, tags, source_notes.

    Common concept_id values:
        Gap:        'power', 'counter-trey', 'trap', 'iso'
        Zone:       'inside-zone', 'outside-zone', 'stretch', 'pin-and-pull'
        Option:     'triple-option-veer', 'midline-option'
        Misdirection: 'draw', 'wham'
        Perimeter:  'lead-toss', 'sweep', 'crack-toss'

    Args:
        concept_id: file stem (no .yaml extension).
    """
    concepts = _load_all()
    if concept_id not in concepts:
        available = sorted(concepts.keys())
        suggestions = [a for a in available if concept_id in a or a.startswith(concept_id[:5])]
        msg = f"No run concept with id '{concept_id}'."
        if suggestions:
            msg += f" Did you mean: {suggestions[:5]}?"
        else:
            msg += f" {len(available)} concepts available; call list_run_concepts() for ids."
        raise ValueError(msg)
    return concepts[concept_id]


@mcp.tool()
def find_run_concepts_by_category(category: str) -> list[str]:
    """Return concept IDs in the given category.

    Category values:
        'gap-scheme'          — power, counter-trey, trap, iso
        'zone-scheme'         — inside-zone, outside-zone, stretch, pin-and-pull
        'option'              — triple-option-veer, midline-option
        'man-blocking-scheme' — lead-toss, sweep, crack-toss
        'misdirection'        — draw, wham

    Args:
        category: category enum value (case-insensitive).
    """
    cat = category.lower()
    return [cid for cid, c in _load_all().items() if c.get("category", "").lower() == cat]


@mcp.tool()
def find_run_concepts_by_aim_point(aim: str) -> list[str]:
    """Return concept IDs whose aim_point contains the given substring.

    Useful for gap-letter queries: 'A-gap', 'B-gap', 'C-gap', 'off-tackle',
    'perimeter', 'outside', 'inside'.

    Example:
        >>> find_run_concepts_by_aim_point('A-gap')
        ['iso', 'midline-option', 'trap']
        >>> find_run_concepts_by_aim_point('perimeter')
        ['crack-toss', 'lead-toss', 'stretch', 'sweep']

    Args:
        aim: substring to search in aim_point (case-insensitive).
    """
    aim_lower = aim.lower()
    return [
        cid for cid, c in _load_all().items()
        if aim_lower in c.get("aim_point", "").lower()
    ]


@mcp.tool()
def find_run_concepts_pairs_with(other_id: str) -> list[str]:
    """Return concept IDs that list other_id in their pairs_with array.

    Useful for building play families: given 'power', find its natural companions.

    Example:
        >>> find_run_concepts_pairs_with('power')
        ['counter-trey', 'iso']  # concepts that reference power as a companion

    Args:
        other_id: concept_id to search for in pairs_with arrays.
    """
    other_lower = other_id.lower()
    return [
        cid for cid, c in _load_all().items()
        if other_lower in [p.lower() for p in c.get("pairs_with", [])]
    ]


@mcp.tool()
def manifest() -> dict[str, Any]:
    """Return this server's purpose, tool list, and worked examples."""
    return {
        "server": "run-concept-library",
        "purpose": "Exposes blitz-command's 15 run-concept abstractions (Power, Counter, ISO, Inside Zone, etc.). Use it to understand blocking assignments, read progressions, and play-family relationships for run plays.",
        "tools": [
            {"name": "list_run_concepts", "description": "All concepts with id, category, aim_point, tags. Start here."},
            {"name": "get_run_concept", "description": "Full YAML: description, read_tree, blocking_scheme_ref, pulls_required, lead_blocker."},
            {"name": "find_run_concepts_by_category", "description": "gap-scheme / zone-scheme / option / man-blocking-scheme / misdirection."},
            {"name": "find_run_concepts_by_aim_point", "description": "Substring search in aim_point — 'A-gap', 'perimeter', 'off-tackle'."},
            {"name": "find_run_concepts_pairs_with", "description": "Concepts that naturally pair with a given concept."},
            {"name": "manifest", "description": "This document."},
        ],
        "examples": [
            "find_run_concepts_by_category('gap-scheme') → ['counter-trey', 'iso', 'power', 'trap']",
            "find_run_concepts_pairs_with('power') → concepts referencing power as a companion",
        ],
    }


if __name__ == "__main__":
    mcp.run()
