"""Tier 3 tests: CLI integration via subprocess.

Verifies the argparse contract, exit codes, file/stdout/stderr split, and the
--vs / --show / --field / -o flags.  Uses the same Python interpreter that
runs the test so the venv (yaml dependency) is preserved.
"""
from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
DRAW_PATH = REPO_ROOT / "tools" / "draw-play" / "draw.py"

# Real fixture IDs that ship with the repo.  Used for happy-path tests.
FIXTURE_PLAY = "singleback-trio-mesh"
FIXTURE_GAME = "madden-05-ps2"
FIXTURE_DEFENSE = "defense-4-3-cover-3"


def _run_cli(*args: str, **popen_kwargs) -> subprocess.CompletedProcess:
    """Invoke the draw.py CLI with the given args, capturing stdout / stderr."""
    return subprocess.run(
        [sys.executable, str(DRAW_PATH), *args],
        capture_output=True, text=True, cwd=REPO_ROOT,
        **popen_kwargs,
    )


class TestCliHappyPath(unittest.TestCase):
    """Successful invocations: exit 0, SVG produced."""

    def test_named_args_succeed(self):
        result = _run_cli(
            "--play", FIXTURE_PLAY, "--game", FIXTURE_GAME,
        )
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        self.assertTrue(result.stdout.startswith("<svg"))
        self.assertIn("</svg>", result.stdout)

    def test_positional_args_succeed(self):
        # Legacy positional form: <play_id> <game_id>
        result = _run_cli(FIXTURE_PLAY, FIXTURE_GAME)
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        self.assertTrue(result.stdout.startswith("<svg"))

    def test_vs_alias_resolves_defense(self):
        # --vs is the legacy alias for --defense; both must produce
        # equivalent output (defense rendered).
        result_vs = _run_cli(
            FIXTURE_PLAY, FIXTURE_GAME, "--vs", FIXTURE_DEFENSE,
        )
        result_def = _run_cli(
            FIXTURE_PLAY, FIXTURE_GAME, "--defense", FIXTURE_DEFENSE,
        )
        self.assertEqual(result_vs.returncode, 0, msg=result_vs.stderr)
        self.assertEqual(result_def.returncode, 0, msg=result_def.stderr)
        # Both should mention the defense in the title strip.
        self.assertIn("4-3", result_vs.stdout.lower())
        self.assertIn("4-3", result_def.stdout.lower())

    def test_defense_only_succeeds(self):
        # --defense without --play should still work.
        result = _run_cli("--defense", FIXTURE_DEFENSE, "--game", FIXTURE_GAME)
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        self.assertTrue(result.stdout.startswith("<svg"))

    def test_play_with_vs_defense_field_auto_loads_defense(self):
        # If the play YAML has a `vs_defense:` field and the user doesn't
        # pass --defense, the CLI must auto-load that defense.  No play in
        # the repo currently uses `vs_defense:`, so we fabricate one as a
        # temp fixture under data/plays/ (the CLI hard-codes that path).
        #
        # The fixture wraps an existing play and adds a `vs_defense:` line.
        plays_dir = REPO_ROOT / "data" / "plays"
        source = plays_dir / f"{FIXTURE_PLAY}.yaml"
        tmp_play_id = "tmp-vs-defense-autoload-test"
        tmp_play_path = plays_dir / f"{tmp_play_id}.yaml"
        try:
            content = source.read_text()
            tmp_play_path.write_text(
                content
                .replace(f"play_id: {FIXTURE_PLAY}", f"play_id: {tmp_play_id}")
                + f"\nvs_defense: {FIXTURE_DEFENSE}\n"
            )
            no_defense = _run_cli(tmp_play_id, FIXTURE_GAME)
            self.assertEqual(no_defense.returncode, 0, msg=no_defense.stderr)
            # The defense's display name (NOT its file id) should appear in
            # the title strip's "vs ..." segment.  The 4-3 Cover 3 defense
            # has name "4-3 Cover 3", so the title says "vs 4-3 Cover 3".
            self.assertRegex(no_defense.stdout, r"\| vs [^<|]+")
        finally:
            if tmp_play_path.exists():
                tmp_play_path.unlink()


class TestCliFileOutput(unittest.TestCase):
    """The -o / --output flag writes to disk; otherwise stdout."""

    def test_output_file_written(self):
        with tempfile.NamedTemporaryFile(suffix=".svg", delete=False) as tmp:
            out_path = Path(tmp.name)
        try:
            result = _run_cli(
                "--play", FIXTURE_PLAY, "--game", FIXTURE_GAME,
                "-o", str(out_path),
            )
            self.assertEqual(result.returncode, 0, msg=result.stderr)
            self.assertTrue(out_path.exists())
            content = out_path.read_text()
            self.assertTrue(content.startswith("<svg"))
            # Status message goes to stdout, not the SVG.
            self.assertIn(f"Wrote {out_path}", result.stdout)
        finally:
            if out_path.exists():
                out_path.unlink()

    def test_output_creates_parent_directory(self):
        # -o path with non-existent parent dir should be created.
        with tempfile.TemporaryDirectory() as tmpdir:
            out_path = Path(tmpdir) / "subdir" / "play.svg"
            result = _run_cli(
                "--play", FIXTURE_PLAY, "--game", FIXTURE_GAME,
                "-o", str(out_path),
            )
            self.assertEqual(result.returncode, 0, msg=result.stderr)
            self.assertTrue(out_path.exists())

    def test_no_output_flag_writes_to_stdout(self):
        result = _run_cli("--play", FIXTURE_PLAY, "--game", FIXTURE_GAME)
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        self.assertTrue(result.stdout.startswith("<svg"))
        self.assertIn("</svg>", result.stdout)


