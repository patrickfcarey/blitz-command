# draw-play architecture

This is a tour of `tools/draw-play/draw.py` for someone who hasn't read it before. Read this first; it points you at the right section of the file for whatever you're trying to change.

For the coordinate-space transformations specifically, see [draw-play-pipeline.md](draw-play-pipeline.md).

## Data flow

```
data/games/<id>/editor-grid.yaml    GameProfile     ─┐
data/plays/<id>.yaml                Play            ─┤
data/formations/<id>.yaml           Formation       ─┤    render()      ──>  SVG string
data/formations/<def>.yaml          Formation       ─┤    + warnings list
data/routes/*.yaml                  RouteLibrary    ─┘
```

Five inputs go in, an SVG string and a `list[str]` of soft warnings come out. Hard errors (malformed inputs, BFS exhaustion) raise typed exceptions instead.

## File layout (16 numbered sections)

`draw.py` is a single module organized as numbered sections. Search for `# ===` to jump.

| Section | Lines (approx) | Contains |
|---------|---------------|----------|
| 0  Module identity & logging | 60–110   | `__version__`, `_git_rev()`, `logger`. |
| 1  Filesystem paths          | 113–125  | `REPO_ROOT`, `ROUTES_DIR`, `FORMATIONS_DIR`, `PLAYS_DIR`, `GAMES_DIR`. |
| 2a–2j Constants              | 130–460  | Football, layout, font, stroke, opacity, color, marker constants. **No magic numbers anywhere outside this block.** |
| 3  Position role sets        | 470–500  | `INTERIOR_OL`, `DEFENSIVE_DL`, `ZONE_ROLES`, `RUSH_ROLES`, `SPY_ROLES`, `MAN_ROLES`, `HOOK_LIKE_ROLES`. |
| 4  Domain types              | 510–580  | `TypedDict`s for `GameProfile`, `Play`, `Formation`, `Player`, `Route`, `Assignment`. |
| 4b Exception hierarchy       | 590–640  | `DrawError` and its 6 subclasses. |
| 4c Validators                | 650–820  | `_validate_profile`, `_validate_play`, `_validate_formation`, `_validate_route`, `_validate_show`, `_validate_field`. |
| 5  Text & XML utilities      | 830–880  | `xml_escape`, `wrap_text`. |
| 6  YAML loaders              | 890–960  | `load_yaml`, `load_route_library`. |
| 7  Hash-spec inference       | 970–1020 | `hash_spec_for_profile`. |
| 8  Coordinate conversions    | 1030–1100| `universal_to_grid`, `total_y_cells`, `grid_to_pixel`, `universal_to_pixel`. |
| 9  Cell assignment           | 1110–1310| `is_tight_cluster`, `_compute_preferred_cells`, `_bfs_score`, `_bfs_nearest_free_cell`, `assign_cells_for_formation`. |
| 10 Route resolution          | 1320–1390| `receiver_route_path`, `route_lookup`. |
| 11 SVG primitives            | 1400–1560| `svg_rect`, `svg_circle`, `svg_line`, `svg_text`, `svg_polyline`, `svg_ellipse`, `svg_arrow_marker`, `render_path_yd`, `render_zone_ellipse`. |
| 12 Style helpers             | 1570–1770| `style_for_player_read`, `style_for_alt_path_priority`, `beats_coverage_badge`, `offensive_player_fill`, `defender_fill`, `label_font_size`, `player_badge_text`, `explicit_path_style` + dispatch table. |
| 13 Layout                    | 1780–1980| `Layout`, `NoteRow`, `_FieldDims`, `_compute_field_dims`, `_compute_notes_height`, `_build_note_rows*`, `_compute_layout`. |
| 14a–e Component renderers    | 1990–2820| One function per visual concern: title strip, field background, grid lines, hash marks, LOS, depth limit, defenders, defensive coverage (rush/man/spy/zone), offensive routes, offensive players, legend, warnings strip, coaching notes. |
| 15 `render()` orchestrator   | 2830–2900| The single public render entry point + `_validate_render_inputs`, `_render_field_chrome`, `_render_play_overlay`, `_render_all_players`. |
| 16 CLI                       | 2910–end | `_build_arg_parser`, `_resolve_inputs`, `_resolve_inputs_safe`, `_render_safe`, `_emit_output`, `main`, `_configure_logging`. |

Total: ~3050 lines, 81 functions. No function exceeds 60 lines of *code* (some have long docstrings).

## Public API surface

External consumers (the MCP servers, the test suite) call only:

| Function | Used by |
|----------|---------|
| `render(profile, play=, formation=, defense=, route_lib=, show=, field=)` | `play-library-mcp:render_play`, all draw tests |
| `assign_cells_for_formation(formation, profile)` | `play-library-mcp:export_play_instructions` |
| `load_route_library()` | All play renders |
| `route_lookup(lib, name)` | `play-library-mcp:export_play_instructions` |
| `receiver_route_path(x, y, route)` | `play-library-mcp:export_play_instructions` |
| `hash_spec_for_profile(profile)` | Tests + future profile-aware code |

