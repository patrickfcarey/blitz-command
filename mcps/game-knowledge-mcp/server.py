#!/usr/bin/env python3
"""Game Knowledge MCP server.

Exposes blitz-command's game profile library (data/games/) to AI agents
over the Model Context Protocol. Covers PS1, PS2, and PS3 era Madden and
NCAA titles.

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
GAMES_DIR = REPO_ROOT / "data" / "games"
FORMATIONS_DIR = REPO_ROOT / "data" / "formations"
PLAYS_DIR = REPO_ROOT / "data" / "plays"
SCHEMA_PATH = REPO_ROOT / "schemas" / "game.schema.json"

_SCHEMA_CACHE: dict | None = None


def _load_schema() -> dict:
    global _SCHEMA_CACHE
    if _SCHEMA_CACHE is None:
        with open(SCHEMA_PATH) as f:
            _SCHEMA_CACHE = json.load(f)
    return _SCHEMA_CACHE


_CACHE: dict[str, dict[str, Any]] | None = None
_CACHE_MTIME: float = 0.0


def _games_dir_mtime() -> float:
    if not GAMES_DIR.exists():
        return 0.0
    return max(
        (p.stat().st_mtime for p in GAMES_DIR.rglob("editor-grid.yaml")),
        default=0.0,
    )


def _load_all() -> dict[str, dict[str, Any]]:
    global _CACHE, _CACHE_MTIME
    current_mtime = _games_dir_mtime()
    if _CACHE is not None and current_mtime == _CACHE_MTIME:
        return _CACHE
    schema = _load_schema()
    games: dict[str, dict[str, Any]] = {}
    for path in sorted(GAMES_DIR.rglob("editor-grid.yaml")):
        try:
            with open(path) as f:
                data = yaml.safe_load(f)
            if not data:
                continue
            validate(data, schema)
            game_id = data.get("game_id") or path.parent.name
            games[game_id] = data
        except (ValidationError, yaml.YAMLError) as e:
            print(f"WARN: skipping {path}: {e}", file=sys.stderr)
    _CACHE = games
    _CACHE_MTIME = current_mtime
    return games


mcp = FastMCP("game-knowledge")


def _paginate(items: list, cursor: str | None, limit: int) -> dict[str, Any]:
    offset = int(cursor) if cursor else 0
    page = items[offset: offset + limit]
    next_offset = offset + len(page)
    return {
        "items": page,
        "next_cursor": str(next_offset) if next_offset < len(items) else None,
    }


@mcp.tool()
def list_games(cursor: str | None = None, limit: int = 50) -> dict[str, Any]:
    """List every game profile with brief metadata.

    Returns:
        {
          "items":       [{...}, ...],
          "next_cursor": str | null,
        }

    Item shape:
        {
          "id":                   "madden-05-ps2",
          "name":                 "Madden NFL 2005",
          "release_year":         2004,
          "platform":             "ps2",
          "era":                  "ps2",
          "custom_play_support":  true,
          "verification_status":  "inferred",
        }

    45 games total: 10 PS1 (no editor), 20 PS2, 15 PS3.

    Args:
        cursor: opaque pagination token from the previous call's next_cursor.
        limit: max items per page (default 50).

    Example:
        >>> page = list_games()
        >>> [g['id'] for g in page['items'] if g['custom_play_support'] and g['era'] == 'ps3']
        ['madden-07-ps3', 'madden-08-ps3', ..., 'ncaa-14-ps3']
    """
    all_items = [
        {
            "id": gid,
            "name": g.get("name"),
            "release_year": g.get("release_year"),
            "platform": g.get("platform"),
            "era": g.get("era"),
            "custom_play_support": g.get("custom_play_support", False),
            "verification_status": g.get("verification_status"),
        }
        for gid, g in _load_all().items()
    ]
    return _paginate(all_items, cursor, limit)


@mcp.tool()
def get_game(game_id: str) -> dict[str, Any]:
    """Get the full game profile for a specific game_id.

    Returns the complete YAML: name, release_year, developer, publisher,
    platform, era, custom_play_support, custom_formation_support, grid
    (width/height/origin), scale (yards per cell), snap_to_cells, limits
    (max_route_depth_yd, max_player_split_yd, max_backfield_depth_yd,
    allowed_motion), playbook_caps, engine_quirks, default_playbooks,
    verification_status, source_notes.

    For PS1 games (no editor), grid/scale/limits/playbook_caps are all null.

    Common game_id patterns:
        PS2 Madden: 'madden-02-ps2' through 'madden-11-ps2'
        PS2 NCAA:   'ncaa-02-ps2' through 'ncaa-11-ps2'
        PS3 Madden: 'madden-07-ps3' through 'madden-13-ps3'
        PS3 NCAA:   'ncaa-07-ps3' through 'ncaa-14-ps3'
        PS1 Madden: 'madden-96-ps1' through 'madden-2002-ps1'
        PS1 NCAA:   'ncaa-99-ps1', 'ncaa-2000-ps1', 'ncaa-2001-ps1'

    Args:
        game_id: e.g., 'madden-05-ps2' (no directory suffix needed).
    """
    games = _load_all()
    if game_id not in games:
        available = sorted(games.keys())
        suggestions = [a for a in available if game_id.replace("-", "") in a.replace("-", "")]
        msg = f"No game with id '{game_id}'."
        if suggestions:
            msg += f" Did you mean: {suggestions[:5]}?"
        else:
            msg += f" {len(available)} games available; call list_games() for ids."
        raise ValueError(msg)
    return games[game_id]


@mcp.tool()
def compare_games(game_id_1: str, game_id_2: str) -> dict[str, Any]:
    """Compare editor capabilities between two games.

    Returns a diff highlighting key differences: grid size, route depth,
    player split, backfield depth, motion options, playbook caps.

    Example:
        >>> compare_games('madden-05-ps2', 'madden-10-ps3')
        {
          "game_1": {"id": "madden-05-ps2", "era": "ps2", "grid": "21x7", ...},
          "game_2": {"id": "madden-10-ps3", "era": "ps3", "grid": "25x9", ...},
          "differences": {
            "grid": "21x7 vs 25x9",
            "max_route_depth_yd": "20 vs 25",
            ...
          }
        }

    Args:
        game_id_1: first game_id.
        game_id_2: second game_id.
    """
    games = _load_all()
    g1 = games.get(game_id_1)
    g2 = games.get(game_id_2)
    if not g1:
        raise ValueError(f"No game with id '{game_id_1}'.")
    if not g2:
        raise ValueError(f"No game with id '{game_id_2}'.")

    def grid_str(g: dict) -> str:
        grid = g.get("grid")
        if not grid:
            return "none"
        return f"{grid['width']}x{grid['height']}"

    def limits_val(g: dict, key: str) -> Any:
        limits = g.get("limits")
        if not limits:
            return None
        return limits.get(key)

    diffs: dict[str, str] = {}

    # Grid
    gs1, gs2 = grid_str(g1), grid_str(g2)
    if gs1 != gs2:
        diffs["grid"] = f"{gs1} vs {gs2}"

    # Scale
    sc1, sc2 = g1.get("scale"), g2.get("scale")
    if sc1 and sc2:
        x1 = sc1.get("x_yards_per_cell")
        x2 = sc2.get("x_yards_per_cell")
        if x1 != x2:
            diffs["x_yards_per_cell"] = f"{x1} vs {x2}"

    # Limits
    for key in ("max_route_depth_yd", "max_player_split_yd", "max_backfield_depth_yd"):
        v1, v2 = limits_val(g1, key), limits_val(g2, key)
        if v1 != v2:
            diffs[key] = f"{v1} vs {v2}"

    # Motion
    m1 = sorted(limits_val(g1, "allowed_motion") or [])
    m2 = sorted(limits_val(g2, "allowed_motion") or [])
    if m1 != m2:
        diffs["allowed_motion"] = f"{m1} vs {m2}"

    # Playbook caps
    pc1 = (g1.get("playbook_caps") or {}).get("max_plays_total")
    pc2 = (g2.get("playbook_caps") or {}).get("max_plays_total")
    if pc1 != pc2:
        diffs["max_plays_total"] = f"{pc1} vs {pc2}"

    return {
        "game_1": {
            "id": game_id_1,
            "name": g1.get("name"),
            "era": g1.get("era"),
            "grid": gs1,
            "custom_play_support": g1.get("custom_play_support"),
        },
        "game_2": {
            "id": game_id_2,
            "name": g2.get("name"),
            "era": g2.get("era"),
            "grid": gs2,
            "custom_play_support": g2.get("custom_play_support"),
        },
        "differences": diffs,
        "identical_capabilities": len(diffs) == 0,
    }


@mcp.tool()
def find_games_supporting(feature: str) -> list[str]:
    """Return game IDs that support a named boolean feature.

    Feature values:
        'custom_play_support'      — game has a create-a-play editor
        'custom_formation_support' — game has a custom formation editor

    Example:
        >>> find_games_supporting('custom_play_support')
        ['madden-02-ps2', 'madden-03-ps2', ..., 'ncaa-14-ps3']  # 35 games

    Args:
        feature: boolean field name in the game profile.
    """
    return [gid for gid, g in _load_all().items() if g.get(feature) is True]


@mcp.tool()
def find_games_by_era(era: str) -> list[str]:
    """Return game IDs from the given era.

    Era values:
        'ps1' — PlayStation 1 titles (no play editor)
        'ps2' — PlayStation 2 titles (21x7 editor grid)
        'ps3' — PlayStation 3 titles (25x9 editor grid)

    Example:
        >>> find_games_by_era('ps2')
        ['madden-02-ps2', ..., 'ncaa-11-ps2']  # 20 games

    Args:
        era: 'ps1', 'ps2', or 'ps3' (case-insensitive).
    """
    era_lower = era.lower()
    return [gid for gid, g in _load_all().items() if g.get("era", "").lower() == era_lower]


# ---------------------------------------------------------------------------
# Coordinate translation helpers
# ---------------------------------------------------------------------------

def _require_editor(game: dict[str, Any], game_id: str) -> None:
    """Raise if this game has no editor grid (PS1 titles)."""
    if not game.get("grid") or not game.get("scale"):
        raise ValueError(
            f"'{game_id}' has no editor grid (PS1 titles have no play editor). "
            "Use find_games_supporting('custom_play_support') for editor-capable games."
        )


def _translate_point(
    game: dict[str, Any],
    x_yd: float,
    y_yd: float,
) -> tuple[float, float]:
    """Convert universal yards to editor grid (col, row). Pure math, no BFS."""
    origin = game["grid"]["origin"]
    scale = game["scale"]
    col = origin["x"] + x_yd / scale["x_yards_per_cell"]
    row = origin["y"] + y_yd / scale["y_yards_per_cell"]
    if game.get("snap_to_cells", False):
        return (round(col), round(row))
    return (round(col, 3), round(row, 3))


def _cell_in_bounds(game: dict[str, Any], col: float, row: float) -> bool:
    grid = game["grid"]
    return 0 <= col < grid["width"] and 0 <= row < grid["height"]


def _load_formation_yaml(formation_id: str) -> dict[str, Any] | None:
    path = FORMATIONS_DIR / f"{formation_id}.yaml"
    if not path.exists():
        return None
    with open(path) as f:
        return yaml.safe_load(f)


def _load_play_yaml(play_id: str) -> dict[str, Any] | None:
    path = PLAYS_DIR / f"{play_id}.yaml"
    if not path.exists():
        return None
    with open(path) as f:
        return yaml.safe_load(f)


@mcp.tool()
def translate_position(game_id: str, x_yd: float, y_yd: float) -> dict[str, Any]:
    """Convert a universal-coordinate point to a game's editor grid cell.

    Uses the game profile's origin, scale, and snap_to_cells flag.
    No BFS conflict resolution — for per-player layout use translate_formation().

    Universal coordinate system:
        Origin: center of ball at line of scrimmage (0, 0)
        x positive = offense's right
        y positive = downfield, y negative = backfield
        Units: real yards

    Returns:
        {
          "game_id":     "madden-05-ps2",
          "x_yd":        float,
          "y_yd":        float,
          "col":         int | float,   # editor column (0-indexed from left)
          "row":         int | float,   # editor row (0-indexed from top; 0 = deepest backfield)
          "snap_to_cells": bool,
          "in_bounds":   bool,          # True if cell is within the editor grid
          "grid_width":  int,
          "grid_height": int,
        }

    Example:
        >>> translate_position('madden-05-ps2', x_yd=0, y_yd=0)
        {"col": 10, "row": 5, "in_bounds": True, ...}   # ball at center LOS
        >>> translate_position('madden-05-ps2', x_yd=10, y_yd=-4)
        {"col": 16, "row": 3, "in_bounds": True, ...}   # WR 10 yd right, HB 4 yd back

    Args:
        game_id: e.g., 'madden-05-ps2'.
        x_yd: universal x coordinate in real yards.
        y_yd: universal y coordinate in real yards.
    """
    game = _load_all().get(game_id)
    if not game:
        raise ValueError(f"No game with id '{game_id}'. Call list_games() for ids.")
    _require_editor(game, game_id)

    col, row = _translate_point(game, x_yd, y_yd)
    return {
        "game_id": game_id,
        "x_yd": x_yd,
        "y_yd": y_yd,
        "col": col,
        "row": row,
        "snap_to_cells": game.get("snap_to_cells", False),
        "in_bounds": _cell_in_bounds(game, col, row),
        "grid_width": game["grid"]["width"],
        "grid_height": game["grid"]["height"],
    }


@mcp.tool()
def translate_formation(game_id: str, formation_id: str) -> dict[str, Any]:
    """Translate all 11 player positions from universal yards to editor grid cells.

    Returns each player's label, position, universal coordinates, and editor cell.
    Out-of-bounds players are flagged — they may need to be adjusted before
    the formation can be entered into the game's editor.

    Note: the renderer applies BFS conflict resolution when two players snap to
    the same cell. This tool returns the raw calculated cell for each player
    without conflict resolution — use render_play() in play-library-mcp to see
    the resolved layout.

    Returns:
        {
          "game_id":       "madden-05-ps2",
          "formation_id":  "singleback-trio",
          "snap_to_cells": bool,
          "players": [
            {
              "label":     "LT",
              "position":  "OL",
              "x_yd":      float,
              "y_yd":      float,
              "col":       int,
              "row":       int,
              "in_bounds": bool,
            }, ...
          ],
          "warnings": list[str],
        }

    Args:
        game_id:       e.g., 'madden-05-ps2'.
        formation_id:  e.g., 'singleback-trio'.
    """
    game = _load_all().get(game_id)
    if not game:
        raise ValueError(f"No game with id '{game_id}'. Call list_games() for ids.")
    _require_editor(game, game_id)

    formation = _load_formation_yaml(formation_id)
    if not formation:
        raise ValueError(f"No formation file for '{formation_id}'. Call formation-library-mcp.list_formations() for ids.")

    warnings: list[str] = []
    players_out = []
    for p in formation.get("players", []):
        x_yd = float(p.get("x", 0))
        y_yd = float(p.get("y", 0))
        col, row = _translate_point(game, x_yd, y_yd)
        in_bounds = _cell_in_bounds(game, col, row)
        if not in_bounds:
            warnings.append(
                f"{p.get('label', '?')} at ({x_yd}, {y_yd}) yd → cell ({col}, {row}) "
                f"is outside {game['grid']['width']}×{game['grid']['height']} editor grid"
            )
        players_out.append({
            "label": p.get("label"),
            "position": p.get("position"),
            "x_yd": x_yd,
            "y_yd": y_yd,
            "col": col,
            "row": row,
            "in_bounds": in_bounds,
        })

    return {
        "game_id": game_id,
        "formation_id": formation_id,
        "snap_to_cells": game.get("snap_to_cells", False),
        "players": players_out,
        "warnings": warnings,
    }


@mcp.tool()
def translate_play(game_id: str, play_id: str) -> dict[str, Any]:
    """Translate a play's assignment paths from universal yards to editor grid cells.

    Returns the starting cell for each player (from the formation) and the
    sequence of cells for each assignment's route/path. This is the data an
    agent needs to enter the play into the game's editor without rendering SVG.

    Waypoints that fall outside the editor grid are flagged in warnings — they
    represent route depth that the game cannot display (common for deep routes).

    Returns:
        {
          "game_id":   "madden-05-ps2",
          "play_id":   "singleback-trio-mesh",
          "formation": "singleback-trio",
          "snap_to_cells": bool,
          "assignments": [
            {
              "player":     "Z",
              "role":       "route",
              "route_name": "drag",
              "waypoints":  [
                {"x_yd": 0, "y_yd": 0, "col": 10, "row": 5},
                {"x_yd": 4, "y_yd": 5, "col": 12, "row": 7},
              ],
            }, ...
          ],
          "warnings": list[str],
        }

    Args:
        game_id: e.g., 'madden-05-ps2'.
        play_id: e.g., 'singleback-trio-mesh'.
    """
    game = _load_all().get(game_id)
    if not game:
        raise ValueError(f"No game with id '{game_id}'. Call list_games() for ids.")
    _require_editor(game, game_id)

    play = _load_play_yaml(play_id)
    if not play:
        raise ValueError(f"No play file for '{play_id}'. Call play-library-mcp.list_plays() for ids.")

    warnings: list[str] = []
    assignments_out = []

    for assign in play.get("assignments", []):
        path = assign.get("path") or []
        waypoints_out = []
        for wp in path:
            if len(wp) < 2:
                continue
            x_yd, y_yd = float(wp[0]), float(wp[1])
            col, row = _translate_point(game, x_yd, y_yd)
            in_bounds = _cell_in_bounds(game, col, row)
            if not in_bounds:
                label = assign.get("player", "?")
                warnings.append(
                    f"{label} path waypoint ({x_yd}, {y_yd}) yd → cell ({col}, {row}) "
                    "is outside editor grid (deep route exceeds grid boundary)"
                )
            waypoints_out.append({
                "x_yd": x_yd,
                "y_yd": y_yd,
                "col": col,
                "row": row,
            })

        entry: dict[str, Any] = {
            "player": assign.get("player"),
            "role": assign.get("role"),
            "waypoints": waypoints_out,
        }
        if assign.get("route_name"):
            entry["route_name"] = assign["route_name"]
        if assign.get("blocking_scheme"):
            entry["blocking_scheme"] = assign["blocking_scheme"]
        assignments_out.append(entry)

    return {
        "game_id": game_id,
        "play_id": play_id,
        "formation": play.get("formation"),
        "play_type": play.get("play_type"),
        "snap_to_cells": game.get("snap_to_cells", False),
        "assignments": assignments_out,
        "warnings": warnings,
    }


@mcp.tool()
def manifest() -> dict[str, Any]:
    """Return this server's purpose, tool list, and worked examples."""
    return {
        "server": "game-knowledge",
        "purpose": "Exposes blitz-command's 45 game profiles covering PS1/PS2/PS3 Madden and NCAA titles. Use it to find editor capabilities (grid size, route depth limits, motion options) before designing plays, and to translate universal-coordinate plays into editor grid cells.",
        "tools": [
            {"name": "list_games", "description": "All 45 profiles with id, year, era, custom_play_support. Start here."},
            {"name": "get_game", "description": "Full profile: grid, scale, limits, playbook_caps, engine_quirks."},
            {"name": "compare_games", "description": "Capability diff between two games (grid, route depth, motion, caps)."},
            {"name": "find_games_supporting", "description": "Boolean feature filter (custom_play_support, custom_formation_support)."},
            {"name": "find_games_by_era", "description": "Filter by ps1 / ps2 / ps3."},
            {"name": "translate_position", "description": "Convert a universal (x_yd, y_yd) point to a game's editor grid (col, row)."},
            {"name": "translate_formation", "description": "Translate all 11 player positions for a formation into editor cells."},
            {"name": "translate_play", "description": "Translate all assignment paths for a play into per-waypoint editor cells."},
            {"name": "manifest", "description": "This document."},
        ],
        "examples": [
            "find_games_by_era('ps2') → 20 games with 21×7 editor grid",
            "compare_games('madden-05-ps2', 'madden-10-ps3') → grid/depth/motion diff",
            "translate_position('madden-05-ps2', x_yd=0, y_yd=0) → {'col': 10, 'row': 5}",
            "translate_formation('madden-05-ps2', 'singleback-trio') → per-player cells",
            "translate_play('madden-05-ps2', 'singleback-trio-mesh') → per-waypoint cells",
        ],
    }


if __name__ == "__main__":
    mcp.run()
