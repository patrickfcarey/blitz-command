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
  --field short            shows LOS + 15 yd downfield (box + deep DBs visible)

Backwards-compatible: old positional form
  draw.py <play-id> <game-id> [--vs <def-id>] -o output.svg
still works.

Module structure
----------------
    1.  Filesystem paths
    2.  Football, layout, style, color and marker constants
    3.  Football-position role sets
    4.  Domain types (TypedDicts describing the YAML schema)
    5.  Text / XML utilities
    6.  YAML loaders
    7.  Hash-spec inference
    8.  Coordinate conversions (universal yards <-> grid cells <-> SVG pixels)
    9.  Cell assignment (tight-cluster snapping + BFS conflict resolution)
    10. Route resolution
    11. SVG primitive emitters (rect / circle / text / line / polyline / ellipse)
    12. Style helpers (read-priority color & marker selection)
    13. Layout dataclass + dimension computation
    14. Component renderers (one function per visual concern)
    15. Top-level render() orchestrator
    16. CLI: argument parsing and main()

Coordinate systems
------------------
The module uses three coordinate spaces.

* **Universal yards** -- real-world football coordinates.
    - Origin: center of the ball at the line of scrimmage.
    - X positive = offensive right.  Y positive = downfield.
    - Units: real yards.  Game-agnostic.

* **Grid cells** -- the target game's editor-grid coordinates.
    - Origin and scale come from `data/games/<id>/editor-grid.yaml`.
    - May be fractional (pre-snap) or integer (after `assign_cells_for_formation`).

* **SVG pixels** -- output image coordinates.
    - Y is inverted (top of SVG = high yards downfield).
    - Margin and per-cell pixel size come from layout constants.
"""
from __future__ import annotations

import argparse
import logging
import math
import subprocess
import sys
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Final, NamedTuple, TypedDict

import yaml


# ============================================================================
# 0. Module identity & logging
# ============================================================================

__version__: Final[str] = "0.3.0"

logger: Final[logging.Logger] = logging.getLogger("draw_play")


def _git_rev() -> str:
    """Best-effort git short rev for the current checkout, or `"unknown"`.

    Cached for the lifetime of the process — git rev cannot change without a
    new module load.  Failures (no git, detached state, network filesystem
    quirks) are swallowed silently because traceability is best-effort.
    """
    global _CACHED_GIT_REV  # noqa: PLW0603 — single-shot module-level cache
    if _CACHED_GIT_REV is not None:
        return _CACHED_GIT_REV
    try:
        result = subprocess.run(
            ["git", "-C", str(Path(__file__).parent), "rev-parse", "--short=10", "HEAD"],
            capture_output=True, text=True, timeout=2.0, check=False,
        )
        if result.returncode == 0 and result.stdout.strip():
            _CACHED_GIT_REV = result.stdout.strip()
            return _CACHED_GIT_REV
    except (OSError, subprocess.SubprocessError):
        pass
    _CACHED_GIT_REV = "unknown"
    return _CACHED_GIT_REV


_CACHED_GIT_REV: str | None = None


# ============================================================================
# 1. Filesystem paths
# ============================================================================

REPO_ROOT: Final[Path] = Path(__file__).resolve().parents[2]
ROUTES_DIR: Final[Path] = REPO_ROOT / "data" / "routes"
FORMATIONS_DIR: Final[Path] = REPO_ROOT / "data" / "formations"
PLAYS_DIR: Final[Path] = REPO_ROOT / "data" / "plays"
GAMES_DIR: Final[Path] = REPO_ROOT / "data" / "games"


# ============================================================================
# 2a. Football constants
# ============================================================================

# Distance from field center to each hash mark, in real yards.
NFL_HASH_DIST_YD: Final[float] = 3.083
NCAA_HASH_DIST_YD: Final[float] = 6.667
HS_HASH_DIST_YD: Final[float] = 8.889

# Off-line player within this many yards of the OL block joins the tight
# cluster (gets a sequential integer cell instead of its raw rounded cell).
CLUSTER_X_TOLERANCE_YD: Final[float] = 3.5

# Off-line player must also be this close to the LOS to count as a tight
# cluster member (so a wing-T WING joins, but a HB in the backfield does not).
TIGHT_CLUSTER_LOS_TOLERANCE_YD: Final[float] = 1.5

# A receiver whose universal X exceeds this magnitude has its route mirrored
# (a slant from the right side breaks left, etc.). Threshold is a small
# epsilon, not zero, so a TE on the +0.0 yard line is not mirrored.
ROUTE_MIRROR_X_THRESHOLD_YD: Final[float] = 0.1


# ============================================================================
# 2b. Cell-assignment (BFS conflict resolution)
# ============================================================================

# Maximum BFS ring radius when searching for a free cell.  Far larger than
# any plausible editor grid; in practice the search exits within 1-2 rings.
BFS_MAX_RINGS: Final[int] = 25

# Cost multiplier on the row delta during BFS scoring.  Same-row bumps cost
# only |delta_x|; vertical bumps cost 2x |delta_x|.  This biases the resolver
# toward sliding sideways before pushing into adjacent rows.
BFS_VERTICAL_BIAS: Final[int] = 2

# Penalty added to BFS score when a candidate cell is on the wrong side of
# the LOS for the player's side (e.g., bumping a defender below the LOS).
BFS_LOS_CROSS_PENALTY: Final[int] = 10


# ============================================================================
# 2c. Layout constants (pixels & yards)
# ============================================================================

PIXELS_PER_CELL: Final[int] = 32

# Player marker dimensions.  10 px gap between adjacent-cell markers keeps
# the editor-grid look readable.
OFFENSE_MARKER_SIZE_PX: Final[int] = 22
DEFENSE_MARKER_SIZE_PX: Final[int] = 20

# Margin between the SVG edge and the playable field area.
FIELD_MARGIN_PX: Final[int] = 40

# How much extra field is shown above the editor's top edge (in real yards).
# 'long' makes deep routes visible; 'short' is enough for box + deep DBs.
FIELD_LONG_EXTRA_YD: Final[int] = 30
FIELD_SHORT_EXTRA_YD: Final[int] = 15

# Cadence of major grid lines and yard markers.
MAJOR_GRID_INTERVAL_CELLS: Final[int] = 5
YARD_MARKER_INTERVAL_YD: Final[int] = 5

# Hash-mark tick geometry.
HASH_TICK_HALF_WIDTH_PX: Final[int] = 4
HASH_MAJOR_EXTRA_HALF_PX: Final[int] = 1  # major (every 5 yd) ticks are 1 px wider on each side

# Chrome strips around the field.
TITLE_STRIP_HEIGHT_PX: Final[int] = 50
WARNINGS_STRIP_HEIGHT_PX: Final[int] = 80
LEGEND_STRIP_HEIGHT_PX: Final[int] = 22

# Maximum number of warnings rendered in the warnings strip; the rest are silent.
MAX_WARNINGS_DISPLAYED: Final[int] = 5

# Title-strip text positions (px from top-left of the strip).
TITLE_TEXT_X_PX: Final[int] = 12
TITLE_TEXT_Y_PX: Final[int] = 22
SUBTITLE_TEXT_Y_PX: Final[int] = 40

# Editor-region tag positions ("downfield (off-editor)", "editor grid").
TAG_TEXT_OFFSET_X_PX: Final[int] = 6
TAG_TEXT_OFFSET_Y_PX: Final[int] = 12

# Axis label positions.
AXIS_LABEL_X_OFFSET_PX: Final[int] = 8     # left margin for Y-axis labels
AXIS_LABEL_Y_OFFSET_PX: Final[int] = 14    # bottom margin for X-axis labels
AXIS_LABEL_Y_TEXT_NUDGE_PX: Final[int] = 3 # vertical baseline nudge

# Warnings strip text positions.
WARNING_HEADER_X_PX: Final[int] = 12
WARNING_HEADER_Y_PX: Final[int] = 18
WARNING_BODY_LINE_HEIGHT_PX: Final[int] = 12
WARNING_BODY_FIRST_Y_PX: Final[int] = 34
NO_WARNING_Y_PX: Final[int] = 24

# Read-priority badge geometry.
BADGE_HEIGHT_PX: Final[int] = 11
BADGE_CHAR_WIDTH_PX: Final[int] = 6
BADGE_HORIZONTAL_PAD_PX: Final[int] = 4

# Beats-coverage badge offsets (small "M"/"Z" letter near the route's tip).
BEAT_BADGE_OFFSET_X_PX: Final[int] = 10
BEAT_BADGE_OFFSET_Y_PX: Final[int] = 4

# Player-label vertical offset (centers text inside the marker).
PLAYER_LABEL_Y_OFFSET_PX: Final[int] = 4

# Legend item spacing.
LEGEND_START_X_PX: Final[int] = 12
LEGEND_SWATCH_SIZE_PX: Final[int] = 10
LEGEND_SWATCH_Y_OFFSET_PX: Final[int] = 7
LEGEND_TEXT_Y_OFFSET_PX: Final[int] = 16
LEGEND_TEXT_X_GAP_PX: Final[int] = 14
LEGEND_ITEM_END_PAD_PX: Final[int] = 8
LEGEND_TEXT_CHAR_WIDTH_PX: Final[int] = 6

# A zone arrow is only drawn from defender to drop point if the offset is
# at least this large; smaller offsets would render as a meaningless dot.
ZONE_ARROW_MIN_OFFSET_YD: Final[float] = 0.5

# LOS label positioning (relative to the right edge of the editor).
LOS_LABEL_RIGHT_PAD_PX: Final[int] = 6
LOS_LABEL_Y_OFFSET_PX: Final[int] = 6

# Depth-limit annotation offset.
DEPTH_LIMIT_LABEL_X_PX: Final[int] = 6
DEPTH_LIMIT_LABEL_Y_PX: Final[int] = 4


# ============================================================================
# 2d. Coaching-notes layout
# ============================================================================

NOTES_LINE_HEIGHT_PX: Final[int] = 15
NOTES_VERTICAL_PAD_PX: Final[int] = 8
NOTES_HEADER_HEIGHT_PX: Final[int] = 22
NOTES_LEFT_PAD_PX: Final[int] = 14
NOTES_RIGHT_PAD_PX: Final[int] = 16
NOTES_INDENT_PX: Final[int] = 14
NOTES_HEADER_TEXT_Y_PX: Final[int] = 15
NOTES_DIVIDER_Y_PX: Final[int] = 19

# Empirical average glyph width for the monospace font used in notes.
# Used to soft-wrap long passages.  Adjust if the font is changed.
NOTES_AVG_CHAR_WIDTH_PX: Final[float] = 6.6


# ============================================================================
# 2e. Font sizes (px)
# ============================================================================

FONT_TITLE: Final[int] = 16
FONT_SUBTITLE: Final[int] = 12
FONT_LABEL: Final[int] = 11
FONT_LABEL_LONG: Final[int] = 9       # used for labels longer than 2 chars
FONT_AXIS: Final[int] = 10
FONT_LEGEND: Final[int] = 10
FONT_AREA_TAG: Final[int] = 9
FONT_DEPTH_LIMIT: Final[int] = 10
FONT_WARNING_HEADER: Final[int] = 12
FONT_WARNING_BODY: Final[int] = 11
FONT_NOTES: Final[int] = 11
FONT_BADGE: Final[int] = 9
FONT_BEAT_BADGE: Final[int] = 10
FONT_LOS_LABEL: Final[int] = 11


# ============================================================================
# 2f. Stroke widths
# ============================================================================

STROKE_ROUTE: Final[float] = 3.0
STROKE_ROUTE_PRIMARY: Final[float] = 4.0
STROKE_RUN_PATH: Final[float] = 4.0
STROKE_ALT_PATH: Final[float] = 2.5
STROKE_LEAD_BLOCK: Final[float] = 3.0
STROKE_PASS_BLOCK: Final[float] = 2.0
STROKE_FAKE_PATH: Final[float] = 2.5
STROKE_COVERAGE: Final[float] = 2.5

# Zone arrows are slightly thinner than other coverage lines.
STROKE_ZONE_ARROW_FACTOR: Final[float] = 0.8

STROKE_GRID_MAJOR: Final[float] = 0.7
STROKE_GRID_FINE: Final[float] = 0.4
STROKE_GRID_MAJOR_EXT: Final[float] = 0.5
STROKE_GRID_FINE_EXT: Final[float] = 0.3
STROKE_EDITOR_BOUNDARY: Final[int] = 2
STROKE_LOS: Final[float] = 2.5
STROKE_DEPTH_LIMIT: Final[float] = 1.2
STROKE_PLAYER_BORDER: Final[float] = 1.5
STROKE_DEFENDER_BORDER: Final[int] = 1
STROKE_YARD_LINE: Final[float] = 0.6
STROKE_HASH_MAJOR: Final[float] = 1.4
STROKE_HASH_MINOR: Final[float] = 1.0
STROKE_MAN_RING: Final[float] = 1.5
STROKE_SPY_RING: Final[float] = 1.5
STROKE_ZONE_OUTLINE: Final[int] = 1
STROKE_NOTES_DIVIDER: Final[int] = 1
STROKE_BADGE_BORDER: Final[float] = 0.5
STROKE_BEAT_BADGE_OUTLINE: Final[float] = 0.4


# ============================================================================
# 2g. Opacities
# ============================================================================

OPACITY_ZONE_FILL: Final[float] = 0.15
OPACITY_DEFENDER_FILL: Final[float] = 0.85
OPACITY_HASH_MAJOR: Final[float] = 0.85
OPACITY_HASH_MINOR: Final[float] = 0.55


# ============================================================================
# 2h. Defensive-coverage geometry (yards)
# ============================================================================

# Rush arrow extends this far into the offensive backfield.
RUSH_ARROW_DEPTH_YD: Final[float] = 4.0

# Deep zone: drop point pushed at least this deep, with extra push above
# the defender's pre-snap depth.
DEEP_ZONE_MIN_DEPTH_YD: Final[float] = 12.0
DEEP_ZONE_PUSH_YD: Final[float] = 3.0
DEEP_ZONE_RX_YD: Final[float] = 6.0
DEEP_ZONE_RY_YD: Final[float] = 5.0

# Flat zone: drop point pushed sideways toward the boundary; depth pulled to LOS.
FLAT_ZONE_PUSH_YD: Final[float] = 4.0
FLAT_ZONE_DROP_BACK_YD: Final[float] = 1.0  # subtracted from defender depth
FLAT_ZONE_MIN_DEPTH_YD: Final[float] = 2.0
FLAT_ZONE_RX_YD: Final[float] = 4.0
FLAT_ZONE_RY_YD: Final[float] = 2.0

# Hook / curl / underneath / etc -- moderate depth drop, smaller radius.
HOOK_ZONE_PUSH_YD: Final[float] = 2.0
HOOK_ZONE_MIN_DEPTH_YD: Final[float] = 6.0
HOOK_ZONE_RX_YD: Final[float] = 3.5
HOOK_ZONE_RY_YD: Final[float] = 2.5

# Generic zone fallback (any zone role not matched above).
DEFAULT_ZONE_PUSH_YD: Final[float] = 2.0
DEFAULT_ZONE_RX_YD: Final[float] = 3.0
DEFAULT_ZONE_RY_YD: Final[float] = 2.0

# Ring around man-coverage and spy defenders (multiplied by DEFENSE_MARKER_SIZE_PX).
MAN_RING_RADIUS_FACTOR: Final[float] = 0.85
SPY_RING_RADIUS_FACTOR: Final[float] = 1.2


# ============================================================================
# 2i. Color palette  (print-first: white field, high-contrast ink)
# ============================================================================

# -- Offensive route colors (read priority) --
COLOR_ROUTE: Final[str] = "#0057B8"           # dark blue  (generic route)
COLOR_PRIMARY_READ: Final[str] = "#0057B8"    # dark blue  (1st read)
COLOR_SECONDARY_READ: Final[str] = "#D55E00"  # burnt orange (2nd read)
COLOR_TERTIARY_READ: Final[str] = "#7A3E9D"   # dark purple  (3rd read)
COLOR_CHECKDOWN: Final[str] = "#007A3D"       # dark green   (checkdown)
COLOR_QUATERNARY_READ: Final[str] = "#555555" # dark gray    (4th)
COLOR_FALLBACK_READ: Final[str] = "#777777"   # medium gray  (fallback)

# -- Run-game / blocking colors --
COLOR_FB_LEAD: Final[str] = "#B00020"   # dark red
COLOR_PULL: Final[str] = "#007A3D"      # dark green
COLOR_PASS_BLOCK: Final[str] = "#555555"
COLOR_FAKE_PATH: Final[str] = "#888888"

# -- Field / chrome (white background, subdued grid) --
COLOR_BG_OUTER: Final[str] = "#F0F0F0"         # outer frame / chrome strips
COLOR_BG_INNER: Final[str] = "#FFFFFF"          # editor sub-region (white paper)
COLOR_BG_EXTENSION: Final[str] = "#F8F8F8"      # downfield extension (near-white)
COLOR_GRID_FINE: Final[str] = "#E2E2E2"         # minor grid lines
COLOR_GRID_FINE_EXT: Final[str] = "#EBEBEB"     # minor grid in extension
COLOR_GRID_MAJOR: Final[str] = "#B5B5B5"        # major grid lines
COLOR_GRID_BOUNDARY: Final[str] = "#111111"     # editor boundary border
COLOR_LOS: Final[str] = "#111111"               # line of scrimmage (bold black)
COLOR_ROUTE_LIMIT: Final[str] = "#B00020"       # max-route-depth ceiling
COLOR_YARD_LINE: Final[str] = "#B5B5B5"         # 5-yd tick lines in extension
COLOR_HASH: Final[str] = "#999999"              # hash-mark ticks

# -- Players --
COLOR_OFFENSE: Final[str] = "#FFFFFF"               # normal player: white fill
COLOR_C: Final[str] = "#003A66"                     # center: dark navy (key)
COLOR_BALL_CARRIER: Final[str] = "#003A66"          # ball carrier: dark navy (key)
COLOR_PRIMARY_READ_PLAYER: Final[str] = "#003A66"   # primary read: dark navy (key)
COLOR_KEY_PLAYER_TEXT: Final[str] = "#FFFFFF"       # label on dark-fill key players
COLOR_OUT_OF_BOUNDS: Final[str] = "#B00020"         # dark red for out-of-bounds
COLOR_DEFENSE: Final[str] = "#CCCCCC"               # default defender fill (light gray)
COLOR_DEFENSE_DL: Final[str] = "#999999"            # DL fill (darker gray)
COLOR_DEFENSE_DEEP: Final[str] = "#DDDDDD"          # safety fill (lighter gray)

# -- Defensive coverage --
COLOR_RUSH: Final[str] = "#B00020"   # dark red
COLOR_BLITZ: Final[str] = "#7A0010"  # deeper red
COLOR_ZONE: Final[str] = "#0057B8"   # dark blue
COLOR_DEEP_ZONE: Final[str] = "#7A3E9D"  # dark purple
COLOR_MAN: Final[str] = "#D55E00"    # burnt orange
COLOR_SPY: Final[str] = "#007A3D"    # dark green

# -- Text & chrome accents --
COLOR_TEXT_PRIMARY: Final[str] = "#111111"   # dark ink (default text + borders)
COLOR_TEXT_SECONDARY: Final[str] = "#444444"
COLOR_TEXT_MUTED: Final[str] = "#666666"
COLOR_TEXT_DIM: Final[str] = "#999999"
COLOR_TEXT_LIGHT: Final[str] = "#111111"     # legend text on light-gray strip
COLOR_TEXT_DARK: Final[str] = "black"
COLOR_LEGEND_BG: Final[str] = "#F0F0F0"     # light legend strip
COLOR_WARNING: Final[str] = "#996600"        # amber warning text on light bg
COLOR_WARNING_BODY: Final[str] = "#333333"
COLOR_OK: Final[str] = "#006600"             # dark green "OK" on light bg

# -- Coaching-notes box --
COLOR_NOTES_BG: Final[str] = "#F5F5F5"
COLOR_NOTES_HEADER: Final[str] = "#111111"
COLOR_NOTES_DIVIDER: Final[str] = "#CCCCCC"
COLOR_NOTES_BODY: Final[str] = "#333333"
COLOR_NOTES_CUE: Final[str] = "#555555"
COLOR_NOTES_RAW: Final[str] = "#444444"


# ============================================================================
# 2j. SVG marker IDs (arrow-head <marker> def references)
# ============================================================================

MARKER_ARROW: Final[str] = "arrow"
MARKER_PRIMARY: Final[str] = "arrow-primary"
MARKER_SECONDARY: Final[str] = "arrow-secondary"
MARKER_TERTIARY: Final[str] = "arrow-tertiary"
MARKER_CHECKDOWN: Final[str] = "arrow-checkdown"
MARKER_FAKE: Final[str] = "arrow-fake"
MARKER_FB_LEAD: Final[str] = "arrow-fb"
MARKER_PULL: Final[str] = "arrow-pull"
MARKER_PASS_BLOCK: Final[str] = "arrow-passblock"
MARKER_RUSH: Final[str] = "arrow-rush"
MARKER_ZONE: Final[str] = "arrow-zone"
MARKER_MAN: Final[str] = "arrow-man"


# ============================================================================
# 3a. String enums (canonical list of every role / mode / side / play type)
# ============================================================================
#
# Every enum below subclasses `(str, Enum)` so members hash and compare equal
# to their underlying string values.  This means:
#
#   * Existing code that compares `role == "ball_carrier"` continues to work
#     after a literal is replaced with `AssignmentRole.BALL_CARRIER`.
#   * YAML files keep using bare strings; the loader returns strings; the
#     renderer compares those strings against enum members without needing a
#     conversion step.
#   * The frozensets below (`ZONE_ROLES`, etc.) can be built from the enum
#     directly, so adding a new member is a one-line change in one place.
#
# To add a new role: add the member here and (if needed) add it to the
# matching category frozenset in section 3b.

class Show(str, Enum):
    """Which side's assignments to render in `render(show=...)`."""
    OFFENSE = "offense"
    DEFENSE = "defense"
    BOTH = "both"
    NONE = "none"


