# pass-concept-mcp

MCP server that exposes blitz-command's pass concept library to AI agents. **6 tools.**

Mirrors the `run-concept-mcp` pattern for pass-side concepts: Mesh, Smash, Snag, Four Verticals, Flood, Dagger, etc.

## Tools

- **`list_pass_concepts(cursor, limit)`** — all concepts with id, category, best_vs_coverage, tags. Paginated.
- **`get_pass_concept(concept_id)`** — full YAML: description, read progression, best_vs_coverage, attacks, pairs_with
- **`find_pass_concepts_by_category(category)`** — filter by `timing-route` / `area-read` / `vertical-stretch` / `horizontal-stretch` / etc.
- **`find_pass_concepts_best_vs_coverage(coverage)`** — concepts best against a coverage type (man, cover-2, cover-3, zone…). Substring match.
- **`find_pass_concepts_pairs_with(other_id)`** — concepts that pair with a given concept, philosophy, or tag
- **`manifest()`** — this server's purpose and worked examples

## Data source

`data/concepts/pass-concepts/` — 16 YAML files validated against `schemas/pass-concept.schema.json`.

## Setup

```bash
python3.11 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python mcps/pass-concept-mcp/server.py
```

## Register with a client

```json
{
  "mcpServers": {
    "pass-concept-library": {
      "command": "/abs/path/to/.venv/bin/python",
      "args": ["/abs/path/to/mcps/pass-concept-mcp/server.py"]
    }
  }
}
```
