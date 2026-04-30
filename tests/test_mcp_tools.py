"""Smoke tests for the MCP server tools.

Calls each tool function directly (not over the MCP transport) to verify
input/output contracts.
"""
import importlib.util
import unittest
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class TestPlayLibraryMCP(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = _load_module(
            "play_server", REPO_ROOT / "mcps" / "play-library-mcp" / "server.py",
        )

    def test_list_plays_returns_metadata(self):
        plays = self.server.list_plays()
        self.assertGreater(len(plays), 0)
        first = plays[0]
        for key in ("id", "name", "formation", "play_type", "ball_carrier", "tags"):
            self.assertIn(key, first)

    def test_get_play_returns_full_play(self):
        play = self.server.get_play("singleback-trio-mesh")
        self.assertEqual(play["formation"], "singleback-trio")
        self.assertIn("assignments", play)

    def test_get_play_unknown_suggests(self):
        with self.assertRaises(ValueError) as ctx:
            self.server.get_play("singleback-trio-mes")
        self.assertIn("Did you mean", str(ctx.exception))

    def test_find_plays_by_formation(self):
        ids = self.server.find_plays_by_formation("singleback-trio")
        self.assertGreater(len(ids), 0)
        self.assertTrue(all("singleback-trio" in i for i in ids))

    def test_find_plays_by_tag(self):
        ids = self.server.find_plays_by_tag("rpo")
        self.assertGreater(len(ids), 0)

    def test_find_plays_vs_defense(self):
        results = self.server.find_plays_vs_defense("cover-3")
        self.assertGreater(len(results), 0)
        self.assertTrue(all(r["rating"] in ("best", "worst") for r in results))

    def test_validate_play_clean(self):
        play = yaml.safe_load((REPO_ROOT / "data" / "plays" / "singleback-trio-mesh.yaml").read_text())
        result = self.server.validate_play(play)
        self.assertTrue(result["valid"])
        self.assertEqual(result["errors"], [])

    def test_validate_play_catches_unknown_player(self):
        play = yaml.safe_load((REPO_ROOT / "data" / "plays" / "singleback-trio-mesh.yaml").read_text())
        play["assignments"].append({"player": "GHOST", "role": "route", "route_name": "drag"})
        result = self.server.validate_play(play)
        self.assertFalse(result["valid"])
        self.assertTrue(any("unknown player" in e for e in result["errors"]))

    def test_render_play_returns_svg(self):
        svg = self.server.render_play(
            "singleback-trio-mesh", "madden-05-ps2",
            defense_id="defense-4-3-cover-3", show="both", field="long",
        )
        self.assertTrue(svg.startswith("<svg"))
        self.assertIn("</svg>", svg)

    def test_build_starter_play_returns_filled_scaffold(self):
        scaffold = self.server.build_starter_play(
            "singleback-trio", "pass", philosophy="west-coast",
        )
        self.assertEqual(scaffold["formation"], "singleback-trio")
        self.assertEqual(scaffold["play_type"], "pass")
        self.assertEqual(scaffold["philosophy"], "west-coast")
        self.assertEqual(len(scaffold["assignments"]), 11)
        # OL pre-assigned
        ol = [a for a in scaffold["assignments"] if a["player"] in ("LT", "LG", "C", "RG", "RT")]
        self.assertEqual(len(ol), 5)
        self.assertTrue(all(a["role"] == "pass_block" for a in ol))

    def test_build_starter_play_pa_creates_fake(self):
        scaffold = self.server.build_starter_play("i-formation", "play-action")
        fakes = [a for a in scaffold["assignments"] if a.get("role") == "fake"]
        self.assertEqual(len(fakes), 1)

    def test_build_then_validate_roundtrip(self):
        scaffold = self.server.build_starter_play("singleback-trio", "pass")
        result = self.server.validate_play(scaffold)
        # Schema-valid (warnings allowed since TODOs remain)
        self.assertEqual(result["errors"], [])
        # Should warn about TODOs
        self.assertTrue(any("TODO" in w for w in result["warnings"]))


class TestFormationLibraryMCP(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = _load_module(
            "formation_server", REPO_ROOT / "mcps" / "formation-library-mcp" / "server.py",
        )

    def test_list_formations(self):
        formations = self.server.list_formations()
        self.assertGreater(len(formations), 0)
        sides = {f["side"] for f in formations}
        self.assertIn("offense", sides)
        self.assertIn("defense", sides)

    def test_get_formation(self):
        form = self.server.get_formation("singleback-trio")
        self.assertEqual(len(form["players"]), 11)

    def test_get_formation_unknown_suggests(self):
        with self.assertRaises(ValueError) as ctx:
            self.server.get_formation("singleback-tri")
        self.assertIn("Did you mean", str(ctx.exception))

    def test_find_formations_by_tag(self):
        ids = self.server.find_formations_by_tag("flexbone")
        self.assertIn("flexbone", ids)

    def test_find_formations_by_concept(self):
        ids = self.server.find_formations_by_concept("inside-zone")
        self.assertGreater(len(ids), 0)


if __name__ == "__main__":
    unittest.main()
