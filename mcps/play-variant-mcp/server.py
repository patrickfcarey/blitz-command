#!/usr/bin/env python3
"""Play Variant MCP server.

Provides tools for generating play variants: mirrors, strength flips, and
(in Phase 7) full play-family generation. Currently ships mirror_play_variant
and flip_strength as the initial toolset.

Requires Python 3.10+.
"""
from __future__ import annotations

import copy
import re
import sys
from pathlib import Path
from typing import Any

import yaml
from mcp.server.fastmcp import FastMCP

REPO_ROOT = Path(__file__).resolve().parents[2]
PLAYS_DIR = REPO_ROOT / "data" / "plays"

mcp = FastMCP("play-variant")


def _load_play(play_id: str) -> dict[str, Any]:
    path = PLAYS_DIR / f"{play_id}.yaml"
    if not path.exists():
        raise ValueError(f"Play not found: {play_id}. Call list_plays() in play-library-mcp for ids.")
    with open(path) as f:
        return yaml.safe_load(f)


def _mirror_coords(path: list[list[float]]) -> list[list[float]]:
    """Flip all x coordinates to produce a mirrored path."""
    return [[-wp[0], wp[1]] for wp in path]


def _mirror_play_data(play: dict[str, Any]) -> dict[str, Any]:
    """Return a deep copy of the play with all x coordinates mirrored."""
    mirrored = copy.deepcopy(play)

    # Mirror assignment paths
    for assign in mirrored.get("assignments", []):
        if assign.get("path"):
            assign["path"] = _mirror_coords(assign["path"])

    # Update strength/direction fields
    for field in ("strength_side", "run_direction"):
        val = mirrored.get(field)
        if val == "right":
            mirrored[field] = "left"
        elif val == "left":
            mirrored[field] = "right"

    # Update play_id: add -left or remove -left suffix
    old_id = mirrored.get("play_id", "")
    if old_id.endswith("-left"):
        mirrored["play_id"] = old_id[:-5]
        mirrored["name"] = (mirrored.get("name") or "").replace(" Left", "").replace(" left", "").strip()
        mirrored["formation"] = (mirrored.get("formation") or "").replace("-left", "")
    else:
        mirrored["play_id"] = old_id + "-left"
        mirrored["name"] = (mirrored.get("name") or "") + " Left"
        mirrored["formation"] = (mirrored.get("formation") or "") + "-left"

    return mirrored


mcp = FastMCP("play-variant")


@mcp.tool()
def mirror_play_variant(play_id: str) -> dict[str, Any]:
    """Generate a mirrored (left/right flipped) variant of the given play.

    Returns the mirrored play as a dict. Does NOT write to disk — call
    save_play() in play-library-mcp if you want to persist it.

    Mirroring rules:
        - All assignment path x-coordinates are negated
        - strength_side / run_direction 'right' → 'left' (and vice-versa)
        - play_id: appends '-left' (or removes it if already present)
        - formation: appends '-left' (or removes it)
        - name: appends ' Left' (or removes it)

    Example:
        >>> v = mirror_play_variant('singleback-trio-mesh')
        >>> v['play_id']
        'singleback-trio-mesh-left'
        >>> v['formation']
        'singleback-trio-left'

    Args:
        play_id: existing play file stem (e.g., 'singleback-trio-mesh').
    """
    play = _load_play(play_id)
    return _mirror_play_data(play)


@mcp.tool()
def flip_strength(play_id: str) -> dict[str, Any]:
    """Flip a play to its strong/weak-side mirror, renaming to reflect the flip.

    Similar to mirror_play_variant but targets plays that have explicit
    'strong' or 'weak' in their name rather than left/right.

    Returns the flipped play dict. Does NOT write to disk.

    Example:
        >>> v = flip_strength('i-formation-power-strong')
        >>> v['play_id']
        'i-formation-power-weak'

    Args:
        play_id: play file stem with 'strong' or 'weak' in the name.
    """
    play = _load_play(play_id)
    flipped = _mirror_play_data(play)

    # Rename strong ↔ weak
    for key in ("play_id", "name", "formation"):
        val = flipped.get(key) or ""
        if "strong" in val.lower():
            flipped[key] = re.sub(r"(?i)strong", lambda m: "weak" if m.group().islower() else "Weak", val)
        elif "weak" in val.lower():
            flipped[key] = re.sub(r"(?i)weak", lambda m: "strong" if m.group().islower() else "Strong", val)

    return flipped


@mcp.tool()
def generate_play_family_stub(base_play_id: str) -> dict[str, Any]:
    """Return a stub play-family dict ready to be filled in.

    Phase 7 placeholder — the full generation algorithm (P7-T03) will replace
    this with a scored candidate list. For now, returns a scaffold with the
    base play's metadata and empty companion slots.

    Args:
        base_play_id: play to use as the family anchor.
    """
    play = _load_play(base_play_id)
    return {
        "family_id": f"{base_play_id}-family",
        "name": f"{play.get('name', base_play_id)} Family",
        "description": "TODO: describe what makes this a coherent play family.",
        "formation_id": play.get("formation"),
        "philosophy": play.get("philosophy"),
        "base_play_id": base_play_id,
        "companion_play_ids": [],
        "tags": play.get("tags", []),
        "verification_status": "unverified",
        "source_notes": [],
        "_note": "Stub — run generate_play_family() (Phase 7) for a scored companion list.",
    }


@mcp.tool()
def manifest() -> dict[str, Any]:
    """Return this server's purpose, tool list, and worked examples."""
    return {
        "server": "play-variant",
        "purpose": "Generates play variants: left/right mirrors, strong/weak flips, and play-family stubs. Phase 7 will add scored family generation. Use mirror_play_variant after designing any right-strength play.",
        "tools": [
            {"name": "mirror_play_variant", "description": "Flip all x-coords + update play_id/name/formation for left/right mirror."},
            {"name": "flip_strength", "description": "Swap strong ↔ weak in play_id, name, and formation."},
            {"name": "generate_play_family_stub", "description": "Return an empty play-family YAML scaffold (Phase 7 placeholder)."},
            {"name": "manifest", "description": "This document."},
        ],
        "examples": [
            "mirror_play_variant('singleback-trio-mesh') → play_id: 'singleback-trio-mesh-left'",
            "generate_play_family_stub('i-formation-power') → family scaffold with empty companion_play_ids",
        ],
    }


if __name__ == "__main__":
    mcp.run()
