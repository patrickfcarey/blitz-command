# Pending Queue

Living list of open work, organized by category. Keep it current as work
lands — see "Keeping the pending queue current" in `CLAUDE.md`.

Format: a short title + 1-line description. Add a `**(blocked: ...)**` note
when an item depends on something external (user input, upstream work).

---

## Highest leverage right now

- **Vision pilot — full M25 geometry extraction.** Pipeline built under
  `tools/playbook-vision-pilot/`: 7,365 deduped canonical crops, Python
  target_gap detector (3/3 ground-truth correct), Haiku 4.5 + caching +
  Python hints dispatch validated on 12 hand-labeled plays. Run cost
  projected at ~$59 to extract every M25 play geometry-fully. Decision
  paused — re-run `dispatch_canonical.py` to launch.



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

- **Play-name extraction (catalog Phase 2) — DONE for madden-04/07/25,
  espn-2k5, ncaa-06/14, and a formation-library for ncaa-05.** Match rates
  landed 2026-05-19/20:
  - madden-25-ps3: 99% (965/968)
  - madden-07-ps2: 87% (701/809) — 8 truncated-cache teams recovered via
    chunked per-image observations
  - madden-04-ps2: 97.6% (484/496) — chunked from the start
  - ncaa-06-ps2: 99.5% (1119/1125) — Heading-1 walker + image map
  - ncaa-05-ps2: formation-library.yaml (50 formations, 947 plays) — no
    per-team source available, emitted as a distinct artifact
  - ncaa-14-ps3: 83% (2570/3084) — gap is defensive formations
  - espn-2k5-ps2: 94%
- **Still source-blocked** (only a formation matrix, no play data found):
  `madden-05-ps2`, `ncaa-04-ps2`, `ncaa-07-ps2`. Next: hunt for sources
  (community spreadsheets, manuals, forum dumps).

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
- ✅ `run-and-shoot` formation renamed to `double-slot`. Run-and-shoot is a
  philosophy (kept as `data/concepts/philosophies/run-and-shoot.yaml`); the
  formation file was a mis-named 10-personnel under-center 2x2 double-slot.
  Renamed formation + `-left` mirror, retargeted 10 plays' `formation:` refs,
  the play-family `formation_id`, hs-base's section, personnel-groupings, and
  the section maps in `expand.py`. Plays / family / philosophy keep their
  run-and-shoot names (they belong to the philosophy).

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
