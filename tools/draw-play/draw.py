#!/usr/bin/env python3
"""Render an offensive play, a defensive formation, or both, in a target
game's editor grid.

Modes (controlled by --play / --defense / --show / --field flags):

  Offense only:    --play <id>
  Defense only:    --defense <id>
  Both, full:      --play <id> --defense <id>                  (or --vs)
  Both, offense:   --play <id> --defense <id> --show offense   (only offensive routes/runs)
  Both, defense:   --play <id> --defense <id> --show defense   (only defensive coverage)
  Both, players:   --play <id> --defense <id> --show none      (no assignments at all)

Field length:
  --field long  (default)  shows LOS + 30 yd downfield (deep routes visible)
  --field short            shows LOS + 5 yd downfield (close-up of the box)

Backwards-compatible: old positional form
  draw.py <play-id> <game-id> [--vs <def-id>] -o output.svg
still works.
"""
from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
ROUTES_DIR = REPO_ROOT / "data" / "routes"
FORMATIONS_DIR = REPO_ROOT / "data" / "formations"
PLAYS_DIR = REPO_ROOT / "data" / "plays"
GAMES_DIR = REPO_ROOT / "data" / "games"

PIXELS_PER_CELL = 32
PLAYER_SIZE = 24
DEF_PLAYER_SIZE = 20
FIELD_MARGIN = 40

FIELD_LONG_YD = 30
FIELD_SHORT_YD = 5

ROUTE_COLOR = "#00d4ff"
ROUTE_WIDTH = 3.5

PRIMARY_READ_COLOR = "#ff8c00"
SECONDARY_READ_COLOR = "#4fc3f7"
TERTIARY_READ_COLOR = "#b39ddb"
CHECKDOWN_COLOR = "#bdbdbd"
RUN_PATH_WIDTH = 4.0
ALT_PATH_WIDTH = 3.0

FB_LEAD_COLOR = "#e91e63"
PULL_COLOR = "#8bc34a"
PASS_BLOCK_COLOR = "#90a4ae"
LEAD_BLOCK_WIDTH = 3.0
PASS_BLOCK_WIDTH = 2.0

FAKE_PATH_COLOR = "#888"
FAKE_PATH_WIDTH = 2.5

LABEL_FONT_SIZE = 11
LABEL_FONT_SIZE_LONG = 9

COLOR_BG_OUTER = "#1a1a1a"
COLOR_BG_INNER = "#2e7d32"        # editor sub-region — grass green
COLOR_BG_EXTENSION = "#1b5e20"    # extension downfield — slightly darker green
COLOR_GRID_FINE = "#388e3c"       # fine grid on green
COLOR_GRID_FINE_EXT = "#2e6b34"   # fine grid on darker extension
COLOR_GRID_MAJOR = "#cccccc"      # major lines (every 5 cells) — light gray
COLOR_GRID_BOUNDARY = "#ffffff"
COLOR_LOS = "#ffd700"
COLOR_ROUTE_LIMIT = "#ff6666"
COLOR_YARD_LINE = "#cfcfcf"       # 5-yard horizontal markers
COLOR_HASH = "#ffffff"            # NFL/NCAA hash tick marks

COLOR_OFFENSE = "#3399ff"
COLOR_C = "#ff8c00"
COLOR_BALL_CARRIER = "#ff8c00"
COLOR_PRIMARY_READ = "#00d4ff"
COLOR_OUT_OF_BOUNDS = "#ff3333"

COLOR_DEFENSE = "#d32f2f"
COLOR_DEFENSE_DL = "#b71c1c"
COLOR_DEFENSE_DEEP = "#ef5350"

# Coverage rendering colors
COLOR_RUSH = "#ff5252"
COLOR_ZONE = "#ff8a80"
COLOR_DEEP_ZONE = "#ffab91"
COLOR_MAN = "#f48fb1"
COLOR_BLITZ = "#ff1744"
COLOR_SPY = "#ce93d8"
ZONE_FILL_OPACITY = 0.15
COVERAGE_LINE_WIDTH = 2.5

INTERIOR_OL = {"LT", "LG", "C", "RG", "RT"}
DEFENSIVE_DL = {"DE", "DT", "NT"}

ZONE_ROLES = {"hook", "curl", "flat", "deep-zone", "underneath-zone", "buzz", "rat", "lurk", "carry"}
RUSH_ROLES = {"rush", "blitz"}
SPY_ROLES = {"spy", "qb-spy", "robber"}
MAN_ROLES = {"man", "press-man", "off-man"}


def load_yaml(path: Path) -> dict:
    with open(path) as f:
        return yaml.safe_load(f)


def load_route_library() -> dict[str, dict]:
    by_name = {}
    for path in sorted(ROUTES_DIR.glob("*.yaml")):
        route = load_yaml(path)
        by_name[route["name"]] = route
        for alias in route.get("aliases", []):
            by_name[alias] = route
    return by_name


