# Pending Queue

Living list of open work, organized by category. Update as items land.

Format: a short title + 1-line description. Add a `**(blocked: ...)**` note when an item depends on something external (user input, upstream work, etc.).

---

## Highest leverage right now

- **Concept libraries (Phase 5).** The data side has plays, formations, routes, and games. What's still missing as first-class data is run-concept / blocking-scheme / coverage / philosophy libraries. These would let plays foreign-key into reusable concept definitions instead of repeating descriptions inline. Once they exist, concept MCPs (`run-concept-mcp`, `blocking-scheme-mcp`, `coverage-mcp`) can wrap them.

- **AI onboarding doc + worked examples.** `docs/ai-onboarding.md` for new Sonnet/Haiku models joining the repo (one-shot tutorial with 5-10 fully-narrated tool-call sequences in `examples/play-design-walkthroughs/`). Smaller models learn from examples >> abstract docs.

- **Game measurements.** *(blocked: user)* Diagrams against any game profile are placeholder-accurate until `data/games/<game-id>/editor-grid.yaml` is filled in via `docs/game-editor-measurement-protocol.md`. Madden 2005 PS2 partially measured (grid + y-scale + x-scale ≈ 9-cell-default-WR + ≥20 yd route depth); still need: max player split, max backfield depth, motion options, max plays per playbook.

- **MCP improvements still open** (after the top-3 + composition tools landed):
  - `update_play(play_id, patch)` for incremental fixes (avoids re-authoring whole YAML)
  - `save_formation(formation_yaml)`, `save_route(route_yaml)` (currently only `save_play`)
  - `manifest()` per server announcing purpose + tool list (smaller AIs benefit)
  - Pagination on `list_*` tools — 144 plays in one response is bandwidth-heavy
  - `find_play_for_situation(formation_constraint, defense, philosophy)` doing a multi-MCP join
  - 10-15 named play templates (`template:power-run`, `template:y-cross-pa`)
  - Provenance auto-tracking (model name, sources, timestamp) on `save_play`
  - Concept-level lint extensions (mesh-point depths match between crossers, WR split vs editor max)
  - Suggest concept-appropriate routes in `build_starter_play` (not just `'TODO-fill-in'`)
  - Cross-reference check: `validate_play` should flag route_names that don't exist in `data/routes/`

## Drawing improvements

- **Motion arrows** as curved dashed lines from start → end position
- **Option-route branching** (snag / stick currently render only primary path; show both branches)
- **Animation** — SVG `<animate>` to show route progression
- **Defense-only via MCP** — `render_play` requires a `play_id`; need a `render_defense(defense_id, game_id)` companion
- **Blocking arrows that target specific defenders** (now possible since defenses exist)

## More plays

- Plays for the formations that still have **none**: Strong I, Weak I, Big I, Full House, Empty (only 2), I-Formation Twins Weak (only 2), Shotgun 2x1 TE-Strong, Shotgun 2x1 TE-Weak, Shotgun 3x0
- Round out existing playbooks — Singleback Trio still needs RPO + screen variants; Wing-T could add Boot / Down / Belly Pass; Wildcat could add a true Pass
- I-Formation has no pure pass (only PA + run + screen) — under-center 5-step concepts missing
- Shotgun-trips-right has no PA despite trey-right having one — port

## Future formations (offensive)

- Single Wing, Double Wing (HS / youth throwback)
- Singleback Doubles / Bunch / Big variants
- Empty 5-wide variants
- Pistol Trips

## Defensive side — more

- 3-3-5 stack
- 4-3 cover-1
- Tampa 2 standalone
- Blitz packages: zero blitz, fire zone, double-A blitz

## More schemas

- `blocking.schema.json`
- `playbook.schema.json` — for saveable named playbooks
- Run concept schema (separate from plays — concepts as reusable building blocks)
- `source_provenance` schema (formalize the `verification_status` distinction; see `docs/play-data-provenance.md`)
- Add `'option'` to `play_type` enum so triple options can self-describe

## More data libraries (Phase 5)

- Blocking scheme library (man, zone, gap, pull, slide, max)
- Run concept library (Power, Counter, Iso, Inside Zone, Outside Zone, Trap, Draw, Sweep, Stretch — as reusable abstractions)
- Pass protection library
- Offensive philosophy files in `data/concepts/philosophies/` — West Coast, Air Raid, Spread Option, Power Run, Pro-Style, Veer Option, Wing-T, Run-and-Shoot, Smashmouth

## More MCP servers (Phase 6)

- `validate-formations` tool / MCP — promote the inline checker to a real reusable tool
- `game-knowledge-mcp`
- `route-tree-mcp`
- `blocking-scheme-mcp`
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

- `tests/` could add test_drawing_modes coverage for defense-only short-field combinations
- Frequent uncommitted work — consider adopting a workflow note for periodic commits
- Consider GitHub Actions running `./run-tests.sh` on PR

---

## Done

(Move items here when they land. Trim periodically — old completions don't need to live here forever.)

### 2026-04-30

- ✅ Drawing tool now supports both/offense-only/defense-only/show-selectively modes + short/long field
- ✅ Green field background + NFL/NCAA hash marks (per game profile)
- ✅ Defensive formations + coverage rendering (zones / man / rush / spy)
- ✅ MCP top-3 — `validate_play`, `render_play`, `build_starter_play`
- ✅ MCP composition — `find_plays_by_concept`, `compare_plays`, `suggest_complementary_plays`, `predict_matchup`
- ✅ MCP write — `save_play`, `mirror_play`
- ✅ All MCP docstrings rewritten with examples + enum hints + "Did you mean…?" suggestions
- ✅ `docs/using-the-mcps.md`, `docs/play-data-provenance.md`, refreshed `README.md` and per-MCP READMEs
- ✅ Repo-local `.venv` (python3.11) + `requirements.txt` + `.gitignore` + `tests/` (50 tests) + `run-tests.sh`
- ✅ Specialty offensive formations: Wishbone, Flexbone, Pistol Diamond, Run-and-Shoot
- ✅ Defensive formations: 3-4 C3, 4-2-5 C2, Goal-Line 6-2, Prevent 3-2-6 (added to existing 4-3 C2/C3, Nickel C1, Dime C4, 46 Bear C0)
- ✅ Round out option family: power-read, counter-read, triple-option-RPO, veer, QB-counter, QB-power
- ✅ Path backfills (P4) — every QB-bearing play now has a QB drop/handoff path

## How to update this file

When something here lands or changes scope:

1. Move completed items to `## Done` (with date) — OR delete them once they've been done long enough that they're not interesting context.
2. If a category empties out, delete the section heading too.
3. Keep items terse — 1 line each. Detail belongs in the implementation, plan.md, or a per-item doc.
