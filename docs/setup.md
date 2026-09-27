# Setup

## Requirements

- Python 3.10+ (the `mcp` SDK requires it; the repo is built and tested against Python 3.11)
- Git

## First-time setup

```bash
# Create the venv (required because the system python is 3.9, too old for the mcp SDK)
python3.11 -m venv .venv

# Install all dependencies (mcp, pyyaml, jsonschema)
.venv/bin/pip install -r requirements.txt
```

## Running the test suite

```bash
./run-tests.sh
```

That script wraps `python -m unittest discover -s tests`. Tests cover:
- Schema validation for every YAML in `data/formations/`, `data/plays/`, `data/routes/`
- Cross-references (play.formation → existing formation, assignment.player → roster)
- Drawing tool — every render mode produces well-formed SVG, hash marks render
- MCP tools — list/get/find/validate/render/build_starter_play

## Running a tool directly

The drawing tool:
```bash
.venv/bin/python tools/draw-play/draw.py --play singleback-trio-mesh --game madden-05-ps2 -o out.svg
```

See `tools/draw-play/draw.py --help` for every flag (offense-only, defense-only, both with selective coverage display, short/long field).

## Running the MCP servers

Each server runs over stdio per the MCP protocol. Register them in your client's `.mcp.json` with absolute paths:

```json
{
  "mcpServers": {
    "play-library": {
      "command": "/abs/path/to/repo/.venv/bin/python",
      "args": ["/abs/path/to/repo/mcps/play-library-mcp/server.py"]
    },
    "formation-library": {
      "command": "/abs/path/to/repo/.venv/bin/python",
      "args": ["/abs/path/to/repo/mcps/formation-library-mcp/server.py"]
    }
  }
}
```

## Regenerating mirrors

When right-side plays change, regenerate left-side mirrors:

```bash
.venv/bin/python tools/generate-mirror-plays/generate.py
.venv/bin/python tools/generate-mirrors/generate.py    # formations
```

The generators skip mirrors that already exist — delete first if you want to regenerate.