def hash_spec_for_profile(profile: dict) -> tuple[float, float] | None:
    """Return (left_x_yd, right_x_yd) hash-mark x-coordinates in universal yards,
    or None if the game/profile doesn't have hash marks defined.

    Reads `hash_marks_yd_from_center` from the profile if present. Otherwise
    falls back to common defaults based on game_id prefix:
      - madden-* → NFL hashes (3.083 yd from center)
      - ncaa*    → NCAA hashes (6.667 yd from center)
      - hs-*     → HS hashes (8.889 yd from center)
    """
    hash_yd = profile.get("hash_marks_yd_from_center")
    if hash_yd is not None:
        return (-float(hash_yd), float(hash_yd))
    gid = (profile.get("game_id") or "").lower()
    if gid.startswith("madden"):
        return (-3.083, 3.083)
    if gid.startswith("ncaa"):
        return (-6.667, 6.667)
    if gid.startswith("hs") or gid.startswith("highschool") or gid.startswith("high-school"):
        return (-8.889, 8.889)
    return None


def universal_to_grid(x_yd: float, y_yd: float, profile: dict) -> tuple[float, float]:
    origin = profile["grid"]["origin"]
    scale = profile["scale"]
    return (
        origin["x"] + x_yd / scale["x_yards_per_cell"],
        origin["y"] + y_yd / scale["y_yards_per_cell"],
    )


def total_y_cells(profile: dict, extra_yd: float) -> int:
    """Total visible vertical cells (editor height + downfield extension)."""
    extra = math.ceil(extra_yd / profile["scale"]["y_yards_per_cell"])
    return profile["grid"]["height"] + extra


def grid_to_pixel(gx: float, gy: float, profile: dict, total_cells: int) -> tuple[float, float]:
    px = FIELD_MARGIN + gx * PIXELS_PER_CELL
    py = FIELD_MARGIN + (total_cells - gy) * PIXELS_PER_CELL
    return (px, py)


def receiver_route_path(receiver_x: float, receiver_y: float, route: dict) -> list[tuple[float, float]]:
    mirror = -1 if receiver_x > 0.1 else 1
    return [
        (receiver_x + (wp[0] * mirror), receiver_y + wp[1])
        for wp in route["path"]
    ]


def route_lookup(route_lib: dict, name: str) -> dict | None:
    if name in route_lib:
        return route_lib[name]
    for sep in (" or ", "-or-"):
        if sep in name:
            first = name.split(sep)[0].strip()
            if first in route_lib:
                return route_lib[first]
    return None


def is_tight_inline(player: dict, formation: dict) -> bool:
    if not player.get("on_line"):
        return False
    pos = player.get("position", "")
    if pos in INTERIOR_OL:
        return True
    if pos == "TE":
        ol_xs = [p["x"] for p in formation["players"] if p.get("position") in INTERIOR_OL]
        if ol_xs:
            return min(abs(player["x"] - x) for x in ol_xs) <= 3.0
    return False


def player_grid_pos(player: dict, formation: dict, profile: dict) -> tuple[float, float]:
    origin_x = profile["grid"]["origin"]["x"]
    if is_tight_inline(player, formation):
        tight = sorted(
            [p for p in formation["players"] if is_tight_inline(p, formation)],
            key=lambda p: p["x"],
        )
        c_player = next((p for p in tight if p.get("label") == "C"), None)
        if c_player is not None and player in tight:
            c_index = tight.index(c_player)
            player_index = tight.index(player)
            snapped_x = origin_x + (player_index - c_index)
            _, gy = universal_to_grid(player["x"], player["y"], profile)
            return (snapped_x, gy)
    return universal_to_grid(player["x"], player["y"], profile)


def render_path(
    parts: list[str],
    waypoints_yd: list[tuple[float, float]],
    profile: dict,
    total_cells: int,
    color: str,
    width: float,
    marker: str,
    dashed: bool = False,
) -> None:
    pixel_points = []
    for x_yd, y_yd in waypoints_yd:
        gx, gy = universal_to_grid(x_yd, y_yd, profile)
        pixel_points.append(grid_to_pixel(gx, gy, profile, total_cells))
    if len(pixel_points) < 2:
        return
    points_str = " ".join(f"{p[0]:.1f},{p[1]:.1f}" for p in pixel_points)
    dasharray = ' stroke-dasharray="6,4"' if dashed else ""
    parts.append(
        f'<polyline points="{points_str}" fill="none" '
        f'stroke="{color}" stroke-width="{width}"{dasharray} '
        f'marker-end="url(#{marker})" />'
    )


