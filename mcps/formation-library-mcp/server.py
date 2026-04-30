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

    Returns one object per formation. Use get_formation(id) for full details
    (player coordinates, run/pass concepts, era, famous users, etc).

    Returned shape (per item):
        {
          "id":            "shotgun-trips-right",
          "name":          "Shotgun Trips Right",
          "side":          "offense" | "defense",
          "personnel":     "11" | "12" | "21" | "10" | "20" | "4-3 base" | ...,
          "strength_side": "right" | "left" | "balanced",
          "tags":          ["shotgun", "trips", "11-personnel", ...],
        }

    Library currently contains both offensive formations (most with -left
    mirrors auto-generated) and defensive formations (front + coverage shell).

    Example:
        >>> all = list_formations()
        >>> [f['id'] for f in all if f['side'] == 'defense']
        ['defense-3-4-cover-3', 'defense-4-2-5-cover-2', 'defense-4-3-cover-2',
         'defense-4-3-cover-3', 'defense-46-bear-cover-0',
         'defense-dime-cover-4', 'defense-goal-line-6-2',
         'defense-nickel-cover-1', 'defense-prevent-3-2-6']
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
    """Get the full formation file for a specific formation_id.

    Returns the complete YAML object: players (with universal coordinates,
    on_line booleans, position labels), strengths, weaknesses, common_uses,
    run_concepts, pass_concepts, era, famous_users, tags, notes, and
    source notes. Defensive formations also include front, coverage_shell,
    responsibilities (per defender role + aim), best_against, and
    vulnerable_to fields.

    Common formation_id values:
        Under center:  'i-formation', 'i-formation-twins-weak', 'strong-i',
                       'weak-i', 'big-i', 'wing-t', 'singleback-ace',
                       'singleback-trio', 'goal-line', 'full-house'
        Shotgun:       'shotgun-2x2', 'shotgun-trips-right',
                       'shotgun-trips-left', 'shotgun-3x0',
                       'shotgun-2x1-te-strong', 'shotgun-2x1-te-weak',
                       'empty', 'trey-right', 'trey-left'
        Pistol:        'pistol', 'pistol-diamond'
        Specialty:     'wildcat', 'wishbone', 'flexbone', 'run-and-shoot'
        Defenses:      'defense-4-3-cover-3', 'defense-4-3-cover-2',
                       'defense-3-4-cover-3', 'defense-4-2-5-cover-2',
                       'defense-nickel-cover-1', 'defense-dime-cover-4',
                       'defense-46-bear-cover-0', 'defense-goal-line-6-2',
                       'defense-prevent-3-2-6'

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
        Defense-specific: 'defense', 'cover-3', 'cover-2', 'cover-1',
                          'cover-4', 'cover-0', '4-3', '3-4', '4-2-5',
                          '46-bear', 'nickel', 'dime', 'prevent',
                          'single-high', 'two-deep', 'base-defense',
                          'run-stopping', 'press-man', 'short-yardage',
                          'end-of-game'

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


if __name__ == "__main__":
    mcp.run()
