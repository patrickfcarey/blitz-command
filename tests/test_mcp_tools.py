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
        page = self.server.list_plays()
        self.assertIn("items", page)
        self.assertIn("next_cursor", page)
        self.assertGreater(len(page["items"]), 0)
        first = page["items"][0]
        for key in ("id", "name", "formation", "play_type", "ball_carrier", "tags"):
            self.assertIn(key, first)

    def test_list_plays_pagination_covers_all(self):
        seen_ids: set[str] = set()
        cursor = None
        while True:
            page = self.server.list_plays(cursor=cursor, limit=20)
            for item in page["items"]:
                seen_ids.add(item["id"])
            cursor = page["next_cursor"]
            if cursor is None:
                break
        self.assertGreater(len(seen_ids), 100)

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

    def test_save_play_refuses_existing(self):
        # Loading an already-saved play and trying to save without overwrite
        play = yaml.safe_load((REPO_ROOT / "data" / "plays" / "singleback-trio-mesh.yaml").read_text())
        result = self.server.save_play(play, overwrite=False)
        self.assertFalse(result["saved"])
        self.assertIn("already exists", result["skipped"])

    def test_save_play_refuses_invalid(self):
        bad = {"play_id": "test-bad-play", "name": "Bad"}  # missing required fields
        result = self.server.save_play(bad)
        self.assertFalse(result["saved"])
        self.assertFalse(result["validation"]["valid"])
        self.assertIn("validation failed", result["skipped"])

    def test_save_play_round_trip_cleanup(self):
        # Build a scaffold, fill the mandatory pieces, save it, then delete
        scaffold = self.server.build_starter_play(
            "singleback-trio", "pass", play_name="Tmp Save Test"
        )
        scaffold["play_id"] = "tmp-save-test-singleback-trio"
        result = self.server.save_play(scaffold)
        try:
            self.assertTrue(result["saved"], f"save failed: {result.get('skipped')}")
            self.assertTrue(Path(result["path"]).exists())
        finally:
            if result.get("saved") and result.get("path"):
                Path(result["path"]).unlink()

    def test_mirror_play_refuses_already_mirror(self):
        result = self.server.mirror_play("singleback-trio-mesh-left")
        self.assertFalse(result["saved"])
        self.assertIn("already a mirror", result["skipped"])

    def test_mirror_play_refuses_existing(self):
        # singleback-trio-mesh and its mirror both exist
        result = self.server.mirror_play("singleback-trio-mesh", overwrite=False)
        self.assertFalse(result["saved"])
        self.assertIn("already exists", result["skipped"])

    def test_mirror_play_refuses_missing_source(self):
        result = self.server.mirror_play("definitely-not-a-play")
        self.assertFalse(result["saved"])
        self.assertIn("source play not found", result["skipped"])

    def test_find_plays_by_concept_mesh(self):
        results = self.server.find_plays_by_concept("mesh")
        ids = [r["play_id"] for r in results]
        self.assertIn("singleback-trio-mesh", ids)
        for r in results:
            self.assertIn("matched_via", r)

    def test_find_plays_by_concept_triple_option(self):
        results = self.server.find_plays_by_concept("triple-option")
        ids = [r["play_id"] for r in results]
        self.assertIn("wishbone-triple-option", ids)
        self.assertIn("flexbone-triple-option", ids)

    def test_compare_plays_one_formation_high_disguise(self):
        result = self.server.compare_plays([
            "singleback-trio-inside-zone",
            "singleback-trio-outside-zone",
            "singleback-trio-power",
            "singleback-trio-mesh",
            "singleback-trio-pa-cross",
        ])
        self.assertTrue(result["all_same_formation"])
        self.assertEqual(result["formations"], ["singleback-trio"])
        self.assertGreaterEqual(len(result["play_types"]), 2)
        self.assertGreater(result["disguise_score"], 0.6)

    def test_compare_plays_mixed_formations_lower_disguise(self):
        result = self.server.compare_plays([
            "singleback-trio-mesh",
            "i-formation-power-o",
            "shotgun-2x2-snag",
        ])
        self.assertFalse(result["all_same_formation"])
        self.assertGreaterEqual(len(result["formations"]), 2)
        self.assertLess(result["disguise_score"], 0.6)

    def test_compare_plays_unknown_id_raises(self):
        with self.assertRaises(ValueError):
            self.server.compare_plays(["singleback-trio-mesh", "definitely-not-a-play"])

    def test_predict_matchup_flood_vs_cover_3_is_best(self):
        # Flood vs cover-3 is the textbook one-sided matchup
        result = self.server.predict_matchup("trey-right-flood", "defense-4-3-cover-3")
        self.assertEqual(result["rating"], "best")
        self.assertEqual(result["best_read"], "TE-R")
        self.assertGreater(len(result["play_best_vs_matches"]), 0)
        self.assertGreater(len(result["defense_vulnerabilities_exposed"]), 0)

    def test_predict_matchup_mesh_vs_cover_1_robber_neutral_or_best(self):
        # Mesh vs nickel cover-1 is genuinely contested in the data —
        # the play claims it beats cover-1, the defense claims it stops mesh.
        # Either 'neutral' or 'best' is acceptable — assert the rationale exposes both.
        result = self.server.predict_matchup("singleback-trio-mesh", "defense-nickel-cover-1")
        self.assertIn(result["rating"], ("neutral", "best"))
        self.assertGreater(len(result["play_best_vs_matches"]), 0)
        self.assertEqual(result["best_read"], "TE")

    def test_predict_matchup_unknown_play_raises(self):
        with self.assertRaises(ValueError):
            self.server.predict_matchup("not-a-play", "defense-4-3-cover-3")

    def test_predict_matchup_unknown_defense_raises(self):
        with self.assertRaises(ValueError):
            self.server.predict_matchup("singleback-trio-mesh", "not-a-defense")

    def test_list_play_templates_returns_concepts(self):
        templates = self.server.list_play_templates()
        self.assertGreater(len(templates), 0)
        ids = [t["concept_id"] for t in templates]
        self.assertIn("mesh", ids)
        self.assertIn("pa-y-cross", ids)
        for t in templates:
            for k in ("concept_id", "name", "play_type", "slots_used", "primary_read_slot"):
                self.assertIn(k, t)

    def test_list_play_templates_filter_by_play_type(self):
        pa_templates = self.server.list_play_templates(play_type="play-action")
        self.assertGreater(len(pa_templates), 0)
        for t in pa_templates:
            self.assertEqual(t["play_type"], "play-action")

    def test_build_starter_play_with_concept_pa_y_cross(self):
        play = self.server.build_starter_play(
            formation_id="singleback-trio",
            play_type="play-action",
            concept="pa-y-cross",
            play_name="PA Cross",
        )
        # TE should have deep-cross (not TODO)
        te = next(a for a in play["assignments"] if a["player"] == "TE")
        self.assertEqual(te["route_name"], "deep-cross")
        self.assertEqual(te["depth_yd"], 18)
        self.assertTrue(te.get("is_primary"))
        # Read tree filled
        self.assertEqual(play["primary_read"], "TE")
        self.assertIn(play["secondary_read"], ("Z", "X"))  # depends on which side is "right_outer"
        # QB has a real path (not just default 5-step)
        qb = next(a for a in play["assignments"] if a["player"] == "QB")
        self.assertEqual(len(qb["path"]), 4)  # pa-5-step-shotgun has 4 waypoints
        # HB is fake (PA mechanic)
        hb = next(a for a in play["assignments"] if a["player"] == "HB")
        self.assertEqual(hb["role"], "fake")

    def test_build_with_concept_then_validate_clean(self):
        play = self.server.build_starter_play(
            formation_id="singleback-trio",
            play_type="pass",
            concept="mesh",
            play_name="Mesh Tmp",
        )
        result = self.server.validate_play(play)
        self.assertTrue(result["valid"], f"errors: {result['errors']}, warnings: {result['warnings']}")
        # Routes should be real (not TODO-fill-in) since template filled them
        for a in play["assignments"]:
            if a.get("role") == "route":
                self.assertNotIn("TODO", a.get("route_name", ""))
        # Read tree should be filled (not TODO)
        self.assertNotEqual(play.get("primary_read"), "TODO")
        # No route_name foreign-key warnings
        route_warnings = [w for w in result["warnings"] if "data/routes/" in w]
        self.assertEqual(len(route_warnings), 0, f"unexpected route warnings: {route_warnings}")

    def test_build_with_unknown_concept_raises(self):
        with self.assertRaises(ValueError) as ctx:
            self.server.build_starter_play(
                "singleback-trio", "pass", concept="not-a-concept",
            )
        self.assertIn("unknown concept", str(ctx.exception))

    def test_validate_play_catches_unknown_route_name(self):
        play = yaml.safe_load((REPO_ROOT / "data" / "plays" / "singleback-trio-mesh.yaml").read_text())
        # Inject an invalid route_name on TE
        for a in play["assignments"]:
            if a["player"] == "TE":
                a["route_name"] = "made-up-route-name"
                break
        result = self.server.validate_play(play)
        self.assertTrue(any("not in data/routes/" in w for w in result["warnings"]))

    def test_export_play_instructions_markdown(self):
        md = self.server.export_play_instructions("singleback-trio-mesh", "madden-05-ps2")
        self.assertIsInstance(md, str)
        self.assertIn("# Recreate", md)
        self.assertIn("## Step 1 — set player cells", md)
        # Cells should be integers in markdown
        self.assertIn("(10, 5)", md)  # C is at (10, 5) on Madden 05

    def test_export_play_instructions_structured(self):
        result = self.server.export_play_instructions(
            "singleback-trio-mesh", "madden-05-ps2", format="structured",
        )
        self.assertEqual(result["formation"], "singleback-trio")
        self.assertEqual(result["snap_rule"], "integer cells only")
        # Every player cell must be an integer pair on Madden 05
        for label, cell in result["player_cells"].items():
            self.assertEqual(len(cell), 2, f"{label} cell should be (col, row)")
            self.assertIsInstance(cell[0], int, f"{label} col should be int")
            self.assertIsInstance(cell[1], int, f"{label} row should be int")
        # No two players share a cell
        cells_list = [tuple(c) for c in result["player_cells"].values()]
        self.assertEqual(len(set(cells_list)), len(cells_list), "no two players may share a cell")

    def test_export_play_instructions_unknown_play(self):
        with self.assertRaises(ValueError):
            self.server.export_play_instructions("not-a-play", "madden-05-ps2")

    def test_predict_matchup_offensive_formation_rejected(self):
        with self.assertRaises(ValueError) as ctx:
            self.server.predict_matchup("singleback-trio-mesh", "singleback-trio")
        self.assertIn("not a defensive formation", str(ctx.exception))

    def test_mirror_play_round_trip_cleanup(self):
        # Build a scaffold, save right-side, mirror it, then delete both
        scaffold = self.server.build_starter_play(
            "singleback-trio", "pass", play_name="Tmp Mirror Test"
        )
        scaffold["play_id"] = "tmp-mirror-test-singleback-trio"
        save_res = self.server.save_play(scaffold)
        right_path = save_res.get("path")
        mirror_res = None
        try:
            self.assertTrue(save_res["saved"])
            mirror_res = self.server.mirror_play("tmp-mirror-test-singleback-trio")
            self.assertTrue(mirror_res["saved"], f"mirror failed: {mirror_res.get('skipped')}")
            self.assertEqual(mirror_res["mirror_play_id"], "tmp-mirror-test-singleback-trio-left")
            mirror_path = Path(mirror_res["mirror_path"])
            self.assertTrue(mirror_path.exists())
            # Verify the mirror has flipped formation reference
            mirror_yaml = yaml.safe_load(mirror_path.read_text())
            self.assertEqual(mirror_yaml["formation"], "singleback-trio-left")
        finally:
            if right_path and Path(right_path).exists():
                Path(right_path).unlink()
            if mirror_res and mirror_res.get("mirror_path") and Path(mirror_res["mirror_path"]).exists():
                Path(mirror_res["mirror_path"]).unlink()


