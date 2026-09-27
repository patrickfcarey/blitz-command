# coverage-mcp

MCP server that exposes blitz-command's defensive coverage library to AI agents. **6 tools.**

## Tools

- **`list_coverages(cursor=None, limit=50)`** — brief metadata for every coverage (id, name, front, coverage_shell, personnel, tags). Paginated
- **`get_coverage(coverage_id)`** — full formation YAML including player coords, responsibilities, best_against, vulnerable_to
- **`find_coverage_by_shell(shell)`** — filter by `cover-0` / `cover-1` / `cover-2` / `cover-3` / `cover-4`
- **`find_coverage_by_front(front)`** — filter by `4-3` / `3-4` / `4-2-5` / `46-bear` / `6-2` / `3-2-6`
- **`find_coverage_vulnerable_to(concept)`** — substring search in vulnerable_to arrays
- **`manifest()`** — this server's purpose, tool list, and worked examples

## Setup

```bash
python3.11 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

## Run standalone

```bash
.venv/bin/python mcps/coverage-mcp/server.py
```

## Register with a client

```json
{
  "mcpServers": {
    "coverage": {
      "command": "/abs/path/to/blitz-command/.venv/bin/python",
      "args": ["/abs/path/to/blitz-command/mcps/coverage-mcp/server.py"]
    }
  }
}
```

## Data source

Reads `data/formations/defense-*.yaml`. Each file must have `side: defense` and validate against `schemas/formation.schema.json`.
