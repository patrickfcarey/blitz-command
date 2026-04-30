# play-library-mcp

MCP server that exposes blitz-command's play library to AI agents.

## Tools

- **`list_plays()`** — brief metadata for every play
- **`get_play(play_id)`** — full details on one play (assignments, motions, routes, reads, strengths, weaknesses, best/worst defenses)
- **`find_plays_by_formation(formation_id)`** — all plays that run from a given formation
- **`find_plays_by_tag(tag)`** — filter by tag (`run`, `pass`, `rpo`, `air-raid`, `high-school`, etc.)
- **`find_plays_vs_defense(coverage)`** — plays that exploit OR struggle against a coverage (returns `best` / `worst` ratings)

## Setup

Requires **Python 3.10+** (the `mcp` SDK does not support 3.9).

```
python3 -m venv .venv
source .venv/bin/activate
pip install -r mcps/play-library-mcp/requirements.txt
```

## Run standalone

```
python mcps/play-library-mcp/server.py
```

Speaks MCP over stdio.

## Register with Claude Code

Add to `.mcp.json` at the project root:

```json
{
  "mcpServers": {
    "formation-library": {
      "command": "python",
      "args": ["mcps/formation-library-mcp/server.py"]
    },
    "play-library": {
      "command": "python",
      "args": ["mcps/play-library-mcp/server.py"]
    }
  }
}
```

(Use the venv's python in `command` if you set one up: `.venv/bin/python`.)

Then start a Claude Code session — Claude sees both MCPs and all their tools.

## Data source

Reads YAML files from `data/plays/`. Each file is validated against `schemas/play.schema.json` at startup; bad files are skipped with a warning to stderr.

To add a new play: drop a YAML file into `data/plays/` matching the schema (and matching player labels in the referenced formation). Server picks it up on next start.
