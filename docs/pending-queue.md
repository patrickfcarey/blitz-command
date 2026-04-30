# Pending Queue

Living list of open work, organized by category. Update as items land.

Format: a short title + 1-line description. Add a `**(blocked: ...)**` note when an item depends on something external (user input, upstream work, etc.).

---

## Highest leverage right now

- **Make MCPs actually useful + document them.** Both servers (`formation-library-mcp`, `play-library-mcp`) are built and tested but not invoked anywhere — they wrap data that's currently read directly from files. Action: (a) write `docs/using-the-mcps.md` showing how to register them in `.mcp.json`, what tools they expose, example queries, and which AI clients can use them; (b) demonstrate their value with a worked example (e.g. ChatGPT or another Claude session querying via MCP); (c) consider whether the *current* drawing/editing workflow should call them too (or if direct file reads are fine here and the MCPs exist for external consumers).

- **Make the MCPs usable by smaller AIs (Sonnet / Haiku) for play design.** Today the MCPs only support retrieval. A smaller model trying to *design* a play needs more. Plan:
  - **(a) Top-3 ship-first improvements** that close the design loop:
    1. Add `render_play(play_id, game_id)` and `validate_play(play_data, game_id)` MCP tools — the AI can author + validate + visualize without leaving the chat.
    2. Add `build_starter_play(formation_id, play_type, philosophy)` returning a 70%-filled YAML scaffold. Smaller models excel at filling in, struggle at authoring from scratch.
    3. Rewrite all existing tool docstrings with worked examples + enum hints (e.g. list common tag values). Pure mechanical change, biggest accuracy win.
  - **(b) New MCP servers/tools** (after the data lands):
    - `route-library-mcp` (list / get / find by category / find by coverage)
    - `run-concept-mcp`, `blocking-scheme-mcp`, `coverage-mcp` (after the concept libraries are built — see Phase 5 work below)
    - `game-knowledge-mcp` exposing the editor-grid + capabilities + limits in one bundled call
  - **(c) Composition tools on existing MCPs**: `mirror_play`, `describe_play`, `compare_plays`, `suggest_complementary(play_id)` (returns 3-5 paired plays), `find_plays_by_concept`, `find_plays_for_situation`.
  - **(d) Workflow scaffolding**: a `/design-a-play` skill (or MCP prompt) walking the AI through the full design recipe — pick formation → pick concept → fill assignments → validate → render. Smaller models follow recipes much better than they author them.
  - **(e) Data improvements that unblock these tools**: explicit `family:` field on plays for play-graph queries, standardized concept references (foreign-key validated once `data/concepts/` exists), 1-2 sentence `description:` field per play tuned for AI consumption.
  - **(f) AI-friendliness polish**: pagination on `list_*` tools, actionable error messages with `Did you mean...?` suggestions, server-level `__doc__` describing the MCP's purpose.
  - **(g) Persistence / write tools** *(critical gap from gap analysis 2026-04-30)*: `save_play(play_yaml, validate=True)`, `save_formation(formation_yaml)`, `save_route(route_yaml)` — AI must be able to commit authored plays back to the library. Plus `update_play(play_id, patch)` for incremental fixes (avoids wasting context re-authoring whole YAML).
  - **(h) Cross-MCP meta-tools**: `/help` or `manifest()` per server announcing purpose + tools + examples. Plus `find_play_for_situation(formation_constraint, defense, philosophy)` doing the multi-MCP join so smaller AIs don't have to coordinate 5 calls.
  - **(i) Pattern library**: 10-15 named play templates (`template:power-run`, `template:y-cross-pa`, `template:stretch-zone`) with the structural skeleton already filled in. AI picks template + fills receivers / targets / coverage tweaks.
  - **(j) AI onboarding & worked examples**: `docs/ai-onboarding.md` — concrete tutorial for a new Sonnet/Haiku model joining the repo. Plus `examples/play-design-walkthroughs/` with 5-10 fully-narrated tool-call sequences. Smaller models learn from examples >> abstract docs.
  - **(k) Provenance tracking**: when an AI saves a play, auto-record authoring model, sources referenced, timestamp, validation pass. Stored in `source_notes`. Useful for auditing once library scales.
  - **(l) Sanity / common-mistakes linter**: beyond schema + legality, catch concept-level errors ("Counter Trey should have 2 pullers, you specified 1"; "Mesh point depths don't match between crossers"; "WR split exceeds editor max"). Saves AI iterations.
  - **(m) Defensive matchup analysis** *(Phase 7+, after defensive side lands)*: `predict_matchup(play_id, def_formation, coverage)` → structured "this play vs this defense" with best read, worst case, expected yards. Killer feature for playbook design.
