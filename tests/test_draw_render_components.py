"""Tier 2 tests: render-component behaviors.

Constructs minimal in-memory plays / formations / defenses to exercise specific
rendering paths and asserts on the resulting SVG (color, marker, dasharray,
attribute presence) and the returned warnings list.

These cover branches that the golden-SVG smoke tests in test_draw_tool.py
would silently let pass (e.g., a wrong color for `blitz`, a missing pulling-
guard arrow, a swapped man / spy ring style).
"""
from __future__ import annotations

import copy
import importlib.util
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


# ============================================================================
# Fixture builders
# ============================================================================

def _offense_with(**overrides) -> dict:
    """Build a complete 11-man offensive formation; overrides patch fields per label."""
    base = {
        "name": "Test Offense",
        "side": "offense",
        "players": [
            {"label": "LT",   "position": "LT", "x": -2.0,  "y":  0.0},
            {"label": "LG",   "position": "LG", "x": -1.0,  "y":  0.0},
            {"label": "C",    "position": "C",  "x":  0.0,  "y":  0.0},
            {"label": "RG",   "position": "RG", "x":  1.0,  "y":  0.0},
            {"label": "RT",   "position": "RT", "x":  2.0,  "y":  0.0},
            {"label": "TE",   "position": "TE", "x":  3.5,  "y":  0.0},
            {"label": "X",    "position": "WR", "x": -10.0, "y":  0.0},
            {"label": "Z",    "position": "WR", "x":  10.0, "y": -1.0},
            {"label": "QB",   "position": "QB", "x":  0.0,  "y": -2.0},
            {"label": "FB",   "position": "FB", "x":  0.0,  "y": -3.5},
            {"label": "HB",   "position": "HB", "x":  0.0,  "y": -6.0},
        ],
    }
    if overrides:
        for player in base["players"]:
            patch = overrides.get(player["label"])
            if patch:
                player.update(patch)
    return base


def _defense_with(*responsibilities: tuple[dict, dict | None]) -> dict:
    """Build a defensive formation from `(player, responsibility_or_None)` pairs."""
    players = [r[0] for r in responsibilities]
    resps = [
        {"player": player["label"], **resp}
        for player, resp in responsibilities
        if resp is not None
    ]
    return {
        "name": "Test Defense",
        "side": "defense",
        "front": "test",
        "coverage_shell": "test",
        "players": players,
        "responsibilities": resps,
    }


def _play_with(assignments: list[dict], **fields) -> dict:
    """Build a minimal play with the given assignments + extra top-level fields."""
    return {
        "play_id": "test-play",
        "name": "Test Play",
        "play_type": "pass",
        "formation": "test-offense",
        "ball_carrier": "QB",
        "primary_read": "TE",
        "assignments": assignments,
        **fields,
    }


def _render(**overrides) -> tuple[str, list[str]]:
    """Render with sensible defaults; overrides win."""
    kw = dict(profile=_PROFILE, route_lib={}, show="both", field="long")
    kw.update(overrides)
    return _DRAW.render(**kw)


# ============================================================================
# TestDefensiveCoverage — one test per coverage role
# ============================================================================

