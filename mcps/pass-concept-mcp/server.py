#!/usr/bin/env python3
"""Pass Concept Library MCP server.

Exposes blitz-command's pass concept library (data/concepts/pass-concepts/)
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
CONCEPTS_DIR = REPO_ROOT / "data" / "concepts" / "pass-concepts"
SCHEMA_PATH = REPO_ROOT / "schemas" / "pass-concept.schema.json"

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


mcp = FastMCP("pass-concept-library")


def _paginate(items: list, cursor: str | None, limit: int) -> dict[str, Any]:
    offset = int(cursor) if cursor else 0
    page = items[offset: offset + limit]
    next_offset = offset + len(page)
    return {
        "items": page,
        "next_cursor": str(next_offset) if next_offset < len(items) else None,
    }


@mcp.tool()
def list_pass_concepts(cursor: str | None = None, limit: int = 50) -> dict[str, Any]:
    """List every pass concept with brief metadata.

    Returns:
        {
          "items":       [{...}, ...],
          "next_cursor": str | null,
        }

    Item shape:
        {
          "id":               "mesh",
          "name":             "Mesh",
          "category":         "timing-route" | "area-read" | ...,
          "best_vs_coverage": ["man", "two-high", ...],
          "tags":             ["mesh", "west-coast", ...],
        }

    Args:
        cursor: opaque pagination token from the previous call's next_cursor.
        limit: max items per page (default 50).

    Example:
        >>> page = list_pass_concepts()
        >>> [c['id'] for c in page['items'] if c['category'] == 'area-read']
        ['hi-lo', 'sail', 'smash', 'snag', 'stick']
    """
    all_items = [
        {
            "id": cid,
            "name": c.get("name"),
            "category": c.get("category"),
            "best_vs_coverage": c.get("best_vs_coverage", []),
            "tags": c.get("tags", []),
        }
        for cid, c in _load_all().items()
    ]
    return _paginate(all_items, cursor, limit)


@mcp.tool()
def get_pass_concept(concept_id: str) -> dict[str, Any]:
    """Get the full pass concept definition.

    Returns: concept_id, name, category, description, progression
    (primary/secondary/tertiary reads), best_vs_coverage, attacks,
    pairs_with, tags, verification_status, source_notes.

    Common concept_id values:
        Timing:        'mesh', 'drive', 'levels'
        Area-read:     'smash', 'snag', 'stick', 'hi-lo', 'sail'
        Vertical:      'four-verticals', 'post-corner', 'switch'
        Horizontal:    'flood', 'dagger', 'slant-flat', 'double-slant'

    Args:
        concept_id: file stem (no .yaml extension).
    """
    concepts = _load_all()
    if concept_id not in concepts:
        available = sorted(concepts.keys())
        suggestions = [a for a in available if concept_id in a or a.startswith(concept_id[:5])]
        msg = f"No pass concept with id '{concept_id}'."
        if suggestions:
            msg += f" Did you mean: {suggestions[:5]}?"
        else:
            msg += f" {len(available)} concepts available; call list_pass_concepts() for ids."
        raise ValueError(msg)
    return concepts[concept_id]


@mcp.tool()
def find_pass_concepts_by_category(category: str) -> list[str]:
    """Return concept IDs in the given category (case-insensitive exact match).

    Category values:
        'timing-route'       — mesh, drive, levels (read the crossing timing window)
        'area-read'          — smash, snag, stick, hi-lo, sail (read the zone area)
        'option-route'       — concepts built around receiver option reads
        'vertical-stretch'   — four-verticals, post-corner, switch (beat deep coverage)
        'horizontal-stretch' — flood, dagger, slant-flat, double-slant (spread zones wide)
        'intermediate-read'  — mid-depth concepts
        'quick-read'         — fast-release, pre-snap-read concepts
        'crossing-route'     — drag and crossing-based concepts

    Args:
        category: category enum value (case-insensitive).
    """
    cat = category.lower()
    return [cid for cid, c in _load_all().items() if c.get("category", "").lower() == cat]


@mcp.tool()
def find_pass_concepts_best_vs_coverage(coverage: str) -> list[str]:
    """Return concept IDs best against the given coverage type.

    Searches the best_vs_coverage array for entries containing the substring
    (case-insensitive). Broader terms like 'zone' match any zone entry.

    Coverage values (sample):
        'man'           — man-to-man coverage
        'cover-2'       — two-high safety shell
        'cover-3'       — three-deep single-high zone
        'cover-4'       — quarters / Tampa-2 variant
        'zone'          — any zone coverage
        '2-high'        — any two-high safety look
        'zone-blitz'    — zone with extra rushers

    Example:
        >>> find_pass_concepts_best_vs_coverage('cover-2')
        ['four-verticals', 'smash', 'switch']
        >>> find_pass_concepts_best_vs_coverage('man')
        ['double-slant', 'drive', 'mesh', 'slant-flat']

    Args:
        coverage: substring to match in best_vs_coverage entries (case-insensitive).
    """
    cov = coverage.lower()
    return [
        cid for cid, c in _load_all().items()
        if any(cov in v.lower() for v in c.get("best_vs_coverage", []))
    ]


@mcp.tool()
def find_pass_concepts_pairs_with(other_id: str) -> list[str]:
    """Return concept IDs that list other_id in their pairs_with array.

    Useful for building play families and philosophy-aware play selection:
    given 'west-coast', find concepts that naturally fit that philosophy.

    Example:
        >>> find_pass_concepts_pairs_with('west-coast')
        ['drive', 'levels', 'mesh', 'stick']
        >>> find_pass_concepts_pairs_with('air-raid')
        ['four-verticals', 'mesh', 'snag']

    Args:
        other_id: concept_id, philosophy, or tag to search for in pairs_with arrays.
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
        "server": "pass-concept-library",
        "purpose": (
            "Exposes blitz-command's 16 pass concept abstractions (Mesh, Smash, Snag, "
            "Four Verticals, Flood, etc.). Use it to understand coverage matchups, read "
            "progressions, and concept pairings when designing pass plays. Pair with "
            "run-concept-mcp and philosophy-mcp for full offensive design context."
        ),
        "tools": [
            {"name": "list_pass_concepts", "description": "All concepts with id, category, best_vs_coverage, tags. Start here."},
            {"name": "get_pass_concept", "description": "Full YAML: description, progression, best_vs_coverage, attacks, pairs_with."},
            {"name": "find_pass_concepts_by_category", "description": "Filter by timing-route / area-read / vertical-stretch / horizontal-stretch / etc."},
            {"name": "find_pass_concepts_best_vs_coverage", "description": "Concepts best vs a coverage type (man, cover-2, cover-3, zone...)."},
            {"name": "find_pass_concepts_pairs_with", "description": "Concepts pairing with a given concept, philosophy, or tag."},
            {"name": "manifest", "description": "This document."},
        ],
        "examples": [
            "find_pass_concepts_best_vs_coverage('man') → ['double-slant', 'drive', 'mesh', ...]",
            "find_pass_concepts_by_category('area-read') → ['hi-lo', 'sail', 'smash', 'snag', 'stick']",
            "find_pass_concepts_pairs_with('west-coast') → concepts designed for West Coast philosophy",
        ],
    }


if __name__ == "__main__":
    mcp.run()
