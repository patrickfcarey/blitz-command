"""Smoke tests for tools/draw-play/draw.py — every render mode produces SVG."""
import importlib.util
import re
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
DRAW_PATH = REPO_ROOT / "tools" / "draw-play" / "draw.py"


def _import_draw():
    spec = importlib.util.spec_from_file_location("draw_play", DRAW_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class TestDrawTool(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.draw = _import_draw()
        cls.profile = yaml.safe_load(
            (REPO_ROOT / "data" / "games" / "madden-05-ps2" / "editor-grid.yaml").read_text()
        )
        cls.play = yaml.safe_load(
            (REPO_ROOT / "data" / "plays" / "singleback-trio-mesh.yaml").read_text()
        )
        cls.formation = yaml.safe_load(
            (REPO_ROOT / "data" / "formations" / "singleback-trio.yaml").read_text()
        )
        cls.defense = yaml.safe_load(
            (REPO_ROOT / "data" / "formations" / "defense-4-3-cover-3.yaml").read_text()
        )
        cls.routes = cls.draw.load_route_library()

    def _render(self, **kw):
        defaults = dict(
            profile=self.profile, play=self.play, formation=self.formation,
            defense=self.defense, route_lib=self.routes, show="both", field="long",
        )
        defaults.update(kw)
        svg, _ = self.draw.render(**defaults)
        return svg

    def test_offense_only(self):
        svg = self._render(defense=None)
        self.assertTrue(svg.startswith("<svg"))
        self.assertIn("singleback-trio", svg)

    def test_defense_only(self):
        svg = self._render(play=None, formation=None)
        self.assertTrue(svg.startswith("<svg"))

    def test_both_show_both(self):
        svg = self._render(show="both")
        self.assertIn("polyline", svg)

    def test_both_show_offense(self):
        svg = self._render(show="offense")
        self.assertIn("polyline", svg)

    def test_both_show_defense(self):
        svg = self._render(show="defense")
        self.assertIn("polyline", svg)

    def test_both_show_none(self):
        svg = self._render(show="none")
        self.assertIn("singleback-trio", svg)

    def test_field_short_is_shorter(self):
        # Parse the SVG root attribute properly rather than slicing string —
        # an unrelated child element with a `height=` attribute would have
        # silently corrupted the old assertion.
        long_svg = self._render(field="long")
        short_svg = self._render(field="short")
        long_h = int(ET.fromstring(long_svg).get("height"))
        short_h = int(ET.fromstring(short_svg).get("height"))
        self.assertLess(short_h, long_h, "short field should be shorter than long field")

    def _hash_tick_x_starts(self, svg: str) -> list[float]:
        """Return every <line>'s x1 attribute as a float (used by hash tests)."""
        return [float(m.group(1)) for m in re.finditer(r'<line\s+x1="([\d.]+)"', svg)]

    def _expected_hash_px(self, profile: dict, hash_x_yd: float) -> float:
        """Compute the SVG pixel column for a hash mark at `hash_x_yd` yards."""
        gx = profile["grid"]["origin"]["x"] + hash_x_yd / profile["scale"]["x_yards_per_cell"]
        # Mirror the renderer's universal_to_pixel: FIELD_MARGIN_PX + gx * PIXELS_PER_CELL.
        return self.draw.FIELD_MARGIN_PX + gx * self.draw.PIXELS_PER_CELL

    def test_nfl_hash_marks_at_expected_pixel_column(self):
        # Madden profiles use NFL hash distances (~3.083 yd from center).
        # Verify hash ticks are rendered at the corresponding pixel column —
        # this is what the user's eye actually sees, regardless of the exact
        # stroke / opacity attribute values.
        svg = self._render()
        spec = self.draw.hash_spec_for_profile(self.profile)
        self.assertIsNotNone(spec)
        right_hash_px = self._expected_hash_px(self.profile, spec[1])

        # The renderer subtracts the half-tick-width from x1, so search a
        # window around `right_hash_px - HASH_TICK_HALF_WIDTH_PX`.  Multiple
        # ticks (one per yard line) should land in this window.
        tick_starts = self._hash_tick_x_starts(svg)
        target = right_hash_px - self.draw.HASH_TICK_HALF_WIDTH_PX
        in_window = [
            x for x in tick_starts
            if abs(x - target) <= self.draw.HASH_MAJOR_EXTRA_HALF_PX + 0.5
        ]
        self.assertGreater(
            len(in_window), 5,
            f"expected multiple hash ticks at x≈{target}, got {in_window}",
        )

    def test_no_cell_overlaps_madden_05(self):
        """Every formation must place all players in distinct cells on Madden 05's grid."""
        from pathlib import Path
        formations_dir = REPO_ROOT / "data" / "formations"
        failures = []
        for fp in sorted(formations_dir.glob("*.yaml")):
            formation = yaml.safe_load(fp.read_text())
            cells = self.draw.assign_cells_for_formation(formation, self.profile)
            cell_list = [tuple(c) for c in cells.values()]
            seen = set()
            dups = []
            for c in cell_list:
                if c in seen:
                    dups.append(c)
                seen.add(c)
            if dups:
                failures.append(f"{fp.stem}: duplicate cells {dups}")
        self.assertEqual(failures, [], "\n".join(failures))

    def test_madden_05_cells_are_integer(self):
        from pathlib import Path
        formations_dir = REPO_ROOT / "data" / "formations"
        # Just check a few representative formations
        for fid in ("singleback-trio", "wing-t", "defense-46-bear-cover-0"):
            formation = yaml.safe_load((formations_dir / f"{fid}.yaml").read_text())
            cells = self.draw.assign_cells_for_formation(formation, self.profile)
            for label, cell in cells.items():
                self.assertIsInstance(cell[0], int, f"{fid}: {label} col must be int")
                self.assertIsInstance(cell[1], int, f"{fid}: {label} row must be int")

    def test_ncaa_hash_marks_at_different_position_than_nfl(self):
        # NCAA hashes (6.667 yd) sit further from center than NFL hashes
        # (3.083 yd).  On the same grid scale this maps to a distinct pixel
        # column.  The previous assertion (`stroke="#ffffff"` is in svg)
        # would also have passed for an NFL profile because hash marks share
        # the same color — this test verifies the position actually differs.
        ncaa_profile = yaml.safe_load(
            (REPO_ROOT / "data" / "games" / "ncaa-06-ps2" / "editor-grid.yaml").read_text()
        )
        ncaa_svg = self._render(profile=ncaa_profile)

        ncaa_spec = self.draw.hash_spec_for_profile(ncaa_profile)
        nfl_spec = self.draw.hash_spec_for_profile(self.profile)
        self.assertIsNotNone(ncaa_spec)
        self.assertIsNotNone(nfl_spec)
        self.assertGreater(ncaa_spec[1], nfl_spec[1],
                           "NCAA hashes are wider than NFL hashes")

        ncaa_right_px = self._expected_hash_px(ncaa_profile, ncaa_spec[1])
        ncaa_tick_starts = self._hash_tick_x_starts(ncaa_svg)
        target = ncaa_right_px - self.draw.HASH_TICK_HALF_WIDTH_PX
        in_window = [
            x for x in ncaa_tick_starts
            if abs(x - target) <= self.draw.HASH_MAJOR_EXTRA_HALF_PX + 0.5
        ]
        self.assertGreater(
            len(in_window), 5,
            f"expected NCAA hash ticks at x≈{target}, got nothing in window",
        )

        # And no NFL-position ticks should appear on the NCAA-profile SVG.
        nfl_target = self._expected_hash_px(ncaa_profile, nfl_spec[1])
        false_window = [
            x for x in ncaa_tick_starts
            if abs(x - (nfl_target - self.draw.HASH_TICK_HALF_WIDTH_PX)) <= 0.5
        ]
        self.assertEqual(
            false_window, [],
            f"NFL-position ticks must not appear on NCAA profile (found {false_window})",
        )


if __name__ == "__main__":
    unittest.main()
