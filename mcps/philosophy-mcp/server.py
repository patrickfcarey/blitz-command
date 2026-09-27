#!/usr/bin/env python3
"""Philosophy Library MCP server.

Exposes blitz-command's offensive philosophy library (data/concepts/philosophies/)
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
PHILOSOPHIES_DIR = REPO_ROOT / "data" / "concepts" / "philosophies"
SCHEMA_PATH = REPO_ROOT / "schemas" / "philosophy.schema.json"

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
    current_mtime = PHILOSOPHIES_DIR.stat().st_mtime if PHILOSOPHIES_DIR.exists() else 0.0
    if _CACHE is not None and current_mtime == _CACHE_MTIME:
        return _CACHE
    schema = _load_schema()
    philosophies: dict[str, dict[str, Any]] = {}
    for path in sorted(PHILOSOPHIES_DIR.glob("*.yaml")):
        try:
            with open(path) as f:
                data = yaml.safe_load(f)
            if not data:
                continue
            validate(data, schema)
            philosophies[path.stem] = data
        except (ValidationError, yaml.YAMLError) as e:
            print(f"WARN: skipping {path.name}: {e}", file=sys.stderr)
    _CACHE = philosophies
    _CACHE_MTIME = current_mtime
    return philosophies


mcp = FastMCP("philosophy-library")


def _paginate(items: list, cursor: str | None, limit: int) -> dict[str, Any]:
    offset = int(cursor) if cursor else 0
    page = items[offset: offset + limit]
    next_offset = offset + len(page)
    return {
        "items": page,
        "next_cursor": str(next_offset) if next_offset < len(items) else None,
    }


@mcp.tool()
def list_philosophies(cursor: str | None = None, limit: int = 50) -> dict[str, Any]:
    """List every offensive philosophy with brief metadata.

    Returns:
        {
          "items":       [{...}, ...],
          "next_cursor": str | null,
        }

    Item shape:
        {
          "id":          "west-coast",
          "name":        "West Coast",
          "era":         "1979–present",
          "tendency_profile": {"run_pct": 0.45, "pass_pct": 0.40, ...},
          "tags":        ["philosophy", "pass-first", "timing-based", ...],
        }

    Args:
        cursor: opaque pagination token from the previous call's next_cursor.
        limit: max items per page (default 50).

    Example:
        >>> page = list_philosophies()
        >>> [p['id'] for p in page['items'] if p['tendency_profile']['run_pct'] >= 0.65]
        ['flexbone', 'high-school-power', 'pop-warner', 'power-run', 'sec-power-run', 'veer-option', 'wing-t']
    """
    all_items = [
        {
            "id": pid,
            "name": p.get("name"),
            "era": p.get("era"),
            "tendency_profile": p.get("tendency_profile", {}),
            "tags": p.get("tags", []),
        }
        for pid, p in _load_all().items()
    ]
    return _paginate(all_items, cursor, limit)


@mcp.tool()
def get_philosophy(philosophy_id: str) -> dict[str, Any]:
    """Get the full philosophy definition.

    Returns: philosophy_id, name, description, era, originators,
    notable_practitioners, canonical_run_concepts, canonical_pass_concepts,
    formation_preferences, tendency_profile, tags, source_notes.

    tendency_profile contains: run_pct, pass_pct, pa_pct, rpo_pct, screen_pct
    (floats that sum to ~1.0).

    Common philosophy_id values:
        NFL classics:   'west-coast', 'coryell', 'erhardt-perkins', 'pro-style'
        College/spread: 'air-raid', 'spread-option', 'big-12-spread', 'rpo-heavy'
        Power run:      'power-run', 'sec-power-run', 'run-and-pound'
        Option:         'veer-option', 'flexbone', 'spread-option', 'option-heavy'
        High school:    'wing-t', 'high-school-power', 'pop-warner'
        Modern:         'shanahan-zone', 'mcvay-rams', 'spread-to-run', 'wildcat'

    Args:
        philosophy_id: file stem (no .yaml extension).
    """
    philosophies = _load_all()
    if philosophy_id not in philosophies:
        available = sorted(philosophies.keys())
        suggestions = [a for a in available if philosophy_id in a or a.startswith(philosophy_id[:5])]
        msg = f"No philosophy with id '{philosophy_id}'."
        if suggestions:
            msg += f" Did you mean: {suggestions[:5]}?"
        else:
            msg += f" {len(available)} philosophies available; call list_philosophies() for ids."
        raise ValueError(msg)
    return philosophies[philosophy_id]


@mcp.tool()
def find_philosophies_by_era(era: str) -> list[str]:
    """Return philosophy IDs whose era field contains the given string.

    The 'era' field is a freeform string like '1979–present' or 'Mid-1990s–'.
    This does a substring search so 'NFL' matches 'Modern NFL era', '1979' matches
    '1979–present', etc.

    Example:
        >>> find_philosophies_by_era('2017')
        ['mcvay-rams']
        >>> find_philosophies_by_era('1980')
        ['coryell', 'run-and-shoot', 'west-coast']

    Args:
        era: substring to search in era field (case-insensitive).
    """
    era_lower = era.lower()
    return [
        pid for pid, p in _load_all().items()
        if era_lower in p.get("era", "").lower()
    ]


@mcp.tool()
def find_philosophies_by_originator(name: str) -> list[str]:
    """Return philosophy IDs whose originators or notable_practitioners mention the given name.

    Example:
        >>> find_philosophies_by_originator('Walsh')
        ['west-coast']
        >>> find_philosophies_by_originator('Shanahan')
        ['erhardt-perkins', 'mcvay-rams', 'shanahan-zone', 'west-coast']

    Args:
        name: substring to search in originators + notable_practitioners (case-insensitive).
    """
    name_lower = name.lower()
    results = []
    for pid, p in _load_all().items():
        all_people = p.get("originators", []) + p.get("notable_practitioners", [])
        if any(name_lower in person.lower() for person in all_people):
            results.append(pid)
    return results


@mcp.tool()
def find_philosophies_by_tendency(
    max_run_pct: float | None = None,
    min_run_pct: float | None = None,
    max_pass_pct: float | None = None,
    min_pass_pct: float | None = None,
    min_rpo_pct: float | None = None,
) -> list[str]:
    """Return philosophy IDs matching the given tendency thresholds.

    Useful for AI queries like "find pass-heavy philosophies" or
    "find run-dominant with some RPO".

    All parameters are optional; only provided ones are checked.

    Example:
        >>> find_philosophies_by_tendency(max_run_pct=0.35)
        ['air-raid', 'coryell', 'run-and-shoot', ...]
        >>> find_philosophies_by_tendency(min_run_pct=0.70)
        ['flexbone', 'pop-warner', 'veer-option']
        >>> find_philosophies_by_tendency(min_rpo_pct=0.20)
        ['rpo-heavy', 'spread-option']

    Args:
        max_run_pct: upper bound on run_pct (inclusive).
        min_run_pct: lower bound on run_pct (inclusive).
        max_pass_pct: upper bound on pass_pct (inclusive).
        min_pass_pct: lower bound on pass_pct (inclusive).
        min_rpo_pct: lower bound on rpo_pct (inclusive).
    """
    results = []
    for pid, p in _load_all().items():
        tp = p.get("tendency_profile", {})
        run = tp.get("run_pct", 0.0)
        pas = tp.get("pass_pct", 0.0)
        rpo = tp.get("rpo_pct", 0.0)

        if max_run_pct is not None and run > max_run_pct:
            continue
        if min_run_pct is not None and run < min_run_pct:
            continue
        if max_pass_pct is not None and pas > max_pass_pct:
            continue
        if min_pass_pct is not None and pas < min_pass_pct:
            continue
        if min_rpo_pct is not None and rpo < min_rpo_pct:
            continue
        results.append(pid)
    return results


@mcp.tool()
def manifest() -> dict[str, Any]:
    """Return this server's purpose, tool list, and worked examples."""
    return {
        "server": "philosophy-library",
        "purpose": "Exposes blitz-command's 24 offensive philosophy profiles (West Coast, Air Raid, Wing-T, etc.). Use it to select a philosophical lens when assembling a playbook or to understand tendency profiles (run%/pass%/RPO%).",
        "tools": [
            {"name": "list_philosophies", "description": "All philosophies with id, era, tendency_profile, tags. Start here."},
            {"name": "get_philosophy", "description": "Full YAML: description, originators, canonical concepts, formation_preferences."},
            {"name": "find_philosophies_by_era", "description": "Substring search in era field."},
            {"name": "find_philosophies_by_originator", "description": "Search originators + notable_practitioners by name."},
            {"name": "find_philosophies_by_tendency", "description": "Filter by run_pct / pass_pct / rpo_pct thresholds."},
            {"name": "manifest", "description": "This document."},
        ],
        "examples": [
            "find_philosophies_by_tendency(max_run_pct=0.35) → pass-heavy philosophies",
            "find_philosophies_by_originator('Walsh') → ['west-coast']",
        ],
    }


if __name__ == "__main__":
    mcp.run()
