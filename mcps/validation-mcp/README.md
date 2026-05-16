# validation-mcp

Central validation server for all blitz-command data types. **7 tools.**

## Tools

- **`validate_play(play_data, strict=False)`** — schema + concept lints: formation cross-ref, route ref, TODO scan, concept foreign keys
- **`validate_formation(formation_data, strict=False)`** — schema + 11-man + 7-on-line checks
- **`validate_route(route_data, strict=False)`** — schema + path waypoint check
- **`validate_concept(concept_data, kind, strict=False)`** — schema for run-concept / pass-concept / blocking-scheme / pass-protection / philosophy
- **`validate_game_profile(profile_data, strict=False)`** — schema + editor-fields consistency
- **`lint_play(play_data)`** — concept-level lints only (no schema; fast path for pre-validated plays)
- **`manifest()`** — server purpose, tool list, and worked examples

## Concept foreign-key checks

When a play declares `run_concept_ref`, `pass_concept_ref`, `pass_protection_ref`, or `philosophy_ref`, the server verifies the referenced file exists in `data/concepts/`.

## Data source

Reads schemas from `schemas/`. Cross-reference checks read live data from `data/formations/`, `data/routes/`, and `data/concepts/`.
