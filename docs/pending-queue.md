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

- **Playbook Gamer — remaining games.** Phase B catalog coverage is 8 games
  (madden-04/05/07/25, ncaa-04/06/07, espn-2k5). Madden 01/03 PS2 still need
  their game profiles + ingest. Vision ingest can run keyless in-session via
  subagents reading the extracted images, or via the script with an
  `ANTHROPIC_API_KEY`.

- **Formation-family classifier for xlsx games.** `_family()` under-classifies
  modern names ("I Pro", "Split Spread" → "other") for the xlsx-sourced games
  (madden-04/05/07, ncaa-04/06/07). Needs a better classifier. (Madden 25's
  families are panel-header-derived; ESPN 2K5's are now a screenshot-verified
  prefix classifier — both accurate. See Done.)

- **Play-name extraction (catalog Phase 2).** The docx catalogs hold formations
  + play counts, not play names. Play names live on the play-diagram screens
  (the "OFFENSE" 3-play screens) which the ingest discards as "other". A second
  vision pass over those screens would give a true per-formation play list.

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
- **`run-and-shoot` is mis-modelled as a formation.** Run-and-shoot is a
  *philosophy*, not a formation — and the repo already has it as one
  (`data/concepts/philosophies/run-and-shoot.yaml`). But `data/formations/
  run-and-shoot.yaml` (+ `-left`) is structurally just a 10-personnel
  under-center 2x2 spread. Rename it to its real identity (e.g. `spread-2x2`)
  and retag the philosophy onto the plays/section. Touches ~15 files
  (formation + mirror, ~10 plays, the family file, hs-base's "Run & Shoot"
  section). Deliberate cross-cutting rename — confirm scope before doing it.

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

### 2026-05-18

- ✅ Team playbook catalog — 6 games ingested (madden-04/05/07-ps2, ncaa-04/06/07-ps2).
  `tools/ingest-research/build_playbook_catalog.py` + `schemas/team-playbooks.schema.json`
  + `find_team_playbooks` / `get_team_playbook` tools on game-knowledge-mcp (now 11 tools).
- ✅ `tools/ingest-research/extract_docx_images.py` — docx image extractor for
  screenshot-based playbooks (untracked from yesterday's crash; included here).
- ✅ docx vision-ingest pipeline — `tools/ingest-research/ingest_docx_playbooks.py`
  classifies per-team screenshot docx via Claude vision into `team-playbooks.yaml`.
  Case-insensitive formation dedup; restartable per-team JSON cache; needs no
  API key for a cache-only re-aggregate. Madden 25 PS3 catalog built (50 teams,
  968 formations, schema-valid). New game profiles: madden-25-ps3, espn-2k5-ps2.
- ✅ ESPN NFL 2K5 PS2 catalog — 34 teams, 773 formations, schema-valid. Vision
  done keyless via in-session subagents (one per team) writing cache JSONs that
  the ingest script's tested aggregation/dedup path then assembled.
- ✅ Catalog formation entries gained `family` + `play_count`. `ingest_docx_playbooks.py`
  now threads the Madden formation-menu panel header (SINGLEBACK/I-FORM/GUN/…)
  through aggregation as the family — accurate, replacing crude name-guessing —
  and carries the per-formation play count. Schema + both docx catalogs updated.
- ✅ ESPN 2K5 family classifier — `_espn_family()`, a prefix classifier verified
  against in-game screenshots (I/Strong-I/Weak-I/Near/Far → i_form; Gun → shotgun;
  empty/spread → shotgun; bare receiver-shapes → singleback). ESPN catalog
  re-run: every formation now classified, no `other`.
- ✅ Formation-level playbook matcher — `tools/playbook-game-match/match.py`.
  Normalizes both a repo playbook and a game catalog to (family-group, alignment
  tags) signatures and scores formation-by-formation coverage. Works for
  madden-25-ps3 and espn-2k5-ps2.

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