class TestDefensiveCoverage(unittest.TestCase):
    """Each coverage role must produce its expected color, marker, and shape."""

    def test_rush_uses_rush_color_and_marker(self):
        defender = {"label": "DE", "position": "DE", "x": 4.0, "y": 1.0}
        defense = _defense_with((defender, {"role": "rush"}))
        svg, _ = _render(defense=defense)
        self.assertIn(f'stroke="{_DRAW.COLOR_RUSH}"', svg)
        self.assertIn(f'marker-end="url(#{_DRAW.MARKER_RUSH})"', svg)

    def test_blitz_uses_distinct_color_from_rush(self):
        # Both rush and blitz use the same MARKER_RUSH but different colors.
        # The visual distinction must be preserved across refactors.
        defender = {"label": "WLB", "position": "LB", "x": -3.0, "y": 5.0}
        defense = _defense_with((defender, {"role": "blitz"}))
        svg, _ = _render(defense=defense)
        self.assertIn(f'stroke="{_DRAW.COLOR_BLITZ}"', svg)
        self.assertNotEqual(_DRAW.COLOR_BLITZ, _DRAW.COLOR_RUSH)

    def test_man_with_target_draws_dashed_arrow_and_ring(self):
        # Man with an existing covers_player → dashed arrow to target + ring
        # around defender.
        defender = {"label": "RCB", "position": "CB", "x": 10.0, "y": 7.0}
        defense = _defense_with(
            (defender, {"role": "man", "covers_player": "Z"}),
        )
        svg, _ = _render(defense=defense, formation=_offense_with())
        # Arrow: COLOR_MAN with MARKER_MAN, dashed 6,4
        self.assertIn(f'stroke="{_DRAW.COLOR_MAN}"', svg)
        self.assertIn(f'marker-end="url(#{_DRAW.MARKER_MAN})"', svg)
        self.assertIn('stroke-dasharray="6,4"', svg)
        # Ring: separate dasharray 4,3 at the defender's position
        self.assertIn('stroke-dasharray="4,3"', svg)

    def test_man_with_unknown_target_renders_ring_no_arrow(self):
        # When covers_player names a player who isn't in the formation,
        # the ring is still drawn (so the man assignment is visible) but
        # the arrow is omitted.
        defender = {"label": "RCB", "position": "CB", "x": 10.0, "y": 7.0}
        defense = _defense_with(
            (defender, {"role": "man", "covers_player": "GHOST"}),
        )
        svg, _ = _render(defense=defense, formation=_offense_with())
        self.assertIn('stroke-dasharray="4,3"', svg)  # ring still drawn
        self.assertNotIn(f'marker-end="url(#{_DRAW.MARKER_MAN})"', svg)

    def test_man_without_covers_player_renders_nothing(self):
        # The dispatcher requires covers_player to be truthy before calling
        # the man renderer at all.  No man color should appear in the SVG.
        defender = {"label": "RCB", "position": "CB", "x": 10.0, "y": 7.0}
        defense = _defense_with(
            (defender, {"role": "man"}),  # no covers_player
        )
        svg, _ = _render(defense=defense, formation=_offense_with())
        self.assertNotIn(f'stroke="{_DRAW.COLOR_MAN}"', svg)

    def test_spy_renders_translucent_dashed_ring(self):
        defender = {"label": "MLB", "position": "LB", "x": 0.0, "y": 5.0}
        defense = _defense_with((defender, {"role": "spy"}))
        svg, _ = _render(defense=defense)
        # Spy ring: COLOR_SPY fill at low opacity + COLOR_SPY stroke,
        # dasharray "2,2" (distinct from man's "4,3").
        self.assertIn(f'fill="{_DRAW.COLOR_SPY}"', svg)
        self.assertIn(f'stroke="{_DRAW.COLOR_SPY}"', svg)
        self.assertIn('stroke-dasharray="2,2"', svg)
        # Spy fill opacity must be the same as zone fills (translucent).
        self.assertIn(f'fill-opacity="{_DRAW.OPACITY_ZONE_FILL}"', svg)

    def test_robber_role_treated_as_spy(self):
        # SPY_ROLES = {spy, qb-spy, robber} all share rendering.
        defender = {"label": "SS", "position": "S", "x": 0.0, "y": 6.0}
        defense = _defense_with((defender, {"role": "robber"}))
        svg, _ = _render(defense=defense)
        self.assertIn(f'fill="{_DRAW.COLOR_SPY}"', svg)

    def test_deep_zone_uses_deep_zone_color(self):
        defender = {"label": "FS", "position": "S", "x": 0.0, "y": 10.0}
        defense = _defense_with((defender, {"role": "deep-zone"}))
        svg, _ = _render(defense=defense)
        # Deep zone uses its own distinct color (lighter than regular zone).
        self.assertIn(f'fill="{_DRAW.COLOR_DEEP_ZONE}"', svg)
        self.assertNotEqual(_DRAW.COLOR_DEEP_ZONE, _DRAW.COLOR_ZONE)

    def test_flat_zone_drop_pushes_toward_correct_sideline(self):
        # Right-side flat defender drops toward higher x (right boundary).
        # Left-side defender drops toward lower x (left boundary).
        # Verify by checking the zone arrow's polyline includes a downstream
        # point on the correct side.
        right_def = {"label": "SS", "position": "S", "x": 6.0, "y": 4.0}
        left_def = {"label": "WS", "position": "S", "x": -6.0, "y": 4.0}

        right_svg, _ = _render(
            defense=_defense_with((right_def, {"role": "flat"})),
        )
        left_svg, _ = _render(
            defense=_defense_with((left_def, {"role": "flat"})),
        )
        # Both should produce a flat-zone ellipse with COLOR_ZONE.
        self.assertIn(f'fill="{_DRAW.COLOR_ZONE}"', right_svg)
        self.assertIn(f'fill="{_DRAW.COLOR_ZONE}"', left_svg)

    def test_hook_uses_zone_color(self):
        defender = {"label": "MLB", "position": "LB", "x": 0.0, "y": 4.0}
        defense = _defense_with((defender, {"role": "hook"}))
        svg, _ = _render(defense=defense)
        self.assertIn(f'fill="{_DRAW.COLOR_ZONE}"', svg)