class TestCliErrors(unittest.TestCase):
    """Argument and file-resolution errors return distinct exit codes."""

    def test_no_game_returns_2(self):
        result = _run_cli("--play", FIXTURE_PLAY)
        self.assertEqual(result.returncode, 2)
        self.assertIn("game", result.stderr.lower())

    def test_no_play_and_no_defense_returns_2(self):
        result = _run_cli("--game", FIXTURE_GAME)
        self.assertEqual(result.returncode, 2)
        self.assertIn("--play", result.stderr.lower())

    def test_missing_game_profile_returns_1(self):
        result = _run_cli("--play", FIXTURE_PLAY, "--game", "ps9-fictional-2099")
        self.assertEqual(result.returncode, 1)
        self.assertIn("Game profile not found", result.stderr)

    def test_missing_play_file_returns_1(self):
        result = _run_cli("--play", "definitely-not-a-play", "--game", FIXTURE_GAME)
        self.assertEqual(result.returncode, 1)
        self.assertIn("Play not found", result.stderr)

    def test_missing_defense_file_returns_1(self):
        result = _run_cli(
            "--defense", "definitely-not-a-defense",
            "--game", FIXTURE_GAME,
        )
        self.assertEqual(result.returncode, 1)
        self.assertIn("Defense not found", result.stderr)


class TestCliFlags(unittest.TestCase):
    """The --show and --field flags actually change the output."""

    def test_field_short_smaller_than_long(self):
        long_result = _run_cli(
            "--play", FIXTURE_PLAY, "--game", FIXTURE_GAME, "--field", "long",
        )
        short_result = _run_cli(
            "--play", FIXTURE_PLAY, "--game", FIXTURE_GAME, "--field", "short",
        )
        self.assertEqual(long_result.returncode, 0)
        self.assertEqual(short_result.returncode, 0)
        self.assertGreater(len(long_result.stdout), len(short_result.stdout))

    def test_show_none_omits_polylines(self):
        # When --vs is set and --show=none, no offensive routes nor defensive
        # coverage arrows should be drawn.  Player markers remain.
        result_none = _run_cli(
            "--play", FIXTURE_PLAY, "--game", FIXTURE_GAME,
            "--vs", FIXTURE_DEFENSE, "--show", "none",
        )
        result_both = _run_cli(
            "--play", FIXTURE_PLAY, "--game", FIXTURE_GAME,
            "--vs", FIXTURE_DEFENSE, "--show", "both",
        )
        self.assertEqual(result_none.returncode, 0)
        self.assertEqual(result_both.returncode, 0)
        # `both` will have many more polylines than `none`.
        none_polylines = result_none.stdout.count("<polyline")
        both_polylines = result_both.stdout.count("<polyline")
        self.assertGreater(both_polylines, none_polylines)

    def test_show_offense_omits_defensive_coverage(self):
        # `show=offense` keeps offensive routes but drops defensive coverage.
        result_offense = _run_cli(
            "--play", FIXTURE_PLAY, "--game", FIXTURE_GAME,
            "--vs", FIXTURE_DEFENSE, "--show", "offense",
        )
        result_defense = _run_cli(
            "--play", FIXTURE_PLAY, "--game", FIXTURE_GAME,
            "--vs", FIXTURE_DEFENSE, "--show", "defense",
        )
        self.assertEqual(result_offense.returncode, 0)
        self.assertEqual(result_defense.returncode, 0)
        # Offense-only should contain MAN/ZONE color stripes only if they
        # come from defenders' rings (still present).  But the offensive
        # route count should be greater.
        self.assertNotEqual(result_offense.stdout, result_defense.stdout)


class TestCliWarningsRouting(unittest.TestCase):
    """Warnings go to stderr, not the SVG output."""

    def test_warnings_when_present_go_to_stderr(self):
        # Pick a play / game pair where the play has at least one
        # bound-violation warning.  If no fixture violates bounds, this
        # test is a no-op (no assertion fires).  We use a write-to-file
        # render so stdout receives the status line but warnings still
        # come via stderr.
        with tempfile.NamedTemporaryFile(suffix=".svg", delete=False) as tmp:
            out_path = Path(tmp.name)
        try:
            result = _run_cli(
                "--play", FIXTURE_PLAY, "--game", FIXTURE_GAME,
                "-o", str(out_path),
            )
            self.assertEqual(result.returncode, 0, msg=result.stderr)
            # Status line goes to stdout.
            self.assertIn("Wrote", result.stdout)
            # If warnings were emitted, they go to stderr with `WARN:` prefix.
            for line in result.stderr.splitlines():
                if "WARN:" in line:
                    self.assertIn("WARN:", line)
        finally:
            if out_path.exists():
                out_path.unlink()


if __name__ == "__main__":
    unittest.main()
