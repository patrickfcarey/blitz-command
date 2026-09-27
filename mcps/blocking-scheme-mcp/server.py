#!/usr/bin/env python3
"""Blocking Scheme Library MCP server.

Exposes blitz-command's blocking scheme library (data/concepts/blocking-schemes/)
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
SCHEMES_DIR = REPO_ROOT / "data" / "concepts" / "blocking-schemes"
SCHEMA_PATH = REPO_ROOT / "schemas" / "blocking-scheme.schema.json"

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
    current_mtime = SCHEMES_DIR.stat().st_mtime if SCHEMES_DIR.exists() else 0.0
    if _CACHE is not None and current_mtime == _CACHE_MTIME:
        return _CACHE
    schema = _load_schema()
    schemes: dict[str, dict[str, Any]] = {}
    for path in sorted(SCHEMES_DIR.glob("*.yaml")):
        try:
            with open(path) as f:
                data = yaml.safe_load(f)
            if not data:
                continue
            validate(data, schema)
            schemes[path.stem] = data
        except (ValidationError, yaml.YAMLError) as e:
            print(f"WARN: skipping {path.name}: {e}", file=sys.stderr)
    _CACHE = schemes
    _CACHE_MTIME = current_mtime
    return schemes


mcp = FastMCP("blocking-scheme-library")


def _paginate(items: list, cursor: str | None, limit: int) -> dict[str, Any]:
    offset = int(cursor) if cursor else 0
    page = items[offset: offset + limit]
    next_offset = offset + len(page)
    return {
        "items": page,
        "next_cursor": str(next_offset) if next_offset < len(items) else None,
    }


@mcp.tool()
def list_blocking_schemes(cursor: str | None = None, limit: int = 50) -> dict[str, Any]:
    """List every blocking scheme with brief metadata.

    Returns:
        {
          "items":       [{...}, ...],
          "next_cursor": str | null,
        }

    Item shape:
        {
          "id":       "gap-blocking",
          "name":     "Gap Blocking",
          "category": "pass-protection" | "run-blocking" | "pull-block" | "combo",
          "tags":     ["run-blocking", "gap-scheme", ...],
        }

    Args:
        cursor: opaque pagination token from the previous call's next_cursor.
        limit: max items per page (default 50).

    Example:
        >>> page = list_blocking_schemes()
        >>> [s['id'] for s in page['items'] if s['category'] == 'run-blocking']
        ['gap-blocking', 'zone-blocking']
    """
    all_items = [
        {
            "id": sid,
            "name": s.get("name"),
            "category": s.get("category"),
            "tags": s.get("tags", []),
        }
        for sid, s in _load_all().items()
    ]
    return _paginate(all_items, cursor, limit)


@mcp.tool()
def get_blocking_scheme(scheme_id: str) -> dict[str, Any]:
    """Get the full blocking scheme definition.

    Returns: scheme_id, name, category, description, assignments_by_position
    (per OL/TE/HB label → blocking rule), pairs_with, defeats, vulnerable_to,
    tags, source_notes.

    Common scheme_id values:
        Pass protection: 'man-protection', 'slide-protection', 'half-slide-protection',
                         'max-protection', 'boss-protection', 'big-on-big'
        Run blocking:    'zone-blocking', 'gap-blocking'

    Args:
        scheme_id: file stem (no .yaml extension).
    """
    schemes = _load_all()
    if scheme_id not in schemes:
        available = sorted(schemes.keys())
        msg = f"No blocking scheme with id '{scheme_id}'. Available: {available}"
        raise ValueError(msg)
    return schemes[scheme_id]


@mcp.tool()
def find_schemes_by_category(category: str) -> list[str]:
    """Return scheme IDs in the given category.

    Category values:
        'pass-protection' — man, slide, half-slide, max, boss, big-on-big
        'run-blocking'    — zone-blocking, gap-blocking
        'pull-block'      — schemes involving pulling linemen
        'combo'           — hybrid pass/run blocking schemes

    Args:
        category: category enum value (case-insensitive).
    """
    cat = category.lower()
    return [sid for sid, s in _load_all().items() if s.get("category", "").lower() == cat]


@mcp.tool()
def find_schemes_that_defeat(defensive_concept: str) -> list[str]:
    """Return scheme IDs whose 'defeats' list mentions the given defensive concept.

    Example:
        >>> find_schemes_that_defeat('4-man rush')
        ['man-protection', 'boss-protection']
        >>> find_schemes_that_defeat('single-DE')
        ['man-protection']

    Args:
        defensive_concept: substring to search in defeats arrays (case-insensitive).
    """
    dc_lower = defensive_concept.lower()
    results = []
    for sid, s in _load_all().items():
        for d in s.get("defeats", []):
            if dc_lower in d.lower():
                results.append(sid)
                break
    return results


@mcp.tool()
def find_schemes_vulnerable_to(pressure: str) -> list[str]:
    """Return scheme IDs that are vulnerable to the given pressure concept.

    Example:
        >>> find_schemes_vulnerable_to('double-A-gap')
        ['man-protection', 'slide-protection', 'full-slide-left', ...]

    Args:
        pressure: substring to search in vulnerable_to arrays (case-insensitive).
    """
    pressure_lower = pressure.lower()
    results = []
    for sid, s in _load_all().items():
        for v in s.get("vulnerable_to", []):
            if pressure_lower in v.lower():
                results.append(sid)
                break
    return results


@mcp.tool()
def manifest() -> dict[str, Any]:
    """Return this server's purpose, tool list, and worked examples."""
    return {
        "server": "blocking-scheme-library",
        "purpose": "Exposes blitz-command's 8 blocking schemes (man, slide, zone, gap, etc.). Use it to look up OL assignment rules, what pressures a scheme defeats, and what it's vulnerable to.",
        "tools": [
            {"name": "list_blocking_schemes", "description": "All schemes with id, category, tags. Start here."},
            {"name": "get_blocking_scheme", "description": "Full YAML: assignments_by_position, defeats, vulnerable_to."},
            {"name": "find_schemes_by_category", "description": "pass-protection / run-blocking / pull-block / combo."},
            {"name": "find_schemes_that_defeat", "description": "Substring search in defeats arrays."},
            {"name": "find_schemes_vulnerable_to", "description": "Substring search in vulnerable_to arrays."},
            {"name": "manifest", "description": "This document."},
        ],
        "examples": [
            "find_schemes_vulnerable_to('double-A-gap') → ['man-protection', 'slide-protection', ...]",
            "get_blocking_scheme('gap-blocking') → full OL assignment rules for Power/Counter",
        ],
    }


if __name__ == "__main__":
    mcp.run()