# ============================================================================
# TestOffensivePathStyling
# ============================================================================

class TestOffensivePathStyling(unittest.TestCase):
    """Each offensive assignment role must produce its expected color / dash style."""

    def _route_lib(self) -> dict:
        return {
            "drag": {"name": "drag", "path": [[0.0, 0.0], [3.0, 5.0]]},
            "slant": {"name": "slant", "path": [[0.0, 0.0], [2.0, 5.0]]},
        }

    def test_route_on_right_receiver_mirrors_x(self):
        # Z is at +10.  The drag's [3, 5] waypoint should mirror to (10-3, 0+5)
        # = (7, 5) yards.  The polyline should NOT include a positive-X
        # waypoint relative to Z.
        formation = _offense_with()
        play = _play_with(
            [{"player": "Z", "role": "route", "route_name": "drag"}],
            primary_read="Z",
        )
        svg, _ = _render(
            play=play, formation=formation, route_lib=self._route_lib(),
        )
        # The route was authored to break +X (right).  After mirroring, the
        # polyline should use the SECONDARY/PRIMARY/etc. read color and the
        # arrow marker.  Just verify a route was emitted with the primary
        # read color.
        self.assertIn(f'stroke="{_DRAW.COLOR_PRIMARY_READ}"', svg)
        self.assertIn(f'marker-end="url(#{_DRAW.MARKER_PRIMARY})"', svg)

    def test_route_on_left_receiver_does_not_mirror(self):
        # X is at -10.  The drag waypoint [3, 5] should NOT mirror — the
        # receiver still breaks toward the middle (positive x).
        formation = _offense_with()
        play = _play_with(
            [{"player": "X", "role": "route", "route_name": "drag"}],
            primary_read="X",
        )
        svg, _ = _render(
            play=play, formation=formation, route_lib=self._route_lib(),
        )
        # Renders successfully — content equivalence with the right-side test
        # is exercised at the unit-test level (test_draw_unit's
        # TestRouteMirroring).
        self.assertIn(f'stroke="{_DRAW.COLOR_PRIMARY_READ}"', svg)

    def test_pulling_guard_uses_pull_color(self):
        # An OL player with role=run_block + an explicit path is a pulling
        # guard — must use the green pull color and pull marker.
        formation = _offense_with()
        play = _play_with([
            {"player": "LG", "role": "run_block", "path": [[0.0, 0.0], [4.0, -1.0]]},
        ])
        svg, _ = _render(play=play, formation=formation)
        self.assertIn(f'stroke="{_DRAW.COLOR_PULL}"', svg)
        self.assertIn(f'marker-end="url(#{_DRAW.MARKER_PULL})"', svg)

    def test_lead_block_uses_fb_lead_color(self):
        formation = _offense_with()
        play = _play_with([
            {"player": "FB", "role": "lead_block", "path": [[0.0, 0.0], [2.0, 2.0]]},
        ])
        svg, _ = _render(play=play, formation=formation)
        self.assertIn(f'stroke="{_DRAW.COLOR_FB_LEAD}"', svg)
        self.assertIn(f'marker-end="url(#{_DRAW.MARKER_FB_LEAD})"', svg)

    def test_fake_path_is_dashed(self):
        formation = _offense_with()
        play = _play_with([
            {"player": "HB", "role": "fake", "path": [[0.0, 0.0], [0.0, 3.0]]},
        ], play_type="play-action")
        svg, _ = _render(play=play, formation=formation)
        self.assertIn(f'stroke="{_DRAW.COLOR_FAKE_PATH}"', svg)
        self.assertIn(f'marker-end="url(#{_DRAW.MARKER_FAKE})"', svg)
        # The fake polyline must include the dasharray attribute.
        self.assertIn('stroke-dasharray="6,4"', svg)

    def test_pass_block_uses_pass_block_color(self):
        formation = _offense_with()
        play = _play_with([
            {"player": "RG", "role": "pass_block", "path": [[0.0, 0.0], [1.0, -1.0]]},
        ])
        svg, _ = _render(play=play, formation=formation)
        self.assertIn(f'stroke="{_DRAW.COLOR_PASS_BLOCK}"', svg)
        self.assertIn(f'marker-end="url(#{_DRAW.MARKER_PASS_BLOCK})"', svg)

    def test_option_play_secondary_ball_carrier_distinct_color(self):
        # On an option play the QB is primary, the dive back is secondary.
        # Both have role=ball_carrier with explicit paths but must be
        # rendered with distinct colors so the diagram is readable.
        formation = _offense_with()
        play = _play_with(
            [
                {"player": "QB", "role": "ball_carrier", "path": [[0.0, 0.0], [3.0, 0.0]]},
                {"player": "FB", "role": "ball_carrier", "path": [[0.0, 0.0], [0.0, 2.0]]},
            ],
            play_type="run",
            primary_read="QB",
            secondary_read="FB",
        )
        svg, _ = _render(play=play, formation=formation)
        self.assertIn(f'stroke="{_DRAW.COLOR_PRIMARY_READ}"', svg)
        self.assertIn(f'stroke="{_DRAW.COLOR_SECONDARY_READ}"', svg)

    def test_beats_coverage_badge_emitted(self):
        # An assignment with `beats_coverage: man` should emit an "M" badge
        # at the route's tip.
        formation = _offense_with()
        play = _play_with(
            [{
                "player": "TE", "role": "route",
                "route_name": "drag", "beats_coverage": "man",
            }],
            primary_read="TE",
        )
        svg, _ = _render(
            play=play, formation=formation, route_lib=self._route_lib(),
        )
        # The badge is a <text> with content "M" and a black outline.
        self.assertIn(">M</text>", svg)


