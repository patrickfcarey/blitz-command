# play-variant-mcp

MCP server for generating play variants and play-family stubs. **4 tools.** Phase 7 will add the full `generate_play_family` algorithm.

## Tools

- **`mirror_play_variant(play_id)`** — flip all x-coords + update play_id/name/formation for left/right mirror
- **`flip_strength(play_id)`** — swap strong ↔ weak in play_id, name, and formation
- **`generate_play_family_stub(base_play_id)`** — return an empty play-family YAML scaffold (Phase 7 placeholder)
- **`manifest()`** — server purpose, tool list, and worked examples

## Phase 7 additions (planned)

- `generate_play_family(base_play_id, family_size=5)` — scored companion-play list based on pre-snap disguise + play-type diversity