class Field(str, Enum):
    """Downfield viewing length in `render(field=...)`."""
    LONG = "long"
    SHORT = "short"


class Side(str, Enum):
    """Which side of the ball a formation belongs to."""
    OFFENSE = "offense"
    DEFENSE = "defense"


class PlayType(str, Enum):
    """Top-level play classification."""
    RUN = "run"
    PASS = "pass"
    PLAY_ACTION = "play-action"


class AssignmentRole(str, Enum):
    """An offensive player's role within a play."""
    ROUTE = "route"
    BALL_CARRIER = "ball_carrier"
    HANDOFF = "handoff"
    LEAD_BLOCK = "lead_block"
    RUN_BLOCK = "run_block"
    PASS_BLOCK = "pass_block"
    FAKE = "fake"


class CoverageRole(str, Enum):
    """A defender's coverage assignment within a play."""
    # --- Rush family ---
    RUSH = "rush"
    BLITZ = "blitz"
    # --- Man family ---
    MAN = "man"
    PRESS_MAN = "press-man"
    OFF_MAN = "off-man"
    # --- Spy family ---
    SPY = "spy"
    QB_SPY = "qb-spy"
    ROBBER = "robber"
    # --- Zone family ---
    HOOK = "hook"
    CURL = "curl"
    FLAT = "flat"
    DEEP_ZONE = "deep-zone"
    UNDERNEATH_ZONE = "underneath-zone"
    BUZZ = "buzz"
    RAT = "rat"
    LURK = "lurk"
    CARRY = "carry"


class BeatsCoverage(str, Enum):
    """Coverage type a route is designed to defeat (drives the M / Z / M-Z badge)."""
    MAN = "man"
    ZONE = "zone"
    ANY = "any"


# ============================================================================
# 3b. Football-position + role categorization sets
# ============================================================================
#
# Position sets stay as bare-string frozensets because positions come from
# the formation YAML and aren't an enum domain (every league has a slightly
# different position vocabulary).
#
# Role-category sets are derived from `CoverageRole` so adding a new zone
# variant in the enum + the relevant category set below covers every
# rendering branch.

INTERIOR_OL: Final[frozenset[str]] = frozenset({"LT", "LG", "C", "RG", "RT"})
DEFENSIVE_DL: Final[frozenset[str]] = frozenset({"DE", "DT", "NT"})

RUSH_ROLES: Final[frozenset[str]] = frozenset({
    CoverageRole.RUSH, CoverageRole.BLITZ,
})
MAN_ROLES: Final[frozenset[str]] = frozenset({
    CoverageRole.MAN, CoverageRole.PRESS_MAN, CoverageRole.OFF_MAN,
})
SPY_ROLES: Final[frozenset[str]] = frozenset({
    CoverageRole.SPY, CoverageRole.QB_SPY, CoverageRole.ROBBER,
})
ZONE_ROLES: Final[frozenset[str]] = frozenset({
    CoverageRole.HOOK, CoverageRole.CURL, CoverageRole.FLAT,
    CoverageRole.DEEP_ZONE, CoverageRole.UNDERNEATH_ZONE,
    CoverageRole.BUZZ, CoverageRole.RAT, CoverageRole.LURK, CoverageRole.CARRY,
})
HOOK_LIKE_ROLES: Final[frozenset[str]] = frozenset({
    CoverageRole.HOOK, CoverageRole.CURL, CoverageRole.UNDERNEATH_ZONE,
    CoverageRole.BUZZ, CoverageRole.RAT, CoverageRole.LURK, CoverageRole.CARRY,
})


# ============================================================================
# 4. Domain types (TypedDicts describing the YAML schema)
# ============================================================================

class GridSpec(TypedDict):
    """Editor-grid dimensions and origin (in cells)."""
    width: int
    height: int
    origin: dict


class ScaleSpec(TypedDict):
    """Yards per editor-grid cell along each axis."""
    x_yards_per_cell: float
    y_yards_per_cell: float


class GameProfile(TypedDict, total=False):
    """A single game's editor-grid profile (`data/games/<id>/editor-grid.yaml`)."""
    game_id: str
    grid: GridSpec
    scale: ScaleSpec
    snap_to_cells: bool
    hash_marks_yd_from_center: float
    limits: dict


class Player(TypedDict, total=False):
    """A single player in a formation."""
    label: str
    position: str
    x: float
    y: float
    on_line: bool


class Formation(TypedDict, total=False):
    """A pre-snap formation (offensive or defensive)."""
    name: str
    side: str  # "offense" | "defense"
    players: list[Player]
    responsibilities: list[dict]  # defense only


class Assignment(TypedDict, total=False):
    """A single player's assignment within a play."""
    player: str
    role: str
    route_name: str
    path: list[list[float]]
    alt_paths: list[dict]
    blocking_scheme: str
    beats_coverage: str


class Play(TypedDict, total=False):
    """An offensive play (`data/plays/<id>.yaml`)."""
    play_id: str
    name: str
    play_type: str
    formation: str
    ball_carrier: str
    primary_read: str
    secondary_read: str
    tertiary_read: str
    checkdown: str
    assignments: list[Assignment]
    run_reads: list[dict]
    notes: str
    vs_defense: str


class Route(TypedDict, total=False):
    """A reusable route shape (`data/routes/*.yaml`)."""
    name: str
    aliases: list[str]
    path: list[list[float]]
    beats_coverage: str


# Convenience aliases used in type hints below.
RouteLibrary = dict[str, Route]
Cell = tuple[int, int]
PointYd = tuple[float, float]
PointPx = tuple[float, float]


# ============================================================================
# 4b. Exception hierarchy
# ============================================================================

class DrawError(Exception):
    """Base class for every error raised by this module.

    Catching `DrawError` in CLI / API integration code catches every
    structured failure produced by the renderer (invalid input, exhausted
    cell assignment, malformed configuration) without swallowing unrelated
    Python exceptions.
    """


class InvalidProfileError(DrawError):
    """A `GameProfile` is missing a required field, has wrong types, or
    contains a non-positive scale / dimension."""


class InvalidPlayError(DrawError):
    """A `Play` is missing a required field or has a malformed assignment."""


class InvalidFormationError(DrawError):
    """A `Formation` is missing the players list, has duplicate labels, or
    has a non-finite player coordinate."""


class InvalidRouteError(DrawError):
    """A `Route` is missing a path or has a malformed waypoint list."""


class CellAssignmentError(DrawError):
    """The BFS conflict resolver could not place a player within
    `BFS_MAX_RINGS` rings of its preferred cell.  Indicates a profile / formation
    pair the renderer cannot lay out (e.g., 12 players on a 10-cell grid)."""


class ConfigError(DrawError):
    """A YAML config file is unreadable, malformed, or empty when content
    was expected."""


# ============================================================================
# 4c. Validators
# ============================================================================
#
# The validators below run at every public entry point (render(), CLI, MCP-
# facing helpers) to catch malformed inputs at the boundary rather than
# crashing partway through rendering with a KeyError or ZeroDivisionError.
#
# All validators are idempotent: calling them twice on the same input is
# safe.  After validation, internal helpers may rely on subscript access
# (e.g. `profile["grid"]["origin"]["x"]`) without further defensive checks.

# Validator membership tests derive their canonical lists from the enums
# defined in section 3a, so adding a new variant is a single-place change.
_VALID_SHOW_VALUES: Final[frozenset[str]] = frozenset(Show)
_VALID_FIELD_VALUES: Final[frozenset[str]] = frozenset(Field)
_VALID_FORMATION_SIDES: Final[frozenset[str]] = frozenset(Side)

# Maximum sensible counts — used as upper bounds in validators so resource
# consumption is provably bounded (Power of 10 rule 2).
_MAX_PLAYERS_PER_FORMATION: Final[int] = 22  # accommodates 11-on-11 plus a small buffer
_MAX_ASSIGNMENTS_PER_PLAY: Final[int] = 22
_MAX_WAYPOINTS_PER_ROUTE: Final[int] = 32


def _require_positive_number(value: object, label: str, exc_type: type[DrawError]) -> None:
    """Raise `exc_type` unless `value` is a finite, strictly-positive number."""
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise exc_type(f"{label} must be a number, got {type(value).__name__}")
    if not math.isfinite(value):
        raise exc_type(f"{label} must be finite, got {value!r}")
    if value <= 0:
        raise exc_type(f"{label} must be positive, got {value!r}")


def _require_finite_number(value: object, label: str, exc_type: type[DrawError]) -> None:
    """Raise `exc_type` unless `value` is a finite number (zero/negative permitted)."""
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise exc_type(f"{label} must be a number, got {type(value).__name__}")
    if not math.isfinite(value):
        raise exc_type(f"{label} must be finite, got {value!r}")


def _validate_profile(profile: object) -> None:
    """Validate that a game profile has every required field with valid values.

    Args:
        profile: Parsed YAML dict (may be malformed; that's what we're checking).

    Raises:
        InvalidProfileError: Any required field is missing, has the wrong type,
            or has a non-positive numeric value.
    """
    if not isinstance(profile, dict):
        raise InvalidProfileError(
            f"profile must be dict, got {type(profile).__name__}"
        )
    if not profile.get("game_id"):
        raise InvalidProfileError("profile missing required 'game_id'")

    grid = profile.get("grid")
    if not isinstance(grid, dict):
        raise InvalidProfileError("profile missing or invalid 'grid'")
    for key in ("origin", "width", "height"):
        if key not in grid:
            raise InvalidProfileError(f"profile.grid missing '{key}'")
    if not (isinstance(grid["width"], int) and grid["width"] > 0):
        raise InvalidProfileError(
            f"profile.grid.width must be positive int, got {grid['width']!r}"
        )
    if not (isinstance(grid["height"], int) and grid["height"] > 0):
        raise InvalidProfileError(
            f"profile.grid.height must be positive int, got {grid['height']!r}"
        )

    origin = grid["origin"]
    if not isinstance(origin, dict) or "x" not in origin or "y" not in origin:
        raise InvalidProfileError("profile.grid.origin must have 'x' and 'y'")
    for axis in ("x", "y"):
        if not isinstance(origin[axis], int):
            raise InvalidProfileError(
                f"profile.grid.origin.{axis} must be int, got {origin[axis]!r}"
            )

    scale = profile.get("scale")
    if not isinstance(scale, dict):
        raise InvalidProfileError("profile missing or invalid 'scale'")
    for axis in ("x_yards_per_cell", "y_yards_per_cell"):
        if axis not in scale:
            raise InvalidProfileError(f"profile.scale missing '{axis}'")
        _require_positive_number(scale[axis], f"profile.scale.{axis}", InvalidProfileError)


def _validate_formation(formation: object, kind: str = "formation") -> None:
    """Validate a formation (offensive or defensive).

    Args:
        formation: Parsed dict to validate.
        kind: Human-readable label used in error messages ("offense" / "defense").

    Raises:
        InvalidFormationError: Missing players list, duplicate labels, or any
            player has a non-finite coordinate / missing required field.
    """
    if not isinstance(formation, dict):
        raise InvalidFormationError(
            f"{kind} must be dict, got {type(formation).__name__}"
        )
    side = formation.get("side")
    if side is not None and side not in _VALID_FORMATION_SIDES:
        raise InvalidFormationError(
            f"{kind}.side must be one of {sorted(_VALID_FORMATION_SIDES)}, got {side!r}"
        )

    players = formation.get("players")
    if not isinstance(players, list):
        raise InvalidFormationError(f"{kind} missing 'players' list")
    if len(players) > _MAX_PLAYERS_PER_FORMATION:
        raise InvalidFormationError(
            f"{kind} has {len(players)} players (max {_MAX_PLAYERS_PER_FORMATION})"
        )

    seen_labels: set[str] = set()
    for index, player in enumerate(players):
        if not isinstance(player, dict):
            raise InvalidFormationError(f"{kind}.players[{index}] must be dict")
        for required in ("label", "x", "y"):
            if required not in player:
                raise InvalidFormationError(
                    f"{kind}.players[{index}] missing '{required}'"
                )
        label = player["label"]
        if not isinstance(label, str) or not label:
            raise InvalidFormationError(
                f"{kind}.players[{index}].label must be non-empty string"
            )
        if label in seen_labels:
            raise InvalidFormationError(
                f"{kind}.players: duplicate label {label!r}"
            )
        seen_labels.add(label)
        for axis in ("x", "y"):
            _require_finite_number(
                player[axis], f"{kind}.players[{index}].{axis}", InvalidFormationError,
            )