def render_zone_ellipse(
    parts: list[str],
    center_x_yd: float,
    center_y_yd: float,
    radius_x_yd: float,
    radius_y_yd: float,
    color: str,
    profile: dict,
    total_cells: int,
) -> None:
    cx_g, cy_g = universal_to_grid(center_x_yd, center_y_yd, profile)
    cx_px, cy_px = grid_to_pixel(cx_g, cy_g, profile, total_cells)
    rx_px = (radius_x_yd / profile["scale"]["x_yards_per_cell"]) * PIXELS_PER_CELL
    ry_px = (radius_y_yd / profile["scale"]["y_yards_per_cell"]) * PIXELS_PER_CELL
    parts.append(
        f'<ellipse cx="{cx_px:.1f}" cy="{cy_px:.1f}" rx="{rx_px:.1f}" ry="{ry_px:.1f}" '
        f'fill="{color}" fill-opacity="{ZONE_FILL_OPACITY}" '
        f'stroke="{color}" stroke-width="1" stroke-dasharray="3,3" />'
    )


def render_defender(player: dict, profile: dict, parts: list[str], total_cells: int) -> None:
    gx, gy = universal_to_grid(player["x"], player["y"], profile)
    px, py = grid_to_pixel(gx, gy, profile, total_cells)
    pos = player.get("position", "")
    label = player.get("label", "")

    if pos in DEFENSIVE_DL:
        fill = COLOR_DEFENSE_DL
    elif pos == "S":
        fill = COLOR_DEFENSE_DEEP
    else:
        fill = COLOR_DEFENSE

    half = DEF_PLAYER_SIZE / 2
    if pos in DEFENSIVE_DL:
        parts.append(
            f'<rect x="{px - half}" y="{py - half}" '
            f'width="{DEF_PLAYER_SIZE}" height="{DEF_PLAYER_SIZE}" '
            f'fill="{fill}" stroke="white" stroke-width="1" '
            f'fill-opacity="0.85" />'
        )
    else:
        parts.append(
            f'<circle cx="{px}" cy="{py}" r="{DEF_PLAYER_SIZE / 2}" '
            f'fill="{fill}" stroke="white" stroke-width="1" '
            f'fill-opacity="0.85" />'
        )
    font_sz = LABEL_FONT_SIZE_LONG if len(label) > 2 else LABEL_FONT_SIZE
    parts.append(
        f'<text x="{px}" y="{py + 4}" text-anchor="middle" '
        f'font-size="{font_sz}" fill="white" font-weight="bold">'
        f'{label}</text>'
    )


def render_defender_coverage(
    defender: dict,
    role: str,
    aim: str,
    covers_player: str | None,
    offensive_formation: dict | None,
    profile: dict,
    parts: list[str],
    total_cells: int,
) -> None:
    """Render a single defender's coverage assignment (rush, zone, man, spy, etc)."""
    dx, dy = defender["x"], defender["y"]

    if role in RUSH_ROLES:
        # Arrow forward into the offensive backfield
        depth = -4.0
        path = [(dx, dy), (dx, dy + depth)]
        color = COLOR_BLITZ if role == "blitz" else COLOR_RUSH
        render_path(parts, path, profile, total_cells, color, COVERAGE_LINE_WIDTH, "arrow-rush")
        return

    if role in MAN_ROLES and covers_player and offensive_formation:
        target = next((p for p in offensive_formation["players"] if p.get("label") == covers_player), None)
        if target is not None:
            path = [(dx, dy), (target["x"], target["y"])]
            render_path(parts, path, profile, total_cells, COLOR_MAN, COVERAGE_LINE_WIDTH, "arrow-man", dashed=True)
        # Ring around defender to mark man
        gx, gy = universal_to_grid(dx, dy, profile)
        cx, cy = grid_to_pixel(gx, gy, profile, total_cells)
        parts.append(
            f'<circle cx="{cx}" cy="{cy}" r="{DEF_PLAYER_SIZE * 0.85}" '
            f'fill="none" stroke="{COLOR_MAN}" stroke-width="1.5" stroke-dasharray="4,3" />'
        )
        return

    if role in SPY_ROLES:
        gx, gy = universal_to_grid(dx, dy, profile)
        cx, cy = grid_to_pixel(gx, gy, profile, total_cells)
        parts.append(
            f'<circle cx="{cx}" cy="{cy}" r="{DEF_PLAYER_SIZE * 1.2}" '
            f'fill="{COLOR_SPY}" fill-opacity="{ZONE_FILL_OPACITY}" '
            f'stroke="{COLOR_SPY}" stroke-width="1.5" stroke-dasharray="2,2" />'
        )
        return

    if role in ZONE_ROLES:
        # Drop point + zone ellipse based on role
        if role == "deep-zone":
            drop_x, drop_y = dx, max(dy, 12.0) + 3.0
            rx, ry = 6.0, 5.0
            color = COLOR_DEEP_ZONE
        elif role == "flat":
            sign = 1 if dx >= 0 else -1
            drop_x, drop_y = dx + sign * 4.0, max(dy - 1.0, 2.0)
            rx, ry = 4.0, 2.0
            color = COLOR_ZONE
        elif role in ("hook", "curl", "underneath-zone", "buzz", "rat", "lurk", "carry"):
            drop_x, drop_y = dx, max(dy + 2.0, 6.0)
            rx, ry = 3.5, 2.5
            color = COLOR_ZONE
        else:
            drop_x, drop_y = dx, dy + 2.0
            rx, ry = 3.0, 2.0
            color = COLOR_ZONE
        render_zone_ellipse(parts, drop_x, drop_y, rx, ry, color, profile, total_cells)
        # Arrow from defender pre-snap to drop point
        if abs(drop_x - dx) > 0.5 or abs(drop_y - dy) > 0.5:
            render_path(
                parts, [(dx, dy), (drop_x, drop_y)], profile, total_cells,
                color, COVERAGE_LINE_WIDTH * 0.8, "arrow-zone", dashed=True,
            )


