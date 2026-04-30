"""Validate every data file against its schema.

Run from repo root with the venv:
    .venv/bin/python -m pytest tests/test_schemas.py
or unittest:
    .venv/bin/python -m unittest tests.test_schemas
"""
import json
import unittest
from pathlib import Path

import yaml
from jsonschema import ValidationError, validate

REPO_ROOT = Path(__file__).resolve().parents[1]
SCHEMAS_DIR = REPO_ROOT / "schemas"
DATA_DIR = REPO_ROOT / "data"


def _load_schema(name: str) -> dict:
    with open(SCHEMAS_DIR / f"{name}.schema.json") as f:
        return json.load(f)


def _load_yaml(path: Path) -> dict:
    with open(path) as f:
        return yaml.safe_load(f)


def _validate_dir(schema_name: str, data_subdir: str):
    """Validate every YAML in data/<subdir>/ against schemas/<name>.schema.json.

    Returns (count, failures: list[(filename, error_message)]).
    """
    schema = _load_schema(schema_name)
    failures: list[tuple[str, str]] = []
    count = 0
    for path in sorted((DATA_DIR / data_subdir).glob("*.yaml")):
        count += 1
        try:
            data = _load_yaml(path)
            validate(data, schema)
        except ValidationError as e:
            failures.append((path.name, f"{e.message} at {'/'.join(str(p) for p in e.absolute_path)}"))
        except Exception as e:
            failures.append((path.name, f"load error: {e}"))
    return count, failures


class TestSchemas(unittest.TestCase):
    def test_plays_validate(self):
        count, failures = _validate_dir("play", "plays")
        self.assertGreater(count, 0, "expected at least one play file")
        self.assertEqual(failures, [], f"{len(failures)} play(s) failed schema validation")

    def test_formations_validate(self):
        count, failures = _validate_dir("formation", "formations")
        self.assertGreater(count, 0, "expected at least one formation file")
        self.assertEqual(failures, [], f"{len(failures)} formation(s) failed schema validation")

    def test_routes_validate(self):
        count, failures = _validate_dir("route", "routes")
        self.assertGreater(count, 0, "expected at least one route file")
        self.assertEqual(failures, [], f"{len(failures)} route(s) failed schema validation")

    def test_play_formation_references_resolve(self):
        """Every play.formation must point to an existing formation file."""
        formation_ids = {p.stem for p in (DATA_DIR / "formations").glob("*.yaml")}
        broken: list[tuple[str, str]] = []
        for path in sorted((DATA_DIR / "plays").glob("*.yaml")):
            data = _load_yaml(path)
            fid = data.get("formation")
            if fid and fid not in formation_ids:
                broken.append((path.name, fid))
        self.assertEqual(broken, [], f"{len(broken)} play(s) reference missing formations")

    def test_play_assignment_players_in_formation(self):
        """Every assignment.player must exist in the referenced formation's roster."""
        formations = {
            p.stem: _load_yaml(p) for p in (DATA_DIR / "formations").glob("*.yaml")
        }
        broken: list[tuple[str, str, str]] = []
        for path in sorted((DATA_DIR / "plays").glob("*.yaml")):
            data = _load_yaml(path)
            form = formations.get(data.get("formation"))
            if not form:
                continue
            roster = {p["label"] for p in form.get("players", [])}
            for a in data.get("assignments", []):
                p = a.get("player")
                if p and p not in roster:
                    broken.append((path.name, p, data["formation"]))
        self.assertEqual(broken, [], f"{len(broken)} play(s) reference players not in their formation")


if __name__ == "__main__":
    unittest.main()
