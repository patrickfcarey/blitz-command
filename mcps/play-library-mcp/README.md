# play-library-mcp

MCP server that exposes blitz-command's play library to AI agents — discovery, authoring, validation, rendering, pairwise analysis, disguise families, and scouting. **22 tools** total.

**Boundary rule**: this server owns single-play concerns. Anything that reasons about a *collection* of plays as a unit (gap-filling, playbook selection, balance scoring) belongs in `playbook-generation-mcp`.

For end-to-end client setup + worked examples, see [`docs/using-the-mcps.md`](../../docs/using-the-mcps.md).

## Tools

### Discovery / read

- **`list_plays()`** — brief metadata for every play (id, name, formation, play_type, ball_carrier, tags)
- **`get_play(play_id)`** — full play YAML; suggests "Did you mean…?" on miss
- **`find_plays_by_formation(formation_id)`** — all plays that run from a given formation
- **`find_plays_by_tag(tag)`** — exact case-insensitive tag match (`air-raid`, `rpo`, `high-school`, `mesh`, etc.)
- **`find_plays_by_rpo_type(rpo_type)`** — RPO plays by sub-type: `alert` (pre-snap) / `peek` (post-snap LB read) / `read` (QB run threat)
- **`find_plays_by_concept(concept)`** — broader cross-field search (id stem + name + aliases + tags + formation concepts + concept refs — both the single `run/pass_concept_ref` and the multi-concept `concepts[]` array); returns the matched-via source for each result
- **`find_plays_vs_defense(coverage)`** — plays that exploit (`best`) or struggle against (`worst`) a coverage substring

### Authoring (closes the design loop)