def _validate_play(play: object) -> None:
    """Validate a play.

    Raises:
        InvalidPlayError: Missing top-level field, malformed assignment list,
            or an assignment without a player label.
    """
    if not isinstance(play, dict):
        raise InvalidPlayError(f"play must be dict, got {type(play).__name__}")
    for required in ("name", "play_type", "formation"):
        if required not in play:
            raise InvalidPlayError(f"play missing '{required}'")
    assignments = play.get("assignments", [])
    if not isinstance(assignments, list):
        raise InvalidPlayError("play.assignments must be a list")
    if len(assignments) > _MAX_ASSIGNMENTS_PER_PLAY:
        raise InvalidPlayError(
            f"play has {len(assignments)} assignments "
            f"(max {_MAX_ASSIGNMENTS_PER_PLAY})"
        )
    for index, assignment in enumerate(assignments):
        if not isinstance(assignment, dict):
            raise InvalidPlayError(f"play.assignments[{index}] must be dict")
        if "player" not in assignment or not assignment["player"]:
            raise InvalidPlayError(
                f"play.assignments[{index}] missing 'player' label"
            )


def _validate_route(route: object, name: str = "<unnamed>") -> None:
    """Validate a route definition.

    Args:
        route: Parsed dict to check.
        name: Route name used in error messages.

    Raises:
        InvalidRouteError: Missing path, non-list path, or malformed waypoint.
    """
    if not isinstance(route, dict):
        raise InvalidRouteError(f"route {name!r} must be dict")
    path = route.get("path")
    if not isinstance(path, list):
        raise InvalidRouteError(f"route {name!r} missing 'path' list")
    if len(path) > _MAX_WAYPOINTS_PER_ROUTE:
        raise InvalidRouteError(
            f"route {name!r} has {len(path)} waypoints "
            f"(max {_MAX_WAYPOINTS_PER_ROUTE})"
        )
    for index, waypoint in enumerate(path):
        if not isinstance(waypoint, (list, tuple)) or len(waypoint) != 2:
            raise InvalidRouteError(
                f"route {name!r}.path[{index}] must be [dx, dy] pair"
            )
        for axis_index, axis_label in enumerate(("dx", "dy")):
            _require_finite_number(
                waypoint[axis_index],
                f"route {name!r}.path[{index}].{axis_label}",
                InvalidRouteError,
            )


def _validate_show(show: str) -> None:
    """Raise ValueError if `show` is not one of the allowed enum values."""
    if show not in _VALID_SHOW_VALUES:
        raise ValueError(
            f"show must be one of {sorted(_VALID_SHOW_VALUES)}, got {show!r}"
        )


def _validate_field(field: str) -> None:
    """Raise ValueError if `field` is not one of the allowed enum values."""
    if field not in _VALID_FIELD_VALUES:
        raise ValueError(
            f"field must be one of {sorted(_VALID_FIELD_VALUES)}, got {field!r}"
        )


# ============================================================================
# 5. Text & XML utilities
# ============================================================================

def xml_escape(text: str) -> str:
    """Escape the five XML metacharacters so `text` is safe inside SVG element bodies.

    Note: this only escapes element-content metacharacters (`&`, `<`, `>`).
    For attribute values, callers should additionally escape quotes; in
    practice this module only emits attribute values that we control, so
    quote-escaping is unnecessary.
    """
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def wrap_text(text: str, max_chars: int, indent: str = "") -> list[str]:
    """Soft-wrap `text` so no line exceeds `max_chars` characters.

    Args:
        text: Free-form string with whitespace-separated words.
        max_chars: Maximum line length (in characters).  Must be positive.
        indent: Prefix added to every line after the first.

    Returns:
        List of wrapped lines.  Returns `[""]` for empty input so callers can
        always treat the result as a non-empty list.
    """
    assert max_chars > 0, f"wrap_text: max_chars must be positive, got {max_chars}"
    assert isinstance(indent, str), f"wrap_text: indent must be str, got {type(indent).__name__}"
    words = text.split()
    lines: list[str] = []
    current = ""
    for word in words:
        candidate = (current + " " + word).lstrip() if current else word
        if len(candidate) <= max_chars:
            current = candidate
            continue
        if current:
            lines.append(current)
        current = indent + word
    if current:
        lines.append(current)
    result = lines or [""]
    assert len(result) >= 1, "wrap_text postcondition: result is never empty"
    return result


# ============================================================================
# 6. YAML loaders
# ============================================================================

def load_yaml(path: Path) -> dict:
    """Load and parse a YAML file.

    Args:
        path: Absolute or working-directory-relative path.

    Returns:
        Parsed YAML as a dict.  An empty file returns an empty dict (this is
        the only case where the original file content is ambiguous; callers
        that require non-empty content should validate the result).

    Raises:
        FileNotFoundError: File does not exist (re-raised unchanged so callers
            can decide whether the missing file is fatal or expected).
        ConfigError: File exists but is unreadable, malformed YAML, or contains
            a top-level value that isn't a mapping.
    """
    assert isinstance(path, Path), f"load_yaml: path must be Path, got {type(path).__name__}"
    try:
        with open(path, encoding="utf-8") as f:
            data = yaml.safe_load(f)
    except yaml.YAMLError as exc:
        raise ConfigError(f"malformed YAML in {path}: {exc}") from exc
    except OSError as exc:
        if isinstance(exc, FileNotFoundError):
            raise
        raise ConfigError(f"cannot read {path}: {exc}") from exc
    if data is None:
        return {}
    if not isinstance(data, dict):
        raise ConfigError(
            f"{path}: top-level YAML value must be a mapping, got {type(data).__name__}"
        )
    return data


def load_route_library() -> RouteLibrary:
    """Load every route definition under `data/routes/` and index by name + alias.

    Skips files that don't have a `name` field (silently — those files are
    not malformed, just incomplete; they may be templates or stubs).  Files
    that do have a name are validated; an invalid path raises
    `InvalidRouteError`.

    Returns:
        Dict mapping route names (and each route's aliases) to the parsed route
        definition.  A single route may appear under multiple keys.

    Raises:
        InvalidRouteError: A route file has a `name` but a malformed `path`.
        ConfigError: A route file is unreadable or contains invalid YAML.
    """
    by_name: RouteLibrary = {}
    for path in sorted(ROUTES_DIR.glob("*.yaml")):
        route: Route = load_yaml(path)  # type: ignore[assignment]
        name = route.get("name")
        if not name:
            continue
        _validate_route(route, name=name)
        by_name[name] = route
        for alias in route.get("aliases", []):
            if not isinstance(alias, str):
                raise InvalidRouteError(
                    f"route {name!r} has non-string alias {alias!r}"
                )
            by_name[alias] = route
    return by_name


# ============================================================================
# 7. Hash-spec inference
# ============================================================================

def hash_spec_for_profile(profile: GameProfile) -> tuple[float, float] | None:
    """Return `(left_x_yd, right_x_yd)` hash-mark positions in universal yards.

    Reads `hash_marks_yd_from_center` from the profile if present.  Otherwise
    falls back to common defaults based on `game_id` prefix:

      - `madden-*` -> NFL hashes (3.083 yd from center)
      - `ncaa*`    -> NCAA hashes (6.667 yd from center)
      - `hs-*` / `highschool*` / `high-school*` -> HS hashes (8.889 yd)

    Args:
        profile: Game profile dict.

    Returns:
        `(left_x, right_x)` in universal yards, or `None` if the profile has
        no explicit setting and the `game_id` prefix is unrecognized.

    Raises:
        InvalidProfileError: `hash_marks_yd_from_center` is present but is not
            a finite, non-negative number.
    """
    assert isinstance(profile, dict), "hash_spec_for_profile: profile must be dict"
    explicit = profile.get("hash_marks_yd_from_center")
    if explicit is not None:
        if not isinstance(explicit, (int, float)) or isinstance(explicit, bool):
            raise InvalidProfileError(
                f"hash_marks_yd_from_center must be number, got {type(explicit).__name__}"
            )
        if not math.isfinite(explicit) or explicit < 0:
            raise InvalidProfileError(
                f"hash_marks_yd_from_center must be finite and non-negative, got {explicit!r}"
            )
        dist = float(explicit)
        return (-dist, dist)

    game_id = (profile.get("game_id") or "").lower()
    if game_id.startswith("madden"):
        return (-NFL_HASH_DIST_YD, NFL_HASH_DIST_YD)
    if game_id.startswith("ncaa"):
        return (-NCAA_HASH_DIST_YD, NCAA_HASH_DIST_YD)
    if game_id.startswith(("hs", "highschool", "high-school")):
        return (-HS_HASH_DIST_YD, HS_HASH_DIST_YD)
    return None


# ============================================================================
# 8. Coordinate conversions
# ============================================================================

def universal_to_grid(x_yd: float, y_yd: float, profile: GameProfile) -> PointYd:
    """Convert universal-yard coordinates to fractional editor-grid cells.

    Args:
        x_yd: Lateral position in real yards from the field center.  Must be finite.
        y_yd: Longitudinal position in real yards from the LOS (positive downfield).
            Must be finite.
        profile: Game profile providing `grid.origin` (cell coords of LOS center)
            and `scale.{x,y}_yards_per_cell`.  Must have already passed
            `_validate_profile`.

    Returns:
        `(column, row)` in fractional grid cells.  Caller decides whether to round.
    """
    assert math.isfinite(x_yd), f"universal_to_grid: x_yd must be finite, got {x_yd}"
    assert math.isfinite(y_yd), f"universal_to_grid: y_yd must be finite, got {y_yd}"
    origin = profile["grid"]["origin"]
    scale = profile["scale"]
    assert scale["x_yards_per_cell"] > 0, "scale.x_yards_per_cell must be positive (validate first)"
    assert scale["y_yards_per_cell"] > 0, "scale.y_yards_per_cell must be positive (validate first)"
    return (
        origin["x"] + x_yd / scale["x_yards_per_cell"],
        origin["y"] + y_yd / scale["y_yards_per_cell"],
    )


def total_y_cells(profile: GameProfile, extra_yd: float) -> int:
    """Compute total visible vertical cells (editor height + downfield extension).

    Args:
        profile: Game profile with `grid.height` and `scale.y_yards_per_cell`.
        extra_yd: Extra downfield space to render, in real yards.  Must be ≥0.

    Returns:
        Total vertical cells (always positive — at least `grid.height`).
    """
    assert extra_yd >= 0, f"total_y_cells: extra_yd must be non-negative, got {extra_yd}"
    assert profile["scale"]["y_yards_per_cell"] > 0, "scale.y_yards_per_cell must be positive"
    extra = math.ceil(extra_yd / profile["scale"]["y_yards_per_cell"])
    result = profile["grid"]["height"] + extra
    assert result >= profile["grid"]["height"], "total_y_cells postcondition: result >= grid.height"
    return result


def grid_to_pixel(gx: float, gy: float, total_cells: int) -> PointPx:
    """Convert grid cells to SVG pixel coordinates.

    Y is inverted: a higher grid row (deeper downfield) maps to a smaller
    pixel-Y (closer to the top of the SVG).

    Args:
        gx: Column in grid cells.
        gy: Row in grid cells.
        total_cells: Total visible vertical cells (from `total_y_cells`).
            Must be positive.

    Returns:
        `(x_px, y_px)` in SVG coordinates.
    """
    assert total_cells > 0, f"grid_to_pixel: total_cells must be positive, got {total_cells}"
    assert math.isfinite(gx) and math.isfinite(gy), \
        f"grid_to_pixel: gx={gx}, gy={gy} must both be finite"
    return (
        FIELD_MARGIN_PX + gx * PIXELS_PER_CELL,
        FIELD_MARGIN_PX + (total_cells - gy) * PIXELS_PER_CELL,
    )


def universal_to_pixel(x_yd: float, y_yd: float, profile: GameProfile, total_cells: int) -> PointPx:
    """Convenience: universal yards -> grid cells -> SVG pixels."""
    gx, gy = universal_to_grid(x_yd, y_yd, profile)
    return grid_to_pixel(gx, gy, total_cells)


# ============================================================================
# 9. Cell assignment (tight-cluster snapping + BFS conflict resolution)
# ============================================================================

def _ol_x_range(formation: Formation) -> tuple[float, float] | None:
    """Return the universal-yard `(min_x, max_x)` of interior OL, or None if no OL."""
    xs = [p["x"] for p in formation["players"] if p.get("position") in INTERIOR_OL]
    return (min(xs), max(xs)) if xs else None


def is_tight_cluster(player: Player, formation: Formation) -> bool:
    """Determine whether `player` belongs to the OL tight cluster.

    Tight-cluster members get sequential integer cells centered on the C,
    guaranteeing no two interior linemen share a cell.  A player joins if any of:

      - Position is an interior OL (LT / LG / C / RG / RT), or
      - Position is TE within `CLUSTER_X_TOLERANCE_YD` of the OL block, or
      - An off-line player (e.g., wing-T WING) is within `CLUSTER_X_TOLERANCE_YD`
        of the OL block AND within `TIGHT_CLUSTER_LOS_TOLERANCE_YD` of the LOS.
    """
    assert isinstance(player, dict), \
        f"is_tight_cluster: player must be dict, got {type(player).__name__}"
    assert "players" in formation, "is_tight_cluster: formation missing 'players'"
    position = player.get("position", "")
    if position in INTERIOR_OL:
        return True

    ol_range = _ol_x_range(formation)
    if ol_range is None:
        return False

    ol_min, ol_max = ol_range
    x = player.get("x", 0)
    near_x = (ol_min - CLUSTER_X_TOLERANCE_YD) <= x <= (ol_max + CLUSTER_X_TOLERANCE_YD)
    if not near_x:
        return False

    if position == "TE":
        return True

    # Off-line player (e.g., WING) -- only join if on or near the LOS row.
    return abs(player.get("y", 0)) <= TIGHT_CLUSTER_LOS_TOLERANCE_YD


def _compute_preferred_cells(
    formation: Formation,
    profile: GameProfile,
) -> dict[str, PointYd]:
    """Compute each player's preferred (fractional) cell.

    Tight-cluster members get a snapped X centered on the C; everyone else
    converts directly from universal yards.  Y is always the raw conversion.
    """
    assert "players" in formation, "_compute_preferred_cells: formation missing 'players'"
    assert "grid" in profile and "origin" in profile["grid"], \
        "_compute_preferred_cells: profile missing grid.origin (validate first)"
    origin_x = profile["grid"]["origin"]["x"]
    players = formation["players"]
    cluster_players = [p for p in players if is_tight_cluster(p, formation)]
    cluster_sorted = sorted(cluster_players, key=lambda p: p["x"])
    c_player = next((p for p in cluster_sorted if p.get("label") == "C"), None)

    preferred: dict[str, PointYd] = {}
    for player in players:
        if c_player is not None and player in cluster_players:
            c_index = cluster_sorted.index(c_player)
            p_index = cluster_sorted.index(player)
            snapped_x = origin_x + (p_index - c_index)
            _, gy = universal_to_grid(player["x"], player["y"], profile)
            preferred[player["label"]] = (snapped_x, gy)
        else:
            preferred[player["label"]] = universal_to_grid(
                player["x"], player["y"], profile,
            )
    assert len(preferred) == len(players), \
        "_compute_preferred_cells postcondition: every player must be assigned a cell"
    return preferred


def _bfs_score(dx: int, dy: int, candidate_row: int, side: str, los_row: int) -> int:
    """Return the BFS bump-cost for moving from a target to `(target+dx, target+dy)`.

    Lower is better.  Same-row bumps are cheapest; vertical bumps cost
    `BFS_VERTICAL_BIAS` per row; bumps onto the wrong side of the LOS add a
    fixed `BFS_LOS_CROSS_PENALTY`.
    """
    assert side in _VALID_FORMATION_SIDES, f"_bfs_score: bad side {side!r}"
    assert isinstance(dx, int) and isinstance(dy, int), \
        f"_bfs_score: dx={dx} dy={dy} must be ints"
    score = abs(dx) + abs(dy) * BFS_VERTICAL_BIAS
    if side == "defense" and candidate_row <= los_row:
        score += BFS_LOS_CROSS_PENALTY
    elif side == "offense" and candidate_row > los_row:
        score += BFS_LOS_CROSS_PENALTY
    assert score >= 0, "_bfs_score postcondition: score must be non-negative"
    return score