class TestFormationLibraryMCP(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = _load_module(
            "formation_server", REPO_ROOT / "mcps" / "formation-library-mcp" / "server.py",
        )

    def test_list_formations(self):
        page = self.server.list_formations()
        self.assertIn("items", page)
        self.assertIn("next_cursor", page)
        self.assertGreater(len(page["items"]), 0)
        sides = {f["side"] for f in page["items"]}
        self.assertIn("offense", sides)
        self.assertNotIn("defense", sides, "defense formations belong to coverage-mcp")

    def test_list_formations_pagination_covers_all(self):
        seen_ids: set[str] = set()
        cursor = None
        while True:
            page = self.server.list_formations(cursor=cursor, limit=10)
            for item in page["items"]:
                seen_ids.add(item["id"])
            cursor = page["next_cursor"]
            if cursor is None:
                break
        self.assertGreater(len(seen_ids), 20)

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


class TestValidateConcepRefForeignKeys(unittest.TestCase):
    """P5-T10 acceptance: validate_play warns on bad concept_ref values."""

    @classmethod
    def setUpClass(cls):
        cls.server = _load_module(
            "play_server", REPO_ROOT / "mcps" / "play-library-mcp" / "server.py",
        )

    def _base_play(self):
        return yaml.safe_load(
            (REPO_ROOT / "data" / "plays" / "singleback-trio-mesh.yaml").read_text()
        )

    def test_good_run_concept_ref_no_warning(self):
        play = self._base_play()
        play["run_concept_ref"] = "inside-zone"
        result = self.server.validate_play(play)
        self.assertFalse(any("run_concept_ref" in w for w in result["warnings"]))

    def test_bad_run_concept_ref_fires_warning(self):
        play = self._base_play()
        play["run_concept_ref"] = "nonexistent-concept-xyz"
        result = self.server.validate_play(play)
        self.assertTrue(any("run_concept_ref" in w for w in result["warnings"]))

    def test_bad_pass_concept_ref_fires_warning(self):
        play = self._base_play()
        play["pass_concept_ref"] = "does-not-exist"
        result = self.server.validate_play(play)
        self.assertTrue(any("pass_concept_ref" in w for w in result["warnings"]))

    def test_bad_philosophy_ref_fires_warning(self):
        play = self._base_play()
        play["philosophy_ref"] = "fake-philosophy"
        result = self.server.validate_play(play)
        self.assertTrue(any("philosophy_ref" in w for w in result["warnings"]))

    def test_good_philosophy_ref_no_warning(self):
        play = self._base_play()
        play["philosophy_ref"] = "west-coast"
        result = self.server.validate_play(play)
        self.assertFalse(any("philosophy_ref" in w for w in result["warnings"]))


class TestUpdatePlay(unittest.TestCase):
    """Roadmap Phase 1: update_play patches fields without re-authoring the whole YAML."""

    _play_id = "singleback-trio-mesh"
    _play_path = REPO_ROOT / "data" / "plays" / f"{_play_id}.yaml"

    @classmethod
    def setUpClass(cls):
        cls.server = _load_module(
            "play_server", REPO_ROOT / "mcps" / "play-library-mcp" / "server.py",
        )

    def setUp(self):
        # Snapshot the raw YAML before each test so tearDown can restore it exactly.
        self._original_bytes = self._play_path.read_bytes()

    def tearDown(self):
        self._play_path.write_bytes(self._original_bytes)
        # Invalidate the server's in-memory cache so subsequent tests see the restored file.
        self.server._invalidate_plays_cache()

    def test_update_known_field(self):
        play = self.server.get_play(self._play_id)
        orig_notes = play.get("notes")
        new_notes = "test-update-sentinel-xyz"
        self.assertNotEqual(orig_notes, new_notes)
        result = self.server.update_play(self._play_id, {"notes": new_notes})
        self.assertTrue(result["updated"])
        self.assertIn("notes", result["changed_keys"])

    def test_update_reports_unchanged_keys(self):
        play = self.server.get_play(self._play_id)
        current_name = play["name"]
        result = self.server.update_play(self._play_id, {"name": current_name})
        self.assertNotIn("name", result["changed_keys"])

    def test_update_missing_play_returns_not_updated(self):
        result = self.server.update_play("does-not-exist-xyz", {"notes": "x"})
        self.assertFalse(result["updated"])
        self.assertIsNotNone(result["skipped"])

    def test_update_includes_validation_result(self):
        result = self.server.update_play(self._play_id, {"primary_read": "Z"})
        self.assertIn("validation", result)
        self.assertIsNotNone(result["validation"])


class TestSaveFormation(unittest.TestCase):
    """Roadmap Phase 1: save_formation + update_formation write-tool symmetry."""

    @classmethod
    def setUpClass(cls):
        cls.server = _load_module(
            "formation_server", REPO_ROOT / "mcps" / "formation-library-mcp" / "server.py",
        )
        # formation_id is derived from name: "Test Formation Tmp" → "test-formation-tmp"
        cls._test_id = "test-formation-tmp"
        cls._test_path = REPO_ROOT / "data" / "formations" / f"{cls._test_id}.yaml"

    def tearDown(self):
        if self._test_path.exists():
            self._test_path.unlink()

    def _minimal_formation(self):
        return {
            "name": "Test Formation Tmp",
            "side": "offense",
            "personnel": "11",
            "strength_side": "right",
            "players": [
                {"label": "LT",   "position": "OL", "x": -4,  "y": 0, "on_line": True},
                {"label": "LG",   "position": "OL", "x": -2,  "y": 0, "on_line": True},
                {"label": "C",    "position": "OL", "x":  0,  "y": 0, "on_line": True},
                {"label": "RG",   "position": "OL", "x":  2,  "y": 0, "on_line": True},
                {"label": "RT",   "position": "OL", "x":  4,  "y": 0, "on_line": True},
                {"label": "TE",   "position": "TE", "x":  6,  "y": 0, "on_line": True},
                {"label": "X",    "position": "WR", "x": -15, "y": 0, "on_line": False},
                {"label": "Z",    "position": "WR", "x":  15, "y": 0, "on_line": False},
                {"label": "SLOT", "position": "WR", "x":  8,  "y": 0, "on_line": False},
                {"label": "QB",   "position": "QB", "x":  0,  "y": -5, "on_line": False},
                {"label": "HB",   "position": "HB", "x":  0,  "y": -8, "on_line": False},
            ],
            "tags": ["test"],
            "verification_status": "unverified",
        }

    def test_save_new_formation(self):
        result = self.server.save_formation(self._minimal_formation())
        self.assertTrue(result["saved"])
        self.assertTrue(self._test_path.exists())

    def test_save_refuses_overwrite_by_default(self):
        self.server.save_formation(self._minimal_formation())
        result = self.server.save_formation(self._minimal_formation())
        self.assertFalse(result["saved"])
        self.assertIn("overwrite", result["skipped"])

    def test_save_allows_overwrite(self):
        self.server.save_formation(self._minimal_formation())
        result = self.server.save_formation(self._minimal_formation(), overwrite=True)
        self.assertTrue(result["saved"])

    def test_save_missing_name_returns_error(self):
        data = self._minimal_formation()
        del data["name"]
        result = self.server.save_formation(data)
        self.assertFalse(result["saved"])
        # schema error for missing required "name", or missing id
        self.assertTrue(result["errors"] or result["skipped"])

    def test_update_formation_patches_field(self):
        self.server.save_formation(self._minimal_formation())
        result = self.server.update_formation(self._test_id, {"name": "Updated Name"})
        self.assertTrue(result["updated"])
        self.assertIn("name", result["changed_keys"])

    def test_update_formation_missing_returns_not_updated(self):
        result = self.server.update_formation("does-not-exist-xyz", {"name": "x"})
        self.assertFalse(result["updated"])


class TestPlaybookGenerationMCP(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = _load_module(
            "playbook_gen_server", REPO_ROOT / "mcps" / "playbook-generation-mcp" / "server.py",
        )

    def test_suggest_complementary_plays_recommends_missing_type(self):
        seed = ["singleback-trio-inside-zone", "singleback-trio-outside-zone"]
        results = self.server.suggest_complementary_plays(seed, max_results=5)
        self.assertGreater(len(results), 0)
        for r in results:
            self.assertIn("play_id", r)
            self.assertIn("reason", r)
            self.assertIn("score", r)
        reasons_text = " ".join(r["reason"] for r in results)
        self.assertTrue("pass" in reasons_text or "play-action" in reasons_text)

    def test_suggest_complementary_excludes_seed_and_mirrors(self):
        seed = ["singleback-trio-mesh"]
        results = self.server.suggest_complementary_plays(seed, max_results=10)
        ids = [r["play_id"] for r in results]
        self.assertNotIn("singleback-trio-mesh", ids)
        self.assertFalse(any(i.endswith("-left") for i in ids), "no -left mirrors should appear")

    def test_list_formations_with_plays_returns_strings(self):
        result = self.server.list_formations_with_plays()
        self.assertIsInstance(result, list)
        self.assertGreater(len(result), 0)
        self.assertIn("singleback-trio", result)

    def test_list_philosophies_with_plays_returns_strings(self):
        result = self.server.list_philosophies_with_plays()
        self.assertIsInstance(result, list)
        self.assertGreater(len(result), 0)

    def test_assemble_playbook_simple_returns_plays(self):
        result = self.server.assemble_playbook_simple(play_count=10)
        self.assertIn("plays", result)
        self.assertIn("count", result)
        self.assertLessEqual(result["count"], 10)

    def test_assemble_playbook_formation_filter(self):
        result = self.server.assemble_playbook_simple(
            formation_constraint="singleback-trio", play_count=5
        )
        for p in result["plays"]:
            self.assertIn("singleback-trio", p["formation"])


class TestPassConceptMCP(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = _load_module(
            "pass_concept_server", REPO_ROOT / "mcps" / "pass-concept-mcp" / "server.py",
        )

    def test_list_returns_concepts(self):
        page = self.server.list_pass_concepts()
        self.assertIn("items", page)
        self.assertGreater(len(page["items"]), 0)
        first = page["items"][0]
        for key in ("id", "name", "category", "best_vs_coverage", "tags"):
            self.assertIn(key, first)

    def test_get_known_concept(self):
        c = self.server.get_pass_concept("mesh")
        self.assertEqual(c["concept_id"], "mesh")
        self.assertIn("description", c)
        self.assertIn("best_vs_coverage", c)

    def test_get_unknown_raises(self):
        with self.assertRaises(ValueError):
            self.server.get_pass_concept("definitely-not-a-concept")

    def test_find_by_category(self):
        results = self.server.find_pass_concepts_by_category("area-read")
        self.assertIsInstance(results, list)
        self.assertGreater(len(results), 0)
        self.assertIn("smash", results)

    def test_find_best_vs_coverage_man(self):
        results = self.server.find_pass_concepts_best_vs_coverage("man")
        self.assertIsInstance(results, list)
        self.assertIn("mesh", results)

    def test_find_best_vs_coverage_cover_2(self):
        results = self.server.find_pass_concepts_best_vs_coverage("cover-2")
        self.assertIsInstance(results, list)
        self.assertIn("smash", results)

    def test_find_pairs_with(self):
        results = self.server.find_pass_concepts_pairs_with("west-coast")
        self.assertIsInstance(results, list)
        self.assertIn("mesh", results)

    def test_manifest_has_all_tools(self):
        m = self.server.manifest()
        tool_names = {t["name"] for t in m["tools"]}
        for expected in ("list_pass_concepts", "get_pass_concept",
                         "find_pass_concepts_by_category",
                         "find_pass_concepts_best_vs_coverage",
                         "find_pass_concepts_pairs_with", "manifest"):
            self.assertIn(expected, tool_names)


class TestGameKnowledgeTranslation(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = _load_module(
            "game_knowledge_server", REPO_ROOT / "mcps" / "game-knowledge-mcp" / "server.py",
        )

    def test_translate_position_ball_at_los(self):
        result = self.server.translate_position("madden-05-ps2", x_yd=0, y_yd=0)
        self.assertEqual(result["col"], 10)
        self.assertEqual(result["row"], 5)
        self.assertTrue(result["in_bounds"])

    def test_translate_position_qb_depth(self):
        # QB 2 yd back: row = 5 + (-2/2.0) = 4
        result = self.server.translate_position("madden-05-ps2", x_yd=0, y_yd=-2)
        self.assertEqual(result["row"], 4)
        self.assertTrue(result["in_bounds"])

    def test_translate_position_wr_split(self):
        # WR 15 yd right (max split): col = 10 + 15/1.667 ≈ 19
        result = self.server.translate_position("madden-05-ps2", x_yd=15, y_yd=0)
        self.assertAlmostEqual(result["col"], 19, delta=1)

    def test_translate_position_out_of_bounds(self):
        # Deep route well past the grid
        result = self.server.translate_position("madden-05-ps2", x_yd=0, y_yd=30)
        self.assertFalse(result["in_bounds"])

    def test_translate_position_ps1_raises(self):
        with self.assertRaises(ValueError):
            self.server.translate_position("madden-96-ps1", x_yd=0, y_yd=0)

    def test_translate_formation_returns_players(self):
        result = self.server.translate_formation("madden-05-ps2", "singleback-trio")
        self.assertIn("players", result)
        self.assertEqual(len(result["players"]), 11)
        for p in result["players"]:
            for key in ("label", "position", "col", "row", "in_bounds"):
                self.assertIn(key, p)

    def test_translate_formation_center_in_bounds(self):
        result = self.server.translate_formation("madden-05-ps2", "singleback-trio")
        center = next(p for p in result["players"] if p["label"] == "C")
        # Center at (0, 0) universal → col=10, row=5 in madden-05-ps2
        self.assertEqual(center["col"], 10)
        self.assertEqual(center["row"], 5)
        self.assertTrue(center["in_bounds"])

    def test_translate_formation_missing_raises(self):
        with self.assertRaises(ValueError):
            self.server.translate_formation("madden-05-ps2", "not-a-real-formation")

    def test_translate_play_returns_assignments(self):
        result = self.server.translate_play("madden-05-ps2", "singleback-trio-mesh")
        self.assertIn("assignments", result)
        self.assertGreater(len(result["assignments"]), 0)
        for a in result["assignments"]:
            self.assertIn("player", a)
            self.assertIn("waypoints", a)

    def test_translate_play_waypoints_have_cells(self):
        result = self.server.translate_play("madden-05-ps2", "singleback-trio-mesh")
        has_waypoints = [a for a in result["assignments"] if a["waypoints"]]
        self.assertGreater(len(has_waypoints), 0)
        for a in has_waypoints:
            for wp in a["waypoints"]:
                for key in ("x_yd", "y_yd", "col", "row"):
                    self.assertIn(key, wp)

    def test_translate_play_missing_raises(self):
        with self.assertRaises(ValueError):
            self.server.translate_play("madden-05-ps2", "not-a-real-play")


if __name__ == "__main__":
    unittest.main()