Everything else (functions starting with `_`, every internal helper) is private; don't reach into it from outside `draw.py`.

## Validation & exception model

Every public entry point validates its inputs at the boundary. Internal helpers can then trust their inputs and skip defensive checks.

```
DrawError                      ← catch this for any structured failure
├── InvalidProfileError        ← scale ≤ 0, missing grid, etc.
├── InvalidPlayError           ← missing required fields, bad assignments
├── InvalidFormationError      ← duplicate labels, non-finite coords
├── InvalidRouteError          ← missing path, malformed waypoints
├── CellAssignmentError        ← BFS exhausted (formation doesn't fit)
└── ConfigError                ← YAML unreadable / malformed / non-mapping
```

The CLI maps these to exit codes:

| Exit | Cause |
|------|-------|
| 0    | Success |
| 1    | Referenced file (play / formation / defense / profile) does not exist |
| 2    | Invalid CLI argument combination |
| 3    | Malformed config or domain validation failure |
| 99   | Unexpected / unclassified |

`render()` returns `(svg, warnings)` where `warnings` lists *soft* issues — out-of-bounds players, unknown route names. *Hard* failures raise an exception. The split rule: if the caller can sensibly produce output despite the issue, it's a warning; if the output would be wrong, it's an exception.

## Where to add things

| Task | Where |
|------|-------|
| New game profile | Add a `data/games/<id>/editor-grid.yaml` matching the schema. The renderer auto-discovers it. Add a hash-mark prefix branch in `hash_spec_for_profile` if needed. |
| New defensive coverage role | Pick a category: rush / man / spy / zone. Add the role string to the relevant `*_ROLES` frozenset (section 3). For zones, also add a branch in `_zone_drop_geometry` and decide if it's a `HOOK_LIKE_ROLES` member. |
| New offensive assignment role | Add to `_SIMPLE_ROLE_STYLES` dict (section 12) if it has a fixed color/marker, or extend `explicit_path_style` for conditional logic. |
| New color / font / stroke | Add a `Final` constant to the appropriate sub-section under section 2. **Never** inline a literal in a render helper. |
| New SVG element type | Add a `svg_*` builder to section 11 with assertions for non-negative dimensions. |
| New chrome strip (alongside title / legend / warnings / notes) | Add `_render_<name>_strip` to section 14e, give it a `<name>_top_y` and `<name>_h` field on `Layout`, update `_compute_layout` and `total_h`. |
| New warning kind | Append to the `warnings` list inside `_check_player_bounds`, `_render_route_assignment`, etc. The strip auto-truncates to `MAX_WARNINGS_DISPLAYED`; the full list still goes to the caller. |
| New render mode | Add to `_VALID_SHOW_VALUES` (a frozenset, section 4c). The `_render_play_overlay` and `_render_defense` dispatchers gate on the value. |
| New `--field` length | Add to `_VALID_FIELD_VALUES` (section 4c) plus a constant `FIELD_<NAME>_EXTRA_YD` and a branch in `_compute_field_dims`. |

## Tests

Six test modules under `tests/`:

| Module | Tests | What it covers |
|--------|-------|----------------|
| `test_draw_tool.py` | 11 | Smoke tests + behavior-based hash-mark tests + shorter-field test. |
| `test_draw_unit.py` | 25 | Pure-function units (hash spec, route resolution, mirroring, coordinate math, cell uniqueness across all 35 snapping profiles, style helpers). |
| `test_draw_render_components.py` | 32 | One test per render branch: each defense role, each offense role, each marker shape, each warning kind. |
| `test_draw_cli.py` | 17 | CLI argparse, exit codes, file vs stdout, flag plumbing. |
| `test_draw_validation.py` | 40 | Every validator rejects its specific failure mode; exception hierarchy; CLI exit code 3. |
| `test_draw_properties.py` | 32 | Determinism (render twice → identical), coordinate round-trip, bijection invariant, fault injection (20+ malformed shapes). |

Total: 157 tests, ~22s wall clock.

To add a test for a new feature, decide which module it belongs in (smoke vs unit vs component vs CLI vs validation vs property). Each module's docstring lists what it covers.

## Determinism & traceability

`render()` is deterministic *given the same inputs* — except for the provenance comment at the top of the SVG, which encodes the build version + git rev + UTC timestamp + input identifiers. To compare two SVGs byte-for-byte across runs, strip the provenance comment first (test_draw_properties has a helper).

## What's still rough

- Role names (`"primary_read"`, `"ball_carrier"`, `"lead_block"`, etc.) are strings scattered across the renderer, the play YAMLs, and the schema. A future pass should convert them to `Enum` types.
- Tests don't yet measure MC/DC coverage on compound predicates.
- `mypy --strict` and `ruff` are configured in `pyproject.toml` but not yet wired into CI.
- The renderer mutates `warnings` in place (`_render_play_overlay`, `_render_all_players`). Acceptable for a single-threaded tool but a cleaner pattern would return them.