def _bfs_nearest_free_cell(
    target: Cell,
    used: set[Cell],
    side: str,
    los_row: int,
) -> Cell:
    """Find the nearest unused cell to `target` using a side-aware BFS scoring.

    Searches outward in expanding rings up to `BFS_MAX_RINGS`.  Within each
    ring the candidate with the lowest `_bfs_score` is chosen.

    Args:
        target: Initial preferred cell (integer coordinates).
        used: Set of already-occupied cells.
        side: `"offense"` or `"defense"`; used for LOS-cross penalty direction.
        los_row: Editor row of the line of scrimmage.

    Returns:
        An unused `(col, row)` cell in the smallest ring that has at least
        one free candidate.

    Raises:
        CellAssignmentError: No free cell exists within `BFS_MAX_RINGS` of
            `target`.  Indicates that the formation cannot fit on this
            profile's grid (previously this returned `target` silently,
            corrupting the caller's `used` set).
    """
    assert side in _VALID_FORMATION_SIDES, f"_bfs_nearest_free_cell: bad side {side!r}"
    assert isinstance(los_row, int), \
        f"_bfs_nearest_free_cell: los_row must be int, got {type(los_row).__name__}"
    for ring in range(1, BFS_MAX_RINGS + 1):
        best: tuple[Cell, int] | None = None
        for dy in range(-ring, ring + 1):
            for dx in range(-ring, ring + 1):
                if max(abs(dx), abs(dy)) != ring:
                    continue  # not on this ring's perimeter
                candidate: Cell = (target[0] + dx, target[1] + dy)
                if candidate in used:
                    continue
                score = _bfs_score(dx, dy, candidate[1], side, los_row)
                if best is None or score < best[1]:
                    best = (candidate, score)
        if best is not None:
            assert best[0] not in used, \
                "_bfs_nearest_free_cell postcondition: returned cell must be free"
            return best[0]
    raise CellAssignmentError(
        f"no free cell within {BFS_MAX_RINGS} rings of {target} "
        f"(side={side}, los_row={los_row}, used_cells={len(used)})"
    )


def assign_cells_for_formation(
    formation: Formation,
    profile: GameProfile,
) -> dict[str, Cell] | dict[str, PointYd]:
    """Compute the editor-grid cell for every player in `formation`.

    Algorithm:
      1. Compute each player's preferred cell (tight-cluster members get
         sequential integers centered on C; others convert directly).
      2. If `profile.snap_to_cells` is False, return the fractional preferred
         cells as-is.
      3. Otherwise round to integers, then resolve conflicts via BFS.

    Cluster players are placed first (already conflict-free among themselves);
    the remaining players are placed in formation order.

    Args:
        formation: Formation dict (must satisfy `_validate_formation`).
        profile: Game profile (must satisfy `_validate_profile`).

    Returns:
        Dict mapping `player.label -> (col, row)`.  The value type is
        type-discriminated by `profile.snap_to_cells`:

        * If `snap_to_cells` is True, every value is `(int, int)` and every
          cell in the dict is unique (postcondition asserted).
        * Otherwise every value is `(float, float)` from raw
          `universal_to_grid` conversion (no overlap guarantee).

        Callers that need a single homogeneous type should branch on
        `profile.get("snap_to_cells", False)`.

    Raises:
        InvalidFormationError: `formation` fails validation.
        InvalidProfileError: `profile` fails validation.
        CellAssignmentError: BFS could not place a player (formation does not
            fit on this profile's grid).
    """
    _validate_formation(formation)
    _validate_profile(profile)

    preferred = _compute_preferred_cells(formation, profile)
    if not profile.get("snap_to_cells", False):
        assert len(preferred) == len(formation["players"]), \
            "assign_cells_for_formation: lost a player during preferred-cell pass"
        return preferred
    return _snap_and_resolve(formation, profile, preferred)


def _snap_and_resolve(
    formation: Formation,
    profile: GameProfile,
    preferred: dict[str, PointYd],
) -> dict[str, Cell]:
    """Round each preferred cell to integers, resolving collisions via BFS.

    Cluster players are placed first (their preferred cells are already
    conflict-free among themselves by construction); other players follow
    in formation order.

    Postconditions:
        - len(result) == len(formation.players)
        - All values are (int, int)
        - All values are unique
    """
    side = formation.get("side", "offense")
    los_row = profile["grid"]["origin"]["y"]
    cluster_players = [p for p in formation["players"] if is_tight_cluster(p, formation)]
    cluster_sorted = sorted(cluster_players, key=lambda p: p["x"])
    placement_order = (
        [p["label"] for p in cluster_sorted]
        + [p["label"] for p in formation["players"] if p not in cluster_players]
    )

    final: dict[str, Cell] = {}
    used: set[Cell] = set()
    for label in placement_order:
        gx, gy = preferred[label]
        target: Cell = (round(gx), round(gy))
        if target in used:
            target = _bfs_nearest_free_cell(target, used, side, los_row)
        final[label] = target
        used.add(target)

    assert len(final) == len(formation["players"]), \
        f"_snap_and_resolve: placed {len(final)} of {len(formation['players'])}"
    assert len(set(final.values())) == len(final), \
        "_snap_and_resolve: duplicate cells in result"
    for label, cell in final.items():
        assert isinstance(cell[0], int) and isinstance(cell[1], int), \
            f"_snap_and_resolve: non-integer cell for {label}: {cell}"
    return final


def player_grid_pos(
    player: Player,
    formation: Formation,
    profile: GameProfile,
) -> PointYd:
    """Return the assigned `(col, row)` for a single player.

    Re-computes the full formation assignment internally; not cached.  Callers
    in tight loops should call `assign_cells_for_formation` once and reuse the
    dict.
    """
    return assign_cells_for_formation(formation, profile)[player["label"]]  # type: ignore[index]


def player_effective_xy(
    player: Player,
    formation: Formation,
    profile: GameProfile,
) -> PointYd:
    """Return the player's snapped position expressed back as universal yards.

    Routes and explicit paths must start from the snapped cell position, not
    the raw universal coordinate, so route arrows connect to the player marker
    rather than floating to a nearby wrong cell.  (Cluster sequential
    assignment can shift TE one cell right of where `universal_to_grid` would
    put it, which would otherwise make TE's route appear to start at RT.)
    """
    gx, gy = assign_cells_for_formation(formation, profile)[player["label"]]
    origin = profile["grid"]["origin"]
    scale = profile["scale"]
    return (
        (gx - origin["x"]) * scale["x_yards_per_cell"],
        (gy - origin["y"]) * scale["y_yards_per_cell"],
    )


# ============================================================================
# 10. Route resolution
# ============================================================================

def receiver_route_path(
    receiver_x: float,
    receiver_y: float,
    route: Route,
) -> list[PointYd]:
    """Translate a route's stored waypoints to absolute universal-yard coordinates.

    Routes are authored as right-hand-side breaks (e.g., a slant breaks toward
    the right hash).  When a receiver is on the offensive right
    (`receiver_x > ROUTE_MIRROR_X_THRESHOLD_YD`), the X component of every
    waypoint is mirrored so the route breaks back toward the inside of the field.

    Args:
        receiver_x: Receiver's universal-yard X position (post-snap).  Must be finite.
        receiver_y: Receiver's universal-yard Y position (post-snap).  Must be finite.
        route: Route definition with a `path` list of `[dx, dy]` offsets.

    Returns:
        Absolute waypoints in universal yards, beginning at the receiver.

    Raises:
        InvalidRouteError: `route` has no `path` list, or any waypoint is
            malformed.
    """
    assert math.isfinite(receiver_x), \
        f"receiver_route_path: receiver_x must be finite, got {receiver_x}"
    assert math.isfinite(receiver_y), \
        f"receiver_route_path: receiver_y must be finite, got {receiver_y}"
    _validate_route(route, name=route.get("name", "<unnamed>"))
    mirror = -1 if receiver_x > ROUTE_MIRROR_X_THRESHOLD_YD else 1
    return [
        (receiver_x + (waypoint[0] * mirror), receiver_y + waypoint[1])
        for waypoint in route["path"]
    ]


def route_lookup(route_lib: RouteLibrary, name: str) -> Route | None:
    """Look up a route by name, with a fallback for compound "or"-style names.

    Some plays specify "snag-or-stick" or "fade or comeback" to indicate an
    option route.  We render the first branch and accept that the diagram is
    a simplification.

    Returning `None` for a missing route is intentional and is part of the
    public contract: the caller (currently `_render_route_assignment`) emits
    a structured warning with the offending route name.  This is therefore
    *not* a silent failure — it is a documented "absence" sentinel.

    Args:
        route_lib: Mapping built by `load_route_library`.
        name: Route name as written on the assignment.  Must be a non-empty string.

    Returns:
        The matching route, or `None` if no resolution succeeds.
    """
    assert isinstance(route_lib, dict), \
        f"route_lookup: route_lib must be dict, got {type(route_lib).__name__}"
    assert isinstance(name, str) and name, \
        f"route_lookup: name must be non-empty string, got {name!r}"
    if name in route_lib:
        return route_lib[name]
    for separator in (" or ", "-or-"):
        if separator in name:
            first_branch = name.split(separator)[0].strip()
            if first_branch in route_lib:
                return route_lib[first_branch]
    return None


# ============================================================================
# 11. SVG primitive emitters
# ============================================================================

def svg_rect(
    x: float, y: float, width: float, height: float,
    *, fill: str,
    stroke: str | None = None, stroke_width: float | None = None,
    fill_opacity: float | None = None,
    rx: float | None = None,
) -> str:
    """Emit a `<rect>` element string.  Optional attributes are omitted if None."""
    assert width >= 0, f"svg_rect: width must be non-negative, got {width}"
    assert height >= 0, f"svg_rect: height must be non-negative, got {height}"
    assert fill, "svg_rect: fill must be a non-empty color string"
    attrs = [f'x="{x}"', f'y="{y}"', f'width="{width}"', f'height="{height}"', f'fill="{fill}"']
    if stroke is not None:
        attrs.append(f'stroke="{stroke}"')
    if stroke_width is not None:
        attrs.append(f'stroke-width="{stroke_width}"')
    if fill_opacity is not None:
        attrs.append(f'fill-opacity="{fill_opacity}"')
    if rx is not None:
        attrs.append(f'rx="{rx}"')
    return f"<rect {' '.join(attrs)} />"


def svg_circle(
    cx: float, cy: float, r: float,
    *, fill: str,
    stroke: str | None = None, stroke_width: float | None = None,
    fill_opacity: float | None = None,
    stroke_dasharray: str | None = None,
) -> str:
    """Emit a `<circle>` element string."""
    assert r >= 0, f"svg_circle: radius must be non-negative, got {r}"
    assert fill, "svg_circle: fill must be a non-empty color string"
    attrs = [f'cx="{cx}"', f'cy="{cy}"', f'r="{r}"', f'fill="{fill}"']
    if stroke is not None:
        attrs.append(f'stroke="{stroke}"')
    if stroke_width is not None:
        attrs.append(f'stroke-width="{stroke_width}"')
    if fill_opacity is not None:
        attrs.append(f'fill-opacity="{fill_opacity}"')
    if stroke_dasharray is not None:
        attrs.append(f'stroke-dasharray="{stroke_dasharray}"')
    return f"<circle {' '.join(attrs)} />"


def svg_line(
    x1: float, y1: float, x2: float, y2: float,
    *, stroke: str, stroke_width: float,
    stroke_opacity: float | None = None,
    stroke_dasharray: str | None = None,
) -> str:
    """Emit a `<line>` element string."""
    assert stroke_width >= 0, f"svg_line: stroke_width must be non-negative, got {stroke_width}"
    assert stroke, "svg_line: stroke must be a non-empty color string"
    attrs = [
        f'x1="{x1}"', f'y1="{y1}"', f'x2="{x2}"', f'y2="{y2}"',
        f'stroke="{stroke}"', f'stroke-width="{stroke_width}"',
    ]
    if stroke_opacity is not None:
        attrs.append(f'stroke-opacity="{stroke_opacity}"')
    if stroke_dasharray is not None:
        attrs.append(f'stroke-dasharray="{stroke_dasharray}"')
    return f"<line {' '.join(attrs)} />"


def svg_text(
    x: float, y: float, content: str,
    *, font_size: int,
    fill: str = COLOR_TEXT_PRIMARY,
    text_anchor: str | None = None,
    font_weight: str | None = None,
    font_style: str | None = None,
    stroke: str | None = None,
    stroke_width: float | None = None,
    letter_spacing: int | None = None,
) -> str:
    """Emit a `<text>` element string."""
    assert font_size > 0, f"svg_text: font_size must be positive, got {font_size}"
    assert isinstance(content, str), \
        f"svg_text: content must be string, got {type(content).__name__}"
    attrs = [f'x="{x}"', f'y="{y}"']
    if text_anchor is not None:
        attrs.append(f'text-anchor="{text_anchor}"')
    attrs.append(f'font-size="{font_size}"')
    attrs.append(f'fill="{fill}"')
    if font_weight is not None:
        attrs.append(f'font-weight="{font_weight}"')
    if font_style is not None:
        attrs.append(f'font-style="{font_style}"')
    if stroke is not None:
        attrs.append(f'stroke="{stroke}"')
    if stroke_width is not None:
        attrs.append(f'stroke-width="{stroke_width}"')
    if letter_spacing is not None:
        attrs.append(f'letter-spacing="{letter_spacing}"')
    return f"<text {' '.join(attrs)}>{content}</text>"


def svg_polyline(
    points_px: list[PointPx],
    *, stroke: str, stroke_width: float, marker_id: str,
    dashed: bool = False,
) -> str:
    """Emit a `<polyline>` with the given pixel points and arrow-end marker."""
    assert len(points_px) >= 2, \
        f"svg_polyline: need >=2 points for a polyline, got {len(points_px)}"
    assert stroke_width > 0, f"svg_polyline: stroke_width must be positive, got {stroke_width}"
    assert marker_id, "svg_polyline: marker_id must be non-empty"
    points_str = " ".join(f"{x:.1f},{y:.1f}" for x, y in points_px)
    dasharray = ' stroke-dasharray="6,4"' if dashed else ""
    return (
        f'<polyline points="{points_str}" fill="none" '
        f'stroke="{stroke}" stroke-width="{stroke_width}"{dasharray} '
        f'marker-end="url(#{marker_id})" />'
    )


def svg_ellipse(
    cx: float, cy: float, rx: float, ry: float,
    *, fill: str, stroke: str,
    fill_opacity: float, stroke_width: float,
    stroke_dasharray: str,
) -> str:
    """Emit a dashed-outline `<ellipse>` (used for zone-coverage area markers)."""
    assert rx >= 0 and ry >= 0, f"svg_ellipse: radii must be non-negative, got rx={rx}, ry={ry}"
    assert 0.0 <= fill_opacity <= 1.0, \
        f"svg_ellipse: fill_opacity must be in [0, 1], got {fill_opacity}"
    return (
        f'<ellipse cx="{cx:.1f}" cy="{cy:.1f}" rx="{rx:.1f}" ry="{ry:.1f}" '
        f'fill="{fill}" fill-opacity="{fill_opacity}" '
        f'stroke="{stroke}" stroke-width="{stroke_width}" '
        f'stroke-dasharray="{stroke_dasharray}" />'
    )


def svg_arrow_marker(marker_id: str, color: str) -> str:
    """Build a `<marker>` definition for a triangular arrow-head.

    Sized for print legibility: wider head, tip placed at the line endpoint
    (refX equals the path's maximum x so the tip touches the waypoint, not
    the midpoint of the arrow body).
    """
    return (
        f'<marker id="{marker_id}" markerWidth="12" markerHeight="8" '
        f'refX="11" refY="4" orient="auto" markerUnits="strokeWidth">'
        f'<path d="M0,0 L0,8 L11,4 z" fill="{color}" /></marker>'
    )


def render_path_yd(
    parts: list[str],
    waypoints_yd: list[PointYd],
    profile: GameProfile,
    total_cells: int,
    *, color: str, width: float, marker_id: str,
    dashed: bool = False,
) -> None:
    """Append a polyline to `parts`, transforming yard waypoints to pixels.

    Args:
        parts: Output list (SVG element strings are appended in place).
        waypoints_yd: Universal-yard waypoints; must contain at least 2 points
            (a polyline with fewer points is meaningless and indicates a
            programmer error upstream).
        profile: Game profile (must satisfy `_validate_profile`).
        total_cells: Total visible vertical cells.  Must be positive.
        color: SVG stroke color (any valid CSS color string).
        width: Stroke width in pixels.  Must be positive.
        marker_id: ID of the `<marker>` arrow head to attach.
        dashed: If True, render with the standard dashed pattern.

    Raises:
        InvalidRouteError: `waypoints_yd` has fewer than 2 points.
    """
    assert isinstance(parts, list), \
        f"render_path_yd: parts must be list, got {type(parts).__name__}"
    assert width > 0, f"render_path_yd: width must be positive, got {width}"
    if len(waypoints_yd) < 2:
        raise InvalidRouteError(
            f"render_path_yd requires >=2 waypoints, got {len(waypoints_yd)}"
        )
    pixel_points = [
        universal_to_pixel(x, y, profile, total_cells) for x, y in waypoints_yd
    ]
    parts.append(svg_polyline(
        pixel_points,
        stroke=color, stroke_width=width, marker_id=marker_id, dashed=dashed,
    ))


