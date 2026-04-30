"""Smoke tests for tools/draw-play/draw.py — every render mode produces SVG."""
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
        long_svg = self._render(field="long")
        short_svg = self._render(field="short")
        long_h = int(long_svg.split('height="', 1)[1].split('"', 1)[0])
        short_h = int(short_svg.split('height="', 1)[1].split('"', 1)[0])
        self.assertLess(short_h, long_h, "short field should be shorter than long field")

    def test_nfl_hash_marks_present(self):
        svg = self._render()
        # NFL hash ticks rendered as white short lines with stroke-opacity
        self.assertIn('stroke="#ffffff" stroke-width="1.4" stroke-opacity="0.85"', svg)

    def test_ncaa_hash_marks_present(self):
        ncaa_profile = yaml.safe_load(
            (REPO_ROOT / "data" / "games" / "ncaa-06-ps2" / "editor-grid.yaml").read_text()
        )
        svg = self._render(profile=ncaa_profile)
        self.assertIn('stroke="#ffffff"', svg)


if __name__ == "__main__":
    unittest.main()
