#!/usr/bin/env python3
"""Coverage MCP server.

Exposes blitz-command's defensive formation library to AI agents over the
Model Context Protocol. Reads YAML files from data/formations/ where
side == 'defense', and serves them via five tools.

Requires Python 3.10+ (mcp SDK requirement).
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
FORMATIONS_DIR = REPO_ROOT / "data" / "formations"
SCHEMA_PATH = REPO_ROOT / "schemas" / "formation.schema.json"

_SCHEMA_CACHE: dict | None = None


def _load_schema() -> dict:
    global _SCHEMA_CACHE
    if _SCHEMA_CACHE is None:
        with open(SCHEMA_PATH) as f:
            _SCHEMA_CACHE = json.load(f)
    return _SCHEMA_CACHE


_COVERAGES_CACHE: dict[str, dict[str, Any]] | None = None
_COVERAGES_CACHE_MTIME: float = 0.0


def _load_all() -> dict[str, dict[str, Any]]:
    """Load every defensive formation file. Cached by directory mtime."""
    global _COVERAGES_CACHE, _COVERAGES_CACHE_MTIME
    current_mtime = FORMATIONS_DIR.stat().st_mtime if FORMATIONS_DIR.exists() else 0.0
    if _COVERAGES_CACHE is not None and current_mtime == _COVERAGES_CACHE_MTIME:
        return _COVERAGES_CACHE
    schema = _load_schema()
    coverages: dict[str, dict[str, Any]] = {}
    for path in sorted(FORMATIONS_DIR.glob("defense-*.yaml")):
        try:
            with open(path) as f:
                data = yaml.safe_load(f)
            if not data or data.get("side") != "defense":
                continue
            validate(data, schema)
            coverages[path.stem] = data
        except (ValidationError, yaml.YAMLError) as e:
            print(f"WARN: skipping {path.name}: {e}", file=sys.stderr)
    _COVERAGES_CACHE = coverages
    _COVERAGES_CACHE_MTIME = current_mtime
    return coverages


mcp = FastMCP("coverage")


def _paginate(items: list, cursor: str | None, limit: int) -> dict[str, Any]:
    offset = int(cursor) if cursor else 0
    page = items[offset: offset + limit]
    next_offset = offset + len(page)
    return {
        "items": page,
        "next_cursor": str(next_offset) if next_offset < len(items) else None,
    }


@mcp.tool()
def list_coverages(cursor: str | None = None, limit: int = 50) -> dict[str, Any]:
    """List every defensive coverage in the library with brief metadata.

    Returns one object per coverage. Use get_coverage(id) for full details
    (player coordinates, responsibilities, best_against, vulnerable_to).

    Returns:
        {
          "items":       [{...}, ...],
          "next_cursor": str | null,
        }

    Item shape:
        {
          "id":            "defense-4-3-cover-3",
          "name":          "4-3 Cover 3",
          "front":         "4-3",
          "coverage_shell": "cover-3",
          "personnel":     "4-3 base",
          "tags":          ["defense", "cover-3", "4-3", ...],
        }

    Args:
        cursor: opaque pagination token from the previous call's next_cursor.
        limit: max items per page (default 50).

    Example:
        >>> page = list_coverages()
        >>> [c['id'] for c in page['items'] if c['coverage_shell'] == 'cover-2']
        ['defense-4-2-5-cover-2', 'defense-4-3-cover-2']
    """
    all_items = [
        {
            "id": cid,
            "name": c.get("name"),
            "front": c.get("front"),
            "coverage_shell": c.get("coverage_shell"),
            "personnel": c.get("personnel"),
            "tags": c.get("tags", []),
        }
        for cid, c in _load_all().items()
    ]
    return _paginate(all_items, cursor, limit)


@mcp.tool()
def get_coverage(coverage_id: str) -> dict[str, Any]:
    """Get the full coverage file for a specific coverage_id.

    Returns the complete YAML: players (with universal coordinates),
    responsibilities (per-defender role + aim), best_against, vulnerable_to,
    front, coverage_shell, tags, and source notes.

    Common coverage_id values:
        'defense-3-4-cover-3'     — 3-4 front, single-high
        'defense-4-2-5-cover-2'   — nickel cover-2
        'defense-4-3-cover-2'     — 4-3 Tampa 2
        'defense-4-3-cover-3'     — 4-3 single-high cover-3
        'defense-46-bear-cover-0' — 46 Bear blitz, cover-0
        'defense-dime-cover-4'    — 6 DB, quarters coverage
        'defense-goal-line-6-2'   — short-yardage 6-2
        'defense-nickel-cover-1'  — 4-2-5 man coverage
        'defense-prevent-3-2-6'   — prevent, 6 DB deep

    Example:
        >>> c = get_coverage('defense-4-3-cover-3')
        >>> c['vulnerable_to']
        ['Four-verticals flooding the deep third boundaries', ...]

    Args:
        coverage_id: file stem (no .yaml extension).
    """
    coverages = _load_all()
    if coverage_id not in coverages:
        available = sorted(coverages.keys())
        suggestions = [a for a in available if coverage_id.replace("defense-", "") in a]
        msg = f"No coverage with id '{coverage_id}'."
        if suggestions:
            msg += f" Did you mean: {suggestions[:5]}?"
        else:
            msg += f" {len(available)} coverages available; call list_coverages() for ids."
        raise ValueError(msg)
    return coverages[coverage_id]


@mcp.tool()
def find_coverage_by_shell(shell: str) -> list[str]:
    """Return coverage IDs with the given coverage shell (case-insensitive).

    Coverage shell values:
        'cover-0' — full man, no deep help
        'cover-1' — man coverage with single free safety
        'cover-2' — two deep safeties, 5 underneath zones
        'cover-3' — three deep zones, four underneath
        'cover-4' — four deep zones (quarters), four underneath

    Example:
        >>> find_coverage_by_shell('cover-3')
        ['defense-3-4-cover-3', 'defense-4-3-cover-3']
        >>> find_coverage_by_shell('cover-2')
        ['defense-4-2-5-cover-2', 'defense-4-3-cover-2']

    Args:
        shell: coverage shell name (case-insensitive).
    """
    s = shell.lower()
    return [cid for cid, c in _load_all().items() if c.get("coverage_shell", "").lower() == s]


@mcp.tool()
def find_coverage_by_front(front: str) -> list[str]:
    """Return coverage IDs with the given defensive front (case-insensitive).

    Front values:
        '4-3'   — four down linemen, three linebackers
        '3-4'   — three down linemen, four linebackers
        '4-2-5' — four DL, two LB, five DB (nickel)
        '4-1-6' — four DL, one LB, six DB (dime)
        '6-2'   — six DL/DE, two linebackers (goal-line)
        '3-2-6' — three DL, two LB, six DB (prevent)
        '46-bear' — 46 Bear (eight in the box)

    Example:
        >>> find_coverage_by_front('4-3')
        ['defense-4-3-cover-2', 'defense-4-3-cover-3', 'defense-46-bear-cover-0']

    Args:
        front: defensive front name (case-insensitive).
    """
    f = front.lower()
    return [cid for cid, c in _load_all().items() if c.get("front", "").lower() == f]


@mcp.tool()
def find_coverage_vulnerable_to(concept: str) -> list[str]:
    """Return coverage IDs whose vulnerable_to list mentions the given concept.

    Searches for the concept substring in each entry of the vulnerable_to
    array (case-insensitive). Useful for "what defenses does Mesh beat?"

    Example:
        >>> find_coverage_vulnerable_to('mesh')
        ['defense-4-3-cover-3', ...]  # covers vulnerable to crossing routes
        >>> find_coverage_vulnerable_to('four-verticals')
        ['defense-4-3-cover-3', 'defense-nickel-cover-1', ...]

    Args:
        concept: substring to search in vulnerable_to entries (case-insensitive).
    """
    concept_lower = concept.lower()
    results = []
    for cid, c in _load_all().items():
        for vuln in c.get("vulnerable_to", []):
            if concept_lower in vuln.lower():
                results.append(cid)
                break
    return results


@mcp.tool()
def manifest() -> dict[str, Any]:
    """Return this server's purpose, tool list, and worked examples."""
    return {
        "server": "coverage",
        "purpose": "Exposes blitz-command's 9 defensive coverage profiles. Use it to find what defenses to attack (or prepare for) when designing plays or calling plays against an opponent.",
        "tools": [
            {"name": "list_coverages", "description": "All coverages with id, front, coverage_shell, tags. Start here."},
            {"name": "get_coverage", "description": "Full defensive YAML including player coords, responsibilities, best_against, vulnerable_to."},
            {"name": "find_coverage_by_shell", "description": "Filter by cover-0 / cover-1 / cover-2 / cover-3 / cover-4."},
            {"name": "find_coverage_by_front", "description": "Filter by 4-3 / 3-4 / 4-2-5 / 46-bear / 6-2 / 3-2-6."},
            {"name": "find_coverage_vulnerable_to", "description": "Substring search — what defenses does a concept beat?"},
            {"name": "manifest", "description": "This document."},
        ],
        "examples": [
            "find_coverage_vulnerable_to('mesh') → defenses with 'mesh' in vulnerable_to",
            "find_coverage_by_shell('cover-2') → ['defense-4-2-5-cover-2', 'defense-4-3-cover-2']",
        ],
    }


if __name__ == "__main__":
    mcp.run()