def render_zone_ellipse(
    parts: list[str],
    center_yd: PointYd,
    radius_x_yd: float,
    radius_y_yd: float,
    color: str,
    profile: GameProfile,
    total_cells: int,
) -> None:
    """Append a dashed zone-coverage ellipse to `parts`, sized in real yards."""
    assert radius_x_yd > 0, f"render_zone_ellipse: radius_x_yd must be positive, got {radius_x_yd}"
    assert radius_y_yd > 0, f"render_zone_ellipse: radius_y_yd must be positive, got {radius_y_yd}"
    cx_px, cy_px = universal_to_pixel(*center_yd, profile, total_cells)
    rx_px = (radius_x_yd / profile["scale"]["x_yards_per_cell"]) * PIXELS_PER_CELL
    ry_px = (radius_y_yd / profile["scale"]["y_yards_per_cell"]) * PIXELS_PER_CELL
    parts.append(svg_ellipse(
        cx_px, cy_px, rx_px, ry_px,
        fill=color, stroke=color,
        fill_opacity=OPACITY_ZONE_FILL,
        stroke_width=STROKE_ZONE_OUTLINE,
        stroke_dasharray="3,3",
    ))


# ============================================================================
# 12. Style helpers (read-priority color & marker selection)
# ============================================================================

# Maps a play's read-priority field name to its (color, marker) style pair.
# Used by `style_for_player_read` to eliminate the four-way if/elif duplication
# that previously appeared in three different places.
_READ_FIELD_STYLES: Final[list[tuple[str, str, str]]] = [
    ("primary_read",   COLOR_PRIMARY_READ,   MARKER_PRIMARY),
    ("secondary_read", COLOR_SECONDARY_READ, MARKER_SECONDARY),
    ("tertiary_read",  COLOR_TERTIARY_READ,  MARKER_TERTIARY),
    ("checkdown",      COLOR_CHECKDOWN,      MARKER_CHECKDOWN),
]


def style_for_player_read(label: str, play: Play | None) -> tuple[str, str]:
    """Return `(color, marker_id)` for a player based on their read priority.

    If the player matches one of the play's read-priority fields, returns the
    corresponding style.  Otherwise returns the generic-route style.
    """
    assert isinstance(label, str), \
        f"style_for_player_read: label must be string, got {type(label).__name__}"
    if not play:
        return (COLOR_ROUTE, MARKER_ARROW)
    for field, color, marker in _READ_FIELD_STYLES:
        if label == play.get(field):
            return (color, marker)
    return (COLOR_ROUTE, MARKER_ARROW)


def style_for_alt_path_priority(priority: str) -> tuple[str, str]:
    """Return `(color, marker_id)` for an alt-path priority tag."""
    assert isinstance(priority, str), \
        f"style_for_alt_path_priority: priority must be string, got {type(priority).__name__}"
    mapping = {
        "primary":   (COLOR_PRIMARY_READ,   MARKER_PRIMARY),
        "secondary": (COLOR_SECONDARY_READ, MARKER_SECONDARY),
        "tertiary":  (COLOR_TERTIARY_READ,  MARKER_TERTIARY),
        "checkdown": (COLOR_CHECKDOWN,      MARKER_CHECKDOWN),
    }
    return mapping.get(priority, (COLOR_ROUTE, MARKER_ARROW))


def beats_coverage_badge(beats: str) -> str:
    """Translate a `beats_coverage` tag to its short badge label."""
    assert isinstance(beats, str), \
        f"beats_coverage_badge: beats must be string, got {type(beats).__name__}"
    if beats == "man":
        return "M"
    if beats == "zone":
        return "Z"
    return "M/Z"


def offensive_player_fill(
    label: str,
    in_bounds: bool,
    play: Play | None,
) -> str:
    """Pick the fill color for an offensive player marker.

    Key players (C, ball carrier, primary read) get a dark navy fill so they
    stand out on a white field.  Normal players get white fill with a black
    border.  Out-of-bounds players get a dark red fill.
    """
    assert isinstance(label, str) and label, \
        f"offensive_player_fill: label must be non-empty string, got {label!r}"
    assert isinstance(in_bounds, bool), \
        f"offensive_player_fill: in_bounds must be bool, got {type(in_bounds).__name__}"
    if not in_bounds:
        return COLOR_OUT_OF_BOUNDS
    if label == "C":
        return COLOR_C
    if play is not None:
        if label == play.get("ball_carrier"):
            return COLOR_BALL_CARRIER
        if label == play.get("primary_read"):
            return COLOR_PRIMARY_READ_PLAYER
    return COLOR_OFFENSE


def offensive_player_text_color(
    label: str,
    in_bounds: bool,
    play: Play | None,
) -> str:
    """Pick the label text color to match the player's fill.

    Key players (dark navy fill) use white text; all others use black.
    """
    assert isinstance(label, str) and label, \
        f"offensive_player_text_color: label must be non-empty string, got {label!r}"
    if not in_bounds:
        return COLOR_TEXT_DARK
    if label == "C":
        return COLOR_KEY_PLAYER_TEXT
    if play is not None:
        if label == play.get("ball_carrier"):
            return COLOR_KEY_PLAYER_TEXT
        if label == play.get("primary_read"):
            return COLOR_KEY_PLAYER_TEXT
    return COLOR_TEXT_DARK


def defender_fill(position: str) -> str:
    """Pick the fill color for a defensive player marker."""
    assert isinstance(position, str), \
        f"defender_fill: position must be string, got {type(position).__name__}"
    if position in DEFENSIVE_DL:
        return COLOR_DEFENSE_DL
    if position == "S":
        return COLOR_DEFENSE_DEEP
    return COLOR_DEFENSE


def label_font_size(label: str) -> int:
    """Pick a font size for a player label based on length."""
    assert isinstance(label, str), \
        f"label_font_size: label must be string, got {type(label).__name__}"
    return FONT_LABEL if len(label) <= 2 else FONT_LABEL_LONG


def player_badge_text(label: str, play: Play | None) -> tuple[str, str] | None:
    """Return `(badge_text, badge_color)` for a player, or None if no badge applies.

    A player can be both the ball carrier and a read; the most informative
    badge wins.  The C is never given a "BC" badge -- the C always carries
    the snap, so the badge would be noise.
    """
    if play is None:
        return None
    if label == play.get("primary_read"):
        return ("1°", COLOR_PRIMARY_READ)
    if label == play.get("secondary_read"):
        return ("2°", COLOR_SECONDARY_READ)
    if label == play.get("tertiary_read"):
        return ("3°", COLOR_TERTIARY_READ)
    if label == play.get("checkdown"):
        return ("C", COLOR_CHECKDOWN)
    if label == play.get("ball_carrier") and label != "C":
        return ("BC", COLOR_BALL_CARRIER)
    return None


# Dispatch table for non-ball-carrier roles.  Each entry is
# (color, stroke_width, marker_id, dashed).  Roles not present here fall
# through to the route default at the bottom of `explicit_path_style`.
# Keys use AssignmentRole members (which compare equal to their string
# values); a raw role string from YAML still hits the right entry.
_SIMPLE_ROLE_STYLES: Final[dict[str, tuple[str, float, str, bool]]] = {
    AssignmentRole.LEAD_BLOCK: (COLOR_FB_LEAD,    STROKE_LEAD_BLOCK, MARKER_FB_LEAD,    False),
    AssignmentRole.FAKE:       (COLOR_FAKE_PATH,  STROKE_FAKE_PATH,  MARKER_FAKE,       True),
    AssignmentRole.PASS_BLOCK: (COLOR_PASS_BLOCK, STROKE_PASS_BLOCK, MARKER_PASS_BLOCK, False),
}

_BALL_CARRIER_ROLES: Final[frozenset[str]] = frozenset({
    AssignmentRole.BALL_CARRIER, AssignmentRole.HANDOFF,
})


def _ball_carrier_style(label: str, play: Play) -> tuple[str, float, str, bool]:
    """Color a ball-carrier path by which read-priority slot the carrier occupies.

    On option plays multiple ball carriers share the field (dive / keep / pitch);
    each gets a distinct color matching its read-priority slot.
    """
    assert isinstance(label, str), "_ball_carrier_style: label must be string"
    if label == play.get("secondary_read"):
        return (COLOR_SECONDARY_READ, STROKE_RUN_PATH, MARKER_SECONDARY, False)
    if label == play.get("tertiary_read"):
        return (COLOR_TERTIARY_READ, STROKE_RUN_PATH, MARKER_TERTIARY, False)
    return (COLOR_PRIMARY_READ, STROKE_RUN_PATH, MARKER_PRIMARY, False)


def explicit_path_style(
    role: str,
    position: str,
    label: str,
    play: Play,
) -> tuple[str, float, str, bool]:
    """Pick `(color, stroke_width, marker_id, dashed)` for an explicit-path assignment.

    Args:
        role: Assignment role (`ball_carrier`, `lead_block`, `run_block`, etc.).
        position: Player's football position (used to distinguish OL pulls).
        label: Player label (used to color option-play branches by read priority).
        play: The play (used for read-priority lookups).
    """
    if role in _BALL_CARRIER_ROLES:
        return _ball_carrier_style(label, play)
    if role == AssignmentRole.RUN_BLOCK and position in INTERIOR_OL:
        return (COLOR_PULL, STROKE_LEAD_BLOCK, MARKER_PULL, False)
    return _SIMPLE_ROLE_STYLES.get(role, (COLOR_ROUTE, STROKE_ROUTE, MARKER_ARROW, False))


# ============================================================================
# 13. Layout dataclass + dimension computation
# ============================================================================

class Layout(NamedTuple):
    """All pixel-space dimensions and offsets needed by the renderers."""
    total_w: int
    total_h: int
    field_w: int
    field_h: int
    inner_x: int
    inner_y: int
    inner_w: int
    inner_h: int
    extension_top_y: int
    extension_h: int
    editor_top_y: int
    editor_h: int
    title_top_y: int
    legend_top_y: int
    warnings_top_y: int
    notes_top_y: int
    notes_h: int
    field_top_y: int
    width_cells: int
    height_cells: int
    total_cells: int
    extension_cells: int
    extra_yd: int


class NoteRow(NamedTuple):
    """A single line of the coaching-notes box (color + text + indent)."""
    color: str
    text: str
    x_px: int


def _note_layout_chars(total_w: int) -> tuple[int, int]:
    """Return `(notes_max_chars, notes_body_max)` for the coaching-notes box."""
    notes_max = int((total_w - NOTES_LEFT_PAD_PX - NOTES_RIGHT_PAD_PX) / NOTES_AVG_CHAR_WIDTH_PX)
    notes_body_max = notes_max - int(NOTES_INDENT_PX / NOTES_AVG_CHAR_WIDTH_PX)
    return notes_max, notes_body_max


_RUN_READ_PRIORITY_COLORS: Final[dict[int, tuple[str, str]]] = {
    1: (COLOR_PRIMARY_READ,    "1st"),
    2: (COLOR_SECONDARY_READ,  "2nd"),
    3: (COLOR_TERTIARY_READ,   "3rd"),
    4: (COLOR_CHECKDOWN,       "4th"),
    5: (COLOR_QUATERNARY_READ, "5th"),
}

_PASS_READ_FIELDS: Final[list[tuple[str, str, str]]] = [
    ("primary_read",   COLOR_PRIMARY_READ,   "1st read"),
    ("secondary_read", COLOR_SECONDARY_READ, "2nd read"),
    ("tertiary_read",  COLOR_TERTIARY_READ,  "3rd read"),
    ("checkdown",      COLOR_CHECKDOWN,      "Checkdown"),
]


def _build_note_rows_for_run(play: Play, body_max_chars: int) -> list[NoteRow]:
    """Build coaching-notes rows for a run play (one block per `run_reads` entry)."""
    rows: list[NoteRow] = []
    for read in sorted(play.get("run_reads") or [], key=lambda r: r.get("priority", 99)):
        priority = read.get("priority", 0)
        color, label = _RUN_READ_PRIORITY_COLORS.get(
            priority, (COLOR_FALLBACK_READ, f"{priority}th"),
        )
        rows.append(NoteRow(color, f"● {label}  {read.get('read_key', '')}", NOTES_LEFT_PAD_PX))
        for line in wrap_text(read.get("run_to", ""), body_max_chars, "  "):
            rows.append(NoteRow(COLOR_NOTES_BODY, line, NOTES_LEFT_PAD_PX + NOTES_INDENT_PX))
        cue = read.get("notes", "")
        if cue:
            for index, line in enumerate(wrap_text(cue, body_max_chars, "    ")):
                prefix = f"↳ {line}" if index == 0 else line
                rows.append(NoteRow(COLOR_NOTES_CUE, prefix, NOTES_LEFT_PAD_PX + NOTES_INDENT_PX))
        rows.append(NoteRow(COLOR_NOTES_DIVIDER, "", NOTES_LEFT_PAD_PX))  # spacer
    return rows


def _build_note_rows_for_pass(play: Play) -> list[NoteRow]:
    """Build coaching-notes rows for a pass / play-action play."""
    rows: list[NoteRow] = []
    for field, color, friendly in _PASS_READ_FIELDS:
        target = play.get(field)
        if target:
            rows.append(NoteRow(color, f"● {friendly}: {target}", NOTES_LEFT_PAD_PX))
    return rows


def _build_note_rows(
    play: Play | None,
    notes_max_chars: int,
    body_max_chars: int,
) -> list[NoteRow]:
    """Build the full list of coaching-notes rows for a play (may be empty)."""
    if not play:
        return []

    play_type = play.get("play_type", "")
    rows: list[NoteRow] = []
    if play.get("run_reads") and play_type == "run":
        rows.extend(_build_note_rows_for_run(play, body_max_chars))
    elif play_type in (PlayType.PASS, PlayType.PLAY_ACTION):
        rows.extend(_build_note_rows_for_pass(play))

    raw_notes = (play.get("notes") or "").strip().replace("\n", " ")
    if raw_notes:
        if rows:
            rows.append(NoteRow(COLOR_NOTES_DIVIDER, "", NOTES_LEFT_PAD_PX))
        for line in wrap_text(raw_notes, notes_max_chars):
            rows.append(NoteRow(COLOR_NOTES_RAW, line, NOTES_LEFT_PAD_PX))

    while rows and rows[-1].text == "":
        rows.pop()
    return rows


class _FieldDims(NamedTuple):
    """Inner field dimensions in cells & pixels (used to assemble Layout)."""
    width_cells: int
    height_cells: int
    total_cells: int
    extension_cells: int
    inner_w: int
    inner_h: int
    field_w: int
    field_h: int
    extension_h: int
    editor_h: int
    extra_yd: int


def _compute_field_dims(profile: GameProfile, field: str) -> _FieldDims:
    """Compute the inner field dimensions (cells + pixels) from profile + field-mode."""
    assert field in _VALID_FIELD_VALUES, f"_compute_field_dims: bad field {field!r}"
    assert "grid" in profile, "_compute_field_dims: profile missing 'grid' (validate first)"
    extra_yd = FIELD_LONG_EXTRA_YD if field == Field.LONG else FIELD_SHORT_EXTRA_YD
    grid = profile["grid"]
    width_cells = grid["width"]
    height_cells = grid["height"]
    total_cells = total_y_cells(profile, extra_yd)
    extension_cells = total_cells - height_cells
    inner_w = width_cells * PIXELS_PER_CELL
    inner_h = total_cells * PIXELS_PER_CELL
    return _FieldDims(
        width_cells=width_cells, height_cells=height_cells,
        total_cells=total_cells, extension_cells=extension_cells,
        inner_w=inner_w, inner_h=inner_h,
        field_w=inner_w + 2 * FIELD_MARGIN_PX,
        field_h=inner_h + 2 * FIELD_MARGIN_PX,
        extension_h=extension_cells * PIXELS_PER_CELL,
        editor_h=height_cells * PIXELS_PER_CELL,
        extra_yd=extra_yd,
    )


def _compute_notes_height(note_rows: list[NoteRow]) -> int:
    """Compute the pixel height of the coaching-notes box (0 if no rows)."""
    assert isinstance(note_rows, list), \
        f"_compute_notes_height: note_rows must be list, got {type(note_rows).__name__}"
    if not note_rows:
        return 0
    result = (
        NOTES_HEADER_HEIGHT_PX + len(note_rows) * NOTES_LINE_HEIGHT_PX
        + NOTES_VERTICAL_PAD_PX * 2
    )
    assert result > 0, "_compute_notes_height postcondition: non-empty rows yield positive height"
    return result


