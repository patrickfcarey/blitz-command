# formation-library-mcp

MCP server that exposes blitz-command's formation library to AI agents.

## Tools

- **`list_formations()`** — brief metadata for every formation
- **`get_formation(formation_id)`** — full details on one formation (players, strengths, weaknesses, concepts, etc.)
- **`find_formations_by_tag(tag)`** — filter by tag (e.g. `spread`, `power`, `jumbo`, `high-school`, `college`, `nfl`)
- **`find_formations_by_concept(concept)`** — find formations that pair with a given run/pass concept (e.g. `inside-zone`, `four-verticals`, `mesh`)

## Setup

Requires **Python 3.10+** (the `mcp` SDK does not support 3.9).

```
python3 -m venv .venv
source .venv/bin/activate
pip install -r mcps/formation-library-mcp/requirements.txt
```

## Run standalone

```
python mcps/formation-library-mcp/server.py
```

The server speaks MCP over stdio.

## Register with Claude Code

Add to `.mcp.json` at the project root:

```json
{
  "mcpServers": {
    "formation-library": {
      "command": "python",
      "args": ["mcps/formation-library-mcp/server.py"]
    }
  }
}
```

(If you used a venv, point `command` at the venv's python: `.venv/bin/python`.)

Then start a Claude Code session in this repo — Claude will see the four tools above.

## Data source

Reads YAML files from `data/formations/`. Each file is validated against `schemas/formation.schema.json` at server startup; bad files are skipped with a warning to stderr (the server keeps running for the rest).

To add a new formation: drop a YAML file into `data/formations/` matching the schema. The server picks it up on next start.
