# run-concept-mcp

MCP server exposing blitz-command's run concept library. **6 tools.**

## Tools

- **`list_run_concepts(cursor, limit)`** — all concepts with id, name, category, aim_point, tags. Paginated.
- **`get_run_concept(concept_id)`** — full YAML: description, read_tree, blocking_scheme_ref, pulls_required, lead_blocker
- **`find_run_concepts_by_category(category)`** — gap-scheme / zone-scheme / option / man-blocking-scheme / misdirection
- **`find_run_concepts_by_aim_point(aim)`** — substring search in aim_point ('A-gap', 'perimeter', etc.)
- **`find_run_concepts_pairs_with(other_id)`** — concepts that pair with a given concept
- **`manifest()`** — this server's purpose, tool list, and worked examples

## Data source

`data/concepts/run-concepts/` validated against `schemas/run-concept.schema.json`.