- **Document play-data provenance.** Add `docs/play-data-provenance.md` explaining the distinction between (a) **generic-football** plays (drafted from training data + WebSearch + coaching texts — what currently fills `data/plays/`) and (b) **Madden-canonical** plays (extracted from a specific game's actual playbook — currently zero of these). Make clear that `verification_status` on a play file does NOT mean "matches the game's built-in playbook" — it means "the football concept is sourced." Future contributors and AI agents need this distinction explicitly.
- **Game measurements.** *(blocked: user)* Diagrams against any game profile are placeholder-accurate until `data/games/<game-id>/editor-grid.yaml` is filled in via `docs/game-editor-measurement-protocol.md`. Madden 2005 PS2 partially measured (grid + y-scale + x-scale ≈ 9-cell-default-WR + ≥20 yd route depth); still need: max player split, max backfield depth, motion options, max plays per playbook.

## Drawing improvements

- **Blocking arrows** on the SVG (need defensive players for block targets, OR draw arrows in named direction).
- **Motion arrows** as curved dashed lines from start → end position.
- **Option-route branching** (snag / stick currently render only primary path; show both branches).
- **Defensive overlay** — once defensive formations exist, draw the defense in muted color.
- **Animation** — SVG `<animate>` to show route progression.
- **`draw_play` MCP tool** — wrap the drawing script as an MCP tool inside `play-library-mcp` so AI agents can render plays on demand.

## More plays

- Plays for the formations that still have **none**: Strong I, Weak I, Big I, Full House, Empty, I-Formation Twins Weak, Shotgun 2x1 TE-Strong, Shotgun 2x1 TE-Weak, Shotgun 3x0.
- Plays for **17 mirror formations** (or build an auto-mirror tool similar to `tools/generate-mirrors/`).
- Round out existing formations' playbooks — e.g. I-Form needs Sweep / Off-Tackle / Smash variants; Singleback Ace needs PA / Y-Stick / Bootleg from 12P; Wing-T needs Boot / Waggle / Down / Reverse / Belly Pass / Jet Sweep; Wildcat needs Pass / Speed Option / Reverse.

## Future formations (offensive)

- Wishbone, Flexbone (option / academy football)
- Single Wing, Double Wing (HS / youth throwback)
- Singleback Doubles / Trips / Bunch / Big variants
- Empty 5-wide (00 personnel, no TE)
- Pistol Diamond / Pistol Trips
- Run-and-Shoot

## Defensive side (entirely new track)

- Defensive formation schema — fronts (4-3, 3-4, 4-2-5, 3-3-5, 46 Bear) + coverage shells (Cover 0/1/2/3/4, Tampa 2, pattern-match)
- Defensive formation files (~12-15 once schema lands)
- Defensive coverage library (zones with assignments + responsibilities)

## More schemas

- `blocking.schema.json`
- `playbook.schema.json`
- Run concept schema (separate from plays — concepts as reusable building blocks)

## More data libraries (Phase 5)

- Blocking scheme library (man, zone, gap, pull, slide, max)
- Run concept library (Power, Counter, Iso, Inside Zone, Outside Zone, Trap, Draw, Sweep, Stretch — as reusable abstractions)
- Pass protection library
- Offensive philosophy files in `data/concepts/philosophies/` — West Coast, Air Raid, Spread Option, Power Run, Pro-Style, Veer Option, Wing-T, Run-and-Shoot, Smashmouth

## More MCP servers (Phase 6)

- `validate-formations` tool / MCP — promote the inline checker to a real reusable tool
- `game-knowledge-mcp`
- `route-tree-mcp` (route library exists, this is small now)
- `blocking-scheme-mcp` (after blocking library exists)
- `play-concept-mcp`
- `validation-mcp`
- `play-variant-mcp`
- `playbook-generation-mcp` — the optimal-playbook generator (Phase 7 work)

## Phase 7–8

- Play family generator — one base play → 2-5 related variants under game constraints
- Game-specific export — manual-entry editor instructions per game title (companion to the SVG diagrams)

## Game knowledge files (after measurements arrive)

- PS1 Madden / NCAA game files (Madden 96-01, NCAA 98-01)
- Additional PS2 Madden / NCAA games (Madden 02, 03, 06-11; NCAA 02-11)
- PS3 Madden / NCAA games (Madden 07-13; NCAA 07-14)

## Administrative

- README.md still just the project title — needs a real intro
- `.gitignore` for `.venv/`, `__pycache__/`, etc.
- Repo-local Python venv (currently using `/tmp/blitz-venv`)
- `tests/` still empty — formal test suite for tools and validators
- Commits — frequent uncommitted work; consider a hook or workflow note

---

## How to update this file

When something here lands or changes scope:

1. Move completed items to the bottom under a `## Done` section, OR delete them once they've been done long enough that they're not interesting context.
2. If a category empties out, delete the section heading too.
3. Keep items terse — 1 line each. Detail belongs in the implementation, plan.md, or a per-item doc.
