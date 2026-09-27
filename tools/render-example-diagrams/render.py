#!/usr/bin/env python3
"""Regenerate every example play diagram under examples/play-diagrams/.

Each diagram is named `<play_id>--<game>.svg`. This re-renders every one from
its current play data with the current draw tool, so the committed example
diagrams never drift from draw.py's output — e.g. after a palette change,
which is exactly how the committed set went stale (dark palette) once.

Re-run this whenever draw.py's rendering changes.

Run from the repo root:
    python3 tools/render-example-diagrams/render.py
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DIAGRAMS_DIR = REPO_ROOT / "examples" / "play-diagrams"
PLAYS_DIR = REPO_ROOT / "data" / "plays"
DRAW_SCRIPT = REPO_ROOT / "tools" / "draw-play" / "draw.py"


def main() -> None:
    """Re-render every examples/play-diagrams/*.svg from its play and game."""
    rendered: list[str] = []
    orphaned: list[str] = []
    failed: list[str] = []

    for svg_path in sorted(DIAGRAMS_DIR.glob("*.svg")):
        # Filename is "<play_id>--<game>.svg"; play_ids carry single hyphens,
        # so the double-hyphen is an unambiguous separator.
        name_parts = svg_path.stem.split("--")
        if len(name_parts) != 2:
            failed.append(f"{svg_path.name}: unexpected filename")
            continue
        play_id, game = name_parts
        if not (PLAYS_DIR / f"{play_id}.yaml").exists():
            orphaned.append(play_id)
            continue
        result = subprocess.run(
            [sys.executable, str(DRAW_SCRIPT), "--play", play_id,
             "--game", game, "-o", str(svg_path)],
            capture_output=True, text=True, timeout=90,
        )
        if result.returncode == 0:
            rendered.append(play_id)
        else:
            failed.append(f"{play_id}: {result.stderr.strip()[:120]}")

    print(f"re-rendered {len(rendered)} example diagrams")
    if orphaned:
        print(f"orphaned — no play file, left untouched ({len(orphaned)}): "
              f"{sorted(orphaned)}")
    if failed:
        print(f"FAILED ({len(failed)}): {failed}")


if __name__ == "__main__":
    main()
