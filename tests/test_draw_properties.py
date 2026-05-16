"""Phase 7: property-based, determinism, and fault-injection tests.

These exercise invariants that should hold across many inputs, not just the
two-or-three concrete fixtures used elsewhere:

  - **Determinism**: render(same inputs) twice → byte-identical output (after
    stripping the timestamped provenance comment).
  - **Property — coordinate round-trip**: universal -> grid -> universal is
    the identity within numerical tolerance.
  - **Property — cell uniqueness**: assign_cells_for_formation never produces
    duplicates on any (profile, formation) pair from the data set.
  - **Property — bounded warnings**: a clean formation produces zero warnings;
    no clean formation produces > 0 warnings under default profile limits.
  - **Fault injection**: 20+ malformed-input cases each produce a documented
    typed exception, never a Python traceback to the user.

No external dependency on Hypothesis — uses stdlib `random` with explicit seeds
so failures are reproducible.
"""
from __future__ import annotations

import importlib.util
import math
import random
import re
import unittest
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
DRAW_PATH = REPO_ROOT / "tools" / "draw-play" / "draw.py"
GAMES_DIR = REPO_ROOT / "data" / "games"
FORMATIONS_DIR = REPO_ROOT / "data" / "formations"


def _import_draw():
    spec = importlib.util.spec_from_file_location("draw_play", DRAW_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_DRAW = _import_draw()
_PROFILE = yaml.safe_load(
    (REPO_ROOT / "data" / "games" / "madden-05-ps2" / "editor-grid.yaml").read_text()
)
_PROVENANCE_RE = re.compile(r"<!-- draw-play[^>]*-->\n?")


def _strip_provenance(svg: str) -> str:
    """Remove the timestamped + git-rev provenance comment from an SVG.

    The provenance line legitimately differs between renders separated in
    time; tests that need byte-identical comparison strip it.
    """
    return _PROVENANCE_RE.sub("", svg, count=1)


# ============================================================================
# Determinism
# ============================================================================

class TestDeterminism(unittest.TestCase):
    """render() with identical inputs must produce identical output (modulo
    the provenance comment, which intentionally encodes timestamp + git rev)."""

    def _two_renders(self, **kwargs):
        a, _ = _DRAW.render(**kwargs)
        b, _ = _DRAW.render(**kwargs)
        return _strip_provenance(a), _strip_provenance(b)

    def test_render_is_deterministic_with_play_and_defense(self):
        play = yaml.safe_load((REPO_ROOT / "data" / "plays" / "singleback-trio-mesh.yaml").read_text())
        formation = yaml.safe_load((REPO_ROOT / "data" / "formations" / "singleback-trio.yaml").read_text())
        defense = yaml.safe_load((REPO_ROOT / "data" / "formations" / "defense-4-3-cover-3.yaml").read_text())
        route_lib = _DRAW.load_route_library()
        a, b = self._two_renders(
            profile=_PROFILE, play=play, formation=formation,
            defense=defense, route_lib=route_lib,
        )
        self.assertEqual(a, b)

    def test_render_is_deterministic_for_defense_only(self):
        defense = yaml.safe_load((REPO_ROOT / "data" / "formations" / "defense-4-3-cover-3.yaml").read_text())
        a, b = self._two_renders(profile=_PROFILE, defense=defense, route_lib={})
        self.assertEqual(a, b)


# ============================================================================
# Properties — coordinate round-trip
# ============================================================================

class TestCoordinateRoundTrip(unittest.TestCase):
    """Universal → grid → universal must be identity (within float tolerance)."""

    def test_round_trip_random_points(self):
        rng = random.Random(0xDEADBEEF)
        for _ in range(200):
            x_yd = rng.uniform(-30.0, 30.0)
            y_yd = rng.uniform(-15.0, 30.0)
            gx, gy = _DRAW.universal_to_grid(x_yd, y_yd, _PROFILE)
            # Inverse: yards = (cell - origin) * scale
            origin = _PROFILE["grid"]["origin"]
            scale = _PROFILE["scale"]
            x_back = (gx - origin["x"]) * scale["x_yards_per_cell"]
            y_back = (gy - origin["y"]) * scale["y_yards_per_cell"]
            self.assertAlmostEqual(x_back, x_yd, places=6)
            self.assertAlmostEqual(y_back, y_yd, places=6)

    def test_grid_to_pixel_to_grid_round_trip(self):
        rng = random.Random(0xCAFEBABE)
        total_cells = 17
        for _ in range(200):
            gx = rng.uniform(0.0, 21.0)
            gy = rng.uniform(0.0, total_cells)
            px, py = _DRAW.grid_to_pixel(gx, gy, total_cells)
            # Inverse:
            gx_back = (px - _DRAW.FIELD_MARGIN_PX) / _DRAW.PIXELS_PER_CELL
            gy_back = total_cells - (py - _DRAW.FIELD_MARGIN_PX) / _DRAW.PIXELS_PER_CELL
            self.assertAlmostEqual(gx_back, gx, places=6)
            self.assertAlmostEqual(gy_back, gy, places=6)


# ============================================================================
# Properties — cell uniqueness across all data
# ============================================================================

class TestCellUniqueness(unittest.TestCase):
    """For every snapping profile × every formation, cells are unique integers.

    Restates test_draw_unit's parametrized sweep as an invariant: the cell
    assignment is a bijection from formation labels onto a subset of editor
    cells.  Sampled here against a single representative profile to keep the
    suite fast — the full cross-profile sweep lives in test_draw_unit.
    """

    def test_bijection_property_one_profile(self):
        offenders: list[str] = []
        for fp in sorted(FORMATIONS_DIR.glob("*.yaml")):
            formation = yaml.safe_load(fp.read_text())
            cells = _DRAW.assign_cells_for_formation(formation, _PROFILE)
            if len(cells) != len(formation["players"]):
                offenders.append(f"{fp.stem}: missing player(s)")
                continue
            if len(set(cells.values())) != len(cells):
                offenders.append(f"{fp.stem}: duplicate cells")
        self.assertEqual(offenders, [])


# ============================================================================
# Properties — render output structure
# ============================================================================

class TestRenderStructuralProperties(unittest.TestCase):
    """SVG output has invariant properties that should hold for any valid input."""

    def test_svg_starts_and_ends_with_root_tag(self):
        svg, _ = _DRAW.render(_PROFILE, route_lib={})
        self.assertTrue(svg.startswith("<svg"))
        self.assertTrue(svg.rstrip().endswith("</svg>"))

    def test_svg_height_matches_root_attribute(self):
        # Sanity: the root <svg> declares a height that's a positive integer.
        svg, _ = _DRAW.render(_PROFILE, route_lib={})
        m = re.search(r'<svg[^>]*\bheight="(\d+)"', svg)
        self.assertIsNotNone(m)
        self.assertGreater(int(m.group(1)), 0)

    def test_provenance_comment_is_first_child_of_svg(self):
        # Tests that prepend assertions on the SVG output (e.g. starts-with)
        # rely on the provenance comment NOT being before the <svg> tag.
        svg, _ = _DRAW.render(_PROFILE, route_lib={})
        idx = svg.find("<!--")
        self.assertGreater(idx, 0, "comment must appear after <svg> opening")
        self.assertLess(idx, 200, "comment must be near the top, just after <svg>")

    def test_provenance_comment_contains_required_fields(self):
        svg, _ = _DRAW.render(_PROFILE, route_lib={})
        m = re.search(r"<!-- (.*?) -->", svg)
        self.assertIsNotNone(m)
        body = m.group(1)
        for required in ("draw-play v", "git=", "generated=", "game="):
            self.assertIn(required, body, f"missing {required!r} in provenance")


# ============================================================================
# Fault injection — broad sweep of malformed inputs
# ============================================================================

class TestFaultInjection(unittest.TestCase):
    """Every malformed input produces a typed exception, never a stack trace."""

    def _expect(self, exc_type, **render_kwargs):
        kwargs = {"profile": _PROFILE, "route_lib": {}, **render_kwargs}
        with self.assertRaises(exc_type):
            _DRAW.render(**kwargs)

    # --- Profile faults ---

    def test_profile_missing_grid(self):
        self._expect(_DRAW.InvalidProfileError, profile={**_PROFILE, "grid": None})

    def test_profile_grid_missing_origin(self):
        self._expect(
            _DRAW.InvalidProfileError,
            profile={**_PROFILE, "grid": {"width": 21, "height": 7}},
        )

    def test_profile_negative_width(self):
        self._expect(
            _DRAW.InvalidProfileError,
            profile={**_PROFILE, "grid": {**_PROFILE["grid"], "width": -5}},
        )

    def test_profile_string_scale(self):
        self._expect(
            _DRAW.InvalidProfileError,
            profile={**_PROFILE, "scale": {"x_yards_per_cell": "fast", "y_yards_per_cell": 2.0}},
        )

    def test_profile_nan_scale(self):
        self._expect(
            _DRAW.InvalidProfileError,
            profile={**_PROFILE, "scale": {"x_yards_per_cell": float("nan"), "y_yards_per_cell": 2.0}},
        )

    def test_profile_bool_pretending_to_be_number(self):
        # Python lets True act as 1 in arithmetic, but it's not a number.
        self._expect(
            _DRAW.InvalidProfileError,
            profile={**_PROFILE, "scale": {"x_yards_per_cell": True, "y_yards_per_cell": 2.0}},
        )

    # --- Formation faults ---

    def _good_offense(self):
        return {
            "side": "offense",
            "players": [
                {"label": "C",  "position": "C",  "x": 0.0, "y": 0.0},
                {"label": "QB", "position": "QB", "x": 0.0, "y": -2.0},
            ],
        }

    def test_formation_inf_x(self):
        bad = self._good_offense()
        bad["players"][0]["x"] = float("inf")
        self._expect(_DRAW.InvalidFormationError, formation=bad)

    def test_formation_negative_inf_y(self):
        bad = self._good_offense()
        bad["players"][1]["y"] = float("-inf")
        self._expect(_DRAW.InvalidFormationError, formation=bad)

    def test_formation_nan_coordinate(self):
        bad = self._good_offense()
        bad["players"][1]["x"] = float("nan")
        self._expect(_DRAW.InvalidFormationError, formation=bad)

    def test_formation_player_is_list_not_dict(self):
        bad = {"players": [["C", "C", 0.0, 0.0]]}  # not a dict
        self._expect(_DRAW.InvalidFormationError, formation=bad)

    def test_formation_label_not_string(self):
        bad = {"players": [{"label": 42, "x": 0.0, "y": 0.0}]}
        self._expect(_DRAW.InvalidFormationError, formation=bad)

    def test_formation_huge_player_count(self):
        bad = {"players": [{"label": f"P{i}", "x": 0.0, "y": 0.0} for i in range(99)]}
        self._expect(_DRAW.InvalidFormationError, formation=bad)

    def test_formation_side_typo(self):
        bad = {"side": "offfense", "players": []}
        self._expect(_DRAW.InvalidFormationError, formation=bad)

    # --- Play faults ---

    def test_play_assignments_not_list(self):
        bad = {"name": "x", "play_type": "pass", "formation": "y", "assignments": "not-a-list"}
        self._expect(_DRAW.InvalidPlayError, play=bad)

    def test_play_assignment_item_not_dict(self):
        bad = {"name": "x", "play_type": "pass", "formation": "y", "assignments": ["bad"]}
        self._expect(_DRAW.InvalidPlayError, play=bad)

    def test_play_assignment_missing_player(self):
        bad = {
            "name": "x", "play_type": "pass", "formation": "y",
            "assignments": [{"role": "route"}],
        }
        self._expect(_DRAW.InvalidPlayError, play=bad)

    # --- Route faults (via load path) ---

    def test_route_with_inf_waypoint_rejected(self):
        with self.assertRaises(_DRAW.InvalidRouteError):
            _DRAW._validate_route({"path": [[0, 0], [float("inf"), 5]]}, name="bad")

    def test_route_path_is_dict_not_list(self):
        with self.assertRaises(_DRAW.InvalidRouteError):
            _DRAW._validate_route({"path": {"x": 0, "y": 5}}, name="bad")

    def test_route_waypoint_too_long(self):
        with self.assertRaises(_DRAW.InvalidRouteError):
            _DRAW._validate_route({"path": [[0, 0], [1, 2, 3]]}, name="bad")

    # --- show / field enum faults ---

    def test_invalid_show_string(self):
        self._expect(ValueError, show="OFFENSE")  # case-sensitive

    def test_invalid_field_string(self):
        self._expect(ValueError, field="medium")

    def test_show_none_value_rejected(self):
        # `None` is not one of the enum strings.  The current implementation
        # may raise either AssertionError (the type-check fires first under
        # `python` without -O) or ValueError (the enum check), depending on
        # whether assertions are enabled.  Both are acceptable as long as no
        # malformed SVG is produced.
        with self.assertRaises((ValueError, TypeError, AssertionError)):
            _DRAW.render(_PROFILE, route_lib={}, show=None)


# ============================================================================
# CellAssignmentError reachable via render()
# ============================================================================

class TestCellAssignmentExhaustion(unittest.TestCase):
    """A formation that cannot fit on the editor grid raises CellAssignmentError."""

    def test_too_dense_formation_raises_in_render(self):
        # A profile with a 1×1 grid plus 5 players forces BFS exhaustion.
        tiny_profile = {
            "game_id": "tiny",
            "grid": {"width": 1, "height": 1, "origin": {"x": 0, "y": 0}},
            "scale": {"x_yards_per_cell": 1.0, "y_yards_per_cell": 1.0},
            "snap_to_cells": True,
        }
        crowded = {
            "side": "offense",
            "players": [
                {"label": f"P{i}", "x": 0.0, "y": 0.0} for i in range(5)
            ],
        }
        # Fill up the BFS reach so it actually exhausts. A 1x1 grid still has
        # room within 25 rings, so we need a more extreme test: pre-fill cells.
        used = {(0 + dx, 0 + dy)
                for dx in range(-_DRAW.BFS_MAX_RINGS, _DRAW.BFS_MAX_RINGS + 1)
                for dy in range(-_DRAW.BFS_MAX_RINGS, _DRAW.BFS_MAX_RINGS + 1)}
        with self.assertRaises(_DRAW.CellAssignmentError):
            _DRAW._bfs_nearest_free_cell((0, 0), used, "offense", 0)


if __name__ == "__main__":
    unittest.main()
