#!/usr/bin/env python3
"""Translate a formation from universal football coordinates into a game's editor grid.

Universal coords are yards from the ball at the line of scrimmage; see
docs/coordinate-systems.md. Each game has an editor-grid profile under
data/games/<game-id>/editor-grid.yaml that describes how to map them.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import yaml
from jsonschema import ValidationError, validate

REPO_ROOT = Path(__file__).resolve().parents[2]
SCHEMA_DIR = REPO_ROOT / "schemas"


def load(path: Path) -> dict:
    with open(path) as f:
        return yaml.safe_load(f)


def translate_point(x: float, y: float, profile: dict) -> tuple[float, float]:
    origin = profile["grid"]["origin"]
    scale = profile["scale"]
    return (
        origin["x"] + x / scale["x_yards_per_cell"],
        origin["y"] + y / scale["y_yards_per_cell"],
    )


def player_warnings(player: dict, profile: dict) -> list[str]:
    warnings: list[str] = []
    limits = profile.get("limits") or {}
    grid = profile["grid"]
    gx, gy = translate_point(player["x"], player["y"], profile)

    if not 0 <= gx <= grid["width"]:
        warnings.append(f"{player['label']}: grid x={gx:.2f} outside [0, {grid['width']}]")
    if not 0 <= gy <= grid["height"]:
        warnings.append(f"{player['label']}: grid y={gy:.2f} outside [0, {grid['height']}]")

    max_split = limits.get("max_player_split_yd")
    if max_split is not None and abs(player["x"]) > max_split:
        warnings.append(
            f"{player['label']}: split |x|={abs(player['x']):.2f} > editor max ({max_split})"
        )

    max_depth = limits.get("max_backfield_depth_yd")
    if max_depth is not None and player["y"] < -max_depth:
        warnings.append(
            f"{player['label']}: backfield depth {abs(player['y']):.2f} > editor max ({max_depth})"
        )

    return warnings


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("formation", type=Path, help="Formation YAML (universal coords).")
    parser.add_argument("profile", type=Path, help="Game editor-grid profile (YAML or JSON).")
    parser.add_argument(
        "--no-validate",
        action="store_true",
        help="Skip JSON Schema validation of inputs.",
    )
    args = parser.parse_args()

    formation = load(args.formation)
    profile = load(args.profile)

    if not args.no_validate:
        try:
            with open(SCHEMA_DIR / "formation.schema.json") as f:
                validate(formation, json.load(f))
            with open(SCHEMA_DIR / "coordinate-map.schema.json") as f:
                validate(profile, json.load(f))
        except ValidationError as e:
            print(f"Schema validation failed: {e.message}", file=sys.stderr)
            return 2

    grid = profile["grid"]
    scale = profile["scale"]
    print(f"# {formation['name']} -> {profile['game_id']}")
    print(
        f"# grid {grid['width']} x {grid['height']}, "
        f"scale {scale['x_yards_per_cell']} yd/x-cell, "
        f"{scale['y_yards_per_cell']} yd/y-cell"
    )
    print()
    print(f"{'Player':<6} {'Pos':<4} {'X(yd)':>7} {'Y(yd)':>7}    {'Grid X':>8} {'Grid Y':>8}")
    print("-" * 52)

    all_warnings: list[str] = []
    for player in formation["players"]:
        gx, gy = translate_point(player["x"], player["y"], profile)
        print(
            f"{player['label']:<6} {player['position']:<4} "
            f"{player['x']:>7.2f} {player['y']:>7.2f}    "
            f"{gx:>8.2f} {gy:>8.2f}"
        )
        all_warnings.extend(player_warnings(player, profile))

    if all_warnings:
        print("\nWARNINGS:")
        for w in all_warnings:
            print(f"  - {w}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