def _compute_layout(
    profile: GameProfile,
    play: Play | None,
    field: str,
    note_rows: list[NoteRow],
) -> Layout:
    """Compute the full pixel layout for one render pass.

    All render helpers consume a `Layout` rather than recomputing dimensions
    on their own.
    """
    dims = _compute_field_dims(profile, field)
    notes_h = _compute_notes_height(note_rows)

    extension_top_y = FIELD_MARGIN_PX
    editor_top_y = extension_top_y + dims.extension_h
    field_top_y = TITLE_STRIP_HEIGHT_PX
    legend_top_y = field_top_y + dims.field_h
    warnings_top_y = legend_top_y + LEGEND_STRIP_HEIGHT_PX
    notes_top_y = warnings_top_y + WARNINGS_STRIP_HEIGHT_PX
    total_h = (
        dims.field_h + TITLE_STRIP_HEIGHT_PX + WARNINGS_STRIP_HEIGHT_PX
        + LEGEND_STRIP_HEIGHT_PX + notes_h
    )

    return Layout(
        total_w=dims.field_w, total_h=total_h,
        field_w=dims.field_w, field_h=dims.field_h,
        inner_x=FIELD_MARGIN_PX, inner_y=FIELD_MARGIN_PX,
        inner_w=dims.inner_w, inner_h=dims.inner_h,
        extension_top_y=extension_top_y, extension_h=dims.extension_h,
        editor_top_y=editor_top_y, editor_h=dims.editor_h,
        title_top_y=0, field_top_y=field_top_y,
        legend_top_y=legend_top_y, warnings_top_y=warnings_top_y,
        notes_top_y=notes_top_y, notes_h=notes_h,
        width_cells=dims.width_cells, height_cells=dims.height_cells,
        total_cells=dims.total_cells, extension_cells=dims.extension_cells,
        extra_yd=dims.extra_yd,
    )


# ============================================================================
# 14a. Component renderers -- header & chrome
# ============================================================================

def _render_svg_header(layout: Layout) -> str:
    """Open the root `<svg>` element."""
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{layout.total_w}" '
        f'height="{layout.total_h}" viewBox="0 0 {layout.total_w} {layout.total_h}" '
        f'font-family="monospace">'
    )


def _render_provenance_comment(
    profile: GameProfile,
    play: Play | None,
    formation: Formation | None,
    defense: Formation | None,
) -> str:
    """Build an SVG `<!-- ... -->` comment recording version, git rev, and inputs.

    Output is deterministic *given the same inputs* — but contains a UTC
    timestamp and a git short-hash, so two renders separated in time, or
    rendered from different commits, will differ here.  Tests that need
    byte-identical comparisons should strip this comment first or compare
    SVGs rendered in the same process.

    Comment text never contains XML-unsafe sequences ("--" or ">"); we pass
    all interpolated values through `xml_escape` and reject any remaining
    "--" by rewriting it.
    """
    fields: list[str] = [
        f"draw-play v{__version__}",
        f"git={_git_rev()}",
        f"generated={datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')}",
        f"game={profile.get('game_id', '?')}",
    ]
    if play is not None:
        fields.append(f"play={play.get('play_id') or play.get('name') or '?'}")
    if formation is not None:
        fields.append(f"formation={formation.get('name', '?')}")
    if defense is not None:
        fields.append(f"defense={defense.get('name', '?')}")
    body = " | ".join(xml_escape(f).replace("--", "—") for f in fields)
    return f"<!-- {body} -->"


def _render_marker_defs() -> str:
    """Build the `<defs>` block containing every arrow-head marker."""
    markers = [
        (MARKER_ARROW,       COLOR_ROUTE),
        (MARKER_PRIMARY,     COLOR_PRIMARY_READ),
        (MARKER_SECONDARY,   COLOR_SECONDARY_READ),
        (MARKER_TERTIARY,    COLOR_TERTIARY_READ),
        (MARKER_CHECKDOWN,   COLOR_CHECKDOWN),
        (MARKER_FAKE,        COLOR_FAKE_PATH),
        (MARKER_FB_LEAD,     COLOR_FB_LEAD),
        (MARKER_PULL,        COLOR_PULL),
        (MARKER_PASS_BLOCK,  COLOR_PASS_BLOCK),
        (MARKER_RUSH,        COLOR_RUSH),
        (MARKER_ZONE,        COLOR_ZONE),
        (MARKER_MAN,         COLOR_MAN),
    ]
    return "<defs>" + "".join(svg_arrow_marker(mid, color) for mid, color in markers) + "</defs>"


def _render_title_strip(
    layout: Layout,
    profile: GameProfile,
    play: Play | None,
    formation: Formation | None,
    defense: Formation | None,
    show: str,
) -> list[str]:
    """Render the dark title strip at the very top of the SVG."""
    assert layout.total_w > 0, f"_render_title_strip: total_w must be positive, got {layout.total_w}"
    assert show in _VALID_SHOW_VALUES, f"_render_title_strip: bad show {show!r}"
    parts: list[str] = [
        svg_rect(0, layout.title_top_y, layout.total_w, TITLE_STRIP_HEIGHT_PX, fill=COLOR_BG_OUTER),
    ]

    if play and formation:
        title = f'{play["name"]} ({play["play_type"]})'
        subtitle = f'Formation: {play["formation"]}'
    elif defense and not (play and formation):
        title = defense["name"]
        subtitle = (
            f'Defense | front: {defense.get("front", "?")} | '
            f'shell: {defense.get("coverage_shell", "?")}'
        )
    else:
        title = "(no formation loaded)"
        subtitle = ""

    def_label = f' | vs {defense["name"]}' if (defense and play and formation) else ""
    scale = profile["scale"]
    metadata = (
        f'{subtitle} | Game: {profile["game_id"]} | '
        f'Editor: {layout.width_cells}x{layout.height_cells} cells, '
        f'{scale["x_yards_per_cell"]} yd/x, {scale["y_yards_per_cell"]} yd/y'
        f' | +{layout.extra_yd}yd downfield ({_field_tag(layout)})'
        f'{def_label} | show: {show}'
    )

    parts.append(svg_text(
        TITLE_TEXT_X_PX, TITLE_TEXT_Y_PX, title,
        font_size=FONT_TITLE, fill=COLOR_TEXT_PRIMARY, font_weight="bold",
    ))
    parts.append(svg_text(
        TITLE_TEXT_X_PX, SUBTITLE_TEXT_Y_PX, metadata,
        font_size=FONT_SUBTITLE, fill=COLOR_TEXT_SECONDARY,
    ))
    return parts


def _field_tag(layout: Layout) -> str:
    """Return 'long' or 'short' to label the field length in the subtitle."""
    return Field.LONG.value if layout.extra_yd == FIELD_LONG_EXTRA_YD else Field.SHORT.value


def _render_field_background(layout: Layout) -> list[str]:
    """Render the outer dark frame, the downfield extension, and the editor sub-region."""
    parts: list[str] = [
        svg_rect(0, 0, layout.field_w, layout.field_h, fill=COLOR_BG_OUTER),
        svg_rect(
            layout.inner_x, layout.extension_top_y, layout.inner_w, layout.extension_h,
            fill=COLOR_BG_EXTENSION,
        ),
        svg_text(
            layout.inner_x + TAG_TEXT_OFFSET_X_PX,
            layout.extension_top_y + TAG_TEXT_OFFSET_Y_PX,
            "downfield (off-editor)",
            font_size=FONT_AREA_TAG, fill=COLOR_TEXT_MUTED, font_style="italic",
        ),
        svg_rect(
            layout.inner_x, layout.editor_top_y, layout.inner_w, layout.editor_h,
            fill=COLOR_BG_INNER,
            stroke=COLOR_GRID_BOUNDARY, stroke_width=STROKE_EDITOR_BOUNDARY,
        ),
        svg_text(
            layout.inner_x + TAG_TEXT_OFFSET_X_PX,
            layout.editor_top_y + TAG_TEXT_OFFSET_Y_PX,
            "editor grid",
            font_size=FONT_AREA_TAG, fill=COLOR_TEXT_DIM, font_style="italic",
        ),
    ]
    return parts


# ============================================================================
# 14b. Component renderers -- grid, yard lines, hash marks, LOS, depth limit
# ============================================================================

def _render_vertical_grid_lines(layout: Layout) -> list[str]:
    """Vertical grid lines spanning both the extension and the editor sub-region."""
    parts: list[str] = []
    for gx in range(layout.width_cells + 1):
        px = layout.inner_x + gx * PIXELS_PER_CELL
        is_major = gx % MAJOR_GRID_INTERVAL_CELLS == 0

        ext_color = COLOR_GRID_MAJOR if is_major else COLOR_GRID_FINE_EXT
        ext_width = STROKE_GRID_MAJOR_EXT if is_major else STROKE_GRID_FINE_EXT
        parts.append(svg_line(
            px, layout.extension_top_y,
            px, layout.extension_top_y + layout.extension_h,
            stroke=ext_color, stroke_width=ext_width,
        ))

        editor_color = COLOR_GRID_MAJOR if is_major else COLOR_GRID_FINE
        editor_width = STROKE_GRID_MAJOR if is_major else STROKE_GRID_FINE
        parts.append(svg_line(
            px, layout.editor_top_y,
            px, layout.editor_top_y + layout.editor_h,
            stroke=editor_color, stroke_width=editor_width,
        ))
    return parts


def _render_horizontal_grid_lines(layout: Layout) -> list[str]:
    """Editor's per-cell horizontal grid lines."""
    parts: list[str] = []
    for gy in range(layout.height_cells + 1):
        py = layout.inner_y + (layout.total_cells - gy) * PIXELS_PER_CELL
        is_major = gy % MAJOR_GRID_INTERVAL_CELLS == 0
        color = COLOR_GRID_MAJOR if is_major else COLOR_GRID_FINE
        width = STROKE_GRID_MAJOR if is_major else STROKE_GRID_FINE
        parts.append(svg_line(
            layout.inner_x, py,
            layout.inner_x + layout.inner_w, py,
            stroke=color, stroke_width=width,
        ))
    return parts


def _render_yard_lines(layout: Layout, profile: GameProfile) -> list[str]:
    """5-yard interval lines through the downfield extension."""
    if layout.extension_cells <= 0:
        return []

    scale_y = profile["scale"]["y_yards_per_cell"]
    cells_per_marker = YARD_MARKER_INTERVAL_YD / scale_y
    parts: list[str] = []
    for k in range(1, math.ceil(layout.extension_cells / cells_per_marker) + 1):
        cells_above_los = k * cells_per_marker
        gy = profile["grid"]["origin"]["y"] + cells_above_los
        if gy > layout.total_cells:
            break
        py = layout.inner_y + (layout.total_cells - gy) * PIXELS_PER_CELL
        parts.append(svg_line(
            layout.inner_x, py,
            layout.inner_x + layout.inner_w, py,
            stroke=COLOR_YARD_LINE, stroke_width=STROKE_YARD_LINE,
            stroke_dasharray="3,3",
        ))
        parts.append(svg_text(
            layout.inner_x - TAG_TEXT_OFFSET_X_PX,
            py + AXIS_LABEL_Y_TEXT_NUDGE_PX,
            f"+{int(k * YARD_MARKER_INTERVAL_YD)}yd",
            font_size=FONT_AREA_TAG, fill=COLOR_TEXT_MUTED, text_anchor="end",
        ))
    return parts


def _render_axis_labels(layout: Layout) -> list[str]:
    """Cell-coordinate labels along the bottom (X) and left (Y) axes."""
    parts: list[str] = []
    for gx in range(0, layout.width_cells + 1, MAJOR_GRID_INTERVAL_CELLS):
        px = layout.inner_x + gx * PIXELS_PER_CELL
        parts.append(svg_text(
            px, layout.editor_top_y + layout.editor_h + AXIS_LABEL_Y_OFFSET_PX,
            str(gx),
            font_size=FONT_AXIS, fill=COLOR_TEXT_MUTED, text_anchor="middle",
        ))
    for gy in range(0, layout.height_cells + 1, MAJOR_GRID_INTERVAL_CELLS):
        py = (
            layout.inner_y + (layout.total_cells - gy) * PIXELS_PER_CELL
            + AXIS_LABEL_Y_TEXT_NUDGE_PX
        )
        parts.append(svg_text(
            layout.inner_x - AXIS_LABEL_X_OFFSET_PX, py, str(gy),
            font_size=FONT_AXIS, fill=COLOR_TEXT_MUTED, text_anchor="end",
        ))
    return parts


def _render_hash_marks(layout: Layout, profile: GameProfile) -> list[str]:
    """NFL / NCAA / HS hash-mark ticks down both hash lines."""
    hash_spec = hash_spec_for_profile(profile)
    if hash_spec is None:
        return []

    grid = profile["grid"]
    scale = profile["scale"]
    y_yd_min = -grid["origin"]["y"] * scale["y_yards_per_cell"]
    y_yd_max = (layout.total_cells - grid["origin"]["y"]) * scale["y_yards_per_cell"]
    parts: list[str] = []

    for hash_x_yd in hash_spec:
        gx = grid["origin"]["x"] + hash_x_yd / scale["x_yards_per_cell"]
        if gx < 0 or gx > layout.width_cells:
            continue
        px = layout.inner_x + gx * PIXELS_PER_CELL
        for y_int in range(int(math.floor(y_yd_min)), int(math.ceil(y_yd_max)) + 1):
            gy = grid["origin"]["y"] + y_int / scale["y_yards_per_cell"]
            if gy < 0 or gy > layout.total_cells:
                continue
            parts.append(_render_one_hash_tick(layout, px, gy, y_int))
    return parts


def _render_one_hash_tick(layout: Layout, px: float, gy: float, y_int: int) -> str:
    """Render a single hash-mark tick (called by `_render_hash_marks`)."""
    py = layout.inner_y + (layout.total_cells - gy) * PIXELS_PER_CELL
    is_major = (y_int % YARD_MARKER_INTERVAL_YD == 0)
    half_width = HASH_TICK_HALF_WIDTH_PX + (HASH_MAJOR_EXTRA_HALF_PX if is_major else 0)
    stroke_w = STROKE_HASH_MAJOR if is_major else STROKE_HASH_MINOR
    opacity = OPACITY_HASH_MAJOR if is_major else OPACITY_HASH_MINOR
    return svg_line(
        px - half_width, py, px + half_width, py,
        stroke=COLOR_HASH, stroke_width=stroke_w, stroke_opacity=opacity,
    )


def _render_los(layout: Layout, profile: GameProfile) -> list[str]:
    """Render the gold LOS line and its 'LOS' label."""
    los_y_px = layout.inner_y + (layout.total_cells - profile["grid"]["origin"]["y"]) * PIXELS_PER_CELL
    return [
        svg_line(
            layout.inner_x, los_y_px,
            layout.inner_x + layout.inner_w, los_y_px,
            stroke=COLOR_LOS, stroke_width=STROKE_LOS,
        ),
        svg_text(
            layout.inner_x + layout.inner_w - LOS_LABEL_RIGHT_PAD_PX,
            los_y_px - LOS_LABEL_Y_OFFSET_PX,
            "LOS",
            font_size=FONT_LOS_LABEL, fill=COLOR_TEXT_PRIMARY,
            font_weight="bold", text_anchor="end",
        ),
    ]


def _render_depth_limit(
    layout: Layout, profile: GameProfile,
    play: Play | None, formation: Formation | None,
) -> list[str]:
    """Render the editor's max-route-depth ceiling line, if applicable."""
    limits = profile.get("limits") or {}
    max_depth = limits.get("max_route_depth_yd")
    if not (max_depth and play and formation):
        return []

    grid = profile["grid"]
    scale = profile["scale"]
    depth_grid = grid["origin"]["y"] + max_depth / scale["y_yards_per_cell"]
    depth_px = layout.inner_y + (layout.total_cells - depth_grid) * PIXELS_PER_CELL
    if not (0 <= depth_px <= layout.inner_y + layout.inner_h):
        return []

    return [
        svg_line(
            layout.inner_x, depth_px,
            layout.inner_x + layout.inner_w, depth_px,
            stroke=COLOR_ROUTE_LIMIT, stroke_width=STROKE_DEPTH_LIMIT,
            stroke_dasharray="6,4",
        ),
        svg_text(
            layout.inner_x + DEPTH_LIMIT_LABEL_X_PX,
            depth_px - DEPTH_LIMIT_LABEL_Y_PX,
            f"editor max route depth ({max_depth} yd)",
            font_size=FONT_DEPTH_LIMIT, fill=COLOR_ROUTE_LIMIT,
        ),
    ]


# ============================================================================
# 14c. Component renderers -- defenders & coverage
# ============================================================================

