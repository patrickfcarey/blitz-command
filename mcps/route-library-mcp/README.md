# route-library-mcp

MCP server that exposes blitz-command's route library to AI agents. **6 tools.**

## Tools

- **`list_routes(cursor, limit)`** — brief metadata for every route (id, name, aliases, category, beats_coverage, option_route, tags). Paginated.
- **`get_route(route_id)`** — full route YAML including path waypoints, break depth, and source notes
- **`find_routes_by_category(category)`** — filter by `quick` / `intermediate` / `deep` / `underneath` / `screen`
- **`find_routes_by_coverage(coverage)`** — filter by `man` / `zone` / `both`
- **`find_routes_by_depth(min_yd, max_yd)`** — filter by typical break depth in yards
- **`manifest()`** — this server's purpose, tool list, and worked examples

## Setup

```bash
python3.11 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

## Run standalone

```bash
.venv/bin/python mcps/route-library-mcp/server.py
```

## Register with a client

```json
{
  "mcpServers": {
    "route-library": {
      "command": "/abs/path/to/blitz-command/.venv/bin/python",
      "args": ["/abs/path/to/blitz-command/mcps/route-library-mcp/server.py"]
    }
  }
}
```

## Data source

Reads YAML files from `data/routes/`. Each file is validated against `schemas/route.schema.json` at startup.
