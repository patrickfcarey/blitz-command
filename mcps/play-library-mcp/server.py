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
    - save_play(play_data, overwrite=False)   — validate then write to data/plays/
    - mirror_play(play_id, overwrite=False)   — generate the -left mirror of a play

  Discovery / analysis composition:
    - find_plays_by_concept(concept)          — search id/name/aliases/tags/formation concepts
    - compare_plays(play_ids)                 — disguise / similarity scorecard for N plays
    - suggest_complementary_plays(seed_ids, max_results=5)
                                              — recommend plays that fill gaps in a playbook
    - predict_matchup(play_id, defense_id)    — best/neutral/worst rating + rationale
    - export_play_instructions(play_id, game_id, format='markdown')
                                              — click-by-click create-a-play instructions

  Disguise families / scouting:
    - list_families()                         — every disguise family (base + companions)
    - get_family(family_id)                   — full family record
    - get_disguise_twins(play_id)             — a play's families + the plays that look like it
    - scout_play(play_id)                     — defensive_counters + flip_reads, keyed to pre-snap looks

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
ROUTES_DIR = REPO_ROOT / "data" / "routes"
GAMES_DIR = REPO_ROOT / "data" / "games"
CONCEPTS_DIR = REPO_ROOT / "data" / "concepts"
FAMILIES_DIR = REPO_ROOT / "data" / "play-families"
TEMPLATES_PATH = CONCEPTS_DIR / "play-templates.yaml"
SCHEMA_PATH = REPO_ROOT / "schemas" / "play.schema.json"
DRAW_SCRIPT_PATH = REPO_ROOT / "tools" / "draw-play" / "draw.py"


_TEMPLATES_CACHE: dict[str, Any] | None = None
_TEMPLATES_CACHE_MTIME: float = 0.0


def _load_templates() -> dict[str, Any]:
    """Load the concept-template registry. Cached by file mtime."""
    global _TEMPLATES_CACHE, _TEMPLATES_CACHE_MTIME
    if not TEMPLATES_PATH.exists():
        return {"templates": {}, "qb_paths": {}}
    current_mtime = TEMPLATES_PATH.stat().st_mtime
    if _TEMPLATES_CACHE is not None and current_mtime == _TEMPLATES_CACHE_MTIME:
        return _TEMPLATES_CACHE
    with open(TEMPLATES_PATH) as f:
        _TEMPLATES_CACHE = yaml.safe_load(f) or {"templates": {}, "qb_paths": {}}
    _TEMPLATES_CACHE_MTIME = current_mtime
    return _TEMPLATES_CACHE


_ROUTES_CACHE: set[str] | None = None
_ROUTES_CACHE_MTIME: float = 0.0


def _load_route_names() -> set[str]:
    """Load every route name + alias from data/routes/. Cached by directory mtime."""
    global _ROUTES_CACHE, _ROUTES_CACHE_MTIME
    current_mtime = _dir_mtime(ROUTES_DIR)
    if _ROUTES_CACHE is not None and current_mtime == _ROUTES_CACHE_MTIME:
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
    _ROUTES_CACHE_MTIME = current_mtime
    return names


def _classify_slots(formation: dict[str, Any]) -> dict[str, str]:
    """Map abstract slot names to player labels for a formation.

    Slot rules:
      - te / te2: position == 'TE' (sorted by abs(x) — first TE is closest to OL)
      - right_outer: position == 'WR' and x >= 8
      - left_outer:  position == 'WR' and x <= -8
      - right_slot:  position == 'WR' and 0 < x < 8
      - left_slot:   position == 'WR' and -8 < x < 0
      - se: only WR if exactly one WR
      - slot1, slot2: HB/FB position with on_line=false and abs(x) > 4
                     (flexbone slot-backs; sorted left-then-right)
      - wing: TE position with abs(x) > 4 and on_line=false (wing-T wing)
      - hb, fb, qb: by position (first match)
    """
    slots: dict[str, str] = {}
    players = formation.get("players", [])

    # TE(s)
    tes = sorted(
        [p for p in players if p.get("position") == "TE" and p.get("on_line", True)],
        key=lambda p: abs(p.get("x", 0)),
    )
    if tes:
        slots["te"] = tes[0]["label"]
    if len(tes) >= 2:
        slots["te2"] = tes[1]["label"]

    # Wing (off-line TE-like player)
    wings = [p for p in players if p.get("position") == "TE" and not p.get("on_line", True) and abs(p.get("x", 0)) > 4]
    if wings:
        slots["wing"] = wings[0]["label"]

    # WRs
    wrs = [p for p in players if p.get("position") == "WR"]
    rights = sorted([p for p in wrs if p.get("x", 0) > 0], key=lambda p: -p["x"])  # outermost first
    lefts = sorted([p for p in wrs if p.get("x", 0) < 0], key=lambda p: p["x"])    # outermost first

    if len(wrs) == 1:
        slots["se"] = wrs[0]["label"]

    for p in rights:
        x = p["x"]
        if x >= 8 and "right_outer" not in slots:
            slots["right_outer"] = p["label"]
        elif 0 < x < 8 and "right_slot" not in slots:
            slots["right_slot"] = p["label"]
        elif x >= 8 and "right_slot" not in slots:
            # Trips: a 3rd WR ends up here
            slots["right_slot"] = p["label"]

    for p in lefts:
        x = p["x"]
        if x <= -8 and "left_outer" not in slots:
            slots["left_outer"] = p["label"]
        elif -8 < x < 0 and "left_slot" not in slots:
            slots["left_slot"] = p["label"]
        elif x <= -8 and "left_slot" not in slots:
            slots["left_slot"] = p["label"]

    # Flexbone-style slot-backs (HB position, off-line, wide)
    slot_hbs = sorted(
        [p for p in players if p.get("position") == "HB" and not p.get("on_line", True) and abs(p.get("x", 0)) > 4],
        key=lambda p: p["x"],
    )
    if len(slot_hbs) >= 1:
        slots["slot1"] = slot_hbs[0]["label"]
    if len(slot_hbs) >= 2:
        slots["slot2"] = slot_hbs[1]["label"]

    # Backfield
    for pos in ("QB", "HB", "FB"):
        match = next((p for p in players if p.get("position") == pos and p["label"] not in slots.values()), None)
        if match:
            slots[pos.lower()] = match["label"]

    return slots


