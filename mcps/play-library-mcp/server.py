#!/usr/bin/env python3
"""Play Library MCP server.

Exposes blitz-command's play library to AI agents over the Model Context
Protocol. Reads YAML files from data/plays/, validates each against
schemas/play.schema.json, and serves them via these tools:

  Discovery / read:
    - list_plays
    - get_play
    - find_plays_by_formation
    - find_plays_by_tag
    - find_plays_vs_defense

  Authoring / closing the design loop:
    - validate_play(play_data, strict=False)  — schema check + concept lints
    - render_play(play_id, game_id, ...)      — return SVG of play in editor grid
    - build_starter_play(formation_id, play_type, philosophy=None)
                                              — return a 70%-filled YAML scaffold

Requires Python 3.10+ (mcp SDK requirement).
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from typing import Any

import yaml
from jsonschema import ValidationError, validate
from mcp.server.fastmcp import FastMCP

REPO_ROOT = Path(__file__).resolve().parents[2]
PLAYS_DIR = REPO_ROOT / "data" / "plays"
FORMATIONS_DIR = REPO_ROOT / "data" / "formations"
GAMES_DIR = REPO_ROOT / "data" / "games"
SCHEMA_PATH = REPO_ROOT / "schemas" / "play.schema.json"
DRAW_SCRIPT_PATH = REPO_ROOT / "tools" / "draw-play" / "draw.py"


def _import_draw_module():
    """Lazy-load the draw script as a module so we can call render() directly."""
    spec = importlib.util.spec_from_file_location("draw_play", DRAW_SCRIPT_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot import draw script at {DRAW_SCRIPT_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _load_schema() -> dict:
    with open(SCHEMA_PATH) as f:
        return json.load(f)


def _load_all() -> dict[str, dict[str, Any]]:
    """Load every play file. Skip files that fail validation, warning to stderr."""
    schema = _load_schema()
    plays: dict[str, dict[str, Any]] = {}
    for path in sorted(PLAYS_DIR.glob("*.yaml")):
        try:
            with open(path) as f:
                data = yaml.safe_load(f)
            if not data:
                continue
            validate(data, schema)
            plays[path.stem] = data
        except (ValidationError, yaml.YAMLError) as e:
            print(f"WARN: skipping {path.name}: {e}", file=sys.stderr)
    return plays


mcp = FastMCP("play-library")


@mcp.tool()
def list_plays() -> list[dict[str, Any]]:
    """List every play in the library with brief metadata.

    Returns one object per play. Use get_play(id) when you need the full
    assignments / routes / strengths / etc.

    Returned shape (per item):
        {
          "id":           "singleback-trio-mesh",
          "name":         "Mesh",
          "formation":    "singleback-trio",
          "play_type":    "pass",       # see find_plays_by_tag for full enum
          "ball_carrier": "QB",
          "tags":         ["pass", "spread", "mesh", ...],
        }

    Example:
        >>> all = list_plays()
        >>> len(all)
        130
        >>> [p['id'] for p in all if p['play_type'] == 'play-action'][:3]
        ['big-i-pa-naked', 'flexbone-pa-bootleg', 'goal-line-pa-te-corner']
    """
    return [
        {
            "id": pid,
            "name": p.get("name"),
            "formation": p.get("formation"),
            "play_type": p.get("play_type"),
            "ball_carrier": p.get("ball_carrier"),
            "tags": p.get("tags", []),
        }
        for pid, p in _load_all().items()
    ]


@mcp.tool()
def get_play(play_id: str) -> dict[str, Any]:
    """Get the full play file for a specific play_id.

    Returns the complete YAML object: per-player assignments (with roles
    like ball_carrier / lead_block / route / pass_block / handoff / fake),
    motions (mandatory / optional with end_position), routes with depths,
    blocking schemes, reads (primary/secondary/tertiary/checkdown),
    strengths, weaknesses, best_vs_defense, worst_vs_defense, era,
    philosophy, famous_examples, tags, and source notes.

    Common play_id stems by formation:
        I-Form:       'i-formation-power-o', 'i-formation-iso',
                      'i-formation-counter-trey', 'i-formation-pa-cross'
        Singleback:   'singleback-trio-mesh', 'singleback-ace-power-o',
                      'singleback-trio-inside-zone'
        Shotgun:      'shotgun-2x2-snag', 'shotgun-trips-right-flood',
                      'shotgun-2x2-jet-sweep'
        Pistol:       'pistol-inside-zone-read', 'pistol-rpo-bubble',
                      'pistol-bootleg'
        Wing-T:       'wing-t-buck-sweep', 'wing-t-belly', 'wing-t-trap',
                      'wing-t-waggle'
        Wildcat:      'wildcat-power', 'wildcat-counter', 'wildcat-jet-sweep',
                      'wildcat-speed-option'
        Specialty:    'wishbone-triple-option', 'flexbone-triple-option',
                      'pistol-diamond-power-read', 'run-and-shoot-choice'
        Goal Line:    'goal-line-power', 'goal-line-qb-sneak',
                      'goal-line-pa-te-corner'

    Every right-side play has a '-left' mirror. Use list_plays() for the
    full inventory.

    Example:
        >>> p = get_play('singleback-trio-mesh')
        >>> p['primary_read']
        'TE'
        >>> p['ball_carrier']
        'QB'

    Args:
        play_id: file stem (no .yaml extension).
    """
    plays = _load_all()
    if play_id not in plays:
        available = sorted(plays.keys())
        # Suggest closest by prefix
        suggestions = [a for a in available if play_id in a or a.startswith(play_id[:6])]
        msg = f"No play with id '{play_id}'."
        if suggestions:
            msg += f" Did you mean: {suggestions[:5]}?"
        else:
            msg += f" {len(available)} plays available; call list_plays() for ids."
        raise ValueError(msg)
    return plays[play_id]


@mcp.tool()
def find_plays_by_formation(formation_id: str) -> list[str]:
    """Return play IDs that run from a given formation.

    Useful for "what plays do we have from X formation?" queries.

    Common formation_id values:
        Under center:  'i-formation', 'strong-i', 'weak-i', 'big-i',
                       'wing-t', 'singleback-ace', 'singleback-trio',
                       'goal-line', 'full-house'
        Shotgun:       'shotgun-2x2', 'shotgun-trips-right',
                       'shotgun-trips-left', 'shotgun-3x0', 'empty',
                       'trey-right', 'trey-left'
        Pistol:        'pistol', 'pistol-diamond'
        Specialty:     'wildcat', 'wishbone', 'flexbone', 'run-and-shoot'

    Use get_formation(formation_id) on the formation-library MCP to inspect
    the formation itself.

    Example:
        >>> find_plays_by_formation('singleback-trio')
        ['singleback-trio-four-verticals', 'singleback-trio-hb-draw',
         'singleback-trio-inside-zone', 'singleback-trio-mesh', ...]

    Args:
        formation_id: formation file stem.
    """
    return [
        pid for pid, p in _load_all().items()
        if p.get("formation") == formation_id
    ]


@mcp.tool()
def find_plays_by_tag(tag: str) -> list[str]:
    """Return play IDs whose tags include the given tag (case-insensitive, exact match).

    Tag categories (sample values from the current library):

        Play type:   'run', 'pass', 'pa' (play-action), 'rpo', 'screen',
                     'option', 'special'
        Concept:     'mesh', 'stick', 'smash', 'snag', 'four-verticals',
                     'jet-sweep', 'flood', 'sail', 'y-cross', 'y-stick',
                     'slant', 'switch', 'choice', 'wheel-route'
        Run scheme:  'inside-zone', 'outside-zone', 'power-run', 'power-o',
                     'counter', 'trap', 'draw', 'iso', 'toss', 'belly',
                     'sweep', 'zone-read', 'split-zone', 'power-read',
                     'triple-option', 'midline'
        Philosophy:  'air-raid', 'west-coast', 'pro-style', 'spread',
                     'spread-option', 'power-run', 'zone-run', 'coryell',
                     'speed-option', 'option', 'erhardt-perkins'
        Personnel:   '11-personnel', '12-personnel', '20-personnel',
                     '21-personnel', '10-personnel', '22-personnel'
        Formation:   'shotgun', 'pistol', 'singleback', 'wing-t', 'wildcat',
                     'wishbone', 'flexbone', 'i-form', 'empty', 'trips',
                     'trey', 'bunch', '4-wide'
        Level:       'any-level', 'high-school', 'college', 'nfl'
        Era:         'modern', 'throwback'
        Special:     'short-yardage', 'goal-line', 'red-zone', 'misdirection',
                     'quick-game', 'deep', 'mandatory-motion', 'service-academy',
                     'tush-push', 'rpo-friendly'

    Example:
        >>> find_plays_by_tag('rpo')
        ['pistol-rpo-bubble', 'pistol-rpo-bubble-left',
         'shotgun-2x2-rpo-slant', ...]
        >>> find_plays_by_tag('air-raid')
        ['empty-mesh', 'empty-mesh-left', 'singleback-trio-mesh', ...]

    Args:
        tag: tag to search for (case-insensitive, exact match — not substring).
    """
    tag_lower = tag.lower()
    return [
        pid for pid, p in _load_all().items()
        if tag_lower in [t.lower() for t in p.get("tags", [])]
    ]


@mcp.tool()
def find_plays_vs_defense(coverage: str) -> list[dict[str, str]]:
    """Find plays that EXPLOIT or STRUGGLE against a specific defensive look.

    Returns a list of objects with:
        - "play_id" — the play
        - "rating"  — "best" if the play beats this defense, "worst" if it
                      gets neutralized

    Substring match (case-insensitive). 'cover-2' matches 'cover-2',
    'cover-2 trap', 'cover-2 invert'.

    Common coverage values to query:
        Coverage shells: 'cover-0', 'cover-1', 'cover-2', 'cover-3',
                         'cover-4', 'cover-1 robber', 'cover-2 robber',
                         'cover-2 trap', 'tampa 2', 'man-free', 'quarters'
        Fronts:          'over-front', 'under-front', 'bear', '4-3', '3-4',
                         '4-2-5', 'nickel', 'dime', '8-man fronts'
        Coverage type:   'man', 'press-man', 'zone', 'pattern-match', 'banjo',
                         'bracket'
        Pressure:        'zero blitz', 'fire zone', 'cross-stunt'
        Specific roles:  'scrape-exchange', 'flat defender'

    Example:
        >>> find_plays_vs_defense('cover-3')
        [{'play_id': 'singleback-trio-flood', 'rating': 'best'},
         {'play_id': 'shotgun-trips-right-flood', 'rating': 'best'},
         {'play_id': 'goal-line-pa-te-corner', 'rating': 'best'},
         {'play_id': 'i-formation-pa-cross', 'rating': 'worst'}, ...]

    Args:
        coverage: substring of a defensive coverage / front / scheme name.
    """
    coverage_lower = coverage.lower()
    matches: list[dict[str, str]] = []
    for pid, p in _load_all().items():
        best = [c.lower() for c in p.get("best_vs_defense", [])]
        worst = [c.lower() for c in p.get("worst_vs_defense", [])]
        if any(coverage_lower in c for c in best):
            matches.append({"play_id": pid, "rating": "best"})
        elif any(coverage_lower in c for c in worst):
            matches.append({"play_id": pid, "rating": "worst"})
    return matches


@mcp.tool()
def validate_play(play_data: dict[str, Any], strict: bool = False) -> dict[str, Any]:
    """Validate a play YAML/JSON object against the play schema and concept lints.

    Use this BEFORE writing a play to disk — catches schema errors and common
    play-design mistakes early.

    Returns an object with:
        valid (bool)        — True if no errors (warnings allowed unless strict)
        errors (list[str])  — schema violations or hard-fail concept errors
        warnings (list[str])— soft issues (missing path, no read tree, etc.)

    Concept lints (warnings, not errors unless strict=True):
        - pass play has no primary_read field
        - QB on a pass play has no path
        - any ball_carrier role has no path
        - run play has no ball_carrier field
        - mesh / split-zone / counter checks (e.g., counter trey wants 2 pullers)
        - PA play has no fake handoff (HB or FB role != fake)
        - assignment references a player not in the formation

    Example:
        play = yaml.safe_load(open('my-new-play.yaml'))
        result = validate_play(play, strict=False)
        if not result['valid']:
            for e in result['errors']: print('ERROR:', e)

    Args:
        play_data: full play object (typically yaml.safe_load of a candidate file).
        strict:    if True, warnings count as errors (valid==False if any warnings).
    """
    errors: list[str] = []
    warnings: list[str] = []

    schema = _load_schema()
    try:
        validate(play_data, schema)
    except ValidationError as e:
        errors.append(f"schema: {e.message} (at {'/'.join(str(p) for p in e.absolute_path)})")
        return {"valid": False, "errors": errors, "warnings": warnings}

    # Resolve formation roster for cross-checks
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

    # Cross-check: every assignment.player must exist in the formation
    if formation_labels:
        for a in assignments:
            p = a.get("player")
            if p and p not in formation_labels:
                errors.append(f"assignment references unknown player '{p}' (not in {formation_id})")

    # Pass play needs a primary_read
    if play_type in ("pass", "play-action") and not play_data.get("primary_read"):
        warnings.append(f"{play_type} play has no primary_read")

    # Run play needs a ball_carrier
    if play_type == "run" and not play_data.get("ball_carrier"):
        warnings.append("run play has no ball_carrier")

    # QB on pass plays should have a path
    if play_type in ("pass", "play-action"):
        qb = by_player.get("QB")
        if qb and not qb.get("path"):
            warnings.append("QB on pass/PA play has no drop-back path")

    # Any ball_carrier role assignment should have a path
    for a in assignments:
        if a.get("role") == "ball_carrier" and not a.get("path"):
            warnings.append(f"{a.get('player')} ball_carrier has no path waypoints")

    # PA play should have a fake assignment (HB / FB usually)
    if play_type == "play-action":
        has_fake = any(a.get("role") == "fake" for a in assignments)
        if not has_fake:
            warnings.append("play-action play has no fake assignment (expected HB or FB)")

    # Counter trey check: 2 pulling OL
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

    # Power scheme check: at least 1 pulling guard
    if "power" in name_lower and "power read" not in name_lower:
        ol_pulls = sum(
            1 for a in assignments
            if a.get("blocking_scheme") in ("pull-around", "pull-trap")
            and a.get("player") in ("LG", "RG")
        )
        if ol_pulls < 1 and play_type == "run":
            warnings.append("power play expects at least 1 pulling guard")

    # TODO placeholder scan — flag scaffolds that haven't been filled in
    todo_paths = _find_todo_placeholders(play_data)
    if todo_paths:
        warnings.append(
            f"{len(todo_paths)} TODO placeholder(s) remain — fill before saving: "
            + ", ".join(todo_paths[:8])
            + ("..." if len(todo_paths) > 8 else "")
        )

    valid = (len(errors) == 0) and (not strict or len(warnings) == 0)
    return {"valid": valid, "errors": errors, "warnings": warnings}


def _find_todo_placeholders(obj: Any, path: str = "") -> list[str]:
    """Recursively find every field path whose value contains 'TODO'."""
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
            sub = f"{path}[{i}]"
            found.extend(_find_todo_placeholders(item, sub))
    return found


@mcp.tool()
def render_play(
    play_id: str,
    game_id: str,
    defense_id: str | None = None,
    show: str = "both",
    field: str = "long",
) -> str:
    """Render a play as SVG, returning the SVG markup directly as a string.

    Closes the design loop — the AI can render-validate-iterate without
    leaving the MCP session.

    Args:
        play_id:    play file stem, e.g. 'singleback-trio-mesh'.
        game_id:    game directory name, e.g. 'madden-05-ps2', 'ncaa-06-ps2'.
        defense_id: optional defensive formation overlay, e.g.
                    'defense-4-3-cover-3'. If None, uses play.vs_defense if set.
        show:       which assignments to render — 'offense', 'defense',
                    'both' (default), or 'none' (just players).
        field:      'short' (LOS+5yd) or 'long' (LOS+30yd, default).

    Returns:
        SVG markup as a string. Save it to a .svg file or embed in markdown.

    Example:
        svg = render_play(
            'singleback-trio-mesh',
            'madden-05-ps2',
            defense_id='defense-4-3-cover-3',
            show='both',
            field='long',
        )
        with open('mesh-vs-c3.svg', 'w') as f:
            f.write(svg)
    """
    draw = _import_draw_module()

    play_path = PLAYS_DIR / f"{play_id}.yaml"
    if not play_path.exists():
        raise ValueError(f"Play not found: {play_id}")
    with open(play_path) as f:
        play = yaml.safe_load(f)

    formation_path = FORMATIONS_DIR / f"{play['formation']}.yaml"
    if not formation_path.exists():
        raise ValueError(f"Formation not found: {play['formation']}")
    with open(formation_path) as f:
        formation = yaml.safe_load(f)

    profile_path = GAMES_DIR / game_id / "editor-grid.yaml"
    if not profile_path.exists():
        raise ValueError(f"Game profile not found: {game_id}")
    with open(profile_path) as f:
        profile = yaml.safe_load(f)

    if defense_id is None:
        defense_id = play.get("vs_defense")

    defense = None
    if defense_id:
        def_path = FORMATIONS_DIR / f"{defense_id}.yaml"
        if not def_path.exists():
            raise ValueError(f"Defense not found: {defense_id}")
        with open(def_path) as f:
            defense = yaml.safe_load(f)

    route_lib = draw.load_route_library()
    svg, _warnings = draw.render(
        profile,
        play=play,
        formation=formation,
        defense=defense,
        route_lib=route_lib,
        show=show,
        field=field,
    )
    return svg


@mcp.tool()
def build_starter_play(
    formation_id: str,
    play_type: str,
    philosophy: str | None = None,
    play_name: str | None = None,
) -> dict[str, Any]:
    """Return a 70%-filled play YAML scaffold for the given formation + play type.

    Smaller AIs are much better at FILLING IN templates than authoring from
    scratch. This tool gives them a structurally-valid skeleton with all
    the OL pre-assigned, all skill-position players listed with placeholder
    role fields, and all required schema fields populated with sensible
    defaults the AI can override.

    What the scaffold pre-fills:
        - play_id (kebab-cased from name + formation)
        - formation reference + ball_carrier guess (HB for run, QB for pass)
        - 5 OL pre-assigned (pass_block for pass/PA, run_block for run/RPO)
        - all skill players present in the formation listed with placeholder role
        - empty motions, strengths, weaknesses, best/worst_vs_defense, tags
        - verification_status: 'unverified'

    Returns the YAML as a dict. The AI fills in routes / paths / blocking
    scheme details and calls validate_play() to check before saving.

    Args:
        formation_id: formation file stem, e.g. 'singleback-trio'.
        play_type:    one of 'run', 'pass', 'play-action', 'rpo', 'screen',
                      'option', 'special'.
        philosophy:   optional, one of 'pro-style', 'air-raid', 'west-coast',
                      'spread-option', 'power-run', 'zone-run', 'speed-option',
                      'option', 'coryell', 'erhardt-perkins', 'any'.
        play_name:    optional human-readable play name; if absent, derived
                      from formation + play_type (e.g. 'New Pass Play').

    Example:
        scaffold = build_starter_play(
            'singleback-trio',
            play_type='pass',
            philosophy='west-coast',
            play_name='Drive Concept',
        )
        # scaffold is a dict; fill in routes, then:
        result = validate_play(scaffold)
    """
    formation_path = FORMATIONS_DIR / f"{formation_id}.yaml"
    if not formation_path.exists():
        raise ValueError(f"Formation not found: {formation_id}")
    with open(formation_path) as f:
        formation = yaml.safe_load(f)

    valid_play_types = {"run", "pass", "play-action", "rpo", "screen", "option", "special"}
    if play_type not in valid_play_types:
        raise ValueError(
            f"play_type must be one of {sorted(valid_play_types)}, got '{play_type}'"
        )

    name = play_name or f"New {play_type.replace('-', ' ').title()} Play"
    play_id = (name.lower().replace(" ", "-").replace("'", "") + "-" + formation_id)

    is_pass_like = play_type in ("pass", "play-action", "screen", "rpo")
    ball_carrier_default = "QB" if play_type in ("pass", "play-action") else "HB"

    assignments: list[dict[str, Any]] = []
    qb_seen = False
    hb_seen = False

    for player in formation.get("players", []):
        label = player.get("label")
        position = player.get("position", "")

        if label in ("LT", "LG", "C", "RG", "RT"):
            assignments.append({
                "player": label,
                "role": "pass_block" if is_pass_like else "run_block",
                "blocking_scheme": "man-protection" if is_pass_like else "drive-block",
            })
            continue

        if position == "TE":
            if is_pass_like:
                assignments.append({
                    "player": label,
                    "role": "route",
                    "route_name": "TODO-fill-in",
                    "depth_yd": 6,
                    "notes": "TODO: pick a TE route (drag, seam, corner, dig).",
                })
            else:
                assignments.append({
                    "player": label,
                    "role": "run_block",
                    "blocking_scheme": "drive-block",
                    "target": "edge-defender",
                })
            continue

        if position == "WR":
            if is_pass_like:
                assignments.append({
                    "player": label,
                    "role": "route",
                    "route_name": "TODO-fill-in",
                    "depth_yd": 10,
                    "notes": f"TODO: pick a route for {label}.",
                })
            else:
                assignments.append({
                    "player": label,
                    "role": "run_block",
                    "blocking_scheme": "stalk",
                    "target": "cornerback",
                })
            continue

        if position == "QB":
            qb_seen = True
            entry: dict[str, Any] = {"player": label, "role": "ball_carrier" if is_pass_like else "handoff"}
            if is_pass_like:
                entry["path"] = [[0, 0], [0, -2], [0, -4]]
                entry["notes"] = "TODO: confirm drop depth (3-step / 5-step / PA / rollout)."
            else:
                entry["path"] = [[0, 0], [-1, -1], [-2, -1]]
                entry["notes"] = "TODO: confirm handoff path (reverse-out / pivot / mesh)."
            assignments.append(entry)
            continue

        if position == "HB":
            hb_seen = True
            if is_pass_like:
                assignments.append({
                    "player": label,
                    "role": "pass_block",
                    "blocking_scheme": "man-protection",
                    "notes": "TODO: confirm — pass-protect, route, or check-release?",
                })
            else:
                assignments.append({
                    "player": label,
                    "role": "ball_carrier",
                    "is_primary": True,
                    "path": [[0, 0], [2, 3], [3, 8]],
                    "notes": "TODO: confirm aim point / read tree (BANG/BEND/BOUNCE for IZ).",
                })
            continue

        if position == "FB":
            if is_pass_like:
                assignments.append({
                    "player": label,
                    "role": "pass_block",
                    "blocking_scheme": "man-protection",
                })
            else:
                assignments.append({
                    "player": label,
                    "role": "lead_block",
                    "target": "playside-LB",
                    "path": [[0, 0], [1, 3], [1, 5]],
                    "notes": "TODO: confirm lead-block target.",
                })
            continue

        # Catch-all (other positions)
        assignments.append({
            "player": label,
            "role": "TODO",
            "notes": f"TODO: assign role for {label} ({position}).",
        })

    scaffold: dict[str, Any] = {
        "play_id": play_id,
        "name": name,
        "aliases": [],
        "formation": formation_id,
        "play_type": play_type,
        "ball_carrier": ball_carrier_default if (qb_seen or hb_seen) else "TODO",
        "motions": [],
        "assignments": assignments,
        "strengths": ["TODO"],
        "weaknesses": ["TODO"],
        "best_vs_defense": ["TODO"],
        "worst_vs_defense": ["TODO"],
        "common_uses": ["TODO"],
        "philosophy": philosophy or "any",
        "era": "TODO",
        "famous_examples": [],
        "tags": [play_type, formation_id.split("-")[0]],
        "verification_status": "unverified",
        "source_notes": [
            f"Scaffold generated by build_starter_play() for {formation_id}/{play_type}.",
            "TODO: fill in route names, paths, blocking targets, and play descriptors.",
            "Run validate_play() before saving to catch missing fields.",
        ],
    }

    if play_type == "pass":
        scaffold["primary_read"] = "TODO"
        scaffold["secondary_read"] = "TODO"
        scaffold["checkdown"] = "TODO"
    elif play_type == "play-action":
        scaffold["primary_read"] = "TODO"
        scaffold["secondary_read"] = "TODO"
        scaffold["checkdown"] = "TODO"
        # For PA, swap one HB/FB to fake role
        for a in scaffold["assignments"]:
            if a["player"] in ("HB", "FB") and a.get("role") in ("pass_block", "lead_block", "ball_carrier"):
                a["role"] = "fake"
                a["notes"] = "Fake handoff to sell PA."
                a.pop("path", None)
                a.pop("blocking_scheme", None)
                a.pop("target", None)
                a.pop("is_primary", None)
                break
    elif play_type == "rpo":
        scaffold["primary_read"] = "TODO"

    return scaffold


if __name__ == "__main__":
    mcp.run()
