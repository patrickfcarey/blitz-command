#!/usr/bin/env python3
"""Route Library MCP server.

Exposes blitz-command's route library to AI agents over the Model Context
Protocol. Reads YAML files from data/routes/, validates each against
schemas/route.schema.json, and serves them via discovery tools.

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
ROUTES_DIR = REPO_ROOT / "data" / "routes"
SCHEMA_PATH = REPO_ROOT / "schemas" / "route.schema.json"

_SCHEMA_CACHE: dict | None = None


def _load_schema() -> dict:
    global _SCHEMA_CACHE
    if _SCHEMA_CACHE is None:
        with open(SCHEMA_PATH) as f:
            _SCHEMA_CACHE = json.load(f)
    return _SCHEMA_CACHE


_ROUTES_CACHE: dict[str, dict[str, Any]] | None = None
_ROUTES_CACHE_MTIME: float = 0.0


def _load_all() -> dict[str, dict[str, Any]]:
    """Load every route file. Cached by directory mtime."""
    global _ROUTES_CACHE, _ROUTES_CACHE_MTIME
    current_mtime = ROUTES_DIR.stat().st_mtime if ROUTES_DIR.exists() else 0.0
    if _ROUTES_CACHE is not None and current_mtime == _ROUTES_CACHE_MTIME:
        return _ROUTES_CACHE
    schema = _load_schema()
    routes: dict[str, dict[str, Any]] = {}
    for path in sorted(ROUTES_DIR.glob("*.yaml")):
        try:
            with open(path) as f:
                data = yaml.safe_load(f)
            if not data:
                continue
            validate(data, schema)
            routes[path.stem] = data
        except (ValidationError, yaml.YAMLError) as e:
            print(f"WARN: skipping {path.name}: {e}", file=sys.stderr)
    _ROUTES_CACHE = routes
    _ROUTES_CACHE_MTIME = current_mtime
    return routes


mcp = FastMCP("route-library")


def _paginate(items: list, cursor: str | None, limit: int) -> dict[str, Any]:
    offset = int(cursor) if cursor else 0
    page = items[offset: offset + limit]
    next_offset = offset + len(page)
    return {
        "items": page,
        "next_cursor": str(next_offset) if next_offset < len(items) else None,
    }


@mcp.tool()
def list_routes(cursor: str | None = None, limit: int = 50) -> dict[str, Any]:
    """List every route in the library with brief metadata.

    Returns one object per route. Use get_route(id) for the full definition
    including path waypoints, break depth, and source notes.

    Returns:
        {
          "items":       [{...}, ...],
          "next_cursor": str | null,  # pass back as cursor to get the next page
        }

    Item shape:
        {
          "id":            "slant",
          "name":          "slant",
          "aliases":       ["drive"],
          "category":      "quick" | "intermediate" | "deep" | "underneath" | "screen",
          "beats_coverage": "man" | "zone" | "both",
          "option_route":  false,
          "tags":          ["quick-game", "anti-man", "inside-breaking"],
        }

    Args:
        cursor: opaque pagination token from the previous call's next_cursor.
        limit: max items per page (default 50).

    Example:
        >>> page = list_routes()
        >>> [r['id'] for r in page['items'] if r['category'] == 'deep']
        ['corner', 'fade', 'go', 'post', 'seam']
    """
    all_items = [
        {
            "id": rid,
            "name": r.get("name"),
            "aliases": r.get("aliases", []),
            "category": r.get("category"),
            "beats_coverage": r.get("beats_coverage"),
            "option_route": r.get("option_route", False),
            "tags": r.get("tags", []),
        }
        for rid, r in _load_all().items()
    ]
    return _paginate(all_items, cursor, limit)


@mcp.tool()
def get_route(route_id: str) -> dict[str, Any]:
    """Get the full route definition for a specific route_id.

    Returns the complete YAML: name, aliases, description, path waypoints
    (as [x, y] pairs relative to receiver start), typical_break_depth_yd,
    option_route flag, category, beats_coverage, tags, and source_notes.

    Path coordinates: x positive = toward inside of field; y positive = downfield.
    The draw tool mirrors x for right-side receivers automatically.

    Common route_id values:
        Quick:        'slant', 'hitch', 'flat', 'bubble-screen'
        Intermediate: 'in', 'out', 'dig', 'comeback', 'drag'
        Deep:         'go', 'post', 'corner', 'fade', 'seam'
        Option:       'snag', 'stick', 'sail', 'wheel'

    Example:
        >>> r = get_route('post')
        >>> r['typical_break_depth_yd']
        12
        >>> r['beats_coverage']
        'zone'

    Args:
        route_id: file stem (no .yaml extension).
    """
    routes = _load_all()
    if route_id not in routes:
        available = sorted(routes.keys())
        suggestions = [a for a in available if route_id in a or a.startswith(route_id[:4])]
        msg = f"No route with id '{route_id}'."
        if suggestions:
            msg += f" Did you mean: {suggestions[:5]}?"
        else:
            msg += f" {len(available)} routes available; call list_routes() for ids."
        raise ValueError(msg)
    return routes[route_id]


@mcp.tool()
def find_routes_by_category(category: str) -> list[str]:
    """Return route IDs in the given category (case-insensitive exact match).

    Category values:
        'quick'        — short, fast-breaking routes (slant, hitch, flat)
        'intermediate' — mid-depth routes (in/dig, out, comeback, drag)
        'deep'         — vertical stretches (go, post, corner, fade, seam)
        'underneath'   — sub-5-yard routes (bubble screen, drag variants)
        'screen'       — designed screens (bubble-screen)

    Example:
        >>> find_routes_by_category('deep')
        ['corner', 'fade', 'go', 'post', 'seam']
        >>> find_routes_by_category('quick')
        ['hitch', 'slant', 'flat']

    Args:
        category: one of the category enum values (case-insensitive).
    """
    cat = category.lower()
    return [rid for rid, r in _load_all().items() if r.get("category", "").lower() == cat]


@mcp.tool()
def find_routes_by_coverage(coverage: str) -> list[str]:
    """Return route IDs that attack the given coverage type.

    Coverage values:
        'man'  — route primarily attacks man coverage (slant, fade, mesh-based)
        'zone' — route primarily attacks zone coverage (post, comeback, corner)
        'both' — route is effective against both (seam, drag, wheel)

    Example:
        >>> find_routes_by_coverage('zone')
        ['comeback', 'corner', 'deep-cross', 'hitch', 'out', 'post', 'sail']
        >>> find_routes_by_coverage('man')
        ['fade', 'go', 'slant', 'wheel']

    Args:
        coverage: 'man', 'zone', or 'both' (case-insensitive).
    """
    cov = coverage.lower()
    return [rid for rid, r in _load_all().items() if r.get("beats_coverage", "").lower() == cov]


@mcp.tool()
def find_routes_by_depth(min_yd: float, max_yd: float) -> list[str]:
    """Return route IDs whose typical_break_depth_yd falls in [min_yd, max_yd].

    Useful for filtering routes by design depth (e.g., "give me everything
    under 5 yards" for quick-game vs "10-15 yards" for intermediate).

    Routes without a typical_break_depth_yd are excluded from results.

    Example:
        >>> find_routes_by_depth(0, 5)
        ['bubble-screen', 'drag', 'flat', 'hitch', 'slant']
        >>> find_routes_by_depth(10, 18)
        ['comeback', 'corner', 'deep-cross', 'in', 'out', 'post', 'seam']

    Args:
        min_yd: minimum break depth in yards (inclusive).
        max_yd: maximum break depth in yards (inclusive).
    """
    results = []
    for rid, r in _load_all().items():
        depth = r.get("typical_break_depth_yd")
        if depth is not None and min_yd <= depth <= max_yd:
            results.append(rid)
    return sorted(results)


@mcp.tool()
def manifest() -> dict[str, Any]:
    """Return this server's purpose, tool list, and worked examples."""
    return {
        "server": "route-library",
        "purpose": "Exposes blitz-command's 25-route pass-route library. Use it to look up route paths, break depths, coverage matchups, and option-route flags when designing plays or reading assignments.",
        "tools": [
            {"name": "list_routes", "description": "All routes with id, category, beats_coverage, tags. Paginated."},
            {"name": "get_route", "description": "Full route YAML including path waypoints and break depth."},
            {"name": "find_routes_by_category", "description": "Filter by quick / intermediate / deep / underneath / screen."},
            {"name": "find_routes_by_coverage", "description": "Filter by man / zone / both."},
            {"name": "find_routes_by_depth", "description": "Filter by break depth range in yards."},
            {"name": "manifest", "description": "This document."},
        ],
        "examples": [
            "find_routes_by_coverage('zone') → ['comeback', 'corner', 'hitch', 'out', 'post', ...]",
            "find_routes_by_depth(0, 5) → ['bubble-screen', 'drag', 'flat', 'hitch', 'slant']",
        ],
    }


if __name__ == "__main__":
    mcp.run()