- **`build_starter_play(formation_id, play_type, philosophy=None, play_name=None, concept=None)`** — returns a play scaffold. With `concept=...` (e.g. `'mesh'`, `'pa-y-cross'`), fills in canonical routes per slot, QB drop path, and read tree from the template registry — fully filled. Without it, returns a 70%-filled scaffold with TODO placeholders. PA play_type auto-sets HB to `fake`
- **`list_play_templates(play_type=None, philosophy=None)`** — list available concept templates for `build_starter_play(concept=...)`; filter by play_type or philosophy
- **`validate_play(play_data, strict=False)`** — schema check + concept lints (counter-trey wants 2 pullers, power wants 1 pulling guard, PA needs a fake, QB on pass needs a path, ball_carrier needs a path, unknown player refs flagged) + route foreign-key check (catches `route_name` that doesn't exist in `data/routes/`) + multi-concept `concepts[]` integrity (concept-ref FK resolves, player labels exist, exactly one `is_primary`) + `defensive_counters`/`flip_reads` id-uniqueness + TODO-placeholder scanner with field paths
- **`render_play(play_id, game_id, defense_id=None, show='both', field='long')`** — returns SVG markup directly. `show` ∈ {`offense`, `defense`, `both`, `none`}; `field` ∈ {`short` (LOS+15yd, deep DBs visible), `long` (LOS+30yd)}
- **`save_play(play_data, overwrite=False, validate_first=True)`** — validate then write to `data/plays/<play_id>.yaml`. Refuses to overwrite or to save invalid plays unless explicitly asked
- **`mirror_play(play_id, overwrite=False)`** — generate the `-left` mirror (flips x on every path/motion waypoint, swaps formation reference)

### Analysis / composition

- **`compare_plays(play_ids)`** — disguise + diversity scorecard for N plays. Returns formations / personnel / play_types / ball_carriers / shared_tags + a `disguise_score` (high when plays share formation+personnel but vary mechanics) and `diversity_score`
- **`predict_matchup(play_id, defense_id)`** — best/neutral/worst rating + rationale by cross-referencing the play's `best_vs_defense` against the defense's `coverage_shell` / `front` / `vulnerable_to` / `best_against`

> `suggest_complementary_plays` (gap-filling for an in-progress playbook) lives in `playbook-generation-mcp` — it reasons about a collection, not a single play.

### Disguise families / scouting

- **`list_families()`** — brief metadata for every disguise family in `data/play-families/` (base play, companion count, `disguise_score`)
- **`get_family(family_id)`** — full family record: base play, companions, `disguise_score`, `defensive_coverage_matrix`, source notes
- **`get_disguise_twins(play_id)`** — the families a play belongs to + its twin plays (the plays that show the defense the same pre-snap + early-action picture, then diverge)
- **`scout_play(play_id)`** — coaching scout: `defensive_counters` (the pre-snap looks that beat the play), `flip_reads` (when to flip the play's direction or the whole formation), and `rpo_type` (for RPOs), keyed to a one-glance QB read

## Setup

Requires **Python 3.10+** (mcp SDK requirement). The repo's `.venv` (created with `python3.11`) covers all MCPs.

```bash
python3.11 -m venv .venv
.venv/bin/pip install -r requirements.txt   # mcp + pyyaml + jsonschema
```

(Per-MCP `requirements.txt` files exist for standalone install but the repo-root `requirements.txt` covers everything.)

## Run standalone

```bash
.venv/bin/python mcps/play-library-mcp/server.py
```

Speaks MCP over stdio.

## Register with a client

See [`docs/using-the-mcps.md`](../../docs/using-the-mcps.md) for full client-setup instructions (Claude Desktop, Claude Code, custom clients). Short version:

```json
{
  "mcpServers": {
    "play-library": {
      "command": "/abs/path/to/blitz-command/.venv/bin/python",
      "args": ["/abs/path/to/blitz-command/mcps/play-library-mcp/server.py"]
    }
  }
}
```

Use **absolute paths** to both the venv Python and the server script.

## Data source

Reads YAML files from `data/plays/`. Each file is validated against `schemas/play.schema.json` at startup; bad files are skipped with a warning to stderr.

To add a new play through code (the recommended path), use `build_starter_play() → fill in → validate_play() → save_play()`. To add manually: drop a schema-valid YAML into `data/plays/` and the server picks it up on next start.

## Dependencies on `tools/draw-play/draw.py`

This server imports the renderer at runtime via `importlib` (see `_import_draw_module()` in `server.py`). If you rename or remove any of the symbols below, this server breaks. The full architecture of `draw.py` is in [`docs/draw-play-architecture.md`](../../docs/draw-play-architecture.md).

| Used in tool | `draw.py` symbol | Purpose |
|---|---|---|
| `render_play` | `load_route_library()` | Load all routes once before invoking `render()` |
| `render_play` | `render(profile, play=, formation=, defense=, route_lib=, show=, field=)` | Generate the SVG |
| `export_play_instructions` | `assign_cells_for_formation(formation, profile)` | Reproduce the same snapped cells the renderer would draw, so markdown / structured exports list cells the user can type into the editor verbatim |
| `export_play_instructions` | `load_route_library()` | Resolve route names for waypoint export |
| `export_play_instructions` | `route_lookup(routes_lib, name)` | Same as above |
| `export_play_instructions` | `receiver_route_path(x, y, route_def)` | Convert route waypoints to absolute universal-yard coordinates |

Behavioral contract — the renderer guarantees:
- `render(...)` returns `(svg, warnings)`. Warnings are non-fatal soft validation; the SVG is always well-formed.
- Cells from `assign_cells_for_formation` are integer `(col, row)` tuples when `profile.snap_to_cells` is true, fractional `(col, row)` floats otherwise.
- `route_lookup` returns `None` (not raises) for unknown routes; `render_play` propagates that as a warning, not an error.
- Hard failures from `draw.py` (`InvalidProfileError`, `CellAssignmentError`, etc.) escape as exceptions from the imported module — wrap calls with `try/except draw.DrawError` if you need to convert them into MCP error replies.

## What `verification_status` means

See [`docs/play-data-provenance.md`](../../docs/play-data-provenance.md) — `verification_status: verified` does **not** mean "in the game's built-in playbook"; it means "the football concept has been sourced."
