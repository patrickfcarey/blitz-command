#!/usr/bin/env python3
"""Pass Protection Library MCP server.

Exposes blitz-command's pass protection library (data/concepts/pass-protections/)
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
PROTECTIONS_DIR = REPO_ROOT / "data" / "concepts" / "pass-protections"
SCHEMA_PATH = REPO_ROOT / "schemas" / "pass-protection.schema.json"

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
    current_mtime = PROTECTIONS_DIR.stat().st_mtime if PROTECTIONS_DIR.exists() else 0.0
    if _CACHE is not None and current_mtime == _CACHE_MTIME:
        return _CACHE
    schema = _load_schema()
    protections: dict[str, dict[str, Any]] = {}
    for path in sorted(PROTECTIONS_DIR.glob("*.yaml")):
        try:
            with open(path) as f:
                data = yaml.safe_load(f)
            if not data:
                continue
            validate(data, schema)
            protections[path.stem] = data
        except (ValidationError, yaml.YAMLError) as e:
            print(f"WARN: skipping {path.name}: {e}", file=sys.stderr)
    _CACHE = protections
    _CACHE_MTIME = current_mtime
    return protections


mcp = FastMCP("pass-protection-library")


def _paginate(items: list, cursor: str | None, limit: int) -> dict[str, Any]:
    offset = int(cursor) if cursor else 0
    page = items[offset: offset + limit]
    next_offset = offset + len(page)
    return {
        "items": page,
        "next_cursor": str(next_offset) if next_offset < len(items) else None,
    }


@mcp.tool()
def list_pass_protections(cursor: str | None = None, limit: int = 50) -> dict[str, Any]:
    """List every pass protection scheme with brief metadata.

    Returns:
        {
          "items":       [{...}, ...],
          "next_cursor": str | null,
        }

    Item shape:
        {
          "id":              "full-slide-left",
          "name":            "Full Slide Left",
          "protection_type": "5-man" | "6-man" | "7-man" | "slide" | "half-slide" | "boss" | "big-on-big",
          "tags":            ["pass-protection", "slide", ...],
        }

    Args:
        cursor: opaque pagination token from the previous call's next_cursor.
        limit: max items per page (default 50).

    Example:
        >>> page = list_pass_protections()
        >>> [p['id'] for p in page['items'] if p['protection_type'] == '7-man']
        ['max-protection-7-man']
    """
    all_items = [
        {
            "id": pid,
            "name": p.get("name"),
            "protection_type": p.get("protection_type"),
            "tags": p.get("tags", []),
        }
        for pid, p in _load_all().items()
    ]
    return _paginate(all_items, cursor, limit)


@mcp.tool()
def get_pass_protection(protection_id: str) -> dict[str, Any]:
    """Get the full pass protection definition.

    Returns: scheme_id, name, description, protection_type, assignments_by_position
    (per OL/TE/HB label → protection rule), vulnerable_to, pairs_with, tags,
    source_notes.

    Common protection_id values:
        'full-slide-left'      — 5-OL slide left, HB scans backside
        'full-slide-right'     — 5-OL slide right, HB scans backside
        'half-slide-protect'   — 3 OL slide, 2 OL man-block
        'max-protection-7-man' — OL + TE + HB, no checkdowns
        'boss-pickup'          — Big-On-Big, HB scans LBs

    Args:
        protection_id: file stem (no .yaml extension).
    """
    protections = _load_all()
    if protection_id not in protections:
        available = sorted(protections.keys())
        msg = f"No pass protection with id '{protection_id}'. Available: {available}"
        raise ValueError(msg)
    return protections[protection_id]


@mcp.tool()
def find_protections_by_type(protection_type: str) -> list[str]:
    """Return protection IDs with the given protection_type.

    Type values:
        '5-man'    — five OL, no extra blockers
        '6-man'    — five OL plus one extra (HB or TE)
        '7-man'    — OL + TE + HB, max blockers
        'slide'    — all OL slide one direction
        'half-slide' — half slide, half man
        'boss'     — Big-On-Big OL assignment
        'big-on-big' — variant of boss

    Args:
        protection_type: protection_type enum value (case-insensitive).
    """
    ptype = protection_type.lower()
    return [pid for pid, p in _load_all().items() if p.get("protection_type", "").lower() == ptype]


@mcp.tool()
def find_protections_vulnerable_to(pressure: str) -> list[str]:
    """Return protection IDs vulnerable to the given pressure concept.

    Example:
        >>> find_protections_vulnerable_to('double-A-gap')
        ['full-slide-left', 'full-slide-right', 'boss-pickup']

    Args:
        pressure: substring to search in vulnerable_to arrays (case-insensitive).
    """
    pressure_lower = pressure.lower()
    results = []
    for pid, p in _load_all().items():
        for v in p.get("vulnerable_to", []):
            if pressure_lower in v.lower():
                results.append(pid)
                break
    return results


@mcp.tool()
def manifest() -> dict[str, Any]:
    """Return this server's purpose, tool list, and worked examples."""
    return {
        "server": "pass-protection-library",
        "purpose": "Exposes blitz-command's 5 pass protection schemes (full-slide, half-slide, max, boss). Use it to select protections when designing pass plays and to match protections against expected pressure.",
        "tools": [
            {"name": "list_pass_protections", "description": "All protections with id, protection_type, tags. Start here."},
            {"name": "get_pass_protection", "description": "Full YAML: description, assignments_by_position, vulnerable_to."},
            {"name": "find_protections_by_type", "description": "5-man / 6-man / 7-man / slide / half-slide / boss / big-on-big."},
            {"name": "find_protections_vulnerable_to", "description": "Substring search in vulnerable_to arrays."},
            {"name": "manifest", "description": "This document."},
        ],
        "examples": [
            "find_protections_by_type('7-man') → ['max-protection-7-man']",
            "find_protections_vulnerable_to('double-A-gap') → protections exposed to A-gap blitzes",
        ],
    }


if __name__ == "__main__":
    mcp.run()