def _import_draw_module():
    """Lazy-load the draw script as a module so we can call render() directly."""
    spec = importlib.util.spec_from_file_location("draw_play", DRAW_SCRIPT_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot import draw script at {DRAW_SCRIPT_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_SCHEMA_CACHE: dict | None = None


def _load_schema() -> dict:
    global _SCHEMA_CACHE
    if _SCHEMA_CACHE is None:
        with open(SCHEMA_PATH) as f:
            _SCHEMA_CACHE = json.load(f)
    return _SCHEMA_CACHE


def _dir_mtime(directory: Path) -> float:
    """Return the directory's own mtime — changes when files are added/removed.
    Doesn't catch in-place edits, so save_play and mirror_play explicitly invalidate.
    """
    if not directory.exists():
        return 0.0
    return directory.stat().st_mtime


def _invalidate_plays_cache() -> None:
    global _PLAYS_CACHE, _PLAYS_CACHE_MTIME
    _PLAYS_CACHE = None
    _PLAYS_CACHE_MTIME = 0.0


_PLAYS_CACHE: dict[str, dict[str, Any]] | None = None
_PLAYS_CACHE_MTIME: float = 0.0


def _load_all() -> dict[str, dict[str, Any]]:
    """Load every play file. Cached by directory mtime — invalidates when any
    file in data/plays/ changes (e.g. after save_play / mirror_play)."""
    global _PLAYS_CACHE, _PLAYS_CACHE_MTIME
    current_mtime = _dir_mtime(PLAYS_DIR)
    if _PLAYS_CACHE is not None and current_mtime == _PLAYS_CACHE_MTIME:
        return _PLAYS_CACHE
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
    _PLAYS_CACHE = plays
    _PLAYS_CACHE_MTIME = current_mtime
    return plays


mcp = FastMCP("play-library")


def _paginate(items: list, cursor: str | None, limit: int) -> dict[str, Any]:
    offset = int(cursor) if cursor else 0
    page = items[offset: offset + limit]
    next_offset = offset + len(page)
    return {
        "items": page,
        "next_cursor": str(next_offset) if next_offset < len(items) else None,
    }


@mcp.tool()
def list_plays(cursor: str | None = None, limit: int = 50) -> dict[str, Any]:
    """List every play in the library with brief metadata.

    Returns one object per play. Use get_play(id) when you need the full
    assignments / routes / strengths / etc.

    Returns:
        {
          "items":       [{...}, ...],
          "next_cursor": str | null,  # pass back as cursor to get the next page
        }

    Item shape:
        {
          "id":           "singleback-trio-mesh",
          "name":         "Mesh",
          "formation":    "singleback-trio",
          "play_type":    "pass",
          "ball_carrier": "QB",
          "tags":         ["pass", "spread", "mesh", ...],
        }

    Args:
        cursor: opaque pagination token from the previous call's next_cursor.
        limit: max items per page (default 50; 144 total plays → 3 pages).

    Example:
        >>> page1 = list_plays()
        >>> page2 = list_plays(cursor=page1['next_cursor'])
        >>> page2['next_cursor'] is None  # last page
        True
    """
    all_items = [
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
    return _paginate(all_items, cursor, limit)


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
def find_plays_by_rpo_type(rpo_type: str) -> list[str]:
    """Return play IDs with the given RPO sub-type (case-insensitive exact match).

    Only run-pass-option plays carry `rpo_type`; it classifies what the QB is
    actually reading:

        'alert' — a pre-snap RPO. The QB throws the tagged route before the
                  snap if the look (box count, leverage) says so, else hands
                  off. No post-snap read.
        'peek'  — a post-snap RPO. The QB rides the mesh and reads one conflict
                  defender (usually a linebacker), then hands off or pulls to
                  throw the tagged route.
        'read'  — the QB is the run threat. A zone/option read where pulling
                  the ball means the QB keeps and runs, not throws.

    Every non-RPO play (no `rpo_type`) is omitted.

    Example:
        >>> find_plays_by_rpo_type('peek')
        ['shotgun-2x2-rpo-slant', 'shotgun-2x2-rpo-slant-left', ...]

    Args:
        rpo_type: 'alert', 'peek', or 'read' (case-insensitive).
    """
    wanted = rpo_type.lower()
    return [
        pid for pid, p in _load_all().items()
        if str(p.get("rpo_type", "")).lower() == wanted
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

    # Run play needs a ball_carrier and run_reads
    if play_type == "run" and not play_data.get("ball_carrier"):
        warnings.append("run play has no ball_carrier")
    if play_type == "run" and not play_data.get("run_reads"):
        warnings.append("run play has no run_reads — add a 3-step read progression (backside key → frontside gap → cutback)")

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

    # Route cross-reference — every route_name should exist in data/routes/
    # (skip placeholder TODOs and option-route compound names like "stick-or-out")
    route_names = _load_route_names()
    if route_names:
        bad_refs: list[str] = []
        for a in assignments:
            if a.get("role") == "route":
                rn = a.get("route_name")
                if not rn or "TODO" in rn:
                    continue
                # Strip option-route suffixes ("snag-or-mini-curl" → first part)
                base = rn.split(" or ", 1)[0].split("-or-", 1)[0]
                if base not in route_names and rn not in route_names:
                    bad_refs.append(f"{a.get('player')}: '{rn}'")
        if bad_refs:
            warnings.append(
                f"{len(bad_refs)} route_name(s) not in data/routes/: "
                + ", ".join(bad_refs[:5])
                + ("..." if len(bad_refs) > 5 else "")
            )

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

    # Multi-concept composition lints (concepts[])
    concepts_list = play_data.get("concepts") or []
    if concepts_list:
        if play_data.get("run_concept_ref") or play_data.get("pass_concept_ref"):
            warnings.append(
                "play sets both the single run/pass_concept_ref AND the concepts[] "
                "array — use concepts[] alone for a multi-concept play"
            )
        primary_count = 0
        for i, c in enumerate(concepts_list):
            ctype = c.get("concept_type")
            ref = c.get("concept_ref")
            dir_name = {"pass": "pass-concepts", "run": "run-concepts"}.get(ctype)
            if ref and dir_name:
                target = CONCEPTS_DIR / dir_name / f"{ref}.yaml"
                if not target.exists():
                    warnings.append(f"concepts[{i}].concept_ref '{ref}' not found at {target}")
            for pl in (c.get("players") or []):
                if formation_labels and pl not in formation_labels:
                    errors.append(
                        f"concepts[{i}] references unknown player '{pl}' (not in {formation_id})"
                    )
            if c.get("is_primary"):
                primary_count += 1
        if primary_count != 1:
            warnings.append(
                f"concepts[] should have exactly one is_primary entry (found {primary_count})"
            )

    # defensive_counters / flip_reads — id uniqueness within the play
    dc_ids = [c.get("counter_id") for c in (play_data.get("defensive_counters") or [])]
    if len(dc_ids) != len(set(dc_ids)):
        warnings.append("defensive_counters has duplicate counter_id values (unique per play)")
    fr_ids = [fr.get("flip_id") for fr in (play_data.get("flip_reads") or [])]
    if len(fr_ids) != len(set(fr_ids)):
        warnings.append("flip_reads has duplicate flip_id values (unique per play)")

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
        field:      'short' (LOS+15yd, deep DBs visible) or 'long' (LOS+30yd, default).

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
    concept: str | None = None,
) -> dict[str, Any]:
    """Return a play YAML scaffold for the given formation + play type.

    With `concept` supplied, the scaffold is **fully filled** for skill positions
    (canonical routes per slot, QB drop path, primary/secondary/tertiary reads)
    based on a template from `data/concepts/play-templates.yaml`. Without
    `concept`, returns a 70%-filled scaffold with placeholder routes the
    caller fills in manually.

    What the scaffold pre-fills (always):
        - play_id (kebab-cased from name + formation)
        - formation reference + ball_carrier guess (HB for run, QB for pass)
        - 5 OL pre-assigned (pass_block for pass/PA, run_block for run/RPO)
        - all skill players listed with role
        - motions, strengths, weaknesses, best/worst_vs_defense placeholders
        - verification_status: 'unverified'

    What `concept=...` adds (when supplied):
        - Real route_name + depth_yd + notes for each skill position
        - QB drop-back path appropriate to the concept (3-step, 5-step, PA, rollout)
        - primary_read / secondary_read / tertiary_read / checkdown filled in
        - HB auto-set to fake on play-action concepts

    Available concepts (call list_play_templates() to see the live list):
        Pass:  mesh, smash-strong, snag-strong, stick-strong, four-verticals,
               flood-strong
        PA:    pa-y-cross, bootleg-flat

    Example with concept:
        play = build_starter_play(
            formation_id='singleback-trio',
            play_type='play-action',
            concept='pa-y-cross',
            play_name='PA Cross',
        )
        result = validate_play(play)   # likely valid, 0 warnings — ready to save
        save_play(play)

    Example without concept (legacy / custom):
        play = build_starter_play('singleback-trio', 'pass')
        # ... AI fills in routes manually, then:
        validate_play(play)

    Args:
        formation_id: formation file stem, e.g. 'singleback-trio'.
        play_type:    one of 'run', 'pass', 'play-action', 'rpo', 'screen',
                      'option', 'special'.
        philosophy:   optional, one of 'pro-style', 'air-raid', 'west-coast',
                      'spread-option', 'power-run', 'zone-run', 'speed-option',
                      'option', 'coryell', 'erhardt-perkins', 'any'.
        play_name:    optional human-readable play name.
        concept:      optional concept template id (see list_play_templates()).
                      If supplied, fills in routes + reads + QB path automatically.
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
    # Build a schema-compliant play_id: lowercase, alphanumeric + hyphens only
    import re
    slug = re.sub(r'[^a-z0-9]+', '-', name.lower()).strip('-')
    play_id = f"{slug}-{formation_id}" if slug else formation_id

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

    if play_type == "run":
        scaffold["run_reads"] = [
            {"priority": 1, "read_key": "TODO — e.g. 'backside DE' or 'pulling guard'", "run_to": "TODO — e.g. 'cut outside' or 'bang the A-gap'", "notes": "TODO"},
            {"priority": 2, "read_key": "TODO — e.g. 'playside linebacker'", "run_to": "TODO", "notes": "TODO"},
            {"priority": 3, "read_key": "TODO — e.g. 'cutback lane'", "run_to": "TODO", "notes": "TODO"},
        ]
    elif play_type == "pass":
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

    # If a concept template was named, apply it now to fill in skill routes,
    # QB path, and read tree.
    if concept:
        scaffold = _apply_concept_template(scaffold, concept, formation, play_type)

    return scaffold


def _apply_concept_template(
    scaffold: dict[str, Any],
    concept_id: str,
    formation: dict[str, Any],
    play_type: str,
) -> dict[str, Any]:
    """Overlay a concept template onto a scaffold — fills in skill routes,
    QB path, and read tree. Returns the modified scaffold.
    """
    bundle = _load_templates()
    templates = bundle.get("templates") or {}
    qb_paths = bundle.get("qb_paths") or {}
    template = templates.get(concept_id)
    if template is None:
        available = sorted(templates.keys())
        raise ValueError(
            f"unknown concept '{concept_id}'. Available: {available[:20]}"
            + ("..." if len(available) > 20 else "")
        )

    expected_type = template.get("play_type")
    if expected_type and expected_type != play_type:
        # Soft warning via source_notes — don't error, the caller may know better
        scaffold.setdefault("source_notes", []).append(
            f"NOTE: concept '{concept_id}' template expects play_type='{expected_type}' "
            f"but caller passed play_type='{play_type}'. Routes applied anyway."
        )

    slots = _classify_slots(formation)
    routes_by_slot = template.get("routes_by_slot") or {}

    # Apply per-slot route assignments
    assignments_by_player = {a["player"]: a for a in scaffold["assignments"]}
    applied: list[str] = []
    skipped_slots: list[str] = []
    for slot_key, route_def in routes_by_slot.items():
        player_label = slots.get(slot_key)
        if not player_label:
            skipped_slots.append(slot_key)
            continue
        existing = assignments_by_player.get(player_label)
        if not existing:
            continue
        # Wipe placeholder fields and apply template
        for k in ("route_name", "depth_yd", "is_primary", "blocking_scheme",
                  "target", "path", "notes"):
            existing.pop(k, None)
        existing["role"] = route_def.get("role", "route")
        for k, v in route_def.items():
            if k != "role":
                existing[k] = v
        applied.append(player_label)

    # Apply QB path template
    qb_path_key = template.get("qb_path_template")
    if qb_path_key and qb_path_key in qb_paths:
        qb_assignment = assignments_by_player.get("QB")
        if qb_assignment:
            qb_assignment["path"] = qb_paths[qb_path_key]
            qb_assignment["notes"] = (
                f"QB path: {qb_path_key} template "
                f"({len(qb_paths[qb_path_key])} waypoints)."
            )

    # Apply read tree — slot keys can be a single string OR a list of fallbacks
    def _resolve_slot(slot_spec) -> str | None:
        if not slot_spec:
            return None
        if isinstance(slot_spec, str):
            return slots.get(slot_spec)
        for s in slot_spec:
            if slots.get(s):
                return slots[s]
        return None

    for read_key in ("primary_read", "secondary_read", "tertiary_read", "checkdown"):
        slot_spec = template.get(f"{read_key}_slot")
        player_label = _resolve_slot(slot_spec)
        if player_label:
            scaffold[read_key] = player_label

    # Update name + add concept tag if not already present
    if template.get("name") and scaffold.get("name", "").startswith("New "):
        scaffold["name"] = template["name"]
    tags = scaffold.setdefault("tags", [])
    if concept_id not in tags:
        tags.insert(0, concept_id)

    # Provenance breadcrumb
    scaffold.setdefault("source_notes", []).append(
        f"Concept template '{concept_id}' applied via build_starter_play(). "
        f"Filled {len(applied)} skill assignments + QB path + read tree. "
        + (f"Skipped slots (no matching player): {skipped_slots}." if skipped_slots else "")
    )

    return scaffold


@mcp.tool()
def list_play_templates(play_type: str | None = None, philosophy: str | None = None) -> list[dict[str, Any]]:
    """List available concept templates for use with build_starter_play(concept=...).

    Each template defines per-slot canonical routes, a QB path, and read tree.
    Filter by play_type ('pass', 'play-action', 'rpo', etc.) or by philosophy
    ('west-coast', 'air-raid', 'pro-style', etc.).

    Returned shape (per item):
        {
          "concept_id":    "pa-y-cross",
          "name":          "PA Y-Cross",
          "play_type":     "play-action",
          "philosophy":    ["west-coast", "coryell", "pro-style"],
          "description":   "PA fake then deep crossing route from the TE — ...",
          "slots_used":    ["te", "right_outer", "left_outer", "right_slot", "left_slot", "hb"],
          "primary_read_slot": "te",
          "qb_path_template":  "pa-5-step-shotgun",
          "has_fake":      true,
        }

    Example:
        >>> list_play_templates(play_type='play-action')
        [{'concept_id': 'pa-y-cross', ...}, {'concept_id': 'bootleg-flat', ...}]

    Args:
        play_type:  filter by play type (e.g. 'pass', 'play-action').
        philosophy: filter by philosophy (e.g. 'west-coast').
    """
    bundle = _load_templates()
    templates = bundle.get("templates") or {}
    out: list[dict[str, Any]] = []
    for cid, t in templates.items():
        if play_type and t.get("play_type") != play_type:
            continue
        if philosophy:
            phil_list = t.get("philosophy") or []
            if philosophy not in phil_list:
                continue
        out.append({
            "concept_id": cid,
            "name": t.get("name"),
            "play_type": t.get("play_type"),
            "philosophy": t.get("philosophy"),
            "description": t.get("description"),
            "slots_used": list((t.get("routes_by_slot") or {}).keys()),
            "primary_read_slot": t.get("primary_read_slot"),
            "qb_path_template": t.get("qb_path_template"),
            "has_fake": t.get("has_fake", False),
        })
    return out


def _mirror_stem(stem: str) -> str | None:
    """Return the left-mirror stem, or None if `stem` is already a mirror."""
    if "-right-" in stem:
        return stem.replace("-right-", "-left-")
    if stem.endswith("-left") or "-left-" in stem:
        return None
    return f"{stem}-left"


def _mirror_formation_id(fid: str) -> str:
    """Return the mirror formation id for a given formation id."""
    if "-right" in fid:
        return fid.replace("-right", "-left")
    if fid.endswith("-left"):
        return fid
    return f"{fid}-left"


def _build_mirror_play(play: dict[str, Any], original_stem: str) -> dict[str, Any]:
    """Apply the mirror transformation to a play dict (does not write to disk)."""
    import copy
    new = copy.deepcopy(play)
    mirrored_stem = _mirror_stem(original_stem)
    if mirrored_stem:
        new["play_id"] = mirrored_stem
    fid = new.get("formation")
    if fid:
        new["formation"] = _mirror_formation_id(fid)
    name = new.get("name", "")
    if "Right" in name:
        new["name"] = name.replace("Right", "Left")
    elif "(Mirror" not in name and "Left" not in name:
        new["name"] = f"{name} (Mirror Left)"
    for motion in new.get("motions", []):
        ep = motion.get("end_position")
        if ep and "x" in ep:
            ep["x"] = -ep["x"]
    for assignment in new.get("assignments", []):
        if "path" in assignment:
            assignment["path"] = [[-wp[0], wp[1]] for wp in assignment["path"]]
        for alt in assignment.get("alt_paths", []):
            alt["path"] = [[-wp[0], wp[1]] for wp in alt["path"]]
    notes = new.setdefault("source_notes", [])
    notes.append(
        f"Mirror of {original_stem}.yaml — path waypoints flipped on x; "
        f"formation reference points to the mirror formation. Routes auto-mirror "
        f"in the drawing tool based on receiver side. Narrative notes may still "
        f"describe the original right-handed look — coordinates and paths are "
        f"the source of truth."
    )
    return new


@mcp.tool()
def save_play(
    play_data: dict[str, Any],
    overwrite: bool = False,
    validate_first: bool = True,
) -> dict[str, Any]:
    """Validate (optionally) and write a play YAML to data/plays/<play_id>.yaml.

    Closes the authoring loop — after build_starter_play + filling + validate_play,
    use save_play to persist the play to the library.

    Returns:
        {
          "saved":      True if file was written,
          "path":       absolute path to the written file (or None),
          "play_id":    the play_id used,
          "validation": validate_play() result,
          "skipped":    explanation if not saved (e.g. validation failed, file exists),
        }

    Behavior:
        - Refuses to write if validate_first=True and validation finds errors
          (warnings are still allowed unless validation is run with strict).
        - Refuses to overwrite an existing file unless overwrite=True.
        - Writes YAML with sort_keys=False, default_flow_style=False — preserves
          the order of fields you set.

    Example (full author → save loop):
        scaffold = build_starter_play('singleback-trio', 'pass')
        # ... fill in routes, paths, etc ...
        result = save_play(scaffold)
        if not result['saved']:
            print(result['skipped'])

    Args:
        play_data:      full play dict.
        overwrite:      allow writing over an existing file (default False — safe).
        validate_first: run validate_play() and refuse to save on errors (default True).
    """
    play_id = play_data.get("play_id")
    if not play_id:
        return {
            "saved": False, "path": None, "play_id": None,
            "validation": None,
            "skipped": "play_data has no play_id field — cannot determine output path",
        }

    validation = None
    if validate_first:
        validation = validate_play(play_data, strict=False)
        if not validation["valid"]:
            return {
                "saved": False, "path": None, "play_id": play_id,
                "validation": validation,
                "skipped": f"validation failed with {len(validation['errors'])} error(s) — "
                           f"fix and retry, or call with validate_first=False to bypass",
            }

    target_path = PLAYS_DIR / f"{play_id}.yaml"
    if target_path.exists() and not overwrite:
        return {
            "saved": False, "path": str(target_path), "play_id": play_id,
            "validation": validation,
            "skipped": f"file already exists at {target_path} — pass overwrite=True to replace",
        }

    PLAYS_DIR.mkdir(parents=True, exist_ok=True)
    with open(target_path, "w") as f:
        yaml.safe_dump(
            play_data, f,
            sort_keys=False,
            default_flow_style=False,
            width=120,
            allow_unicode=True,
        )
    _invalidate_plays_cache()

    return {
        "saved": True, "path": str(target_path), "play_id": play_id,
        "validation": validation,
        "skipped": None,
    }


@mcp.tool()
def mirror_play(play_id: str, overwrite: bool = False) -> dict[str, Any]:
    """Generate the left-handed mirror of a right-side play and save it.

    Mirrors:
        - x-coordinate sign flipped on every path waypoint and motion end_position
        - play_id and formation references swapped to their -left counterparts
          (e.g. 'shotgun-trips-right-snag' → 'shotgun-trips-left-snag';
          plain stems get '-left' appended: 'wishbone-fb-dive' → 'wishbone-fb-dive-left')
        - "Right" in the name swapped to "Left" (else "(Mirror Left)" appended)
        - source_notes appended with a mirror-of breadcrumb

    Routes are NOT touched — the drawing tool already mirrors them based on the
    receiver's x position.

    Refuses to mirror if:
        - play_id doesn't exist in the library
        - the play is already a mirror (-left or -left- in stem)
        - the mirror formation file doesn't exist
        - the target mirror file already exists (unless overwrite=True)

    Returns:
        {
          "saved":             True if mirror was written,
          "mirror_play_id":    the new play_id (or None),
          "mirror_path":       absolute path to the new file (or None),
          "skipped":           reason if not saved,
        }

    Example (standard right-side authoring workflow):
        save_play(my_filled_scaffold)             # save the right-side play
        mirror_play('my-new-play-singleback-trio') # auto-create the left mirror

    Args:
        play_id:   stem of the right-side play to mirror.
        overwrite: allow writing over an existing mirror (default False — safe).
    """
    new_stem = _mirror_stem(play_id)
    if new_stem is None:
        return {
            "saved": False, "mirror_play_id": None, "mirror_path": None,
            "skipped": f"'{play_id}' is already a mirror (or has -left- mid-stem) — nothing to do",
        }

    src_path = PLAYS_DIR / f"{play_id}.yaml"
    if not src_path.exists():
        return {
            "saved": False, "mirror_play_id": None, "mirror_path": None,
            "skipped": f"source play not found: {src_path}",
        }

    with open(src_path) as f:
        play = yaml.safe_load(f)

    fid = play.get("formation")
    if fid:
        mirror_fid = _mirror_formation_id(fid)
        mirror_form_path = FORMATIONS_DIR / f"{mirror_fid}.yaml"
        if not mirror_form_path.exists():
            return {
                "saved": False, "mirror_play_id": new_stem, "mirror_path": None,
                "skipped": f"mirror formation '{mirror_fid}' missing — build it first",
            }

    target_path = PLAYS_DIR / f"{new_stem}.yaml"
    if target_path.exists() and not overwrite:
        return {
            "saved": False, "mirror_play_id": new_stem, "mirror_path": str(target_path),
            "skipped": f"mirror file already exists at {target_path} — pass overwrite=True to replace",
        }

    new_play = _build_mirror_play(play, play_id)
    with open(target_path, "w") as f:
        yaml.safe_dump(
            new_play, f,
            sort_keys=False,
            default_flow_style=False,
            width=120,
            allow_unicode=True,
        )
    _invalidate_plays_cache()
    return {
        "saved": True, "mirror_play_id": new_stem, "mirror_path": str(target_path),
        "skipped": None,
    }


@mcp.tool()
def update_play(
    play_id: str,
    patch: dict[str, Any],
) -> dict[str, Any]:
    """Apply a shallow field-level patch to an existing play file.

    Merges `patch` into the play's top-level fields. Fields not in `patch`
    are unchanged. Nested fields (e.g. `assignments`, `motions`) are replaced
    wholesale if included — to modify one assignment, provide the full list.

    Runs schema validation after applying the patch; refuses to write if errors
    are introduced.

    Returns:
        {
          "updated":      bool,
          "path":         absolute path to the file,
          "play_id":      the id,
          "changed_keys": list of top-level keys that were modified,
          "validation":   validate_play() result after patch,
          "skipped":      explanation if not updated,
        }

    Example — fix a missing primary_read:
        >>> update_play('singleback-trio-mesh', {'primary_read': 'Z'})
        {"updated": True, "changed_keys": ["primary_read"], ...}

    Example — add a concept ref:
        >>> update_play('i-formation-power-o', {'run_concept_ref': 'power'})
        {"updated": True, "changed_keys": ["run_concept_ref"], ...}

    Args:
        play_id: file stem of the play to update (e.g. 'singleback-trio-mesh').
        patch:   dict of top-level fields to set/replace.
    """
    target_path = PLAYS_DIR / f"{play_id}.yaml"
    if not target_path.exists():
        return {
            "updated": False, "path": None, "play_id": play_id,
            "changed_keys": [], "validation": None,
            "skipped": f"no play file for '{play_id}' — call list_plays() for valid ids",
        }

    with open(target_path) as f:
        existing = yaml.safe_load(f) or {}

    changed_keys = [k for k, v in patch.items() if existing.get(k) != v]
    existing.update(patch)

    validation = validate_play(existing, strict=False)
    if not validation["valid"]:
        return {
            "updated": False, "path": str(target_path), "play_id": play_id,
            "changed_keys": changed_keys, "validation": validation,
            "skipped": f"patch introduces schema errors — no changes written",
        }

    with open(target_path, "w") as f:
        yaml.safe_dump(existing, f, sort_keys=False, default_flow_style=False,
                       width=120, allow_unicode=True)
    _invalidate_plays_cache()

    return {
        "updated": True, "path": str(target_path), "play_id": play_id,
        "changed_keys": changed_keys, "validation": validation, "skipped": None,
    }


_FORMATIONS_CACHE: dict[str, dict[str, Any]] | None = None
_FORMATIONS_CACHE_MTIME: float = 0.0


def _load_all_formations() -> dict[str, dict[str, Any]]:
    """Load every formation file. Cached by directory mtime."""
    global _FORMATIONS_CACHE, _FORMATIONS_CACHE_MTIME
    current_mtime = _dir_mtime(FORMATIONS_DIR)
    if _FORMATIONS_CACHE is not None and current_mtime == _FORMATIONS_CACHE_MTIME:
        return _FORMATIONS_CACHE
    forms: dict[str, dict[str, Any]] = {}
    for fp in FORMATIONS_DIR.glob("*.yaml"):
        try:
            with open(fp) as f:
                data = yaml.safe_load(f)
            if data:
                forms[fp.stem] = data
        except Exception:
            continue
    _FORMATIONS_CACHE = forms
    _FORMATIONS_CACHE_MTIME = current_mtime
    return forms


def _load_formation(formation_id: str) -> dict[str, Any] | None:
    return _load_all_formations().get(formation_id)


_FAMILIES_CACHE: dict[str, dict[str, Any]] | None = None
_FAMILIES_CACHE_MTIME: float = 0.0


def _load_all_families() -> dict[str, dict[str, Any]]:
    """Load every disguise-family file from data/play-families/. Cached by directory mtime."""
    global _FAMILIES_CACHE, _FAMILIES_CACHE_MTIME
    current_mtime = _dir_mtime(FAMILIES_DIR)
    if _FAMILIES_CACHE is not None and current_mtime == _FAMILIES_CACHE_MTIME:
        return _FAMILIES_CACHE
    fams: dict[str, dict[str, Any]] = {}
    if FAMILIES_DIR.exists():
        for fp in FAMILIES_DIR.glob("*.yaml"):
            try:
                with open(fp) as f:
                    data = yaml.safe_load(f)
                if data and data.get("family_id"):
                    fams[data["family_id"]] = data
            except Exception:
                continue
    _FAMILIES_CACHE = fams
    _FAMILIES_CACHE_MTIME = current_mtime
    return fams


@mcp.tool()
def find_plays_by_concept(concept: str) -> list[dict[str, Any]]:
    """Find plays implementing a named football concept (broader than tag search).

    Searches across multiple fields:
        - play_id stem      (e.g. 'mesh' matches 'singleback-trio-mesh')
        - name              (e.g. 'Mesh', 'PA Y-Cross')
        - aliases           (e.g. 'Y-Stick' matches stick plays)
        - tags              (e.g. 'mesh', 'four-verticals', 'rpo')
        - formation's run_concepts / pass_concepts (transitive — if a formation
          declares the concept and the play uses that formation, it counts)

    Returns one object per matching play with the source field that matched,
    so the caller can tell why it was returned.

    Concept names are case-insensitive, kebab-case preferred but not required.

    Example:
        >>> find_plays_by_concept('mesh')
        [{'play_id': 'singleback-trio-mesh', 'name': 'Mesh', 'matched_via': 'name+stem+tag'},
         {'play_id': 'empty-mesh', 'name': 'Mesh (Empty 5-Wide)', 'matched_via': 'name+stem+tag'},
         {'play_id': 'i-formation-twins-weak-mesh', 'name': '...', 'matched_via': 'name+stem+tag'}, ...]

    Common concepts to query:
        Run:   power, counter, counter-trey, iso, inside-zone, outside-zone,
               trap, draw, sweep, jet-sweep, buck-sweep, belly, toss,
               triple-option, midline, veer, zone-read, power-read, qb-counter
        Pass:  mesh, smash, snag, stick, flood, sail, four-verticals, y-cross,
               choice, switch, drag, post, slant, fade, comeback, wheel
        Other: pa, play-action, rpo, screen, hb-screen, bootleg, waggle,
               qb-sneak, tush-push

    Args:
        concept: concept name (e.g. 'mesh', 'triple-option', 'rpo-bubble').
    """
    target = concept.lower().strip()
    target_compact = target.replace(" ", "-")

    # Build formation_concepts dict from the cached formations
    formation_concepts: dict[str, set[str]] = {}
    for fid, f in _load_all_formations().items():
        concepts = set()
        for c in (f.get("run_concepts") or []):
            concepts.add(c.lower())
        for c in (f.get("pass_concepts") or []):
            concepts.add(c.lower())
        formation_concepts[fid] = concepts

    matches: list[dict[str, Any]] = []
    for pid, p in _load_all().items():
        sources: list[str] = []
        if target in pid.lower() or target_compact in pid.lower():
            sources.append("stem")
        name = (p.get("name") or "").lower()
        if target in name or target_compact in name:
            sources.append("name")
        for alias in (p.get("aliases") or []):
            if target in alias.lower() or target_compact in alias.lower():
                sources.append("alias")
                break
        tags = [t.lower() for t in (p.get("tags") or [])]
        if target in tags or target_compact in tags:
            sources.append("tag")
        # Concept references — single (run/pass_concept_ref) AND the multi-concept
        # composition array (concepts[].concept_ref)
        ref_set = {
            (p.get("run_concept_ref") or "").lower(),
            (p.get("pass_concept_ref") or "").lower(),
        }
        for c in (p.get("concepts") or []):
            ref_set.add((c.get("concept_ref") or "").lower())
        ref_set.discard("")
        if target in ref_set or target_compact in ref_set:
            sources.append("concept-ref")
        # Transitive via formation
        fid = p.get("formation")
        if fid and fid in formation_concepts and target_compact in formation_concepts[fid]:
            sources.append("formation-concept")
        if sources:
            matches.append({
                "play_id": pid,
                "name": p.get("name"),
                "play_type": p.get("play_type"),
                "matched_via": "+".join(dict.fromkeys(sources)),  # de-dup, preserve order
            })
    return matches


def _normalize_set(items) -> set[str]:
    return {str(x).strip().lower() for x in (items or [])}


@mcp.tool()
def compare_plays(play_ids: list[str]) -> dict[str, Any]:
    """Structural comparison across N plays — assess disguise / diversity.

    Use this to certify that a candidate playbook is well-disguised (same
    pre-snap look, varied mechanics) or to spot redundancy (different plays
    that look identical post-snap too).

    Returns:
        {
          "n":                       count of plays compared,
          "all_same_formation":      bool — all plays from one formation,
          "formations":              list of distinct formation ids used,
          "personnel_groups":        list of distinct personnel strings (from formations),
          "play_types":              list of distinct play_types,
          "ball_carriers":           list of distinct ball_carrier labels,
          "primary_reads":           list of distinct primary_read labels,
          "philosophies":            list of distinct philosophies,
          "uses_motion":             list of {play_id, mandatory: bool} for plays with motions,
          "shared_tags":             tags present on every play in the set,
          "disguise_score":          float 0-1 — high when plays share formation+personnel
                                     but vary in play_type, ball_carrier, and mechanics,
          "diversity_score":         float 0-1 — high when play_types and ball_carriers
                                     are varied,
          "notes":                   plain-language summary of strengths/weaknesses,
        }

    Disguise score formula (heuristic):
        + 0.4 if all plays share the same formation
        + 0.2 if all plays share the same personnel grouping
        + 0.2 if play_types are diverse (>=3 distinct)
        + 0.1 if ball_carriers are diverse (>=2 distinct)
        + 0.1 if at least one play uses a fake / PA mechanic

    Diversity score formula:
        - distinct_play_types / max(n, 4)        (capped)
        - distinct_ball_carriers / max(n, 3)     (capped)
        - 0.5 weight each

    Example:
        >>> r = compare_plays([
        ...     'singleback-trio-inside-zone',
        ...     'singleback-trio-outside-zone',
        ...     'singleback-trio-power',
        ...     'singleback-trio-mesh',
        ...     'singleback-trio-pa-cross',
        ... ])
        >>> r['all_same_formation']
        True
        >>> r['disguise_score'] > 0.7
        True

    Args:
        play_ids: list of play_ids to compare.
    """
    plays = _load_all()
    loaded: list[tuple[str, dict[str, Any]]] = []
    missing: list[str] = []
    for pid in play_ids:
        if pid in plays:
            loaded.append((pid, plays[pid]))
        else:
            missing.append(pid)
    if missing:
        raise ValueError(f"unknown play_ids: {missing}")
    if not loaded:
        raise ValueError("compare_plays needs at least 1 play_id")

    formations = sorted({p.get("formation") for _, p in loaded if p.get("formation")})
    play_types = sorted({p.get("play_type") for _, p in loaded if p.get("play_type")})
    ball_carriers = sorted({p.get("ball_carrier") for _, p in loaded if p.get("ball_carrier")})
    primary_reads = sorted({p.get("primary_read") for _, p in loaded if p.get("primary_read")})
    philosophies = sorted({p.get("philosophy") for _, p in loaded if p.get("philosophy")})

    personnel_groups: list[str] = []
    seen_personnel: set[str] = set()
    for fid in formations:
        f = _load_formation(fid)
        if f and f.get("personnel"):
            pg = f["personnel"]
            if pg not in seen_personnel:
                seen_personnel.add(pg)
                personnel_groups.append(pg)

    uses_motion = []
    for pid, p in loaded:
        for m in (p.get("motions") or []):
            uses_motion.append({"play_id": pid, "mandatory": m.get("type") == "mandatory"})
            break

    shared_tags = None
    for _, p in loaded:
        tags = set(p.get("tags") or [])
        shared_tags = tags if shared_tags is None else shared_tags & tags
    shared_tags = sorted(shared_tags or [])

    has_fake = any(
        any(a.get("role") == "fake" for a in (p.get("assignments") or []))
        for _, p in loaded
    )

    n = len(loaded)
    disguise = (
        (0.4 if len(formations) == 1 else 0.0)
        + (0.2 if len(personnel_groups) == 1 else 0.0)
        + (0.2 if len(play_types) >= 3 else (0.1 if len(play_types) == 2 else 0.0))
        + (0.1 if len(ball_carriers) >= 2 else 0.0)
        + (0.1 if has_fake else 0.0)
    )
    diversity = 0.5 * min(len(play_types) / max(n, 4), 1.0) + 0.5 * min(len(ball_carriers) / max(n, 3), 1.0)

    notes_lines: list[str] = []
    if len(formations) == 1:
        notes_lines.append(f"All {n} plays share formation '{formations[0]}' — strong pre-snap disguise.")
    else:
        notes_lines.append(f"{n} plays from {len(formations)} different formations — defense can pre-snap-key based on formation tells.")
    if len(play_types) >= 3:
        notes_lines.append(f"{len(play_types)} distinct play_types ({', '.join(play_types)}) — defense must defend wide variety.")
    elif len(play_types) == 1:
        notes_lines.append(f"All plays are play_type='{play_types[0]}' — playbook is one-dimensional.")
    if has_fake:
        notes_lines.append("At least one play uses a fake/PA mechanic — adds misdirection layer.")
    else:
        notes_lines.append("No plays use fakes/PA — defense doesn't need to honor run-fakes.")

    return {
        "n": n,
        "all_same_formation": len(formations) == 1,
        "formations": formations,
        "personnel_groups": personnel_groups,
        "play_types": play_types,
        "ball_carriers": ball_carriers,
        "primary_reads": primary_reads,
        "philosophies": philosophies,
        "uses_motion": uses_motion,
        "shared_tags": shared_tags,
        "disguise_score": round(disguise, 3),
        "diversity_score": round(diversity, 3),
        "notes": notes_lines,
    }


def _coverage_intersect(play_field: list[str], def_match_terms: list[str]) -> list[str]:
    """Return strings from play_field that contain any of the def_match_terms (case-insensitive)."""
    matches: list[str] = []
    play_lower = [s.lower() for s in (play_field or [])]
    for term in def_match_terms:
        term_l = term.lower()
        for orig, lower in zip(play_field or [], play_lower):
            if term_l in lower and orig not in matches:
                matches.append(orig)
    return matches


@mcp.tool()
def predict_matchup(play_id: str, defense_id: str) -> dict[str, Any]:
    """Predict how an offensive play matches up against a defensive formation.

    Cross-references the play's best_vs_defense / worst_vs_defense lists against
    the defense's coverage_shell, front, and tags.

    Returns:
        {
          "play_id":               echo,
          "defense_id":            echo,
          "rating":                "best" | "neutral" | "worst",
          "rationale":             plain-language summary,
          "best_read":             play.primary_read (where to look first),
          "secondary_read":        play.secondary_read (or null),
          "checkdown":             play.checkdown (or null),
          "play_strengths_relevant":   strings from play.strengths that match this defense,
          "play_weaknesses_exposed":   strings from play.weaknesses that match this defense,
          "play_best_vs_matches":      entries in play.best_vs_defense matching this defense,
          "play_worst_vs_matches":     entries in play.worst_vs_defense matching this defense,
          "defense_strengths_relevant":strings from defense.best_against that match this play,
          "defense_vulnerabilities_exposed": strings from defense.vulnerable_to that match this play,
        }

    Rating logic:
        - "best"    if the defense's coverage_shell or front substring appears
                    in any play.best_vs_defense entry, OR if play tags
                    appear in defense.vulnerable_to
        - "worst"   if the defense's coverage_shell or front substring appears
                    in any play.worst_vs_defense, OR if play tags appear in
                    defense.best_against
        - "neutral" if neither matches (no documented edge in either direction)

    Example:
        >>> predict_matchup('singleback-trio-mesh', 'defense-nickel-cover-1')
        {'rating': 'best',
         'rationale': "Mesh exploits cover-1 ... rubs at the mesh point legal vs man",
         'best_read': 'TE',
         ...}

    Args:
        play_id:    offensive play stem.
        defense_id: defensive formation stem (e.g. 'defense-4-3-cover-3').
    """
    plays = _load_all()
    if play_id not in plays:
        raise ValueError(f"unknown play_id: {play_id}")
    play = plays[play_id]

    defense = _load_formation(defense_id)
    if defense is None:
        raise ValueError(f"defense formation not found: {defense_id}")
    if defense.get("side") != "defense":
        raise ValueError(f"{defense_id} is not a defensive formation (side='{defense.get('side')}')")

    coverage = (defense.get("coverage_shell") or "").strip()
    front = (defense.get("front") or "").strip()
    def_tags = list(defense.get("tags") or [])
    play_tags = list(play.get("tags") or [])
    play_concepts = [play.get("play_type") or "", *play_tags]

    # Match coverage / front into play.best_vs_defense / worst_vs_defense
    def_terms = [t for t in (coverage, front, *def_tags) if t]
    best_matches = _coverage_intersect(play.get("best_vs_defense") or [], def_terms)
    worst_matches = _coverage_intersect(play.get("worst_vs_defense") or [], def_terms)

    # Match the play's tags / concepts into defense.vulnerable_to / best_against
    def_vuln_matches = _coverage_intersect(defense.get("vulnerable_to") or [], play_concepts)
    def_strong_matches = _coverage_intersect(defense.get("best_against") or [], play_concepts)

    # Strengths / weaknesses keyword scan (lighter heuristic)
    def_keywords = [s.lower() for s in def_terms]
    strengths_relevant = [
        s for s in (play.get("strengths") or [])
        if any(k in s.lower() for k in def_keywords)
    ]
    weaknesses_exposed = [
        w for w in (play.get("weaknesses") or [])
        if any(k in w.lower() for k in def_keywords)
    ]

    # Rating
    favors_offense = bool(best_matches) or bool(def_vuln_matches)
    favors_defense = bool(worst_matches) or bool(def_strong_matches)
    if favors_offense and not favors_defense:
        rating = "best"
    elif favors_defense and not favors_offense:
        rating = "worst"
    elif favors_offense and favors_defense:
        rating = "neutral"
    else:
        rating = "neutral"

    rationale_parts: list[str] = []
    if best_matches:
        rationale_parts.append(f"Play's best_vs_defense matches: {best_matches}")
    if worst_matches:
        rationale_parts.append(f"Play's worst_vs_defense matches: {worst_matches}")
    if def_vuln_matches:
        rationale_parts.append(f"Defense's vulnerable_to matches play type/tags: {def_vuln_matches}")
    if def_strong_matches:
        rationale_parts.append(f"Defense's best_against matches play type/tags: {def_strong_matches}")
    if not rationale_parts:
        rationale_parts.append(
            f"No documented edge for either side. Play designed for {coverage or 'unknown'} "
            f"coverage; defense is a {coverage or 'unknown'}/{front or 'unknown'}."
        )
    rationale = " | ".join(rationale_parts)

    return {
        "play_id": play_id,
        "defense_id": defense_id,
        "rating": rating,
        "rationale": rationale,
        "best_read": play.get("primary_read"),
        "secondary_read": play.get("secondary_read"),
        "checkdown": play.get("checkdown"),
        "play_strengths_relevant": strengths_relevant,
        "play_weaknesses_exposed": weaknesses_exposed,
        "play_best_vs_matches": best_matches,
        "play_worst_vs_matches": worst_matches,
        "defense_strengths_relevant": def_strong_matches,
        "defense_vulnerabilities_exposed": def_vuln_matches,
    }


@mcp.tool()
def export_play_instructions(
    play_id: str,
    game_id: str,
    format: str = "markdown",
    defense_id: str | None = None,
) -> str | dict[str, Any]:
    """Return click-by-click instructions for reproducing a play in the game's
    create-a-play editor.

    Uses the game profile's snap rule + the same conflict-aware cell-assignment
    helper as render_play, so the cells reported here are exactly what the
    editor will accept (integer cells for Madden 05, no overlaps).

    Args:
        play_id:    play file stem
        game_id:    game profile id, e.g. 'madden-05-ps2'
        format:     'markdown' (human-readable, default) or 'structured' (dict)
        defense_id: optional defense to include in the structured output (no
                    impact on the offensive instructions, just for reference)

    Markdown output structure:
        # Recreate "<play name>" in <game>
        ## Formation: <formation_id>
        ## Pre-snap player positions (column, row)
        | Player | Cell    | Universal yards   |
        ## QB drop / handoff path
        ## Routes
        ## Blocking
        ## Motion (if any)
        ## Read tree
        ## Notes

    Structured output:
        {
          "play_id": "...", "game_id": "...", "play_name": "...",
          "formation": "...", "snap_rule": "...",
          "player_cells": {"TE": [12, 5], ...},
          "qb_path": [{"cell": [10, 4], "yd_offset": [0, 0]}, ...],
          "routes": [{"player": "TE", "route_name": "drag", "depth_yd": 6,
                      "waypoints_cells": [[12, 5], [12, 8], [4, 8]]}, ...],
          "blocking": [{"player": "LT", "scheme": "man-protection"}, ...],
          "motion": [...],
          "reads": {"primary": "TE", "secondary": "X", ...},
        }

    Example:
        md = export_play_instructions('singleback-trio-mesh', 'madden-05-ps2')
        Path('mesh-instructions.md').write_text(md)
    """
    play_path = PLAYS_DIR / f"{play_id}.yaml"
    if not play_path.exists():
        raise ValueError(f"Play not found: {play_id}")
    with open(play_path) as f:
        play = yaml.safe_load(f)

    formation_id = play["formation"]
    formation_path = FORMATIONS_DIR / f"{formation_id}.yaml"
    if not formation_path.exists():
        raise ValueError(f"Formation not found: {formation_id}")
    with open(formation_path) as f:
        formation = yaml.safe_load(f)

    profile_path = GAMES_DIR / game_id / "editor-grid.yaml"
    if not profile_path.exists():
        raise ValueError(f"Game profile not found: {game_id}")
    with open(profile_path) as f:
        profile = yaml.safe_load(f)

    draw = _import_draw_module()
    cells = draw.assign_cells_for_formation(formation, profile)

    sx = profile["scale"]["x_yards_per_cell"]
    sy = profile["scale"]["y_yards_per_cell"]
    ox = profile["grid"]["origin"]["x"]
    oy = profile["grid"]["origin"]["y"]
    snap_to_cells = profile.get("snap_to_cells", False)

    def yd_to_cell(x_yd: float, y_yd: float, base_label: str) -> tuple[int, int]:
        """Translate a route waypoint (player_x + offset) to the editor cell."""
        gx = ox + x_yd / sx
        gy = oy + y_yd / sy
        return (round(gx), round(gy)) if snap_to_cells else (gx, gy)

    formation_by_label = {p["label"]: p for p in formation["players"]}

    structured: dict[str, Any] = {
        "play_id": play_id,
        "game_id": game_id,
        "play_name": play.get("name"),
        "formation": formation_id,
        "snap_rule": "integer cells only" if snap_to_cells else "fractional cells permitted",
        "player_cells": {label: list(cell) for label, cell in cells.items()},
        "qb_path": [],
        "routes": [],
        "blocking": [],
        "motion": [],
        "reads": {
            "primary": play.get("primary_read"),
            "secondary": play.get("secondary_read"),
            "tertiary": play.get("tertiary_read"),
            "checkdown": play.get("checkdown"),
        },
        "ball_carrier": play.get("ball_carrier"),
        "play_type": play.get("play_type"),
    }

    # Routes, blocking, paths
    for assignment in play.get("assignments", []):
        label = assignment["player"]
        player_obj = formation_by_label.get(label)
        if player_obj is None:
            continue
        role = assignment.get("role")
        if role == "route" and assignment.get("route_name"):
            # Compute waypoints from the route library if known
            routes_lib = draw.load_route_library()
            route_def = draw.route_lookup(routes_lib, assignment["route_name"])
            if route_def:
                wp_yd = draw.receiver_route_path(player_obj["x"], player_obj["y"], route_def)
                wp_cells = [yd_to_cell(x, y, label) for x, y in wp_yd]
            else:
                wp_cells = []
            structured["routes"].append({
                "player": label,
                "route_name": assignment["route_name"],
                "depth_yd": assignment.get("depth_yd"),
                "is_primary": bool(assignment.get("is_primary")),
                "waypoints_cells": [list(c) for c in wp_cells],
                "notes": assignment.get("notes"),
            })
        elif role in ("ball_carrier", "handoff", "lead_block", "fake") and assignment.get("path"):
            wp_yd = [(player_obj["x"] + dx, player_obj["y"] + dy) for dx, dy in assignment["path"]]
            wp_cells = [yd_to_cell(x, y, label) for x, y in wp_yd]
            entry = {
                "player": label,
                "role": role,
                "waypoints_cells": [list(c) for c in wp_cells],
                "notes": assignment.get("notes"),
            }
            if label == "QB":
                structured["qb_path"] = entry["waypoints_cells"]
            else:
                structured.setdefault("ball_carrier_paths", []).append(entry)
        elif role in ("pass_block", "run_block"):
            structured["blocking"].append({
                "player": label,
                "scheme": assignment.get("blocking_scheme"),
                "target": assignment.get("target"),
                "notes": assignment.get("notes"),
            })

    # Motion
    for m in play.get("motions", []):
        ep = m.get("end_position", {})
        end_cell = yd_to_cell(ep.get("x", 0), ep.get("y", 0), m.get("player", "")) if ep else None
        structured["motion"].append({
            "player": m.get("player"),
            "type": m.get("type"),
            "motion_type": m.get("motion_type"),
            "end_cell": list(end_cell) if end_cell else None,
            "snap_on_motion": m.get("snap_on_motion"),
            "notes": m.get("notes"),
        })

    if format == "structured":
        return structured

    # ---- Markdown rendering ----
    L: list[str] = []
    L.append(f'# Recreate "{play.get("name")}" in `{game_id}`')
    L.append("")
    L.append(f'**Formation:** `{formation_id}`  •  '
             f'**Type:** {play.get("play_type", "?")}  •  '
             f'**Ball carrier:** {play.get("ball_carrier", "?")}')
    L.append(f'**Snap rule:** {structured["snap_rule"]}')
    L.append("")

    # Read tree
    reads = structured["reads"]
    if any(reads.values()):
        L.append("## Read tree")
        L.append("")
        for k in ("primary", "secondary", "tertiary", "checkdown"):
            if reads.get(k):
                L.append(f"- **{k.title()}:** `{reads[k]}`")
        L.append("")

    # Player positions
    L.append("## Step 1 — set player cells")
    L.append("")
    L.append("| Player | Cell (col, row) | Position | On line | Universal yds |")
    L.append("|--------|-----------------|----------|---------|---------------|")
    for p in formation["players"]:
        cell = cells.get(p["label"])
        if cell is None:
            continue
        L.append(
            f"| `{p['label']}` | ({cell[0]}, {cell[1]}) | {p.get('position','')} | "
            f"{'yes' if p.get('on_line') else 'no'} | "
            f"({p['x']:.1f}, {p['y']:.1f}) |"
        )
    L.append("")

    # Motion (if any)
    if structured["motion"]:
        L.append("## Step 2 — set motion")
        L.append("")
        for m in structured["motion"]:
            ec = m['end_cell']
            ec_str = f"({ec[0]}, {ec[1]})" if ec else "n/a"
            L.append(f"- `{m['player']}` — {m.get('motion_type','motion')} ({m.get('type','?')}) "
                     f"to cell {ec_str}"
                     + (" — snap on motion" if m.get('snap_on_motion') else ""))
            if m.get('notes'):
                L.append(f"  - {m['notes']}")
        L.append("")
        next_step = 3
    else:
        next_step = 2

    # Routes
    if structured["routes"]:
        L.append(f"## Step {next_step} — draw routes")
        L.append("")
        L.append("| Player | Route | Depth | Waypoints (cells) | Notes |")
        L.append("|--------|-------|-------|-------------------|-------|")
        for r in structured["routes"]:
            wps = " → ".join(f"({c[0]}, {c[1]})" for c in r["waypoints_cells"])
            primary_marker = " ★" if r.get("is_primary") else ""
            note = (r.get("notes") or "").replace("|", "\\|").split("\n")[0][:80]
            L.append(f"| `{r['player']}`{primary_marker} | {r['route_name']} | "
                     f"{r.get('depth_yd', '-')} yd | {wps} | {note} |")
        L.append("")
        next_step += 1

    # Ball carrier / QB path
    if structured["qb_path"]:
        L.append(f"## Step {next_step} — QB drop / handoff path")
        L.append("")
        wps = " → ".join(f"({c[0]}, {c[1]})" for c in structured["qb_path"])
        L.append(f"`QB`: {wps}")
        L.append("")
        next_step += 1

    if structured.get("ball_carrier_paths"):
        L.append(f"## Step {next_step} — ball-carrier / lead-block paths")
        L.append("")
        for entry in structured["ball_carrier_paths"]:
            wps = " → ".join(f"({c[0]}, {c[1]})" for c in entry["waypoints_cells"])
            L.append(f"- `{entry['player']}` ({entry['role']}): {wps}")
            if entry.get("notes"):
                L.append(f"  - {entry['notes']}")
        L.append("")
        next_step += 1

    # Blocking
    if structured["blocking"]:
        L.append(f"## Step {next_step} — blocking assignments")
        L.append("")
        for b in structured["blocking"]:
            target = f" → {b['target']}" if b.get("target") else ""
            L.append(f"- `{b['player']}`: {b['scheme']}{target}")
            if b.get("notes"):
                L.append(f"  - {b['notes']}")
        L.append("")

    # Notes
    if play.get("notes"):
        L.append("## Notes")
        L.append("")
        L.append(play["notes"].strip())
        L.append("")

    return "\n".join(L)


@mcp.tool()
def list_families(cursor: str | None = None, limit: int = 50) -> dict[str, Any]:
    """List every disguise family in data/play-families/.

    A disguise family is a base play plus companion plays that show the
    defense the same pre-snap look and the same first ~1-2 seconds of action,
    then diverge — the deception unit of the offense. Returns brief metadata
    per family; use get_family(id) for the full record.
    """
    fams = _load_all_families()
    items = [
        {
            "family_id": fid,
            "name": f.get("name"),
            "formation_id": f.get("formation_id"),
            "base_play_id": f.get("base_play_id"),
            "companion_count": len(f.get("companion_play_ids") or []),
            "disguise_score": f.get("disguise_score"),
        }
        for fid, f in sorted(fams.items())
    ]
    return _paginate(items, cursor, limit)


@mcp.tool()
def get_family(family_id: str) -> dict[str, Any]:
    """Return a disguise family's full record — base play, companions,
    disguise_score, defensive_coverage_matrix, tags, source_notes.

    Args:
        family_id: the family id (see list_families()).
    """
    fams = _load_all_families()
    fam = fams.get(family_id)
    if fam is None:
        from difflib import get_close_matches
        return {
            "error": f"no family '{family_id}'",
            "did_you_mean": get_close_matches(family_id, list(fams), n=3),
            "available": sorted(fams),
        }
    return fam


@mcp.tool()
def get_disguise_twins(play_id: str) -> dict[str, Any]:
    """Given a play, return the disguise families it belongs to and its twin
    plays — the other family members that show the defense the same early
    picture, then diverge.

    Answers the core deception question: "what does this play look like, and
    what else looks identical to it through the first ~1-2 seconds?"

    Args:
        play_id: the play to look up.
    """
    plays = _load_all()
    if play_id not in plays:
        from difflib import get_close_matches
        return {"error": f"no play '{play_id}'",
                "did_you_mean": get_close_matches(play_id, list(plays), n=3)}
    fams = _load_all_families()
    memberships: list[dict[str, Any]] = []
    twins: set[str] = set()
    for fid, f in fams.items():
        members = [f.get("base_play_id")] + list(f.get("companion_play_ids") or [])
        if play_id in members:
            memberships.append({
                "family_id": fid,
                "role_in_family": "base" if f.get("base_play_id") == play_id else "companion",
                "base_play_id": f.get("base_play_id"),
                "disguise_score": f.get("disguise_score"),
            })
            twins.update(m for m in members if m and m != play_id)
    return {
        "play_id": play_id,
        "in_families": memberships,
        "twins": sorted(twins),
        "note": ("twins show the defense the same pre-snap + early-action picture, then diverge"
                 if twins else "this play is not in any disguise family yet"),
    }


@mcp.tool()
def scout_play(play_id: str) -> dict[str, Any]:
    """Coaching scout of a play: how a defense beats it (defensive_counters)
    and when to flip its direction (flip_reads) — both keyed to a pre-snap
    alignment the QB can read in one glance.

    Args:
        play_id: the play to scout.
    """
    plays = _load_all()
    p = plays.get(play_id)
    if p is None:
        from difflib import get_close_matches
        return {"error": f"no play '{play_id}'",
                "did_you_mean": get_close_matches(play_id, list(plays), n=3)}
    counters = [
        {k: c.get(k) for k in ("counter_id", "pre_snap_look", "qb_key", "read_category", "why")}
        for c in (p.get("defensive_counters") or [])
    ]
    flips = [
        {k: fr.get(k) for k in ("flip_id", "pre_snap_look", "qb_key", "read_category", "flip_to", "why")}
        for fr in (p.get("flip_reads") or [])
    ]
    rpo_type = p.get("rpo_type")
    summary = f"{len(counters)} pre-snap counter look(s), {len(flips)} flip read(s)"
    if rpo_type:
        summary += f"; RPO ({rpo_type}-type read)"
    return {
        "play_id": play_id,
        "name": p.get("name"),
        "play_type": p.get("play_type"),
        "rpo_type": rpo_type,
        "defensive_counters": counters,
        "flip_reads": flips,
        "summary": summary,
    }


@mcp.tool()
def manifest() -> dict[str, Any]:
    """Return this server's purpose, tool list, and worked examples."""
    return {
        "server": "play-library",
        "purpose": "Central play library: plays across 20+ formations, plus disguise families. Owns single-play + family discovery, authoring, validation, rendering, scouting, pairwise analysis, and export. For collection-level assembly (playbooks, audibles, gap-filling) use playbook-generation-mcp.",
        "tools": [
            {"name": "list_plays", "description": "All plays with id, name, type, formation, philosophy. Paginated (cursor/limit)."},
            {"name": "get_play", "description": "Full YAML: assignments, paths, routes, blocking, concept refs, defensive_counters, flip_reads, tags."},
            {"name": "find_plays_by_formation", "description": "Plays matching a formation_id."},
            {"name": "find_plays_by_tag", "description": "Plays whose tags include the given value."},
            {"name": "find_plays_by_rpo_type", "description": "RPO plays by sub-type — alert (pre-snap) / peek (post-snap LB read) / read (QB run threat)."},
            {"name": "find_plays_vs_defense", "description": "Plays tagged to beat a specific defensive shell."},
            {"name": "find_plays_by_concept", "description": "Search across id, name, aliases, tags, formation concepts, and concept refs (single + multi-concept concepts[])."},
            {"name": "validate_play", "description": "Schema + concept lints: formation cross-ref, route ref, concept FKs, concepts[] integrity, defensive_counters/flip_reads ids, TODO scan."},
            {"name": "render_play", "description": "Return SVG of play in a game's editor grid."},
            {"name": "build_starter_play", "description": "Return a 70%-filled YAML scaffold for a given formation + play type."},
            {"name": "list_play_templates", "description": "Concept templates available for build_starter_play(concept=...); filter by play_type or philosophy."},
            {"name": "save_play", "description": "Validate then write to data/plays/. Requires overwrite=True to update existing."},
            {"name": "update_play", "description": "Shallow-patch top-level fields of an existing play (re-validates schema)."},
            {"name": "mirror_play", "description": "Generate and optionally save the -left mirror of a play."},
            {"name": "compare_plays", "description": "Disguise/similarity scorecard for N plays."},
            {"name": "predict_matchup", "description": "Best/neutral/worst rating vs a defense + rationale."},
            {"name": "list_families", "description": "All disguise families with base play, companion count, disguise_score. Paginated."},
            {"name": "get_family", "description": "Full disguise-family record: base, companions, disguise_score, coverage matrix."},
            {"name": "get_disguise_twins", "description": "A play's disguise families + its twin plays (what looks identical to it early)."},
            {"name": "scout_play", "description": "Coaching scout: defensive_counters (how to beat it), flip_reads (when to flip it), and rpo_type, keyed to pre-snap looks."},
            {"name": "export_play_instructions", "description": "Click-by-click create-a-play instructions for a specific game."},
            {"name": "manifest", "description": "This document."},
        ],
        "examples": [
            "list_plays() → {items: [{play_id, name, play_type, formation, philosophy}, ...], next_cursor: null}",
            "find_plays_by_formation('i-formation') → [play_id, ...]",
            "build_starter_play('singleback-ace', 'pass', philosophy='west-coast') → YAML scaffold",
            "update_play('singleback-trio-mesh', {'primary_read': 'Z'}) → {updated: True, changed_keys: ['primary_read']}",
        ],
    }


if __name__ == "__main__":
    mcp.run()
