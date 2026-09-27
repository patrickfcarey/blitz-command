# coordinate-translator

Convert a formation from the universal football coordinate system (yards from the ball at the LOS) into a specific game's editor-grid coordinates.

## Setup

```
python3 -m venv .venv
source .venv/bin/activate
pip install -r tools/coordinate-translator/requirements.txt
```

## Usage

From the repo root:

```
python tools/coordinate-translator/translate.py \
    data/formations/i-formation.yaml \
    data/games/ncaa-06-ps2/editor-grid.yaml
```

The script validates both inputs against the JSON Schemas in `schemas/`, prints each player's universal and grid coordinates, and lists any positions that fall outside the editor's representable range.

Exit codes:

- `0` — translation completed, no warnings
- `1` — translation completed, one or more warnings
- `2` — schema validation failed

Pass `--no-validate` to skip schema checks (useful while iterating on a profile).

## See also

- `docs/coordinate-systems.md` — universal coordinate spec
- `schemas/formation.schema.json` — formation schema
- `schemas/coordinate-map.schema.json` — game-profile schema
