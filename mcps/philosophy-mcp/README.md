# philosophy-mcp

MCP server exposing blitz-command's offensive philosophy library. **6 tools.**

## Tools

- **`list_philosophies()`** — all philosophies with id, name, era, tendency_profile, tags
- **`get_philosophy(philosophy_id)`** — full YAML: description, originators, canonical concepts, formation_preferences, tendency_profile
- **`find_philosophies_by_era(era)`** — substring search in era field
- **`find_philosophies_by_originator(name)`** — substring search in originators + notable_practitioners
- **`find_philosophies_by_tendency(...)`** — filter by run_pct / pass_pct / rpo_pct thresholds
- **`manifest()`** — server purpose, tool list, and worked examples

## Data source

`data/concepts/philosophies/` (24 philosophies) validated against `schemas/philosophy.schema.json`.