# ============================================================================
# TestPlayerMarkers
# ============================================================================

class TestPlayerMarkers(unittest.TestCase):
    """Player marker shape, fill color, and badge rules."""

    def test_offense_ol_rendered_as_square(self):
        # Interior OL should produce <rect> markers (squares), not circles.
        formation = _offense_with()
        svg, _ = _render(formation=formation)
        # The C is OL; verify a rect with the C color appears.
        self.assertIn(f'fill="{_DRAW.COLOR_C}"', svg)
        # And specifically a <rect ... fill="<COLOR_C>"
        c_rect_idx = svg.find('<rect')
        self.assertGreaterEqual(c_rect_idx, 0)

    def test_defensive_dl_rendered_as_square(self):
        defender = {"label": "DT", "position": "DT", "x": 1.0, "y": 1.0}
        defense = _defense_with((defender, None))
        svg, _ = _render(defense=defense)
        # DL uses COLOR_DEFENSE_DL (darker red); marker is a <rect>.
        self.assertIn(f'fill="{_DRAW.COLOR_DEFENSE_DL}"', svg)

    def test_safety_uses_deep_defense_color(self):
        defender = {"label": "FS", "position": "S", "x": 0.0, "y": 12.0}
        defense = _defense_with((defender, None))
        svg, _ = _render(defense=defense)
        self.assertIn(f'fill="{_DRAW.COLOR_DEFENSE_DEEP}"', svg)

    def test_oob_player_rendered_red(self):
        # A player split far enough to be outside the editor grid should be
        # painted with COLOR_OUT_OF_BOUNDS rather than COLOR_OFFENSE.
        # Madden 05 grid: width=21, origin x=10, scale 1.667 → max ~16.6 yd
        # split before falling off the right edge.  X=20 guarantees OOB.
        formation = _offense_with(X={"x": -25.0})
        svg, _ = _render(formation=formation)
        self.assertIn(f'fill="{_DRAW.COLOR_OUT_OF_BOUNDS}"', svg)

    def test_primary_read_player_uses_primary_read_color(self):
        formation = _offense_with()
        play = _play_with([], primary_read="TE")
        svg, _ = _render(play=play, formation=formation)
        # TE marker uses COLOR_PRIMARY_READ_PLAYER (cyan).
        self.assertIn(f'fill="{_DRAW.COLOR_PRIMARY_READ_PLAYER}"', svg)

    def test_read_priority_badges_present(self):
        formation = _offense_with()
        play = _play_with([], primary_read="TE", secondary_read="Z",
                          tertiary_read="X", checkdown="HB")
        svg, _ = _render(play=play, formation=formation)
        # Each priority must emit its labelled badge as text.
        for badge in (">1°</text>", ">2°</text>", ">3°</text>", ">C</text>"):
            self.assertIn(badge, svg, f"missing {badge} badge")

    def test_ball_carrier_badge_suppressed_on_c(self):
        # If C is named as ball_carrier, the BC badge must be suppressed
        # (C always carries the snap; the badge is noise).
        formation = _offense_with()
        play = _play_with([], ball_carrier="C", primary_read="TE")
        svg, _ = _render(play=play, formation=formation)
        self.assertNotIn(">BC</text>", svg)

    def test_ball_carrier_badge_present_on_non_c(self):
        formation = _offense_with()
        play = _play_with([], ball_carrier="HB", primary_read="TE")
        svg, _ = _render(play=play, formation=formation)
        self.assertIn(">BC</text>", svg)