def render(
    profile: dict,
    play: dict | None = None,
    formation: dict | None = None,
    defense: dict | None = None,
    route_lib: dict | None = None,
    show: str = "both",
    field: str = "long",
) -> tuple[str, list[str]]:
    """Render an SVG. Any or all of play / formation / defense may be None.

    show: which side's assignments to render — "offense", "defense", "both", "none".
    field: "long" (LOS + 30 yd) or "short" (LOS + 5 yd).
    """
    extra_yd = FIELD_LONG_YD if field == "long" else FIELD_SHORT_YD

    grid = profile["grid"]
    scale = profile["scale"]
    width_cells = grid["width"]
    height_cells = grid["height"]
    total_cells = total_y_cells(profile, extra_yd)
    extension_cells = total_cells - height_cells

    inner_w = width_cells * PIXELS_PER_CELL
    inner_h = total_cells * PIXELS_PER_CELL
    field_w = inner_w + 2 * FIELD_MARGIN
    field_h = inner_h + 2 * FIELD_MARGIN
    title_strip_h = 50
    warnings_strip_h = 80
    legend_strip_h = 22
    total_w = field_w
    total_h = field_h + title_strip_h + warnings_strip_h + legend_strip_h

    parts: list[str] = []
    warnings: list[str] = []

    parts.append(
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{total_w}" '
        f'height="{total_h}" viewBox="0 0 {total_w} {total_h}" '
        f'font-family="monospace">'
    )

    def _marker(name: str, color: str) -> str:
        return (f'<marker id="{name}" markerWidth="10" markerHeight="10" '
                f'refX="6" refY="3" orient="auto" markerUnits="strokeWidth">'
                f'<path d="M0,0 L0,6 L9,3 z" fill="{color}" /></marker>')
    parts.append(
        "<defs>"
        + _marker("arrow", ROUTE_COLOR)
        + _marker("arrow-primary", PRIMARY_READ_COLOR)
        + _marker("arrow-secondary", SECONDARY_READ_COLOR)
        + _marker("arrow-tertiary", TERTIARY_READ_COLOR)
        + _marker("arrow-checkdown", CHECKDOWN_COLOR)
        + _marker("arrow-fake", FAKE_PATH_COLOR)
        + _marker("arrow-fb", FB_LEAD_COLOR)
        + _marker("arrow-pull", PULL_COLOR)
        + _marker("arrow-passblock", PASS_BLOCK_COLOR)
        + _marker("arrow-rush", COLOR_RUSH)
        + _marker("arrow-zone", COLOR_ZONE)
        + _marker("arrow-man", COLOR_MAN)
        + "</defs>"
    )

    # Title strip
    parts.append(f'<rect x="0" y="0" width="{total_w}" height="{title_strip_h}" fill="#1a1a1a" />')

    if play and formation:
        title = f'{play["name"]} ({play["play_type"]})'
        sub = f'Formation: {play["formation"]}'
    elif defense and not (play and formation):
        title = defense["name"]
        sub = f'Defense | front: {defense.get("front", "?")} | shell: {defense.get("coverage_shell", "?")}'
    else:
        title = "(no formation loaded)"
        sub = ""

    def_label = ""
    if defense and play and formation:
        def_label = f' | vs {defense["name"]}'

    parts.append(
        f'<text x="12" y="22" font-size="16" fill="white" font-weight="bold">'
        f'{title}</text>'
    )
    parts.append(
        f'<text x="12" y="40" font-size="12" fill="#aaa">'
        f'{sub} | Game: {profile["game_id"]} | '
        f'Editor: {width_cells}x{height_cells} cells, '
        f'{scale["x_yards_per_cell"]} yd/x, {scale["y_yards_per_cell"]} yd/y'
        f' | +{extra_yd}yd downfield ({field}){def_label} | show: {show}</text>'
    )

    field_top = title_strip_h
    parts.append(f'<g transform="translate(0,{field_top})">')

    # Outer background
    parts.append(
        f'<rect x="0" y="0" width="{field_w}" height="{field_h}" fill="{COLOR_BG_OUTER}" />'
    )

    inner_x = FIELD_MARGIN
    inner_y = FIELD_MARGIN

    # Extension area (downfield, above editor)
    ext_top = inner_y
    ext_h = extension_cells * PIXELS_PER_CELL
    parts.append(
        f'<rect x="{inner_x}" y="{ext_top}" width="{inner_w}" height="{ext_h}" '
        f'fill="{COLOR_BG_EXTENSION}" />'
    )
    parts.append(
        f'<text x="{inner_x + 6}" y="{ext_top + 12}" font-size="9" fill="#666" '
        f'font-style="italic">downfield (off-editor)</text>'
    )

    # Editor sub-region
    editor_top = ext_top + ext_h
    editor_h = height_cells * PIXELS_PER_CELL
    parts.append(
        f'<rect x="{inner_x}" y="{editor_top}" width="{inner_w}" height="{editor_h}" '
        f'fill="{COLOR_BG_INNER}" stroke="{COLOR_GRID_BOUNDARY}" stroke-width="2" />'
    )
    parts.append(
        f'<text x="{inner_x + 6}" y="{editor_top + 12}" font-size="9" fill="#888" '
        f'font-style="italic">editor grid</text>'
    )

    # Vertical grid lines
    for gx in range(0, width_cells + 1):
        px = inner_x + gx * PIXELS_PER_CELL
        is_major = gx % 5 == 0
        parts.append(
            f'<line x1="{px}" y1="{ext_top}" x2="{px}" y2="{ext_top + ext_h}" '
            f'stroke="{COLOR_GRID_MAJOR if is_major else COLOR_GRID_FINE_EXT}" '
            f'stroke-width="{0.5 if is_major else 0.3}" />'
        )
        parts.append(
            f'<line x1="{px}" y1="{editor_top}" x2="{px}" y2="{editor_top + editor_h}" '
            f'stroke="{COLOR_GRID_MAJOR if is_major else COLOR_GRID_FINE}" '
            f'stroke-width="{0.7 if is_major else 0.4}" />'
        )

    # 5-yard interval lines through the extension
    extra_yd_per_5 = 5
    extra_cells_per_5 = extra_yd_per_5 / scale["y_yards_per_cell"]
    if extension_cells > 0:
        for k in range(1, math.ceil(extension_cells / extra_cells_per_5) + 1):
            cells_above_los = k * extra_cells_per_5
            gy = grid["origin"]["y"] + cells_above_los
            if gy > total_cells:
                break
            py = inner_y + (total_cells - gy) * PIXELS_PER_CELL
            parts.append(
                f'<line x1="{inner_x}" y1="{py}" x2="{inner_x + inner_w}" y2="{py}" '
                f'stroke="{COLOR_YARD_LINE}" stroke-width="0.6" stroke-dasharray="3,3" />'
            )
            parts.append(
                f'<text x="{inner_x - 6}" y="{py + 3}" text-anchor="end" '
                f'font-size="9" fill="#888">+{int(k * 5)}yd</text>'
            )

    # Editor's own per-cell horizontal grid lines
    for gy in range(0, height_cells + 1):
        py = inner_y + (total_cells - gy) * PIXELS_PER_CELL
        is_major = gy % 5 == 0
        parts.append(
            f'<line x1="{inner_x}" y1="{py}" x2="{inner_x + inner_w}" y2="{py}" '
            f'stroke="{COLOR_GRID_MAJOR if is_major else COLOR_GRID_FINE}" '
            f'stroke-width="{0.7 if is_major else 0.4}" />'
        )

    # Cell-coordinate labels
    for gx in range(0, width_cells + 1, 5):
        px = inner_x + gx * PIXELS_PER_CELL
        parts.append(
            f'<text x="{px}" y="{editor_top + editor_h + 14}" text-anchor="middle" '
            f'font-size="10" fill="#888">{gx}</text>'
        )
    for gy in range(0, height_cells + 1, 5):
        py = inner_y + (total_cells - gy) * PIXELS_PER_CELL + 3
        parts.append(
            f'<text x="{inner_x - 8}" y="{py}" text-anchor="end" '
            f'font-size="10" fill="#888">{gy}</text>'
        )

    # Hash marks (NFL / NCAA / HS — depends on game profile)
    hash_spec = hash_spec_for_profile(profile)
    if hash_spec is not None:
        left_x, right_x = hash_spec
        y_yd_min = -grid["origin"]["y"] * scale["y_yards_per_cell"]
        y_yd_max = (total_cells - grid["origin"]["y"]) * scale["y_yards_per_cell"]
        tick_half_w = 4
        for hash_x in (left_x, right_x):
            gx = grid["origin"]["x"] + hash_x / scale["x_yards_per_cell"]
            if gx < 0 or gx > width_cells:
                continue
            px = inner_x + gx * PIXELS_PER_CELL
            for y_int in range(int(math.floor(y_yd_min)), int(math.ceil(y_yd_max)) + 1):
                gy = grid["origin"]["y"] + y_int / scale["y_yards_per_cell"]
                if gy < 0 or gy > total_cells:
                    continue
                py = inner_y + (total_cells - gy) * PIXELS_PER_CELL
                # Major hash every 5 yards (slightly longer + brighter)
                is_major = (y_int % 5 == 0)
                w = tick_half_w + 1 if is_major else tick_half_w
                opac = 0.85 if is_major else 0.55
                parts.append(
                    f'<line x1="{px - w}" y1="{py}" x2="{px + w}" y2="{py}" '
                    f'stroke="{COLOR_HASH}" stroke-width="{1.4 if is_major else 1.0}" '
                    f'stroke-opacity="{opac}" />'
                )

    # LOS line (universal y=0)
    los_y_px = inner_y + (total_cells - grid["origin"]["y"]) * PIXELS_PER_CELL
    parts.append(
        f'<line x1="{inner_x}" y1="{los_y_px}" x2="{inner_x + inner_w}" y2="{los_y_px}" '
        f'stroke="{COLOR_LOS}" stroke-width="2.5" />'
    )
    parts.append(
        f'<text x="{inner_x + inner_w - 6}" y="{los_y_px - 6}" '
        f'text-anchor="end" font-size="11" fill="{COLOR_LOS}" font-weight="bold">LOS</text>'
    )

    # Editor max route depth ceiling
    limits = profile.get("limits") or {}
    max_depth = limits.get("max_route_depth_yd")
    if max_depth and play and formation:
        depth_grid = grid["origin"]["y"] + max_depth / scale["y_yards_per_cell"]
        depth_px = inner_y + (total_cells - depth_grid) * PIXELS_PER_CELL
        if 0 <= depth_px <= inner_y + inner_h:
            parts.append(
                f'<line x1="{inner_x}" y1="{depth_px}" x2="{inner_x + inner_w}" y2="{depth_px}" '
                f'stroke="{COLOR_ROUTE_LIMIT}" stroke-width="1.2" stroke-dasharray="6,4" />'
            )
            parts.append(
                f'<text x="{inner_x + 6}" y="{depth_px - 4}" font-size="10" fill="{COLOR_ROUTE_LIMIT}">'
                f'editor max route depth ({max_depth} yd)</text>'
            )

    # Defense first (so offense draws on top)
    if defense is not None:
        for d in defense.get("players", []):
            render_defender(d, profile, parts, total_cells)

        # Defensive coverage (zones / man / rush)
        if show in ("defense", "both"):
            responsibilities_by_player = {
                r.get("player"): r for r in defense.get("responsibilities", [])
            }
            for d in defense.get("players", []):
                resp = responsibilities_by_player.get(d.get("label"))
                if resp is None:
                    continue
                role = resp.get("role", "")
                aim = resp.get("aim", "")
                covers_player = resp.get("covers_player")
                render_defender_coverage(
                    d, role, aim, covers_player, formation, profile, parts, total_cells,
                )

    # Offensive routes & paths
    if play is not None and formation is not None and show in ("offense", "both"):
        formation_by_label = {p["label"]: p for p in formation["players"]}
        for assignment in play.get("assignments", []):
            player = formation_by_label.get(assignment["player"])
            if player is None:
                continue
            role = assignment.get("role")

            explicit_path = assignment.get("path")
            if explicit_path:
                waypoints = [(player["x"] + wp[0], player["y"] + wp[1]) for wp in explicit_path]
                position = player.get("position", "")
                if role in ("ball_carrier", "handoff"):
                    render_path(parts, waypoints, profile, total_cells, PRIMARY_READ_COLOR, RUN_PATH_WIDTH, "arrow-primary")
                elif role == "lead_block":
                    render_path(parts, waypoints, profile, total_cells, FB_LEAD_COLOR, LEAD_BLOCK_WIDTH, "arrow-fb")
                elif role == "run_block" and position in INTERIOR_OL:
                    render_path(parts, waypoints, profile, total_cells, PULL_COLOR, LEAD_BLOCK_WIDTH, "arrow-pull")
                elif role == "fake":
                    render_path(parts, waypoints, profile, total_cells, FAKE_PATH_COLOR, FAKE_PATH_WIDTH, "arrow-fake", dashed=True)
                elif role == "pass_block":
                    render_path(parts, waypoints, profile, total_cells, PASS_BLOCK_COLOR, PASS_BLOCK_WIDTH, "arrow-passblock")
                else:
                    render_path(parts, waypoints, profile, total_cells, ROUTE_COLOR, ROUTE_WIDTH, "arrow")

            priority_to_marker = {
                "primary": ("arrow-primary", PRIMARY_READ_COLOR),
                "secondary": ("arrow-secondary", SECONDARY_READ_COLOR),
                "tertiary": ("arrow-tertiary", TERTIARY_READ_COLOR),
                "checkdown": ("arrow-checkdown", CHECKDOWN_COLOR),
            }
            for alt in assignment.get("alt_paths", []):
                alt_marker, alt_color = priority_to_marker.get(
                    alt["priority"], ("arrow", ROUTE_COLOR)
                )
                alt_waypoints = [(player["x"] + wp[0], player["y"] + wp[1]) for wp in alt["path"]]
                render_path(parts, alt_waypoints, profile, total_cells, alt_color, ALT_PATH_WIDTH, alt_marker)

            if role == "route":
                route_name = assignment.get("route_name")
                if not route_name:
                    continue
                route = route_lookup(route_lib or {}, route_name)
                if route is None:
                    warnings.append(f"unknown route '{route_name}' for {assignment['player']}")
                    continue
                path_yd = receiver_route_path(player["x"], player["y"], route)
                label = assignment["player"]
                if label == play.get("primary_read"):
                    color, marker = PRIMARY_READ_COLOR, "arrow-primary"
                elif label == play.get("secondary_read"):
                    color, marker = SECONDARY_READ_COLOR, "arrow-secondary"
                elif label == play.get("tertiary_read"):
                    color, marker = TERTIARY_READ_COLOR, "arrow-tertiary"
                elif label == play.get("checkdown"):
                    color, marker = CHECKDOWN_COLOR, "arrow-checkdown"
                else:
                    color, marker = ROUTE_COLOR, "arrow"
                render_path(parts, path_yd, profile, total_cells, color, ROUTE_WIDTH, marker)

                beats = assignment.get("beats_coverage") or route.get("beats_coverage")
                if beats and len(path_yd) >= 1:
                    last_x, last_y = path_yd[-1]
                    last_gx, last_gy = universal_to_grid(last_x, last_y, profile)
                    last_px, last_py = grid_to_pixel(last_gx, last_gy, profile, total_cells)
                    badge = "M" if beats == "man" else "Z" if beats == "zone" else "M/Z"
                    parts.append(
                        f'<text x="{last_px + 10}" y="{last_py - 4}" '
                        f'font-size="10" fill="white" font-weight="bold" '
                        f'stroke="black" stroke-width="0.4">{badge}</text>'
                    )

    # Offensive players (drawn last, on top)
    if formation is not None:
        for player in formation["players"]:
            gx, gy = player_grid_pos(player, formation, profile)
            px, py = grid_to_pixel(gx, gy, profile, total_cells)

            in_x = 0 <= gx <= width_cells
            in_y_editor = 0 <= gy <= height_cells
            in_bounds = in_x and in_y_editor

            if not in_bounds:
                warnings.append(
                    f"{player['label']} ({player['x']:.1f}, {player['y']:.1f}) "
                    f"outside editor grid (cell {gx:.1f}, {gy:.1f})"
                )

            max_split = limits.get("max_player_split_yd")
            if max_split is not None and abs(player["x"]) > max_split:
                warnings.append(
                    f"{player['label']} split {abs(player['x']):.1f} yd > "
                    f"editor max ({max_split} yd)"
                )
            max_back = limits.get("max_backfield_depth_yd")
            if max_back is not None and player["y"] < -max_back:
                warnings.append(
                    f"{player['label']} backfield depth {abs(player['y']):.1f} yd > "
                    f"editor max ({max_back} yd)"
                )

            ball_carrier = play.get("ball_carrier") if play else None
            primary_read = play.get("primary_read") if play else None
            label = player["label"]
            position = player.get("position", "")
            if not in_bounds:
                fill = COLOR_OUT_OF_BOUNDS
            elif label == "C":
                fill = COLOR_C
            elif label == ball_carrier:
                fill = COLOR_BALL_CARRIER
            elif label == primary_read:
                fill = COLOR_PRIMARY_READ
            else:
                fill = COLOR_OFFENSE

            is_ol = position in INTERIOR_OL
            if is_ol:
                half = PLAYER_SIZE / 2
                parts.append(
                    f'<rect x="{px - half}" y="{py - half}" '
                    f'width="{PLAYER_SIZE}" height="{PLAYER_SIZE}" '
                    f'fill="{fill}" stroke="white" stroke-width="1.5" />'
                )
            else:
                parts.append(
                    f'<circle cx="{px}" cy="{py}" r="{PLAYER_SIZE / 2}" '
                    f'fill="{fill}" stroke="white" stroke-width="1.5" />'
                )

            font_sz = LABEL_FONT_SIZE if len(label) <= 2 else LABEL_FONT_SIZE_LONG
            parts.append(
                f'<text x="{px}" y="{py + 4}" text-anchor="middle" '
                f'font-size="{font_sz}" fill="black" font-weight="bold">'
                f'{label}</text>'
            )

    parts.append('</g>')

    # Legend strip
    legend_y = field_top + field_h
    parts.append(
        f'<rect x="0" y="{legend_y}" width="{total_w}" height="{legend_strip_h}" fill="#0f0f0f" />'
    )
    legend_items = []
    if play and formation and show in ("offense", "both"):
        legend_items += [
            (PRIMARY_READ_COLOR, "1°/run"),
            (SECONDARY_READ_COLOR, "2°"),
            (TERTIARY_READ_COLOR, "3°"),
            (FB_LEAD_COLOR, "FB lead"),
            (PULL_COLOR, "pull"),
            (ROUTE_COLOR, "route"),
        ]
    if defense:
        legend_items.append((COLOR_DEFENSE, "defense"))
        if show in ("defense", "both"):
            legend_items += [
                (COLOR_RUSH, "rush"),
                (COLOR_ZONE, "zone"),
                (COLOR_DEEP_ZONE, "deep zone"),
                (COLOR_MAN, "man"),
                (COLOR_SPY, "spy"),
            ]
    lx = 12
    for color, label in legend_items:
        parts.append(
            f'<rect x="{lx}" y="{legend_y + 7}" width="10" height="10" '
            f'fill="{color}" />'
        )
        parts.append(
            f'<text x="{lx + 14}" y="{legend_y + 16}" font-size="10" fill="#ccc">'
            f'{label}</text>'
        )
        lx += 14 + 10 + len(label) * 6 + 8

    # Warnings strip
    warn_y = legend_y + legend_strip_h
    parts.append(
        f'<rect x="0" y="{warn_y}" width="{total_w}" '
        f'height="{warnings_strip_h}" fill="#1a1a1a" />'
    )
    if warnings:
        parts.append(
            f'<text x="12" y="{warn_y + 18}" font-size="12" fill="#ff8800" '
            f'font-weight="bold">{len(warnings)} warning(s):</text>'
        )
        for i, w in enumerate(warnings[:5]):
            parts.append(
                f'<text x="12" y="{warn_y + 34 + i * 12}" font-size="11" fill="#ddd">'
                f'• {w}</text>'
            )
    else:
        parts.append(
            f'<text x="12" y="{warn_y + 24}" font-size="12" fill="#88dd88">'
            f'OK — all positions within editor limits.</text>'
        )

    parts.append('</svg>')
    return "\n".join(parts), warnings


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "play_id_pos", nargs="?",
        help="Play file stem (positional, optional). Equivalent to --play.",
    )
    parser.add_argument(
        "game_id_pos", nargs="?",
        help="Game directory name (positional, optional). Equivalent to --game.",
    )
    parser.add_argument("--play", help="Offensive play id (alternative to positional).")
    parser.add_argument("--defense", help="Defensive formation id to draw (standalone or with --play).")
    parser.add_argument("--vs", dest="vs_defense", help="Alias for --defense (legacy).")
    parser.add_argument("--game", help="Game profile id (alternative to positional).")
    parser.add_argument(
        "--show",
        choices=["offense", "defense", "both", "none"],
        default="both",
        help="Which side's assignments (routes / coverage) to render. Default: both.",
    )
    parser.add_argument(
        "--field",
        choices=["short", "long"],
        default="long",
        help="Downfield field length: short = LOS+5yd, long = LOS+30yd. Default: long.",
    )
    parser.add_argument("-o", "--output", help="SVG output path (default: stdout)")
    args = parser.parse_args()

    play_id = args.play or args.play_id_pos
    game_id = args.game or args.game_id_pos
    defense_id = args.defense or args.vs_defense

    if not game_id:
        print("error: must provide --game or positional game_id", file=sys.stderr)
        return 2
    if not play_id and not defense_id:
        print("error: must provide at least --play or --defense (or positional play_id)", file=sys.stderr)
        return 2

    profile_path = GAMES_DIR / game_id / "editor-grid.yaml"
    if not profile_path.exists():
        print(f"Game profile not found: {profile_path}", file=sys.stderr)
        return 1
    profile = load_yaml(profile_path)

    play = None
    formation = None
    if play_id:
        play_path = PLAYS_DIR / f"{play_id}.yaml"
        if not play_path.exists():
            print(f"Play not found: {play_path}", file=sys.stderr)
            return 1
        play = load_yaml(play_path)
        formation_path = FORMATIONS_DIR / f"{play['formation']}.yaml"
        if not formation_path.exists():
            print(f"Formation not found: {formation_path}", file=sys.stderr)
            return 1
        formation = load_yaml(formation_path)
        if not defense_id:
            defense_id = play.get("vs_defense")

    defense = None
    if defense_id:
        def_path = FORMATIONS_DIR / f"{defense_id}.yaml"
        if not def_path.exists():
            print(f"Defense not found: {def_path}", file=sys.stderr)
            return 1
        defense = load_yaml(def_path)

    route_lib = load_route_library()
    svg, warnings = render(
        profile,
        play=play,
        formation=formation,
        defense=defense,
        route_lib=route_lib,
        show=args.show,
        field=args.field,
    )

    if args.output:
        out_path = Path(args.output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, "w") as f:
            f.write(svg)
        print(f"Wrote {out_path} ({len(warnings)} warnings)")
    else:
        print(svg)

    if warnings:
        for w in warnings:
            print(f"  WARN: {w}", file=sys.stderr)

    return 0


if __name__ == "__main__":
    sys.exit(main())
