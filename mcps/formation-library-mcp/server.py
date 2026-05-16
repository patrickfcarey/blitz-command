#!/usr/bin/env python3
"""Formation Library MCP server.

Exposes blitz-command's **offensive** formation library to AI agents over the
Model Context Protocol. Reads YAML files from data/formations/ where
side == 'offense', validates each against schemas/formation.schema.json, and
serves them via discovery and authoring tools.

Defensive formations are owned by coverage-mcp — use get_coverage() there.

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


def _dir_mtime(directory: Path) -> float:
    if not directory.exists():
        return 0.0
    return directory.stat().st_mtime


_FORMATIONS_CACHE: dict[str, dict[str, Any]] | None = None
_FORMATIONS_CACHE_MTIME: float = 0.0


def _load_all() -> dict[str, dict[str, Any]]:
    """Load every formation file. Cached by directory mtime."""
    global _FORMATIONS_CACHE, _FORMATIONS_CACHE_MTIME
    current_mtime = _dir_mtime(FORMATIONS_DIR)
    if _FORMATIONS_CACHE is not None and current_mtime == _FORMATIONS_CACHE_MTIME:
        return _FORMATIONS_CACHE
    schema = _load_schema()
    formations: dict[str, dict[str, Any]] = {}
    for path in sorted(FORMATIONS_DIR.glob("*.yaml")):
        try:
            with open(path) as f:
                data = yaml.safe_load(f)
            if not data:
                continue
            if data.get("side") == "defense":
                continue  # defensive formations are owned by coverage-mcp
            validate(data, schema)
            formations[path.stem] = data
        except (ValidationError, yaml.YAMLError) as e:
            print(f"WARN: skipping {path.name}: {e}", file=sys.stderr)
    _FORMATIONS_CACHE = formations
    _FORMATIONS_CACHE_MTIME = current_mtime
    return formations


def _invalidate_formations_cache() -> None:
    global _FORMATIONS_CACHE, _FORMATIONS_CACHE_MTIME
    _FORMATIONS_CACHE = None
    _FORMATIONS_CACHE_MTIME = 0.0


mcp = FastMCP("formation-library")


def _paginate(items: list, cursor: str | None, limit: int) -> dict[str, Any]:
    offset = int(cursor) if cursor else 0
    page = items[offset: offset + limit]
    next_offset = offset + len(page)
    return {
        "items": page,
        "next_cursor": str(next_offset) if next_offset < len(items) else None,
    }


@mcp.tool()
def list_formations(cursor: str | None = None, limit: int = 50) -> dict[str, Any]:
    """List every formation in the library with brief metadata.

    Returns one object per formation. Use get_formation(id) for full details
    (player coordinates, run/pass concepts, era, famous users, etc).

    Returns:
        {
          "items":       [{...}, ...],
          "next_cursor": str | null,
        }

    Item shape:
        {
          "id":            "shotgun-trips-right",
          "name":          "Shotgun Trips Right",
          "side":          "offense" | "defense",
          "personnel":     "11" | "12" | "21" | "10" | "20" | "4-3 base" | ...,
          "strength_side": "right" | "left" | "balanced",
          "tags":          ["shotgun", "trips", "11-personnel", ...],
        }

    Library contains offensive formations only (most with -left mirrors
    auto-generated). For defensive formations use coverage-mcp.list_coverages().

    Args:
        cursor: opaque pagination token from the previous call's next_cursor.
        limit: max items per page (default 50).

    Example:
        >>> page = list_formations()
        >>> [f['id'] for f in page['items'][:3]]
        ['big-i', 'empty', 'flexbone']
    """
    all_items = [
        {
            "id": fid,
            "name": f.get("name"),
            "side": f.get("side"),
            "personnel": f.get("personnel"),
            "strength_side": f.get("strength_side"),
            "tags": f.get("tags", []),
        }
        for fid, f in _load_all().items()
    ]
    return _paginate(all_items, cursor, limit)


@mcp.tool()
def get_formation(formation_id: str) -> dict[str, Any]:
    """Get the full formation file for a specific formation_id.

    Returns the complete YAML object: players (with universal coordinates,
    on_line booleans, position labels), strengths, weaknesses, common_uses,
    run_concepts, pass_concepts, era, famous_users, tags, notes, and
    source notes. Defensive formations also include front, coverage_shell,
    responsibilities (per defender role + aim), best_against, and
    vulnerable_to fields.

    Offensive formation_id values (use coverage-mcp for defenses):
        Under center:  'i-formation', 'i-formation-twins-weak', 'strong-i',
                       'weak-i', 'big-i', 'wing-t', 'singleback-ace',
                       'singleback-trio', 'goal-line', 'full-house'
        Shotgun:       'shotgun-2x2', 'shotgun-trips-right',
                       'shotgun-trips-left', 'shotgun-3x0',
                       'shotgun-2x1-te-strong', 'shotgun-2x1-te-weak',
                       'empty', 'trey-right', 'trey-left'
        Pistol:        'pistol', 'pistol-diamond'
        Specialty:     'wildcat', 'wishbone', 'flexbone', 'run-and-shoot'

    Example:
        >>> f = get_formation('singleback-trio')
        >>> f['personnel']
        '11'
        >>> [p['label'] for p in f['players']]
        ['LT', 'LG', 'C', 'RG', 'RT', 'TE', 'X', 'Z', 'SLOT', 'QB', 'HB']

    Args:
        formation_id: file stem (no .yaml extension).
    """
    formations = _load_all()
    if formation_id not in formations:
        available = sorted(formations.keys())
        suggestions = [a for a in available if formation_id in a or a.startswith(formation_id[:6])]
        msg = f"No formation with id '{formation_id}'."
        if suggestions:
            msg += f" Did you mean: {suggestions[:5]}?"
        else:
            msg += f" {len(available)} formations available; call list_formations() for ids."
        raise ValueError(msg)
    return formations[formation_id]


@mcp.tool()
def find_formations_by_tag(tag: str) -> list[str]:
    """Return formation IDs whose tags include the given tag (case-insensitive, exact match).

    Tag categories (sample values from the current library):

        Type:         'shotgun', 'pistol', 'singleback', 'wildcat',
                      'wishbone', 'flexbone', 'i-form', 'wing-t',
                      'goal-line', 'empty', 'run-and-shoot'
        Personnel:    '11-personnel', '12-personnel', '20-personnel',
                      '21-personnel', '22-personnel', '10-personnel',
                      '32-personnel'
        Style:        'spread', 'pro-style', 'jumbo', 'balanced',
                      'symmetric', 'modern', 'throwback', 'rpo-friendly',
                      'shotgun-hybrid', 'zone-read', 'mandatory-motion'
        Spread shape: 'twins', 'trips', 'bunch', 'trey', 'diamond',
                      '4-wide', '5-wide'
        Level:        'any-level', 'high-school', 'college', 'nfl',
                      'service-academy'
    For defensive coverage tags use coverage-mcp.find_coverage_by_shell().

    Example:
        >>> find_formations_by_tag('triple-option')
        []  # no offensive formations tagged 'triple-option' alone
        >>> find_formations_by_tag('flexbone')
        ['flexbone', 'flexbone-left']

    Args:
        tag: tag string (case-insensitive, exact whole-tag match).
    """
    tag_lower = tag.lower()
    return [
        fid for fid, f in _load_all().items()
        if tag_lower in [t.lower() for t in f.get("tags", [])]
    ]


@mcp.tool()
def find_formations_by_concept(concept: str) -> list[str]:
    """Return formation IDs whose run_concepts or pass_concepts include this concept.

    Useful for "what formations support inside zone?" type queries. Exact
    case-insensitive match against the concept name (kebab-case).

    Common concept values:
        Run concepts:  'inside-zone', 'inside-zone-read', 'outside-zone',
                       'outside-zone-read', 'power-o', 'power-read',
                       'counter', 'counter-read', 'counter-trey', 'iso',
                       'lead', 'lead-toss', 'toss', 'sweep', 'jet-sweep',
                       'buck-sweep', 'stretch', 'trap', 'draw', 'belly',
                       'midline-option', 'triple-option-veer', 'veer',
                       'fb-dive', 'qb-sneak', 'split-zone'
        Pass concepts: 'mesh', 'mesh-te', 'stick', 'snag', 'smash',
                       'smash-strong', 'four-verticals', 'flood',
                       'pa-y-cross', 'pa-flood', 'pa-bootleg', 'pa-naked',
                       'pa-deep-shot', 'bootleg-flat', 'waggle', 'choice',
                       'switch-vertical', 'rpo-slant', 'rpo-bubble',
                       'rpo-glance'

    Example:
        >>> find_formations_by_concept('inside-zone')
        ['flexbone', 'flexbone-left', 'pistol', 'pistol-diamond',
         'pistol-diamond-left', 'pistol-left', 'shotgun-2x2', ...]
        >>> find_formations_by_concept('triple-option')
        []  # exact match — try 'triple-option-veer' instead

    Args:
        concept: concept identifier (kebab-case, exact match).
    """
    concept_lower = concept.lower()
    matches: list[str] = []
    for fid, f in _load_all().items():
        runs = [c.lower() for c in f.get("run_concepts", [])]
        passes = [c.lower() for c in f.get("pass_concepts", [])]
        if concept_lower in runs or concept_lower in passes:
            matches.append(fid)
    return matches


@mcp.tool()
def save_formation(
    formation_data: dict[str, Any],
    overwrite: bool = False,
) -> dict[str, Any]:
    """Validate and write a formation YAML to data/formations/<formation_id>.yaml.

    Returns:
        {
          "saved":          bool,
          "path":           absolute path written (or None),
          "formation_id":   the id used,
          "errors":         list[str] — schema violations (non-empty means not saved),
          "warnings":       list[str] — soft lints (saved regardless),
          "skipped":        explanation if not saved,
        }

    Behavior:
        - Refuses to write if schema validation finds errors.
        - Refuses to overwrite unless overwrite=True.
        - Writes YAML with sort_keys=False to preserve field order.

    Args:
        formation_data: full formation dict (id field used as filename stem).
        overwrite:      allow replacing an existing file (default False).
    """
    formation_id = (
        formation_data.get("formation_id")
        or formation_data.get("id")
        or (formation_data.get("name", "").lower().replace(" ", "-") or None)
    )
    if not formation_id:
        return {
            "saved": False, "path": None, "formation_id": None,
            "errors": ["formation_data has no formation_id, id, or name field"],
            "warnings": [], "skipped": "missing formation_id",
        }

    errors: list[str] = []
    warnings: list[str] = []
    try:
        validate(formation_data, _load_schema())
    except ValidationError as e:
        errors.append(f"schema: {e.message} (at {'/'.join(str(p) for p in e.absolute_path)})")

    if errors:
        return {
            "saved": False, "path": None, "formation_id": formation_id,
            "errors": errors, "warnings": warnings,
            "skipped": f"schema validation failed with {len(errors)} error(s)",
        }

    side = formation_data.get("side", "offense")
    players = formation_data.get("players", [])
    if side == "offense":
        if len(players) != 11:
            warnings.append(f"offense formation has {len(players)} players (expected 11)")
        on_line = sum(1 for p in players if p.get("on_line"))
        if on_line < 7:
            warnings.append(f"only {on_line} players on line of scrimmage (minimum 7)")

    target_path = FORMATIONS_DIR / f"{formation_id}.yaml"
    if target_path.exists() and not overwrite:
        return {
            "saved": False, "path": str(target_path), "formation_id": formation_id,
            "errors": errors, "warnings": warnings,
            "skipped": f"file already exists — pass overwrite=True to replace",
        }

    FORMATIONS_DIR.mkdir(parents=True, exist_ok=True)
    with open(target_path, "w") as f:
        yaml.safe_dump(formation_data, f, sort_keys=False, default_flow_style=False,
                       width=120, allow_unicode=True)
    _invalidate_formations_cache()

    return {
        "saved": True, "path": str(target_path), "formation_id": formation_id,
        "errors": errors, "warnings": warnings, "skipped": None,
    }


@mcp.tool()
def update_formation(
    formation_id: str,
    patch: dict[str, Any],
) -> dict[str, Any]:
    """Apply a shallow field-level patch to an existing formation file.

    Merges `patch` into the formation's top-level fields. Existing fields not
    in `patch` are unchanged. Nested fields (e.g. `players`) are replaced
    wholesale if included — to update a single player, include the full players
    list.

    Returns:
        {
          "updated":      bool,
          "path":         absolute path to the file,
          "formation_id": the id,
          "changed_keys": list of top-level keys that were modified,
          "errors":       schema errors after patch (non-empty means not written),
          "skipped":      explanation if not updated,
        }

    Example:
        >>> update_formation('singleback-trio', {'era': '1990s–present', 'tags': [...]})
        {"updated": True, "changed_keys": ["era", "tags"], ...}

    Args:
        formation_id: file stem of the formation to update.
        patch:        dict of top-level fields to set/replace.
    """
    target_path = FORMATIONS_DIR / f"{formation_id}.yaml"
    if not target_path.exists():
        return {
            "updated": False, "path": None, "formation_id": formation_id,
            "changed_keys": [], "errors": [f"no formation file for '{formation_id}'"],
            "skipped": "formation not found",
        }

    with open(target_path) as f:
        existing = yaml.safe_load(f) or {}

    changed_keys = [k for k, v in patch.items() if existing.get(k) != v]
    existing.update(patch)

    errors: list[str] = []
    try:
        validate(existing, _load_schema())
    except ValidationError as e:
        errors.append(f"schema: {e.message} (at {'/'.join(str(p) for p in e.absolute_path)})")

    if errors:
        return {
            "updated": False, "path": str(target_path), "formation_id": formation_id,
            "changed_keys": changed_keys, "errors": errors,
            "skipped": "patch would break schema validation — no changes written",
        }

    with open(target_path, "w") as f:
        yaml.safe_dump(existing, f, sort_keys=False, default_flow_style=False,
                       width=120, allow_unicode=True)
    _invalidate_formations_cache()

    return {
        "updated": True, "path": str(target_path), "formation_id": formation_id,
        "changed_keys": changed_keys, "errors": [], "skipped": None,
    }


@mcp.tool()
def manifest() -> dict[str, Any]:
    """Return this server's purpose, tool list, and worked examples."""
    return {
        "server": "formation-library",
        "purpose": "Exposes blitz-command's offensive formation library. Use it to discover valid formation_ids for play design, find formations supporting a run or pass concept, or look up player coordinates. Defensive formations are served by coverage-mcp.",
        "tools": [
            {"name": "list_formations", "description": "All formations with id, side, personnel, strength_side, tags. Paginated."},
            {"name": "get_formation", "description": "Full YAML: player coords, on_line flags, run_concepts, pass_concepts, era, famous_users."},
            {"name": "find_formations_by_tag", "description": "Exact tag match (e.g., 'shotgun', 'trips', '11-personnel', 'defense')."},
            {"name": "find_formations_by_concept", "description": "Formations whose run_concepts or pass_concepts include this concept."},
            {"name": "save_formation", "description": "Validate + write a new formation YAML to data/formations/."},
            {"name": "update_formation", "description": "Shallow-patch top-level fields of an existing formation (re-validates schema)."},
            {"name": "manifest", "description": "This document."},
        ],
        "examples": [
            "find_formations_by_tag('shotgun') → shotgun-2x2, shotgun-trips-right, ...",
            "save_formation(data) → {saved: True, path: '...', warnings: [...]}",
            "update_formation('singleback-trio', {'era': '1990s–present'}) → {updated: True, changed_keys: ['era']}",
        ],
    }


if __name__ == "__main__":
    mcp.run()
