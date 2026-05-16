# blocking-scheme-mcp

MCP server exposing blitz-command's blocking scheme library. **6 tools.**

## Tools

- **`list_blocking_schemes(cursor=None, limit=50)`** — all schemes with id, name, category, tags. Paginated
- **`get_blocking_scheme(scheme_id)`** — full YAML: description, assignments_by_position, defeats, vulnerable_to
- **`find_schemes_by_category(category)`** — pass-protection / run-blocking / pull-block / combo
- **`find_schemes_that_defeat(defensive_concept)`** — substring search in defeats arrays
- **`find_schemes_vulnerable_to(pressure)`** — substring search in vulnerable_to arrays
- **`manifest()`** — this server's purpose, tool list, and worked examples

## Data source

`data/concepts/blocking-schemes/` validated against `schemas/blocking-scheme.schema.json`.
