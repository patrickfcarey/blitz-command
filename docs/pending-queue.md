# Pending Queue

Living list of open work, organized by category. Keep it current as work
lands — see "Keeping the pending queue current" in `CLAUDE.md`.

Format: a short title + 1-line description. Add a `**(blocked: ...)**` note
when an item depends on something external (user input, upstream work).

---

## Highest leverage right now

- **Game-editor measurements.** *(blocked: user)* Diagrams against any game
  profile stay placeholder-accurate until `data/games/<game-id>/editor-grid.yaml`
  is filled in via `docs/game-editor-measurement-protocol.md`. Madden 2005 PS2
  is partially measured; still needed: max player split, max backfield depth,
  motion options, max plays per playbook.

- **Playbook Gamer PDF integration.** *(blocked: user)* Ingest the team-playbook
  PDFs from the Playbook Gamer Vault as reference data — see
  `docs/playbookgamer-pdf-integration.md`. The user supplies the files
  (Phase 1); inventory, extraction, and integration follow.

- **AI onboarding doc.** `docs/ai-onboarding.md` for smaller models joining the
  repo — a one-shot tutorial with fully-narrated tool-call sequences under
  `examples/play-design-walkthroughs/`.

- **Session log + README refresh.** Bring `docs/session-log.md` and `README.md`
  current with the playbook, front-matter, and MCP work.

## Plays + data

- Sweep the remaining RPO plays (`pistol-rpo-bubble`, the trips RPO bubbles,
  `shotgun-2x2-qb-power-keep-throw`) for the QB/HB mesh-waypoint bug fixed in
  `shotgun-2x2-rpo-slant`.
- Wire plays to the 6 new run concepts (duo, jet-sweep, reverse, power-read,
  shovel-option, speed-option) via `run_concept_ref`.
- Future offensive formations: Single Wing, Double Wing, Bunch, Pistol Trips.

## Drawing improvements

- Motion arrows — curved dashed lines from start → end position.
- Option-route branching — snag / stick render only the primary path.
- `render_defense(defense_id, game_id)` MCP companion (`render_play` needs a play_id).

## Defensive side

- 3-3-5 stack, 4-3 cover-1, Tampa 2 standalone.
- Blitz packages: zero blitz, fire zone, double-A.

## MCP / tooling improvements

- `assemble_playbook(philosophy, formations, target_size, game_id)` — the full
  playbook optimizer with family balance + disguise scoring (Phase 7).
- `update_play(play_id, patch)` for incremental fixes.
- `save_formation`, `save_route` (currently only `save_play`).
- Pagination on `list_*` tools.

## Administrative

- Consider GitHub Actions running `./run-tests.sh` on PR.
- Uncommitted work tends to pile up between sessions — commit at natural
  checkpoints.

---

## Done

Trim periodically — old completions need not live here forever.

### 2026-05

- ✅ Playbook system — `playbook.schema.json`, the `hs-base` master playbook
  (88 plays), the playbook validator, audibles + counter_responses, and
  `front_matter` (identity, glossary, appendix).
- ✅ 12 disguise families, `flip_reads` on every directional run play, and
  multi-concept (`concepts[]`) plays.
- ✅ All 13 MCP servers built and documentation-audited; `playbook-generation-mcp`
  gained `playbook_glossary` and `playbook_tendency_profile`.
- ✅ Detailed playbook PDF — front matter, glossary, tendency profile,
  on-demand diagram rendering, and `--layout` side-by-side / one-per-page.
- ✅ Concept library — pass-concept `depth` + run-system categories, 6 new run
  concepts, the personnel-grouping model, the RPO `rpo_type` sub-taxonomy.

### 2026-04-30

- ✅ Drawing tool modes (both/offense/defense/none, short/long field), green
  field + hash marks, defensive formations + coverage rendering.
- ✅ MCP top-3 + composition + write tools; all MCP docstrings with examples.
- ✅ Repo `.venv`, `requirements.txt`, `tests/`, `run-tests.sh`.
- ✅ Specialty formations (Wishbone, Flexbone, Pistol Diamond, Run-and-Shoot),
  defensive formations, the option family, QB-path backfills.

## How to update this file

When something lands or changes scope:

1. Move completed items to `## Done` (with date) — or delete them once they
   are no longer interesting context.
2. If a category empties out, delete the heading too.
3. Keep items terse — one line each. Detail belongs in the implementation,
   `plan.md`, or a per-item doc.