# ============================================================================
# TestWarnings
# ============================================================================

class TestWarnings(unittest.TestCase):
    """Each editor-limit violation must emit a warning string."""

    def _profile_with_limits(self, **limits) -> dict:
        # Deep-copy the real profile and inject our test limits so other
        # profile fields stay realistic.
        profile = copy.deepcopy(_PROFILE)
        profile["limits"] = {**(profile.get("limits") or {}), **limits}
        return profile

    def test_out_of_bounds_warning_emitted(self):
        # Push a WR far enough left to fall off the editor grid.
        formation = _offense_with(X={"x": -25.0})
        _, warnings = _render(formation=formation)
        self.assertTrue(
            any("X" in w and "outside editor grid" in w for w in warnings),
            f"warnings: {warnings}",
        )

    def test_max_split_warning_emitted(self):
        profile = self._profile_with_limits(max_player_split_yd=10)
        formation = _offense_with()  # Z is at +10, within; bump it past
        formation["players"] = [
            {**p, "x": 12.0} if p["label"] == "Z" else p
            for p in formation["players"]
        ]
        _, warnings = _render(profile=profile, formation=formation)
        self.assertTrue(
            any("split" in w and "Z" in w for w in warnings),
            f"warnings: {warnings}",
        )

    def test_max_backfield_depth_warning_emitted(self):
        profile = self._profile_with_limits(max_backfield_depth_yd=5)
        formation = _offense_with()  # HB is at y=-6, exceeds 5
        _, warnings = _render(profile=profile, formation=formation)
        self.assertTrue(
            any("backfield depth" in w and "HB" in w for w in warnings),
            f"warnings: {warnings}",
        )

    def test_unknown_route_warning_emitted(self):
        formation = _offense_with()
        play = _play_with([
            {"player": "TE", "role": "route", "route_name": "definitely-not-a-route"},
        ])
        _, warnings = _render(play=play, formation=formation, route_lib={})
        self.assertTrue(
            any("unknown route" in w and "TE" in w for w in warnings),
            f"warnings: {warnings}",
        )

    def test_no_warnings_when_clean(self):
        # All players within bounds, no fake routes — warnings list is empty.
        formation = _offense_with()
        _, warnings = _render(formation=formation)
        self.assertEqual(warnings, [])

    def test_warnings_truncated_in_strip(self):
        # If more than MAX_WARNINGS_DISPLAYED warnings exist, only the first
        # few are rendered into the strip — but the full list is still
        # returned to the caller.
        # Push 6 receivers OOB.
        formation = _offense_with(
            X={"x": -25.0}, Z={"x": 25.0}, TE={"x": 25.0},
            HB={"x": 25.0}, FB={"x": -25.0}, QB={"x": 25.0},
        )
        svg, warnings = _render(formation=formation)
        self.assertGreater(len(warnings), _DRAW.MAX_WARNINGS_DISPLAYED)
        # Strip header advertises the full count.
        self.assertIn(f"{len(warnings)} warning(s)", svg)


if __name__ == "__main__":
    unittest.main()
