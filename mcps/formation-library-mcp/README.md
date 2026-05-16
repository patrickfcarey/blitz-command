# formation-library-mcp

MCP server that exposes blitz-command's **offensive** formation library to AI agents. Defensive formations are owned by coverage-mcp. **7 tools.**

For end-to-end client setup + worked examples, see [`docs/using-the-mcps.md`](../../docs/using-the-mcps.md).

## Tools

- **`list_formations(cursor=None, limit=50)`** — brief metadata for every formation (id, name, side, personnel, strength_side, tags). Paginated. Offensive formations only (most with `-left` mirrors)
- **`get_formation(formation_id)`** — full formation YAML; suggests "Did you mean…?" on miss
- **`find_formations_by_tag(tag)`** — exact case-insensitive tag match (`shotgun`, `flexbone`, `trips`, `11-personnel`, etc.)
- **`find_formations_by_concept(concept)`** — formations whose `run_concepts` or `pass_concepts` include this concept (e.g. `inside-zone`, `four-verticals`, `mesh`)
- **`save_formation(formation_data, overwrite=False)`** — validate and write a new formation YAML to `data/formations/`
- **`update_formation(formation_id, patch)`** — shallow-patch top-level fields of an existing formation (re-validates schema)
- **`manifest()`** — this server's purpose, tool list, and worked examples

## Setup

Requires **Python 3.10+** (mcp SDK requirement). The repo's `.venv` (created with `python3.11`) covers all MCPs.

```bash
python3.11 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

## Run standalone

```bash
.venv/bin/python mcps/formation-library-mcp/server.py
```

Speaks MCP over stdio.

## Register with a client

See [`docs/using-the-mcps.md`](../../docs/using-the-mcps.md) for full client setup. Short version:

```json
{
  "mcpServers": {
    "formation-library": {
      "command": "/abs/path/to/blitz-command/.venv/bin/python",
      "args": ["/abs/path/to/blitz-command/mcps/formation-library-mcp/server.py"]
    }
  }
}
```

Use **absolute paths**.

## Data source

Reads YAML files from `data/formations/` where `side != 'defense'`. Each file is validated against `schemas/formation.schema.json` at startup; bad files are skipped with a warning to stderr. Defensive formations (`side: defense`) are skipped here — they are served by coverage-mcp.

To add a new offensive formation, drop a schema-valid YAML into `data/formations/` and run `tools/generate-mirrors/generate.py` to auto-create the `-left` mirror.

## See also

- [`docs/coordinate-systems.md`](../../docs/coordinate-systems.md) — universal coordinate system used by every formation
- [`docs/formation-rules.md`](../../docs/formation-rules.md) — football legality (7 on line, eligible ends, 11-on-11)
- [`docs/formation-roadmap.md`](../../docs/formation-roadmap.md) — what formations exist and what's planned
