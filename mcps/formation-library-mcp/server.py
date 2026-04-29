#!/usr/bin/env python3
"""Formation Library MCP server.

Exposes blitz-command's formation library to AI agents over the Model Context
Protocol. Reads YAML files from data/formations/, validates each against
schemas/formation.schema.json, and serves them via four tools.

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


def _load_schema() -> dict:
    with open(SCHEMA_PATH) as f:
        return json.load(f)


def _load_all() -> dict[str, dict[str, Any]]:
    """Load every formation file. Skip files that fail validation, warning to stderr."""
    schema = _load_schema()
    formations: dict[str, dict[str, Any]] = {}
    for path in sorted(FORMATIONS_DIR.glob("*.yaml")):
        try:
            with open(path) as f:
                data = yaml.safe_load(f)
            if not data:
                continue
            validate(data, schema)
            formations[path.stem] = data
        except (ValidationError, yaml.YAMLError) as e:
            print(f"WARN: skipping {path.name}: {e}", file=sys.stderr)
    return formations


mcp = FastMCP("formation-library")


@mcp.tool()
def list_formations() -> list[dict[str, Any]]:
    """List every formation in the library with brief metadata.

    Returns a list of objects with id, name, side, personnel, strength_side,
    and tags. Use get_formation(id) for full details on a specific formation.
    """
    return [
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


@mcp.tool()
def get_formation(formation_id: str) -> dict[str, Any]:
    """Get full details on a specific formation.

    Returns the complete formation file: players (with universal coordinates),
    strengths, weaknesses, common_uses, run_concepts, pass_concepts, era,
    famous_users, tags, notes, and source notes.

    Args:
        formation_id: file stem, e.g. 'i-formation', 'shotgun-trips-right'.
    """
    formations = _load_all()
    if formation_id not in formations:
        available = sorted(formations.keys())
        raise ValueError(
            f"No formation with id '{formation_id}'. Available: {available}"
        )
    return formations[formation_id]


@mcp.tool()
def find_formations_by_tag(tag: str) -> list[str]:
    """Return formation IDs whose tags include the given tag (case-insensitive).

    Common tags: 'spread', 'power', 'jumbo', 'shotgun', 'empty', 'pro-style',
    'twins', 'trips', '11-personnel', '21-personnel', '22-personnel',
    '32-personnel', 'modern', 'high-school', 'college', 'nfl', 'any-level'.
    """
    tag_lower = tag.lower()
    return [
        fid for fid, f in _load_all().items()
        if tag_lower in [t.lower() for t in f.get("tags", [])]
    ]


@mcp.tool()
def find_formations_by_concept(concept: str) -> list[str]:
    """Return formation IDs whose run_concepts or pass_concepts include this concept.

    Useful for "what formations support inside zone?" type queries. Match is
    case-insensitive and exact (whole-name); concept names follow kebab-case
    (e.g. 'inside-zone', 'power-o', 'four-verticals', 'mesh').

    Args:
        concept: concept identifier, e.g. 'inside-zone', 'pa-post', 'mesh'.
    """
    concept_lower = concept.lower()
    matches: list[str] = []
    for fid, f in _load_all().items():
        runs = [c.lower() for c in f.get("run_concepts", [])]
        passes = [c.lower() for c in f.get("pass_concepts", [])]
        if concept_lower in runs or concept_lower in passes:
            matches.append(fid)
    return matches


if __name__ == "__main__":
    mcp.run()