def _render_player_marker(
    px: float, py: float,
    label: str, fill: str, size: int,
    *, is_square: bool, label_color: str, border_width: float,
    fill_opacity: float | None = None,
) -> list[str]:
    """Emit either a square-or-circle marker plus its centered label.

    Args:
        fill_opacity: Explicit fill opacity.  Pass None for fully opaque (1.0).
            Defenders use OPACITY_DEFENDER_FILL; offense markers are fully opaque.
    """
    assert size > 0, f"_render_player_marker: size must be positive, got {size}"
    assert border_width >= 0, \
        f"_render_player_marker: border_width must be non-negative, got {border_width}"
    half = size / 2
    if is_square:
        marker = svg_rect(
            px - half, py - half, size, size,
            fill=fill, stroke=COLOR_TEXT_PRIMARY, stroke_width=border_width,
            fill_opacity=fill_opacity,
        )
    else:
        marker = svg_circle(
            px, py, size / 2,
            fill=fill, stroke=COLOR_TEXT_PRIMARY, stroke_width=border_width,
            fill_opacity=fill_opacity,
        )
    text = svg_text(
        px, py + PLAYER_LABEL_Y_OFFSET_PX, label,
        font_size=label_font_size(label),
        fill=label_color, font_weight="bold", text_anchor="middle",
    )
    return [marker, text]


def _render_defender(
    defender: Player,
    profile: GameProfile,
    layout: Layout,
    cell_override: Cell | None,
) -> list[str]:
    """Render a single defender (DL as square, others as circle) plus label."""
    assert "label" in defender, "_render_defender: defender missing 'label'"
    assert "x" in defender and "y" in defender, "_render_defender: missing x/y"
    if cell_override is not None:
        gx, gy = cell_override
    else:
        gx, gy = universal_to_grid(defender["x"], defender["y"], profile)
    px, py = grid_to_pixel(gx, gy, layout.total_cells)

    position = defender.get("position", "")
    fill = defender_fill(position)
    is_square = position in DEFENSIVE_DL
    return _render_player_marker(
        px, py,
        defender.get("label", ""), fill, DEFENSE_MARKER_SIZE_PX,
        is_square=is_square, label_color=COLOR_TEXT_PRIMARY,
        border_width=STROKE_DEFENDER_BORDER,
        fill_opacity=OPACITY_DEFENDER_FILL,
    )


def _render_rush_coverage(
    defender: Player, role: str,
    profile: GameProfile, layout: Layout,
) -> list[str]:
    """Render the forward-arrow for a rushing defender."""
    dx, dy = defender["x"], defender["y"]
    color = COLOR_BLITZ if role == CoverageRole.BLITZ else COLOR_RUSH
    parts: list[str] = []
    render_path_yd(
        parts, [(dx, dy), (dx, dy - RUSH_ARROW_DEPTH_YD)],
        profile, layout.total_cells,
        color=color, width=STROKE_COVERAGE, marker_id=MARKER_RUSH,
    )
    return parts


def _render_man_coverage(
    defender: Player,
    covers_player: str | None,
    offensive_formation: Formation | None,
    profile: GameProfile, layout: Layout,
) -> list[str]:
    """Render man-coverage: a dashed arrow to the target plus a ring on the defender."""
    parts: list[str] = []
    dx, dy = defender["x"], defender["y"]

    if covers_player and offensive_formation:
        target = next(
            (p for p in offensive_formation["players"] if p.get("label") == covers_player),
            None,
        )
        if target is not None:
            render_path_yd(
                parts, [(dx, dy), (target["x"], target["y"])],
                profile, layout.total_cells,
                color=COLOR_MAN, width=STROKE_COVERAGE, marker_id=MARKER_MAN,
                dashed=True,
            )

    cx, cy = universal_to_pixel(dx, dy, profile, layout.total_cells)
    parts.append(svg_circle(
        cx, cy, DEFENSE_MARKER_SIZE_PX * MAN_RING_RADIUS_FACTOR,
        fill="none", stroke=COLOR_MAN, stroke_width=STROKE_MAN_RING,
        stroke_dasharray="4,3",
    ))
    return parts


def _render_spy_coverage(
    defender: Player,
    profile: GameProfile, layout: Layout,
) -> list[str]:
    """Render a translucent ring marking a spy / robber assignment."""
    cx, cy = universal_to_pixel(defender["x"], defender["y"], profile, layout.total_cells)
    return [svg_circle(
        cx, cy, DEFENSE_MARKER_SIZE_PX * SPY_RING_RADIUS_FACTOR,
        fill=COLOR_SPY, stroke=COLOR_SPY,
        fill_opacity=OPACITY_ZONE_FILL, stroke_width=STROKE_SPY_RING,
        stroke_dasharray="2,2",
    )]


def _zone_drop_geometry(
    role: str, defender: Player,
) -> tuple[PointYd, float, float, str]:
    """Compute `(drop_point_yd, radius_x_yd, radius_y_yd, color)` for a zone role."""
    dx, dy = defender["x"], defender["y"]

    if role == CoverageRole.DEEP_ZONE:
        return (
            (dx, max(dy, DEEP_ZONE_MIN_DEPTH_YD) + DEEP_ZONE_PUSH_YD),
            DEEP_ZONE_RX_YD, DEEP_ZONE_RY_YD, COLOR_DEEP_ZONE,
        )
    if role == CoverageRole.FLAT:
        sign = 1 if dx >= 0 else -1
        return (
            (dx + sign * FLAT_ZONE_PUSH_YD, max(dy - FLAT_ZONE_DROP_BACK_YD, FLAT_ZONE_MIN_DEPTH_YD)),
            FLAT_ZONE_RX_YD, FLAT_ZONE_RY_YD, COLOR_ZONE,
        )
    if role in HOOK_LIKE_ROLES:
        return (
            (dx, max(dy + HOOK_ZONE_PUSH_YD, HOOK_ZONE_MIN_DEPTH_YD)),
            HOOK_ZONE_RX_YD, HOOK_ZONE_RY_YD, COLOR_ZONE,
        )
    return (
        (dx, dy + DEFAULT_ZONE_PUSH_YD),
        DEFAULT_ZONE_RX_YD, DEFAULT_ZONE_RY_YD, COLOR_ZONE,
    )


def _render_zone_coverage(
    defender: Player, role: str,
    profile: GameProfile, layout: Layout,
) -> list[str]:
    """Render a zone ellipse plus, if the drop is far enough, a dashed drop arrow."""
    parts: list[str] = []
    drop_point, rx, ry, color = _zone_drop_geometry(role, defender)
    render_zone_ellipse(parts, drop_point, rx, ry, color, profile, layout.total_cells)

    drop_x, drop_y = drop_point
    dx, dy = defender["x"], defender["y"]
    if abs(drop_x - dx) > ZONE_ARROW_MIN_OFFSET_YD or abs(drop_y - dy) > ZONE_ARROW_MIN_OFFSET_YD:
        render_path_yd(
            parts, [(dx, dy), (drop_x, drop_y)],
            profile, layout.total_cells,
            color=color, width=STROKE_COVERAGE * STROKE_ZONE_ARROW_FACTOR,
            marker_id=MARKER_ZONE, dashed=True,
        )
    return parts


def _render_defender_coverage(
    defender: Player, role: str,
    covers_player: str | None,
    offensive_formation: Formation | None,
    profile: GameProfile, layout: Layout,
) -> list[str]:
    """Dispatch a defender's coverage assignment to its specialized renderer."""
    if role in RUSH_ROLES:
        return _render_rush_coverage(defender, role, profile, layout)
    if role in MAN_ROLES and covers_player and offensive_formation:
        return _render_man_coverage(defender, covers_player, offensive_formation, profile, layout)
    if role in SPY_ROLES:
        return _render_spy_coverage(defender, profile, layout)
    if role in ZONE_ROLES:
        return _render_zone_coverage(defender, role, profile, layout)
    return []


def _render_defense(
    defense: Formation,
    formation: Formation | None,
    profile: GameProfile, layout: Layout,
    show: str,
) -> list[str]:
    """Render every defender plus, if `show` permits, their coverage assignments."""
    parts: list[str] = []
    defense_cells = assign_cells_for_formation(defense, profile)

    for defender in defense.get("players", []):
        cell = defense_cells.get(defender.get("label"))
        parts.extend(_render_defender(defender, profile, layout, cell))  # type: ignore[arg-type]

    if show not in (Show.DEFENSE, Show.BOTH):
        return parts

    responsibilities_by_player = {
        resp.get("player"): resp for resp in defense.get("responsibilities", [])
    }
    for defender in defense.get("players", []):
        resp = responsibilities_by_player.get(defender.get("label"))
        if resp is None:
            continue
        parts.extend(_render_defender_coverage(
            defender,
            resp.get("role", ""),
            resp.get("covers_player"),
            formation,
            profile, layout,
        ))
    return parts


# ============================================================================
# 14d. Component renderers -- offensive routes & players
# ============================================================================

def _render_route_assignment(
    parts: list[str],
    warnings: list[str],
    assignment: Assignment,
    player: Player,
    formation: Formation,
    play: Play,
    profile: GameProfile, layout: Layout,
    route_lib: RouteLibrary,
) -> None:
    """Render the route polyline and optional beats-coverage badge for a receiver."""
    route_name = assignment.get("route_name")
    if not route_name:
        return
    route = route_lookup(route_lib, route_name)
    if route is None:
        warnings.append(f"unknown route '{route_name}' for {assignment['player']}")
        return

    eff_x, eff_y = player_effective_xy(player, formation, profile)
    path_yd = receiver_route_path(eff_x, eff_y, route)

    color, marker = style_for_player_read(assignment["player"], play)
    is_primary = assignment["player"] == play.get("primary_read")
    route_width = STROKE_ROUTE_PRIMARY if is_primary else STROKE_ROUTE
    render_path_yd(
        parts, path_yd, profile, layout.total_cells,
        color=color, width=route_width, marker_id=marker,
    )

    beats = assignment.get("beats_coverage") or route.get("beats_coverage")
    if beats and path_yd:
        last_px, last_py = universal_to_pixel(*path_yd[-1], profile, layout.total_cells)
        parts.append(svg_text(
            last_px + BEAT_BADGE_OFFSET_X_PX,
            last_py - BEAT_BADGE_OFFSET_Y_PX,
            beats_coverage_badge(beats),
            font_size=FONT_BEAT_BADGE, fill=COLOR_TEXT_PRIMARY, font_weight="bold",
            stroke=COLOR_TEXT_DARK, stroke_width=STROKE_BEAT_BADGE_OUTLINE,
        ))


def _render_explicit_path(
    parts: list[str],
    assignment: Assignment,
    player: Player,
    formation: Formation,
    play: Play,
    profile: GameProfile, layout: Layout,
) -> None:
    """Render a manually-authored path (run path, FB lead, pull, fake, pass-block).

    Silently no-ops when the assignment has no `path` field or when the path
    has fewer than 2 waypoints (a degenerate path can't be rendered as a
    polyline).  This is a deliberate fail-safe at the assignment-data
    boundary; bug-finding callers (the synthetic test fixtures, `render()`)
    have already validated the play before reaching here.
    """
    explicit_path = assignment.get("path")
    if not explicit_path or len(explicit_path) < 2:
        return
    eff_x, eff_y = player_effective_xy(player, formation, profile)
    waypoints = [(eff_x + wp[0], eff_y + wp[1]) for wp in explicit_path]

    color, width, marker, dashed = explicit_path_style(
        assignment.get("role", ""),
        player.get("position", ""),
        assignment["player"],
        play,
    )
    render_path_yd(
        parts, waypoints, profile, layout.total_cells,
        color=color, width=width, marker_id=marker, dashed=dashed,
    )


def _render_alt_paths(
    parts: list[str],
    assignment: Assignment,
    player: Player,
    formation: Formation,
    profile: GameProfile, layout: Layout,
) -> None:
    """Render any auxiliary paths (option branches, secondary reads) for an assignment.

    Skips alts with no path or fewer than 2 waypoints — same fail-safe
    rationale as `_render_explicit_path`.
    """
    for alt in assignment.get("alt_paths", []):
        path = alt.get("path") or []
        if len(path) < 2:
            continue
        color, marker = style_for_alt_path_priority(alt.get("priority", ""))
        eff_x, eff_y = player_effective_xy(player, formation, profile)
        waypoints = [(eff_x + wp[0], eff_y + wp[1]) for wp in path]
        render_path_yd(
            parts, waypoints, profile, layout.total_cells,
            color=color, width=STROKE_ALT_PATH, marker_id=marker,
        )


def _render_offensive_assignments(
    play: Play, formation: Formation,
    route_lib: RouteLibrary,
    profile: GameProfile, layout: Layout,
) -> tuple[list[str], list[str]]:
    """Render every offensive assignment (routes + explicit paths + alt paths).

    Returns `(svg_parts, warnings)`.
    """
    parts: list[str] = []
    warnings: list[str] = []
    formation_by_label = {p["label"]: p for p in formation["players"]}

    for assignment in play.get("assignments", []):
        player = formation_by_label.get(assignment["player"])
        if player is None:
            continue
        _render_explicit_path(parts, assignment, player, formation, play, profile, layout)
        _render_alt_paths(parts, assignment, player, formation, profile, layout)
        if assignment.get("role") == "route":
            _render_route_assignment(
                parts, warnings, assignment, player,
                formation, play, profile, layout, route_lib,
            )
    return parts, warnings


def _check_player_bounds(
    player: Player, gx: float, gy: float,
    layout: Layout, limits: dict,
) -> tuple[bool, list[str]]:
    """Return `(in_bounds, warnings)` after checking editor-grid and limits."""
    assert "label" in player, "_check_player_bounds: player missing 'label'"
    assert math.isfinite(gx) and math.isfinite(gy), \
        f"_check_player_bounds: gx={gx}, gy={gy} must both be finite"
    in_x = 0 <= gx <= layout.width_cells
    in_y_editor = 0 <= gy <= layout.height_cells
    in_bounds = in_x and in_y_editor
    warnings: list[str] = []
    label = player["label"]

    if not in_bounds:
        warnings.append(
            f"{label} ({player['x']:.1f}, {player['y']:.1f}) "
            f"outside editor grid (cell {gx:.1f}, {gy:.1f})"
        )

    max_split = limits.get("max_player_split_yd")
    if max_split is not None and abs(player["x"]) > max_split:
        warnings.append(
            f"{label} split {abs(player['x']):.1f} yd > "
            f"editor max ({max_split} yd)"
        )

    max_back = limits.get("max_backfield_depth_yd")
    if max_back is not None and player["y"] < -max_back:
        warnings.append(
            f"{label} backfield depth {abs(player['y']):.1f} yd > "
            f"editor max ({max_back} yd)"
        )
    return in_bounds, warnings


