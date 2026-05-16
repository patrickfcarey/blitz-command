#!/usr/bin/env python3
"""Validation MCP server.

Central validation server for all blitz-command data types. Provides schema
validation plus concept-level linting for plays, formations, routes, concepts,
and game profiles.

The existing validate_play in play-library-mcp stays for backwards compat;
this server provides the canonical, unified validation surface.

Requires Python 3.10+.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Literal

import yaml
from jsonschema import ValidationError, validate
from mcp.server.fastmcp import FastMCP

REPO_ROOT = Path(__file__).resolve().parents[2]
FORMATIONS_DIR = REPO_ROOT / "data" / "formations"
ROUTES_DIR = REPO_ROOT / "data" / "routes"
CONCEPTS_DIR = REPO_ROOT / "data" / "concepts"

SCHEMAS: dict[str, Path] = {
    "play": REPO_ROOT / "schemas" / "play.schema.json",
    "formation": REPO_ROOT / "schemas" / "formation.schema.json",
    "route": REPO_ROOT / "schemas" / "route.schema.json",
    "blocking-scheme": REPO_ROOT / "schemas" / "blocking-scheme.schema.json",
    "run-concept": REPO_ROOT / "schemas" / "run-concept.schema.json",
    "pass-protection": REPO_ROOT / "schemas" / "pass-protection.schema.json",
    "pass-concept": REPO_ROOT / "schemas" / "pass-concept.schema.json",
    "philosophy": REPO_ROOT / "schemas" / "philosophy.schema.json",
    "game": REPO_ROOT / "schemas" / "game.schema.json",
}

_SCHEMA_CACHE: dict[str, dict] = {}
_ROUTES_CACHE: set[str] | None = None


def _load_schema(kind: str) -> dict:
    if kind not in _SCHEMA_CACHE:
        path = SCHEMAS.get(kind)
        if not path or not path.exists():
            raise ValueError(f"No schema for kind '{kind}'. Available: {list(SCHEMAS)}")
        with open(path) as f:
            _SCHEMA_CACHE[kind] = json.load(f)
    return _SCHEMA_CACHE[kind]


def _load_route_names() -> set[str]:
    global _ROUTES_CACHE
    if _ROUTES_CACHE is not None:
        return _ROUTES_CACHE
    names: set[str] = set()
    for p in ROUTES_DIR.glob("*.yaml"):
        try:
            with open(p) as f:
                r = yaml.safe_load(f)
            if r and r.get("name"):
                names.add(r["name"])
            for alias in (r or {}).get("aliases") or []:
                names.add(alias)
        except Exception:
            continue
    _ROUTES_CACHE = names
    return names


def _find_todo_placeholders(obj: Any, path: str = "") -> list[str]:
    found: list[str] = []
    if isinstance(obj, str):
        if "TODO" in obj:
            found.append(path or "(root)")
    elif isinstance(obj, dict):
        for k, v in obj.items():
            sub = f"{path}.{k}" if path else k
            found.extend(_find_todo_placeholders(v, sub))
    elif isinstance(obj, list):
        for i, item in enumerate(obj):
            found.extend(_find_todo_placeholders(item, f"{path}[{i}]"))
    return found


mcp = FastMCP("validation")


@mcp.tool()
def validate_play(play_data: dict[str, Any], strict: bool = False) -> dict[str, Any]:
    """Validate a play YAML/JSON object against the schema and concept lints.

    Returns:
        {
          "valid":    bool,
          "errors":   list[str],  # schema violations + hard failures
          "warnings": list[str],  # soft lints (ignored unless strict=True)
        }

    Concept lints checked:
        - pass/PA play missing primary_read
        - QB on pass play missing drop-back path
        - ball_carrier role missing path
        - run play missing ball_carrier
        - play-action play missing fake assignment
        - counter trey check (expects 2 OL pullers)
        - power check (expects 1 pulling guard)
        - route_name cross-reference against data/routes/
        - assignment.player cross-reference against formation roster
        - TODO placeholder scan

    Args:
        play_data: full play dict (from yaml.safe_load).
        strict: if True, any warning makes valid=False.
    """
    errors: list[str] = []
    warnings: list[str] = []

    try:
        validate(play_data, _load_schema("play"))
    except ValidationError as e:
        errors.append(f"schema: {e.message} (at {'/'.join(str(p) for p in e.absolute_path)})")
        return {"valid": False, "errors": errors, "warnings": warnings}

    formation_id = play_data.get("formation")
    formation_path = FORMATIONS_DIR / f"{formation_id}.yaml"
    formation_labels: set[str] = set()
    if formation_path.exists():
        try:
            with open(formation_path) as f:
                form = yaml.safe_load(f)
            formation_labels = {p["label"] for p in form.get("players", [])}
        except Exception as e:
            warnings.append(f"could not load formation {formation_id}: {e}")
    else:
        warnings.append(f"formation file not found: {formation_id}.yaml")

    play_type = play_data.get("play_type", "")
    assignments = play_data.get("assignments", [])
    by_player = {a.get("player"): a for a in assignments}

    if formation_labels:
        for a in assignments:
            p = a.get("player")
            if p and p not in formation_labels:
                errors.append(f"assignment references unknown player '{p}' (not in {formation_id})")

    if play_type in ("pass", "play-action") and not play_data.get("primary_read"):
        warnings.append(f"{play_type} play has no primary_read")

    if play_type == "run" and not play_data.get("ball_carrier"):
        warnings.append("run play has no ball_carrier")
    if play_type == "run" and not play_data.get("run_reads"):
        warnings.append("run play has no run_reads — add a 3-step read progression (backside key → frontside gap → cutback)")

    if play_type in ("pass", "play-action"):
        qb = by_player.get("QB")
        if qb and not qb.get("path"):
            warnings.append("QB on pass/PA play has no drop-back path")

    for a in assignments:
        if a.get("role") == "ball_carrier" and not a.get("path"):
            warnings.append(f"{a.get('player')} ball_carrier has no path waypoints")

    if play_type == "play-action":
        if not any(a.get("role") == "fake" for a in assignments):
            warnings.append("play-action play has no fake assignment (expected HB or FB)")

    name_lower = (play_data.get("name") or "").lower()
    aliases_lower = " ".join((play_data.get("aliases") or [])).lower()
    if "counter trey" in name_lower or "counter trey" in aliases_lower:
        ol_pulls = sum(
            1 for a in assignments
            if a.get("blocking_scheme") in ("pull-around", "pull-trap")
            and a.get("player") in ("LT", "LG", "RG", "RT")
        )
        if ol_pulls < 2:
            warnings.append(f"counter trey expects 2 OL pullers (found {ol_pulls})")

    if "power" in name_lower and "power read" not in name_lower:
        ol_pulls = sum(
            1 for a in assignments
            if a.get("blocking_scheme") in ("pull-around", "pull-trap")
            and a.get("player") in ("LG", "RG")
        )
        if ol_pulls < 1 and play_type == "run":
            warnings.append("power play expects at least 1 pulling guard")

    # Concept foreign-key checks
    for ref_field, dir_name in (
        ("run_concept_ref", "run-concepts"),
        ("pass_concept_ref", "pass-concepts"),
        ("pass_protection_ref", "pass-protections"),
        ("philosophy_ref", "philosophies"),
    ):
        ref = play_data.get(ref_field)
        if ref:
            target = CONCEPTS_DIR / dir_name / f"{ref}.yaml"
            if not target.exists():
                warnings.append(f"{ref_field} '{ref}' not found at {target}")

    route_names = _load_route_names()
    if route_names:
        bad_refs: list[str] = []
        for a in assignments:
            if a.get("role") == "route":
                rn = a.get("route_name")
                if not rn or "TODO" in rn:
                    continue
                base = rn.split(" or ", 1)[0].split("-or-", 1)[0]
                if base not in route_names and rn not in route_names:
                    bad_refs.append(f"{a.get('player')}: '{rn}'")
        if bad_refs:
            warnings.append(
                f"{len(bad_refs)} route_name(s) not in data/routes/: "
                + ", ".join(bad_refs[:5])
                + ("..." if len(bad_refs) > 5 else "")
            )

    todo_paths = _find_todo_placeholders(play_data)
    if todo_paths:
        warnings.append(
            f"{len(todo_paths)} TODO placeholder(s) remain: "
            + ", ".join(todo_paths[:8])
            + ("..." if len(todo_paths) > 8 else "")
        )

    valid = (len(errors) == 0) and (not strict or len(warnings) == 0)
    return {"valid": valid, "errors": errors, "warnings": warnings}


@mcp.tool()
def validate_formation(formation_data: dict[str, Any], strict: bool = False) -> dict[str, Any]:
    """Validate a formation YAML/JSON object against the formation schema.

    Lints checked:
        - Schema validation
        - Offense: must have 7+ players on line of scrimmage (on_line == True)
        - Offense: must have exactly 11 players
        - Defense: must have 'front' and 'coverage_shell' fields

    Args:
        formation_data: full formation dict.
        strict: if True, warnings are errors.
    """
    errors: list[str] = []
    warnings: list[str] = []

    try:
        validate(formation_data, _load_schema("formation"))
    except ValidationError as e:
        errors.append(f"schema: {e.message} (at {'/'.join(str(p) for p in e.absolute_path)})")
        return {"valid": False, "errors": errors, "warnings": warnings}

    side = formation_data.get("side", "offense")
    players = formation_data.get("players", [])

    if side == "offense":
        if len(players) != 11:
            warnings.append(f"offense formation has {len(players)} players (expected 11)")
        on_line = sum(1 for p in players if p.get("on_line"))
        if on_line < 7:
            warnings.append(f"offense has {on_line} players on line (minimum 7 required by football rules)")
    elif side == "defense":
        if not formation_data.get("front"):
            warnings.append("defense formation missing 'front' field")
        if not formation_data.get("coverage_shell"):
            warnings.append("defense formation missing 'coverage_shell' field")

    valid = (len(errors) == 0) and (not strict or len(warnings) == 0)
    return {"valid": valid, "errors": errors, "warnings": warnings}


@mcp.tool()
def validate_route(route_data: dict[str, Any], strict: bool = False) -> dict[str, Any]:
    """Validate a route YAML/JSON object against the route schema.

    Args:
        route_data: full route dict.
        strict: if True, warnings are errors.
    """
    errors: list[str] = []
    warnings: list[str] = []

    try:
        validate(route_data, _load_schema("route"))
    except ValidationError as e:
        errors.append(f"schema: {e.message} (at {'/'.join(str(p) for p in e.absolute_path)})")
        return {"valid": False, "errors": errors, "warnings": warnings}

    path = route_data.get("path", [])
    if len(path) < 2:
        warnings.append("route path has fewer than 2 waypoints (cannot draw)")

    valid = (len(errors) == 0) and (not strict or len(warnings) == 0)
    return {"valid": valid, "errors": errors, "warnings": warnings}


@mcp.tool()
def validate_concept(
    concept_data: dict[str, Any],
    kind: str,
    strict: bool = False,
) -> dict[str, Any]:
    """Validate a concept YAML/JSON object by kind.

    Args:
        concept_data: full concept dict.
        kind: one of 'run-concept', 'pass-concept', 'blocking-scheme',
              'pass-protection', 'philosophy'.
        strict: if True, warnings are errors.
    """
    valid_kinds = ("run-concept", "pass-concept", "blocking-scheme", "pass-protection", "philosophy")
    if kind not in valid_kinds:
        return {
            "valid": False,
            "errors": [f"unknown kind '{kind}'. Use one of: {list(valid_kinds)}"],
            "warnings": [],
        }

    errors: list[str] = []
    warnings: list[str] = []

    try:
        validate(concept_data, _load_schema(kind))
    except ValidationError as e:
        errors.append(f"schema: {e.message} (at {'/'.join(str(p) for p in e.absolute_path)})")
        return {"valid": False, "errors": errors, "warnings": warnings}

    # Cross-reference checks for run-concept
    if kind == "run-concept":
        scheme_ref = concept_data.get("blocking_scheme_ref")
        if scheme_ref:
            target = CONCEPTS_DIR / "blocking-schemes" / f"{scheme_ref}.yaml"
            if not target.exists():
                warnings.append(f"blocking_scheme_ref '{scheme_ref}' not found")

    # Tendency profile sum for philosophy
    if kind == "philosophy":
        tp = concept_data.get("tendency_profile", {})
        total = sum(tp.get(k, 0.0) for k in ("run_pct", "pass_pct", "pa_pct", "rpo_pct", "screen_pct"))
        if abs(total - 1.0) > 0.02:
            warnings.append(f"tendency_profile sums to {total:.3f} (expected 1.0 ±0.02)")

    valid = (len(errors) == 0) and (not strict or len(warnings) == 0)
    return {"valid": valid, "errors": errors, "warnings": warnings}


@mcp.tool()
def validate_game_profile(profile_data: dict[str, Any], strict: bool = False) -> dict[str, Any]:
    """Validate a game profile YAML/JSON object against the game schema.

    Lints checked:
        - Schema validation
        - If custom_play_support is True, grid/scale/limits must not be null
        - If custom_play_support is False, grid/scale/limits should be null

    Args:
        profile_data: full game profile dict.
        strict: if True, warnings are errors.
    """
    errors: list[str] = []
    warnings: list[str] = []

    try:
        validate(profile_data, _load_schema("game"))
    except ValidationError as e:
        errors.append(f"schema: {e.message} (at {'/'.join(str(p) for p in e.absolute_path)})")
        return {"valid": False, "errors": errors, "warnings": warnings}

    has_editor = profile_data.get("custom_play_support", False)
    if has_editor and profile_data.get("grid") is None:
        warnings.append("custom_play_support=true but grid is null — add grid dimensions")
    if not has_editor and profile_data.get("grid") is not None:
        warnings.append("custom_play_support=false but grid is set — consider setting null")

    valid = (len(errors) == 0) and (not strict or len(warnings) == 0)
    return {"valid": valid, "errors": errors, "warnings": warnings}


@mcp.tool()
def lint_play(play_data: dict[str, Any]) -> dict[str, Any]:
    """Run concept-level lints only (no schema validation).

    Faster than validate_play for AI-authored plays that are already schema-valid.
    Checks concept logic, foreign key refs, route refs, and TODO placeholders.

    Returns:
        {
          "clean":    bool,
          "warnings": list[str],
        }

    Args:
        play_data: full play dict (assumed schema-valid; schema errors silently skipped).
    """
    result = validate_play(play_data, strict=False)
    return {
        "clean": len(result["warnings"]) == 0,
        "warnings": result["warnings"],
    }


@mcp.tool()
def manifest() -> dict[str, Any]:
    """Return this server's purpose, tool list, and worked examples."""
    return {
        "server": "validation",
        "purpose": "Central validation server for all blitz-command data types. Use validate_play before saving any new play. Use validate_concept / validate_game_profile when authoring new data files.",
        "tools": [
            {"name": "validate_play", "description": "Schema + concept lints: formation cross-ref, route ref, concept foreign keys, TODO scan."},
            {"name": "validate_formation", "description": "Schema + 11-man + 7-on-line checks."},
            {"name": "validate_route", "description": "Schema + path waypoint check."},
            {"name": "validate_concept", "description": "Schema for run-concept / pass-concept / blocking-scheme / pass-protection / philosophy."},
            {"name": "validate_game_profile", "description": "Schema + editor-fields consistency."},
            {"name": "lint_play", "description": "Concept-level lints only (no schema; fast path for pre-validated plays)."},
            {"name": "manifest", "description": "This document."},
        ],
        "examples": [
            "validate_play(play_data) → {valid: True, errors: [], warnings: ['QB has no path']}",
            "validate_concept(data, 'philosophy') → checks tendency_profile sums to 1.0",
        ],
    }


if __name__ == "__main__":
    mcp.run()
