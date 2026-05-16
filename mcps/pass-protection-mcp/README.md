# pass-protection-mcp

MCP server exposing blitz-command's pass protection library. **5 tools.**

## Tools

- **`list_pass_protections(cursor, limit)`** — all protections with id, name, protection_type, tags. Paginated.
- **`get_pass_protection(protection_id)`** — full YAML: description, assignments_by_position, vulnerable_to
- **`find_protections_by_type(protection_type)`** — 5-man / 6-man / 7-man / slide / half-slide / boss / big-on-big
- **`find_protections_vulnerable_to(pressure)`** — substring search in vulnerable_to arrays
- **`manifest()`** — this server's purpose, tool list, and worked examples

## Data source

`data/concepts/pass-protections/` validated against `schemas/pass-protection.schema.json`.
