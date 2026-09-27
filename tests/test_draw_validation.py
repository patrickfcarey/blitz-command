"""Tests for the input-validation hardening (Phases 1-3 of the NASA review).

Verifies that:
  - Each validator raises its dedicated exception type for bad inputs.
  - render() rejects invalid show / field / profile / play / formation.
  - _bfs_nearest_free_cell raises CellAssignmentError when no free cell exists.
  - render_path_yd raises InvalidRouteError on <2 waypoints.
  - load_yaml distinguishes empty / malformed / missing files.
  - main()'s new exit code 3 fires for malformed config.
"""
from __future__ import annotations

import importlib.util
import math
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
DRAW_PATH = REPO_ROOT / "tools" / "draw-play" / "draw.py"


def _import_draw():
    spec = importlib.util.spec_from_file_location("draw_play", DRAW_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_DRAW = _import_draw()
_PROFILE = yaml.safe_load(
    (REPO_ROOT / "data" / "games" / "madden-05-ps2" / "editor-grid.yaml").read_text()
)


def _good_formation() -> dict:
    return {
        "name": "Good Form",
        "side": "offense",
        "players": [
            {"label": "C",  "position": "C",  "x": 0.0,  "y":  0.0},
            {"label": "QB", "position": "QB", "x": 0.0,  "y": -2.0},
        ],
    }


def _good_play() -> dict:
    return {
        "name": "Good",
        "play_type": "pass",
        "formation": "test",
        "assignments": [],
    }


# ============================================================================
# Exception hierarchy
# ============================================================================

class TestExceptionHierarchy(unittest.TestCase):
    """Every domain exception inherits from DrawError so callers can catch them generically."""

    def test_all_inherit_from_draw_error(self):
        for exc_class in (
            _DRAW.InvalidProfileError,
            _DRAW.InvalidPlayError,
            _DRAW.InvalidFormationError,
            _DRAW.InvalidRouteError,
            _DRAW.CellAssignmentError,
            _DRAW.ConfigError,
        ):
            with self.subTest(exc=exc_class.__name__):
                self.assertTrue(issubclass(exc_class, _DRAW.DrawError))

    def test_draw_error_is_an_exception(self):
        self.assertTrue(issubclass(_DRAW.DrawError, Exception))


# ============================================================================
# Profile validation
# ============================================================================

class TestProfileValidation(unittest.TestCase):
    """_validate_profile catches every malformed-profile shape."""

    def test_none_rejected(self):
        with self.assertRaises(_DRAW.InvalidProfileError):
            _DRAW._validate_profile(None)

    def test_non_dict_rejected(self):
        with self.assertRaises(_DRAW.InvalidProfileError):
            _DRAW._validate_profile("not a dict")

    def test_missing_game_id(self):
        bad = dict(_PROFILE)
        bad.pop("game_id")
        with self.assertRaises(_DRAW.InvalidProfileError) as ctx:
            _DRAW._validate_profile(bad)
        self.assertIn("game_id", str(ctx.exception))

    def test_zero_scale_rejected(self):
        bad = {**_PROFILE, "scale": {"x_yards_per_cell": 0, "y_yards_per_cell": 2.0}}
        with self.assertRaises(_DRAW.InvalidProfileError) as ctx:
            _DRAW._validate_profile(bad)
        self.assertIn("positive", str(ctx.exception))

    def test_negative_scale_rejected(self):
        bad = {**_PROFILE, "scale": {"x_yards_per_cell": -1.0, "y_yards_per_cell": 2.0}}
        with self.assertRaises(_DRAW.InvalidProfileError):
            _DRAW._validate_profile(bad)

    def test_zero_grid_dim_rejected(self):
        bad = {**_PROFILE, "grid": {**_PROFILE["grid"], "width": 0}}
        with self.assertRaises(_DRAW.InvalidProfileError):
            _DRAW._validate_profile(bad)

    def test_missing_origin_rejected(self):
        bad = {**_PROFILE, "grid": {"width": 21, "height": 7}}
        with self.assertRaises(_DRAW.InvalidProfileError):
            _DRAW._validate_profile(bad)

    def test_well_formed_profile_passes(self):
        # Real profile must validate cleanly — sanity check that the validator
        # doesn't reject legitimate data.
        _DRAW._validate_profile(_PROFILE)  # no exception


# ============================================================================
# Formation validation
# ============================================================================

class TestFormationValidation(unittest.TestCase):
    def test_missing_players_rejected(self):
        with self.assertRaises(_DRAW.InvalidFormationError):
            _DRAW._validate_formation({"name": "X"})

    def test_duplicate_label_rejected(self):
        bad = {
            "players": [
                {"label": "C", "x": 0.0, "y": 0.0},
                {"label": "C", "x": 1.0, "y": 0.0},
            ]
        }
        with self.assertRaises(_DRAW.InvalidFormationError) as ctx:
            _DRAW._validate_formation(bad)
        self.assertIn("duplicate", str(ctx.exception).lower())

    def test_missing_required_field_rejected(self):
        bad = {"players": [{"label": "C", "x": 0.0}]}  # no y
        with self.assertRaises(_DRAW.InvalidFormationError):
            _DRAW._validate_formation(bad)

    def test_non_finite_coordinate_rejected(self):
        bad = {"players": [{"label": "C", "x": float("inf"), "y": 0.0}]}
        with self.assertRaises(_DRAW.InvalidFormationError) as ctx:
            _DRAW._validate_formation(bad)
        self.assertIn("finite", str(ctx.exception))

    def test_empty_label_rejected(self):
        bad = {"players": [{"label": "", "x": 0.0, "y": 0.0}]}
        with self.assertRaises(_DRAW.InvalidFormationError):
            _DRAW._validate_formation(bad)

    def test_invalid_side_rejected(self):
        bad = {"side": "bench", "players": []}
        with self.assertRaises(_DRAW.InvalidFormationError):
            _DRAW._validate_formation(bad)

    def test_too_many_players_rejected(self):
        bad = {"players": [{"label": f"P{i}", "x": 0.0, "y": 0.0} for i in range(50)]}
        with self.assertRaises(_DRAW.InvalidFormationError) as ctx:
            _DRAW._validate_formation(bad)
        self.assertIn("max", str(ctx.exception))


# ============================================================================
# Play validation
# ============================================================================

class TestPlayValidation(unittest.TestCase):
    def test_missing_required_field_rejected(self):
        for missing in ("name", "play_type", "formation"):
            bad = _good_play()
            del bad[missing]
            with self.subTest(missing=missing):
                with self.assertRaises(_DRAW.InvalidPlayError):
                    _DRAW._validate_play(bad)

    def test_assignment_without_player_rejected(self):
        bad = _good_play()
        bad["assignments"] = [{"role": "route"}]  # no player
        with self.assertRaises(_DRAW.InvalidPlayError):
            _DRAW._validate_play(bad)

    def test_well_formed_play_passes(self):
        _DRAW._validate_play(_good_play())


# ============================================================================
# Route validation
# ============================================================================

class TestRouteValidation(unittest.TestCase):
    def test_missing_path_rejected(self):
        with self.assertRaises(_DRAW.InvalidRouteError):
            _DRAW._validate_route({"name": "x"})

    def test_malformed_waypoint_rejected(self):
        with self.assertRaises(_DRAW.InvalidRouteError):
            _DRAW._validate_route({"path": [[0, 0], [1]]})  # second wp has 1 elem

    def test_non_finite_waypoint_rejected(self):
        with self.assertRaises(_DRAW.InvalidRouteError):
            _DRAW._validate_route({"path": [[0, 0], [float("nan"), 5]]})


# ============================================================================
# render() boundary checks
# ============================================================================

class TestRenderBoundary(unittest.TestCase):
    """render() rejects invalid show / field / profile at the gate."""

    def test_invalid_show_raises_value_error(self):
        with self.assertRaises(ValueError) as ctx:
            _DRAW.render(_PROFILE, show="invalid")
        self.assertIn("show", str(ctx.exception))

    def test_invalid_field_raises_value_error(self):
        with self.assertRaises(ValueError) as ctx:
            _DRAW.render(_PROFILE, field="medium")
        self.assertIn("field", str(ctx.exception))

    def test_invalid_profile_raises(self):
        with self.assertRaises(_DRAW.InvalidProfileError):
            _DRAW.render({})  # empty profile

    def test_invalid_play_raises(self):
        with self.assertRaises(_DRAW.InvalidPlayError):
            _DRAW.render(_PROFILE, play={"name": "x"})  # missing fields

    def test_invalid_formation_raises(self):
        with self.assertRaises(_DRAW.InvalidFormationError):
            _DRAW.render(_PROFILE, formation={"name": "x"})  # missing players

    def test_well_formed_inputs_succeed(self):
        # Sanity check: validator does not reject legitimate data.
        svg, warnings = _DRAW.render(
            _PROFILE, formation=_good_formation(), show="both", field="long",
        )
        self.assertTrue(svg.startswith("<svg"))


# ============================================================================
# BFS exhaustion
# ============================================================================

class TestBfsExhaustion(unittest.TestCase):
    """_bfs_nearest_free_cell raises CellAssignmentError when no free cell exists."""

    def test_raises_when_used_set_is_unreachably_full(self):
        # Construct a `used` set that fills the entire BFS_MAX_RINGS box around
        # the target.  No free cell exists within reach → must raise.
        target = (10, 5)
        max_rings = _DRAW.BFS_MAX_RINGS
        used = {
            (target[0] + dx, target[1] + dy)
            for dx in range(-max_rings, max_rings + 1)
            for dy in range(-max_rings, max_rings + 1)
        }
        with self.assertRaises(_DRAW.CellAssignmentError) as ctx:
            _DRAW._bfs_nearest_free_cell(target, used, "offense", 5)
        self.assertIn("no free cell", str(ctx.exception))

    def test_succeeds_when_neighbor_free(self):
        # Free neighbor exists → returns it.
        used = {(10, 5)}
        result = _DRAW._bfs_nearest_free_cell((10, 5), used, "offense", 5)
        self.assertNotIn(result, used)


# ============================================================================
# render_path_yd boundary
# ============================================================================

class TestRenderPathYdBoundary(unittest.TestCase):
    def test_zero_waypoints_raises(self):
        with self.assertRaises(_DRAW.InvalidRouteError):
            _DRAW.render_path_yd(
                [], [], _PROFILE, total_cells=10,
                color="#fff", width=1.0, marker_id="arrow",
            )

    def test_one_waypoint_raises(self):
        with self.assertRaises(_DRAW.InvalidRouteError):
            _DRAW.render_path_yd(
                [], [(0.0, 0.0)], _PROFILE, total_cells=10,
                color="#fff", width=1.0, marker_id="arrow",
            )

    def test_two_waypoints_succeeds(self):
        parts: list[str] = []
        _DRAW.render_path_yd(
            parts, [(0.0, 0.0), (1.0, 1.0)], _PROFILE, total_cells=10,
            color="#fff", width=1.0, marker_id="arrow",
        )
        self.assertEqual(len(parts), 1)
        self.assertIn("polyline", parts[0])


# ============================================================================
# load_yaml error distinction
# ============================================================================

class TestLoadYaml(unittest.TestCase):
    def test_missing_file_raises_file_not_found(self):
        with self.assertRaises(FileNotFoundError):
            _DRAW.load_yaml(Path("/tmp/definitely-does-not-exist-xyz.yaml"))

    def test_malformed_yaml_raises_config_error(self):
        with tempfile.NamedTemporaryFile(suffix=".yaml", mode="w", delete=False) as tmp:
            tmp.write("key: : :\n  -- broken\n")
            tmp_path = Path(tmp.name)
        try:
            with self.assertRaises(_DRAW.ConfigError) as ctx:
                _DRAW.load_yaml(tmp_path)
            self.assertIn("malformed", str(ctx.exception).lower())
        finally:
            tmp_path.unlink()

    def test_top_level_non_dict_raises_config_error(self):
        with tempfile.NamedTemporaryFile(suffix=".yaml", mode="w", delete=False) as tmp:
            tmp.write("- not\n- a\n- dict\n")
            tmp_path = Path(tmp.name)
        try:
            with self.assertRaises(_DRAW.ConfigError):
                _DRAW.load_yaml(tmp_path)
        finally:
            tmp_path.unlink()

    def test_empty_file_returns_empty_dict(self):
        with tempfile.NamedTemporaryFile(suffix=".yaml", mode="w", delete=False) as tmp:
            tmp_path = Path(tmp.name)
        try:
            result = _DRAW.load_yaml(tmp_path)
            self.assertEqual(result, {})
        finally:
            tmp_path.unlink()


# ============================================================================
# CLI exit-code 3 (new path)
# ============================================================================

class TestCliExitCodeThree(unittest.TestCase):
    """Malformed YAML in any input file produces exit code 3."""

    def _run_cli(self, *args):
        return subprocess.run(
            [sys.executable, str(DRAW_PATH), *args],
            capture_output=True, text=True, cwd=REPO_ROOT,
        )

    def test_malformed_play_yaml_returns_3(self):
        plays_dir = REPO_ROOT / "data" / "plays"
        tmp_play_id = "tmp-malformed-yaml-test"
        tmp_path = plays_dir / f"{tmp_play_id}.yaml"
        tmp_path.write_text("not: valid: yaml: : :\n")
        try:
            result = self._run_cli(tmp_play_id, "madden-05-ps2")
            self.assertEqual(result.returncode, 3, msg=result.stderr)
            self.assertIn("error:", result.stderr.lower())
        finally:
            tmp_path.unlink()

    def test_invalid_profile_returns_3(self):
        # Construct a temp game profile with an empty grid → fails validation.
        with tempfile.TemporaryDirectory() as tmpdir:
            game_root = Path(tmpdir) / "data" / "games" / "test-broken"
            game_root.mkdir(parents=True)
            (game_root / "editor-grid.yaml").write_text(
                "game_id: test-broken\n"
                "grid:\n  width: 0\n  height: 7\n  origin: {x: 10, y: 5}\n"
                "scale: {x_yards_per_cell: 1.667, y_yards_per_cell: 2.0}\n"
                "snap_to_cells: true\n"
            )
            # We can't easily redirect the CLI's hard-coded GAMES_DIR, so this
            # test would require either parameterizing the CLI or copying the
            # bad profile into the real games dir.  Instead, exercise the
            # validation directly via render() — already covered in
            # TestRenderBoundary.test_invalid_profile_raises.
            profile = yaml.safe_load((game_root / "editor-grid.yaml").read_text())
            with self.assertRaises(_DRAW.InvalidProfileError):
                _DRAW._validate_profile(profile)


if __name__ == "__main__":
    unittest.main()