def _render_read_priority_badge(
    px: float, py: float, badge: tuple[str, str],
) -> list[str]:
    """Emit the small read-priority badge in the player marker's top-right corner."""
    text, color = badge
    half = OFFENSE_MARKER_SIZE_PX / 2
    bx = px + half + 2  # 2px gap between marker and badge
    by = py - half + 2
    width = BADGE_CHAR_WIDTH_PX * len(text) + BADGE_HORIZONTAL_PAD_PX
    return [
        svg_rect(
            bx - 1, by - (BADGE_HEIGHT_PX - 2), width, BADGE_HEIGHT_PX,
            fill=color, stroke=COLOR_TEXT_PRIMARY, stroke_width=STROKE_BADGE_BORDER,
            rx=2,
        ),
        svg_text(
            bx + (BADGE_CHAR_WIDTH_PX // 2) * len(text) + 1, by - 1, text,
            font_size=FONT_BADGE, fill=COLOR_KEY_PLAYER_TEXT,
            font_weight="bold", text_anchor="middle",
        ),
    ]


def _render_offensive_player(
    player: Player,
    formation: Formation,
    profile: GameProfile, layout: Layout,
    play: Play | None,
    limits: dict,
) -> tuple[list[str], list[str]]:
    """Render one offensive player marker, label, badge, and bounds warnings."""
    assert "label" in player, "_render_offensive_player: player missing 'label'"
    assert isinstance(limits, dict), \
        f"_render_offensive_player: limits must be dict, got {type(limits).__name__}"
    gx, gy = player_grid_pos(player, formation, profile)
    px, py = grid_to_pixel(gx, gy, layout.total_cells)

    in_bounds, warnings = _check_player_bounds(player, gx, gy, layout, limits)
    label = player["label"]
    fill = offensive_player_fill(label, in_bounds, play)
    text_color = offensive_player_text_color(label, in_bounds, play)
    is_square = player.get("position", "") in INTERIOR_OL

    parts = _render_player_marker(
        px, py, label, fill, OFFENSE_MARKER_SIZE_PX,
        is_square=is_square, label_color=text_color,
        border_width=STROKE_PLAYER_BORDER,
    )

    badge = player_badge_text(label, play)
    if badge:
        parts.extend(_render_read_priority_badge(px, py, badge))
    return parts, warnings


def _render_offensive_players(
    formation: Formation,
    profile: GameProfile, layout: Layout,
    play: Play | None,
    limits: dict,
) -> tuple[list[str], list[str]]:
    """Render every offensive player and collect bounds warnings."""
    parts: list[str] = []
    warnings: list[str] = []
    for player in formation["players"]:
        player_parts, player_warnings = _render_offensive_player(
            player, formation, profile, layout, play, limits,
        )
        parts.extend(player_parts)
        warnings.extend(player_warnings)
    return parts, warnings


# ============================================================================
# 14e. Component renderers -- legend, warnings, coaching notes
# ============================================================================

def _legend_items(
    play: Play | None,
    formation: Formation | None,
    defense: Formation | None,
    show: str,
) -> list[tuple[str, str]]:
    """Build the list of `(color, label)` pairs for the legend strip."""
    items: list[tuple[str, str]] = []
    if play and formation and show in (Show.OFFENSE, Show.BOTH):
        items += [
            (COLOR_PRIMARY_READ,   "1°/run"),
            (COLOR_SECONDARY_READ, "2°"),
            (COLOR_TERTIARY_READ,  "3°"),
            (COLOR_CHECKDOWN,      "C/checkdown"),
            (COLOR_FB_LEAD,        "FB lead"),
            (COLOR_PULL,           "pull"),
            (COLOR_ROUTE,          "route"),
        ]
    if defense:
        items.append((COLOR_DEFENSE, "defense"))
        if show in (Show.DEFENSE, Show.BOTH):
            items += [
                (COLOR_RUSH,      "rush"),
                (COLOR_ZONE,      "zone"),
                (COLOR_DEEP_ZONE, "deep zone"),
                (COLOR_MAN,       "man"),
                (COLOR_SPY,       "spy"),
            ]
    return items


def _render_legend(
    layout: Layout,
    play: Play | None,
    formation: Formation | None,
    defense: Formation | None,
    show: str,
) -> list[str]:
    """Render the dark legend strip below the field."""
    parts: list[str] = [
        svg_rect(0, layout.legend_top_y, layout.total_w, LEGEND_STRIP_HEIGHT_PX, fill=COLOR_LEGEND_BG),
    ]
    cursor_x = LEGEND_START_X_PX
    for color, label in _legend_items(play, formation, defense, show):
        parts.append(svg_rect(
            cursor_x, layout.legend_top_y + LEGEND_SWATCH_Y_OFFSET_PX,
            LEGEND_SWATCH_SIZE_PX, LEGEND_SWATCH_SIZE_PX, fill=color,
        ))
        parts.append(svg_text(
            cursor_x + LEGEND_TEXT_X_GAP_PX,
            layout.legend_top_y + LEGEND_TEXT_Y_OFFSET_PX,
            label,
            font_size=FONT_LEGEND, fill=COLOR_TEXT_LIGHT,
        ))
        cursor_x += (
            LEGEND_TEXT_X_GAP_PX + LEGEND_SWATCH_SIZE_PX
            + len(label) * LEGEND_TEXT_CHAR_WIDTH_PX + LEGEND_ITEM_END_PAD_PX
        )
    return parts


def _render_warnings_strip(layout: Layout, warnings: list[str]) -> list[str]:
    """Render the warnings strip, listing up to MAX_WARNINGS_DISPLAYED entries."""
    parts: list[str] = [
        svg_rect(0, layout.warnings_top_y, layout.total_w, WARNINGS_STRIP_HEIGHT_PX, fill=COLOR_BG_OUTER),
    ]

    if not warnings:
        parts.append(svg_text(
            WARNING_HEADER_X_PX, layout.warnings_top_y + NO_WARNING_Y_PX,
            "OK — all positions within editor limits.",
            font_size=FONT_WARNING_HEADER, fill=COLOR_OK,
        ))
        return parts

    parts.append(svg_text(
        WARNING_HEADER_X_PX, layout.warnings_top_y + WARNING_HEADER_Y_PX,
        f"{len(warnings)} warning(s):",
        font_size=FONT_WARNING_HEADER, fill=COLOR_WARNING, font_weight="bold",
    ))
    for index, warning in enumerate(warnings[:MAX_WARNINGS_DISPLAYED]):
        parts.append(svg_text(
            WARNING_HEADER_X_PX,
            layout.warnings_top_y + WARNING_BODY_FIRST_Y_PX + index * WARNING_BODY_LINE_HEIGHT_PX,
            f"• {warning}",
            font_size=FONT_WARNING_BODY, fill=COLOR_WARNING_BODY,
        ))
    return parts


def _render_coaching_notes(layout: Layout, rows: list[NoteRow]) -> list[str]:
    """Render the coaching-notes box at the bottom of the SVG, if non-empty."""
    if not rows:
        return []

    parts: list[str] = [
        svg_rect(0, layout.notes_top_y, layout.total_w, layout.notes_h, fill=COLOR_NOTES_BG),
        svg_text(
            NOTES_LEFT_PAD_PX, layout.notes_top_y + NOTES_HEADER_TEXT_Y_PX,
            "COACHING NOTES",
            font_size=FONT_NOTES, fill=COLOR_NOTES_HEADER,
            font_weight="bold", letter_spacing=1,
        ),
        svg_line(
            NOTES_LEFT_PAD_PX, layout.notes_top_y + NOTES_DIVIDER_Y_PX,
            layout.total_w - NOTES_RIGHT_PAD_PX, layout.notes_top_y + NOTES_DIVIDER_Y_PX,
            stroke=COLOR_NOTES_DIVIDER, stroke_width=STROKE_NOTES_DIVIDER,
        ),
    ]

    for index, row in enumerate(rows):
        ty = (
            layout.notes_top_y + NOTES_HEADER_HEIGHT_PX + NOTES_VERTICAL_PAD_PX
            + index * NOTES_LINE_HEIGHT_PX
        )
        parts.append(svg_text(
            row.x_px, ty, xml_escape(row.text),
            font_size=FONT_NOTES, fill=row.color,
        ))
    return parts


# ============================================================================
# 15. Top-level render() orchestrator
# ============================================================================

def render(
    profile: GameProfile,
    play: Play | None = None,
    formation: Formation | None = None,
    defense: Formation | None = None,
    route_lib: RouteLibrary | None = None,
    show: str = "both",
    field: str = "long",
) -> tuple[str, list[str]]:
    """Render an SVG representation of a play / formation / defense.

    Any combination of `play`, `formation`, and `defense` may be `None`.

    Args:
        profile: Game profile (`data/games/<id>/editor-grid.yaml`).
        play: Offensive play, or None to skip offensive routes.
        formation: Offensive formation referenced by the play, or None.
        defense: Defensive formation, or None.
        route_lib: Output of `load_route_library()`.  May be None when no play.
        show: Which side's assignments to render -- `"offense"`, `"defense"`,
              `"both"`, or `"none"`.
        field: `"long"` (LOS + 30 yd) or `"short"` (LOS + 15 yd).

    Returns:
        `(svg_string, warnings)`.  `warnings` lists out-of-bounds players, missing
        routes, and other soft validation failures encountered during rendering.

    Raises:
        ValueError: `show` or `field` is outside the allowed enum values.
        InvalidProfileError: `profile` is missing required fields or has invalid types.
        InvalidPlayError: `play` is malformed.
        InvalidFormationError: `formation` or `defense` is malformed.
    """
    _validate_render_inputs(profile, play, formation, defense, show, field)

    notes_max_chars, body_max_chars = _note_layout_chars(_provisional_total_w(profile))
    note_rows = _build_note_rows(play, notes_max_chars, body_max_chars)
    layout = _compute_layout(profile, play, field, note_rows)

    parts: list[str] = [
        _render_svg_header(layout),
        _render_provenance_comment(profile, play, formation, defense),
        _render_marker_defs(),
    ]
    parts.extend(_render_title_strip(layout, profile, play, formation, defense, show))
    parts.append(f'<g transform="translate(0,{layout.field_top_y})">')
    parts.extend(_render_field_chrome(layout, profile, play, formation))

    warnings: list[str] = []
    if defense is not None:
        # Defense first so offense draws on top.
        parts.extend(_render_defense(defense, formation, profile, layout, show))
    parts.extend(_render_play_overlay(
        play, formation, route_lib, show, profile, layout, warnings,
    ))
    parts.extend(_render_all_players(formation, profile, layout, play, warnings))

    parts.append("</g>")
    parts.extend(_render_legend(layout, play, formation, defense, show))
    parts.extend(_render_warnings_strip(layout, warnings))
    parts.extend(_render_coaching_notes(layout, note_rows))
    parts.append("</svg>")
    return "\n".join(parts), warnings


def _validate_render_inputs(
    profile: GameProfile,
    play: Play | None,
    formation: Formation | None,
    defense: Formation | None,
    show: str,
    field: str,
) -> None:
    """Boundary validation for `render()`.  Idempotent and fast on typical inputs."""
    assert isinstance(show, str), f"_validate_render_inputs: show must be string, got {show!r}"
    assert isinstance(field, str), f"_validate_render_inputs: field must be string, got {field!r}"
    _validate_show(show)
    _validate_field(field)
    _validate_profile(profile)
    if play is not None:
        _validate_play(play)
    if formation is not None:
        _validate_formation(formation, kind="offense")
    if defense is not None:
        _validate_formation(defense, kind="defense")


def _render_field_chrome(
    layout: Layout, profile: GameProfile,
    play: Play | None, formation: Formation | None,
) -> list[str]:
    """Render the field background, grid lines, axis labels, hashes, LOS, and depth limit."""
    parts: list[str] = []
    parts.extend(_render_field_background(layout))
    parts.extend(_render_vertical_grid_lines(layout))
    parts.extend(_render_yard_lines(layout, profile))
    parts.extend(_render_horizontal_grid_lines(layout))
    parts.extend(_render_axis_labels(layout))
    parts.extend(_render_hash_marks(layout, profile))
    parts.extend(_render_los(layout, profile))
    parts.extend(_render_depth_limit(layout, profile, play, formation))
    return parts


def _render_play_overlay(
    play: Play | None, formation: Formation | None,
    route_lib: RouteLibrary | None, show: str,
    profile: GameProfile, layout: Layout,
    warnings: list[str],
) -> list[str]:
    """Render offensive routes & explicit paths if all preconditions are met.

    Mutates `warnings` in place to collect route-resolution failures.
    """
    if play is None or formation is None or route_lib is None:
        return []
    if show not in (Show.OFFENSE, Show.BOTH):
        return []
    offense_parts, route_warnings = _render_offensive_assignments(
        play, formation, route_lib, profile, layout,
    )
    warnings.extend(route_warnings)
    return offense_parts


def _render_all_players(
    formation: Formation | None,
    profile: GameProfile, layout: Layout,
    play: Play | None,
    warnings: list[str],
) -> list[str]:
    """Render every offensive player marker (if a formation is provided).

    Mutates `warnings` in place to collect bounds-violation messages.
    """
    if formation is None:
        return []
    limits = profile.get("limits") or {}
    player_parts, player_warnings = _render_offensive_players(
        formation, profile, layout, play, limits,
    )
    warnings.extend(player_warnings)
    return player_parts


def _provisional_total_w(profile: GameProfile) -> int:
    """Compute the SVG total width before the full layout is built.

    The note-row builder needs the wrap-width to soft-wrap long passages, but
    `_compute_layout` needs the note rows to know how tall the SVG is.  Since
    width depends only on the editor cell count and the field margin, we can
    compute it standalone here without circular dependency.
    """
    return profile["grid"]["width"] * PIXELS_PER_CELL + 2 * FIELD_MARGIN_PX


# ============================================================================
# 16. CLI: argument parsing and main()
# ============================================================================

def _build_arg_parser() -> argparse.ArgumentParser:
    """Construct the argparse parser for the draw-play CLI."""
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
        choices=[s.value for s in Show],
        default=Show.BOTH.value,
        help="Which side's assignments (routes / coverage) to render. Default: both.",
    )
    parser.add_argument(
        "--field",
        choices=[f.value for f in Field],
        default=Field.LONG.value,
        help="Downfield field length: short = LOS+15yd, long = LOS+30yd. Default: long.",
    )
    parser.add_argument("-o", "--output", help="SVG output path (default: stdout)")
    return parser


class _CliInputs(NamedTuple):
    """Resolved inputs from the CLI: profile + optional play/formation/defense."""
    profile: GameProfile
    play: Play | None
    formation: Formation | None
    defense: Formation | None


def _resolve_inputs(args: argparse.Namespace) -> _CliInputs:
    """Load every YAML file referenced by the CLI arguments.

    Raises:
        FileNotFoundError: If any referenced file does not exist.
    """
    play_id = args.play or args.play_id_pos
    game_id = args.game or args.game_id_pos
    defense_id = args.defense or args.vs_defense

    if not game_id:
        raise SystemExit("error: must provide --game or positional game_id")
    if not play_id and not defense_id:
        raise SystemExit("error: must provide at least --play or --defense (or positional play_id)")

    profile_path = GAMES_DIR / game_id / "editor-grid.yaml"
    if not profile_path.exists():
        raise FileNotFoundError(f"Game profile not found: {profile_path}")
    profile: GameProfile = load_yaml(profile_path)  # type: ignore[assignment]
    _validate_profile(profile)

    play: Play | None = None
    formation: Formation | None = None
    if play_id:
        play_path = PLAYS_DIR / f"{play_id}.yaml"
        if not play_path.exists():
            raise FileNotFoundError(f"Play not found: {play_path}")
        play = load_yaml(play_path)  # type: ignore[assignment]
        _validate_play(play)
        formation_path = FORMATIONS_DIR / f"{play['formation']}.yaml"
        if not formation_path.exists():
            raise FileNotFoundError(f"Formation not found: {formation_path}")
        formation = load_yaml(formation_path)  # type: ignore[assignment]
        _validate_formation(formation, kind="offense")
        if not defense_id:
            defense_id = play.get("vs_defense")

    defense: Formation | None = None
    if defense_id:
        def_path = FORMATIONS_DIR / f"{defense_id}.yaml"
        if not def_path.exists():
            raise FileNotFoundError(f"Defense not found: {def_path}")
        defense = load_yaml(def_path)  # type: ignore[assignment]
        _validate_formation(defense, kind="defense")
    return _CliInputs(profile=profile, play=play, formation=formation, defense=defense)


def _configure_logging() -> None:
    """Configure the module's logger to emit timestamped records to stderr.

    Idempotent: if a handler is already attached (e.g., by the test harness
    or a parent application embedding this module), no duplicate is added.
    """
    if logger.handlers:
        return
    handler = logging.StreamHandler(stream=sys.stderr)
    handler.setFormatter(logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
    ))
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)


def _resolve_inputs_safe(args: argparse.Namespace) -> tuple[_CliInputs | None, int]:
    """Wrap `_resolve_inputs` with structured exit-code mapping.

    Returns:
        `(inputs, 0)` on success, `(None, exit_code)` on a controlled failure.
    """
    try:
        return _resolve_inputs(args), 0
    except SystemExit as err:
        logger.error("%s", err)
        return None, 2
    except FileNotFoundError as err:
        logger.error("%s", err)
        return None, 1
    except ConfigError as err:
        logger.error("config error: %s", err)
        return None, 3


def _render_safe(
    inputs: _CliInputs, args: argparse.Namespace,
) -> tuple[str | None, list[str], int]:
    """Wrap `render()` + `load_route_library()` with structured exit-code mapping.

    Returns:
        `(svg, warnings, 0)` on success; `(None, [], exit_code)` on failure.
    """
    try:
        route_lib = load_route_library()
        svg, warnings = render(
            inputs.profile,
            play=inputs.play,
            formation=inputs.formation,
            defense=inputs.defense,
            route_lib=route_lib,
            show=args.show,
            field=args.field,
        )
        return svg, warnings, 0
    except DrawError as err:
        logger.error("%s", err)
        return None, [], 3
    except ValueError as err:
        # Bad --show / --field value reaching render() (defence-in-depth;
        # argparse should normally catch these via its `choices=` parameter).
        logger.error("%s", err)
        return None, [], 2
    except Exception as err:  # pylint: disable=broad-except
        # No unhandled exception may escape main() (NASA convention).
        logger.exception("unexpected failure during render: %s", err)
        return None, [], 99


def _emit_output(svg: str, warnings: list[str], output_path: str | None) -> None:
    """Write the SVG to file or stdout; emit warnings via the logger."""
    if output_path:
        out_path = Path(output_path)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(svg, encoding="utf-8")
        # Status line stays on stdout (caller may pipe it); not a log record.
        print(f"Wrote {out_path} ({len(warnings)} warnings)")
    else:
        # SVG is the primary product — must be on stdout.
        print(svg)
    for warning in warnings:
        logger.warning("%s", warning)


def main() -> int:
    """CLI entrypoint: parse args, render, write output, return process exit code.

    Exit codes:
        0 — success
        1 — referenced file (play / formation / defense / profile) does not exist
        2 — invalid CLI argument combination (caught by argparse / `_resolve_inputs`)
        3 — config file is malformed (invalid YAML, wrong shape) or input data
            fails domain validation (`Invalid*Error`)
        99 — unexpected / unclassified error
    """
    _configure_logging()
    parser = _build_arg_parser()
    args = parser.parse_args()

    inputs, code = _resolve_inputs_safe(args)
    if inputs is None:
        return code

    svg, warnings, code = _render_safe(inputs, args)
    if svg is None:
        return code

    _emit_output(svg, warnings, args.output)
    return 0


if __name__ == "__main__":
    sys.exit(main())
