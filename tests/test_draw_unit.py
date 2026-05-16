"""Tier 1 unit tests for tools/draw-play/draw.py — pure-function coverage.

Exercises the deterministic helpers that have no SVG side-effect:
  - hash_spec_for_profile
  - route_lookup
  - receiver_route_path (mirroring)
  - universal_to_grid / grid_to_pixel
  - assign_cells_for_formation (snap modes, integer guarantee, no-overlap guarantee)
  - style helpers (style_for_player_read, offensive_player_fill, player_badge_text,
    explicit_path_style)

These tests defend against regressions that the existing golden-SVG smoke tests
in test_draw_tool.py would silently miss.
"""
from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
DRAW_PATH = REPO_ROOT / "tools" / "draw-play" / "draw.py"
GAMES_DIR = REPO_ROOT / "data" / "games"
FORMATIONS_DIR = REPO_ROOT / "data" / "formations"


def _import_draw():
    """Load draw.py as a standalone module (matches test_draw_tool.py's pattern)."""
    spec = importlib.util.spec_from_file_location("draw_play", DRAW_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# Module-level cache so each TestCase doesn't pay the import cost.
_DRAW = _import_draw()


def _make_profile(
    *,
    origin_x: int = 10,
    origin_y: int = 5,
    width: int = 21,
    height: int = 7,
    x_yards_per_cell: float = 1.667,
    y_yards_per_cell: float = 2.0,
    snap_to_cells: bool = True,
    game_id: str = "test-profile",
    hash_marks_yd_from_center: float | None = None,
) -> dict:
    """Construct a minimal game profile for unit testing."""
    profile = {
        "game_id": game_id,
        "grid": {"origin": {"x": origin_x, "y": origin_y}, "width": width, "height": height},
        "scale": {"x_yards_per_cell": x_yards_per_cell, "y_yards_per_cell": y_yards_per_cell},
        "snap_to_cells": snap_to_cells,
    }
    if hash_marks_yd_from_center is not None:
        profile["hash_marks_yd_from_center"] = hash_marks_yd_from_center
    return profile


# ============================================================================
# TestHashSpec — hash_spec_for_profile
# ============================================================================

class TestHashSpec(unittest.TestCase):
    """Verify hash-mark inference handles explicit overrides and prefix fallbacks."""

    def test_explicit_override_wins_over_game_id(self):
        # Even with a Madden game_id, an explicit override must take precedence.
        profile = _make_profile(game_id="madden-05-ps2", hash_marks_yd_from_center=5.0)
        self.assertEqual(_DRAW.hash_spec_for_profile(profile), (-5.0, 5.0))

    def test_madden_prefix_returns_nfl_hashes(self):
        profile = _make_profile(game_id="madden-05-ps2")
        spec = _DRAW.hash_spec_for_profile(profile)
        self.assertIsNotNone(spec)
        self.assertAlmostEqual(spec[0], -3.083, places=3)
        self.assertAlmostEqual(spec[1], 3.083, places=3)

    def test_ncaa_prefix_returns_ncaa_hashes(self):
        profile = _make_profile(game_id="ncaa-06-ps2")
        spec = _DRAW.hash_spec_for_profile(profile)
        self.assertIsNotNone(spec)
        self.assertAlmostEqual(spec[1], 6.667, places=3)

    def test_hs_prefix_returns_hs_hashes(self):
        profile = _make_profile(game_id="hs-football")
        spec = _DRAW.hash_spec_for_profile(profile)
        self.assertIsNotNone(spec)
        self.assertAlmostEqual(spec[1], 8.889, places=3)

    def test_unknown_prefix_returns_none(self):
        # A future game with an unrecognized prefix and no explicit override
        # must return None so the renderer can omit hash marks rather than guess.
        profile = _make_profile(game_id="xfl-23-ps5")
        self.assertIsNone(_DRAW.hash_spec_for_profile(profile))


# ============================================================================
# TestRouteResolution — route_lookup
# ============================================================================

class TestRouteResolution(unittest.TestCase):
    """Verify route name resolution handles aliases and option-route fallbacks."""

    def _route(self, name: str) -> dict:
        return {"name": name, "path": [[0, 0], [1, 5]]}

    def test_direct_name_hit(self):
        lib = {"slant": self._route("slant")}
        result = _DRAW.route_lookup(lib, "slant")
        self.assertIsNotNone(result)
        self.assertEqual(result["name"], "slant")

    def test_alias_lookup(self):
        # load_route_library() indexes aliases; route_lookup should find via alias key.
        slant = self._route("slant")
        lib = {"slant": slant, "slant-3": slant, "quick-slant": slant}
        self.assertIs(_DRAW.route_lookup(lib, "slant-3"), slant)
        self.assertIs(_DRAW.route_lookup(lib, "quick-slant"), slant)

    def test_or_fallback_resolves_first_branch(self):
        # "X or Y" option routes resolve to the first branch.
        snag = self._route("snag")
        lib = {"snag": snag}
        result = _DRAW.route_lookup(lib, "snag or stick")
        self.assertIs(result, snag)

    def test_dash_or_fallback_resolves_first_branch(self):
        snag = self._route("snag")
        lib = {"snag": snag}
        result = _DRAW.route_lookup(lib, "snag-or-stick")
        self.assertIs(result, snag)

    def test_unknown_route_returns_none(self):
        # No match, no "or" separator — unresolvable.
        self.assertIsNone(_DRAW.route_lookup({"slant": self._route("slant")}, "unicorn"))


# ============================================================================
# TestRouteMirroring — receiver_route_path
# ============================================================================

class TestRouteMirroring(unittest.TestCase):
    """Verify routes mirror correctly based on the receiver's universal X."""

    def test_right_side_receiver_mirrors_x(self):
        # Receiver at +10 (offensive right) — a route that breaks +3 toward the
        # right hash should instead break -3 (back toward the middle of the field).
        route = {"path": [[3, 5]]}
        waypoints = _DRAW.receiver_route_path(10.0, 0.0, route)
        self.assertEqual(waypoints, [(7.0, 5.0)])

    def test_left_side_receiver_preserves_x(self):
        # Receiver at -10 (offensive left) — route is authored as right-side
        # break, so X is preserved (the break runs +3, taking the receiver
        # back toward the middle of the field).
        route = {"path": [[3, 5]]}
        waypoints = _DRAW.receiver_route_path(-10.0, 0.0, route)
        self.assertEqual(waypoints, [(-7.0, 5.0)])

    def test_te_at_zero_does_not_mirror(self):
        # A TE on the +0.0 yard line is below the 0.1 mirror threshold — its
        # routes must not mirror, otherwise a TE on-line would render its
        # break in the wrong direction.
        route = {"path": [[3, 5]]}
        waypoints = _DRAW.receiver_route_path(0.0, 0.0, route)
        self.assertEqual(waypoints, [(3.0, 5.0)])


# ============================================================================
# TestCoordinateMath — universal_to_grid, grid_to_pixel, total_y_cells
# ============================================================================

class TestCoordinateMath(unittest.TestCase):
    """Verify coordinate transformations for football-yards <-> grid-cells <-> SVG-pixels."""

    def test_universal_origin_maps_to_grid_origin(self):
        # (0, 0) in universal yards is the LOS-center, which maps to the
        # game profile's grid origin in editor cells.
        profile = _make_profile(origin_x=10, origin_y=5)
        gx, gy = _DRAW.universal_to_grid(0.0, 0.0, profile)
        self.assertEqual((gx, gy), (10, 5))

    def test_universal_to_grid_uses_per_axis_scale(self):
        # The X and Y scales are independent — test with different values to
        # verify they're not swapped.
        profile = _make_profile(
            origin_x=10, origin_y=5,
            x_yards_per_cell=2.0, y_yards_per_cell=4.0,
        )
        gx, gy = _DRAW.universal_to_grid(4.0, 8.0, profile)
        # X: 10 + 4.0/2.0 = 12.0;  Y: 5 + 8.0/4.0 = 7.0
        self.assertAlmostEqual(gx, 12.0)
        self.assertAlmostEqual(gy, 7.0)

    def test_grid_to_pixel_y_inverted(self):
        # Y in grid space increases downfield; Y in pixel space decreases
        # downfield (top of SVG = high Y).  Same column should give same X.
        px_los, py_los = _DRAW.grid_to_pixel(5, 0, total_cells=10)
        px_deep, py_deep = _DRAW.grid_to_pixel(5, 10, total_cells=10)
        self.assertEqual(px_los, px_deep)
        self.assertLess(py_deep, py_los, "downfield (higher gy) must produce smaller py")


# ============================================================================
# TestCellAssignment — assign_cells_for_formation
# ============================================================================

class TestCellAssignment(unittest.TestCase):
    """Verify cell-assignment respects snap mode, produces no overlaps, and gives integers when snapping."""

    # Loaded once at class scope: each YAML is parsed only once across all tests.
    _snapping_profiles: list[tuple[str, dict]] = []
    _formations: list[tuple[str, dict]] = []

    @classmethod
    def setUpClass(cls):
        for game_dir in sorted(GAMES_DIR.iterdir()):
            if not game_dir.is_dir():
                continue
            profile_path = game_dir / "editor-grid.yaml"
            if not profile_path.exists():
                continue
            profile = yaml.safe_load(profile_path.read_text())
            if profile.get("snap_to_cells"):
                cls._snapping_profiles.append((game_dir.name, profile))
        for fp in sorted(FORMATIONS_DIR.glob("*.yaml")):
            cls._formations.append((fp.stem, yaml.safe_load(fp.read_text())))

    def test_non_snap_profile_returns_fractional_cells(self):
        # When snap_to_cells is False, cells come straight from
        # universal_to_grid (no rounding, no BFS).  A non-cluster player at a
        # fractional yard offset must come back as a fractional cell.
        profile = _make_profile(snap_to_cells=False)
        formation = {
            "side": "offense",
            "players": [
                {"label": "QB", "position": "QB", "x": 0.5, "y": -2.5},
            ],
        }
        cells = _DRAW.assign_cells_for_formation(formation, profile)
        qb_cell = cells["QB"]
        # X: 10 + 0.5/1.667 ≈ 10.30  (must remain float, not rounded)
        self.assertNotEqual(qb_cell[0], round(qb_cell[0]),
                            "non-snap profile must leave non-integer x as float")

    def test_snapping_profiles_no_overlaps_and_integer_cells(self):
        # Combined cross-profile sweep — checks both invariants in one pass over
        # ~35 profiles × ~150 formations = ~5k assignments.  Splitting into two
        # tests would double the runtime without adding diagnostic value (the
        # subTest output already pinpoints the failing combination).
        for game_id, profile in self._snapping_profiles:
            for formation_id, formation in self._formations:
                with self.subTest(game=game_id, formation=formation_id):
                    cells = _DRAW.assign_cells_for_formation(formation, profile)
                    cell_list = [tuple(c) for c in cells.values()]
                    self.assertEqual(
                        len(set(cell_list)), len(cell_list),
                        "duplicate cells",
                    )
                    for label, cell in cells.items():
                        self.assertIsInstance(cell[0], int, f"{label} col not int")
                        self.assertIsInstance(cell[1], int, f"{label} row not int")


# ============================================================================
# TestStyleHelpers — pure mappings from play state to (color, marker, etc.)
# ============================================================================

class TestStyleHelpers(unittest.TestCase):
    """Verify the style-selection helpers that were duplicated 3x before the refactor."""

    def test_style_for_player_read_each_priority(self):
        # Each read-priority field must map to its corresponding (color, marker)
        # pair.  This is the helper that replaced the 3x-duplicated if/elif chain.
        play = {
            "primary_read":   "TE",
            "secondary_read": "Z",
            "tertiary_read":  "X",
            "checkdown":      "HB",
        }
        cases = [
            ("TE", _DRAW.COLOR_PRIMARY_READ,   _DRAW.MARKER_PRIMARY),
            ("Z",  _DRAW.COLOR_SECONDARY_READ, _DRAW.MARKER_SECONDARY),
            ("X",  _DRAW.COLOR_TERTIARY_READ,  _DRAW.MARKER_TERTIARY),
            ("HB", _DRAW.COLOR_CHECKDOWN,      _DRAW.MARKER_CHECKDOWN),
        ]
        for label, color, marker in cases:
            with self.subTest(label=label):
                self.assertEqual(_DRAW.style_for_player_read(label, play), (color, marker))

    def test_style_for_player_read_fallback(self):
        # Players not in the read tree, and the no-play case, fall back to
        # the generic-route style.
        play = {"primary_read": "TE"}
        self.assertEqual(
            _DRAW.style_for_player_read("LT", play),
            (_DRAW.COLOR_ROUTE, _DRAW.MARKER_ARROW),
        )
        self.assertEqual(
            _DRAW.style_for_player_read("TE", None),
            (_DRAW.COLOR_ROUTE, _DRAW.MARKER_ARROW),
        )

    def test_offensive_player_fill_priority_order(self):
        # The fill-color priority (highest wins): out-of-bounds > C > ball_carrier
        # > primary_read > default offense.  This order matters: a C who is
        # also the ball_carrier must still render as C-orange, not BC-orange.
        play = {"ball_carrier": "C", "primary_read": "TE"}
        # OOB always wins, even for C.
        self.assertEqual(
            _DRAW.offensive_player_fill("C", in_bounds=False, play=play),
            _DRAW.COLOR_OUT_OF_BOUNDS,
        )
        # C wins over ball_carrier when label is also C.
        self.assertEqual(
            _DRAW.offensive_player_fill("C", in_bounds=True, play=play),
            _DRAW.COLOR_C,
        )
        # Primary read wins for non-C.
        self.assertEqual(
            _DRAW.offensive_player_fill("TE", in_bounds=True, play=play),
            _DRAW.COLOR_PRIMARY_READ_PLAYER,
        )
        # Default offense for everyone else.
        self.assertEqual(
            _DRAW.offensive_player_fill("LT", in_bounds=True, play=play),
            _DRAW.COLOR_OFFENSE,
        )

    def test_player_badge_text_excludes_c_from_bc_badge(self):
        # The C always carries the snap, so a "BC" badge on the C is noise —
        # it must be suppressed even when the play declares C as ball carrier.
        self.assertIsNone(_DRAW.player_badge_text("C", {"ball_carrier": "C"}))

        # Other ball carriers do get the BC badge.
        result = _DRAW.player_badge_text("HB", {"ball_carrier": "HB"})
        self.assertIsNotNone(result)
        self.assertEqual(result[0], "BC")

        # Read-priority badges win over BC when both apply.
        play = {"ball_carrier": "TE", "primary_read": "TE"}
        result = _DRAW.player_badge_text("TE", play)
        self.assertEqual(result[0], "1°")

    def test_explicit_path_style_pulling_guard_distinct_from_lead(self):
        # Pulling guard (role=run_block, position in INTERIOR_OL) must use
        # the pull-green color and marker, not the FB-pink lead-block style.
        # This was a duplication-risk path that the refactor pulled into a
        # single helper; this test catches a swapped-color regression.
        pull_color, _, pull_marker, _ = _DRAW.explicit_path_style(
            "run_block", "LG", "LG", play={},
        )
        self.assertEqual(pull_color, _DRAW.COLOR_PULL)
        self.assertEqual(pull_marker, _DRAW.MARKER_PULL)

        lead_color, _, lead_marker, _ = _DRAW.explicit_path_style(
            "lead_block", "FB", "FB", play={},
        )
        self.assertEqual(lead_color, _DRAW.COLOR_FB_LEAD)
        self.assertEqual(lead_marker, _DRAW.MARKER_FB_LEAD)
        self.assertNotEqual(pull_color, lead_color)

    def test_explicit_path_style_fake_is_dashed(self):
        # PA fakes are dashed; nothing else is.
        _, _, _, fake_dashed = _DRAW.explicit_path_style(
            "fake", "HB", "HB", play={},
        )
        self.assertTrue(fake_dashed)
        for role in ("run_block", "lead_block", "pass_block", "ball_carrier"):
            with self.subTest(role=role):
                _, _, _, dashed = _DRAW.explicit_path_style(
                    role, "LG" if role == "run_block" else "FB", "X", play={},
                )
                self.assertFalse(dashed, f"{role} must not be dashed")

    def test_explicit_path_style_option_play_ball_carriers_distinct(self):
        # On option plays (e.g. triple option), multiple ball_carriers share
        # the field.  Coloring them by read priority (dive=primary,
        # keep=secondary, pitch=tertiary) is what makes the diagram readable.
        play = {
            "primary_read":   "QB",
            "secondary_read": "FB",
            "tertiary_read":  "HB",
        }
        primary_color, _, _, _ = _DRAW.explicit_path_style("ball_carrier", "QB", "QB", play)
        secondary_color, _, _, _ = _DRAW.explicit_path_style("ball_carrier", "FB", "FB", play)
        tertiary_color, _, _, _ = _DRAW.explicit_path_style("ball_carrier", "HB", "HB", play)
        self.assertEqual(primary_color, _DRAW.COLOR_PRIMARY_READ)
        self.assertEqual(secondary_color, _DRAW.COLOR_SECONDARY_READ)
        self.assertEqual(tertiary_color, _DRAW.COLOR_TERTIARY_READ)
        self.assertEqual(len({primary_color, secondary_color, tertiary_color}), 3)


if __name__ == "__main__":
    unittest.main()
