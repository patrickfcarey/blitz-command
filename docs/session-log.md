# Session Log

Append-only handoff log. The newest session goes at the **top**. The point is so a fresh Claude session (or a human returning after a crash) can answer "where did we leave off?" without reconstructing from `git status` timestamps.

## Conventions

- One entry per working session. Append at the top, under the heading below.
- Date is ISO (`YYYY-MM-DD`). Use `date +%Y-%m-%d`, don't guess.
- Keep entries short. Link to docs/files rather than re-describing them.
- Trim entries older than ~30 days when they stop being load-bearing — git history is the long-term archive.

### Entry template

```markdown
## YYYY-MM-DD — <one-line thread title>

**Active thread:** what we were actually working on this session.

**Landed this session:**
- bullet
- bullet

**In progress / next step:** the single most useful thing for the next session to pick up. Be specific (filename + what to do, not "continue work").

**Blockers / waiting on:** external dependencies, user input needed, decisions deferred. Omit the section if none.

**Uncommitted state:** one line on whether work is committed or sitting in the tree, and whether that's intentional.
```

---

## 2026-05-18 (cont.) — docx vision-ingest pipeline + Madden 25 & ESPN 2K5 catalogs

**Active thread:** running the docx-screenshot playbook ingest for games with
no xlsx data, starting with Madden NFL 25 (PS3).

**Landed this session:**
- `tools/ingest-research/ingest_docx_playbooks.py` — finished + hardened. Two
  fixes after the first run: (1) **case-insensitive formation dedup** — vision
  OCR reads the same formation with inconsistent casing ("Bunch Wk" / "Bunch WK");
  exact-string dedup left 10 teams with dupes. (2) **lazy Anthropic client** —
  a cache-only re-aggregate run now needs no `ANTHROPIC_API_KEY` at all.
- **Madden 25 PS3 catalog** — `data/games/madden-25-ps3/team-playbooks.yaml`:
  50 teams (38 NFL + 12 scheme/coach playbooks), 968 formation entries,
  schema-valid. Run was done with an API key; `.docx-cache-m25/` (gitignored)
  holds the restartable per-team classification cache.
- New game profiles: `data/games/madden-25-ps3/editor-grid.yaml`,
  `data/games/espn-2k5-ps2/editor-grid.yaml` (both `inferred`, grid unmeasured).
- `.gitignore` — added `.docx-cache-*/`.
- `requirements.txt` — added `anthropic>=0.50`.
- Data-quality note: low formation counts on legends playbooks (Vince Lombardi=3,
  etc.) are *real* — verified by eye, those docs are play-screen heavy and use
  colour-coded families (RED/BROWN). Not vision misses. Status stays `unverified`.
- 266 tests pass.

**ESPN NFL 2K5 PS2 catalog — done (keyless route):** 34 teams, 773 formations,
schema-valid. To avoid a second pay-as-you-go API bill (user flagged the cost),
the vision was done *in-session* — one Haiku subagent per team read the
extracted screenshots with the Read tool and wrote a cache JSON in the format
`ingest_docx_playbooks.py` consumes; the script's tested aggregation/dedup path
then assembled `data/games/espn-2k5-ps2/team-playbooks.yaml` with no API key.
Hit a usage limit mid-run; the per-team cache made it cleanly resumable.

**Catalog formation entries gained `family` + `play_count`:** `ingest_docx_playbooks.py`
now threads the Madden formation-menu panel header (SINGLEBACK/I-FORM/GUN/…)
through aggregation as the family — accurate, replacing crude `_family()` name
guessing — and carries each formation's play count. Schema + both docx catalogs
regenerated from cache (no API key); 266 tests pass.

**Formation-level playbook matcher built** — `tools/playbook-game-match/match.py`.
Normalizes a repo playbook and a game catalog to (family-group, alignment-tag)
signatures and scores formation-by-formation coverage. hs-base vs madden-25:
Pittsburgh Steelers #1; vs espn-2k5: San Diego Chargers #1.

**ESPN 2K5 family classifier** — `_espn_family()` in `ingest_docx_playbooks.py`,
a prefix classifier verified against in-game screenshots (3 subagents read
backfield alignment off 44 formations). ESPN catalog re-run — every formation
now classified (singleback 357 / i_form 261 / shotgun 155), no `other`.

**`run-and-shoot` formation → `double-slot`:** run-and-shoot is a philosophy
(already `data/concepts/philosophies/run-and-shoot.yaml`); the formation file
was a mis-named 10-personnel under-center 2x2 double-slot. Renamed the
formation + `-left` mirror, retargeted 10 plays, the play-family, hs-base's
section, personnel-groupings, and `expand.py`'s section maps. Plays / family /
philosophy keep their run-and-shoot names.

**ESPN `_espn_family` — Jokers/Jacks fix:** per user, `Jacks` (1HB+1FB+3TE)
and `Jokers` (1HB+1FB+2TE+1WR) are two-back heavy power sets — `_espn_family`
now maps any name containing "jokers"/"jacks" to i_form (was defaulting bare
ones to singleback). ESPN catalog re-run: 24 Jokers/Jacks formations now
i_form (singleback 334 / i_form 284 / shotgun 155).

**Play-name extraction (catalog Phase 2) — started.** Pipeline built and
validated: `tools/ingest-research/extract_play_names.py`, a `plays` field on
the catalog schema, chunked Haiku vision (one-shot Haiku over ~150 images was
too lossy — ~40-image chunks fixed it). Madden association is play_count
segmentation (play screens don't name their formation, but appear in formation
order); ESPN will use the on-screen formation header. Indianapolis Colts done —
333 plays, 24/24 formations within +/-2 of play_count. Chunk caches live in
`.docx-cache-<game>-plays/` (gitignored), resumable.

**Play-name grind progress:** 10/50 madden-25 playbooks done (Arizona, Atlanta,
Cleveland, Indianapolis, Minnesota, New Orleans, NY Giants, Oakland, Pittsburgh,
Seattle) — 224/227 formations within +/-2 of play_count. Per-team workflow:
extract docx images to /tmp/m25-img/<slug>/, launch 4 chunked Haiku subagents
(~40 imgs each) writing `.docx-cache-m25-plays/<Team>__chunkNN.json`, then
`extract_play_names.py --game madden-25-ps3 --cache-dir .docx-cache-m25-plays`.

**In progress / next step:** 40 madden-25 playbooks + 34 espn-2k5 remain. Same
workflow; ESPN uses header-based association (its play screens name the
formation). (2) Madden 01/03 PS2 catalogs still need profiles + ingest.

**Uncommitted state:** Madden 25 work committed earlier (e48d0ad). ESPN 2K5
catalog committed at end of this session.

---

## 2026-05-18 — Real-game playbook catalog — Phase B build

**Active thread:** Building the per-team playbook catalog from the Playbook
Gamer corpus so the system can answer "which real team playbook from Madden 04
fits West Coast style?" User confirmed: the docx/xlsx data is NOT for learning
new plays — it is a lookup catalog so generated playbooks are grounded in what
a specific game actually contains.

**User direction (confirmed this session):** Catalog every game's per-team
playbooks as structured data. Primary use: `find_team_playbook(game_id, style)`
so when a user asks for "a Madden 08 playbook" we match the closest real team.

**Landed this session:**
- `tools/ingest-research/extract_docx_images.py` — extracts docx images in
  document order (carries over from crash mid-session-17).
- `tools/ingest-research/build_playbook_catalog.py` — ingests xlsx formation
  lists into `data/games/<id>/team-playbooks.yaml`. Handles row format
  (PLAYBOOK|FORMATION|STYLE|PERSONNEL), matrix format (formation×team X-marks),
  and style-only sheets (NCAA Formation Type). 6 games built:
  madden-04/05/07-ps2 (38 teams each), ncaa-04-ps2 (123), ncaa-06-ps2 (125),
  ncaa-07-ps2 (125).
- `schemas/team-playbooks.schema.json` — per-team catalog schema.
- `find_team_playbooks(game_id, style, formation_family)` + `get_team_playbook(game_id, team_name)` 
  added to game-knowledge-mcp (9 → 11 tools). README + manifest updated.
- Memory + pending queue updated to reflect clarified purpose.
- 266 tests pass.

**In progress / next step:** Remaining games with docx-only playbooks (Madden 25 PS3
= 51 teams, others without xlsx). `extract_docx_images.py` is ready; need a vision
agent to read the extracted screenshots and produce formation names.

**Blockers / waiting on:** User — commit this work? Proceed to docx vision pipeline?

**Uncommitted state:** Everything above is uncommitted.

---

## 2026-05-17 — MCP capability additions + playbook presentation + research corpus

**Active thread:** four approved MCP additions, the per-formation play-call
breakdown the user asked for mid-session, and starting analysis of the
Playbook Gamer research corpus.

**Landed this session:**
- **formation-library-mcp** +3 personnel tools — `list_personnel_groupings`,
  `get_personnel_grouping`, `find_formations_by_personnel` (10 tools).
- **pass-concept-mcp** +`find_pass_concepts_by_depth` (7 tools).
  **play-library-mcp** +`find_plays_by_rpo_type`, `rpo_type` now surfaced in
  `scout_play` (22 tools — also fixed a manifest missing `list_play_templates`).
  run-concept-mcp's category filter already existed — no change.
- `update_play` on play-library-mcp was already implemented — verified only.
- **Per-formation play-call breakdown** — new `tools/playbook-call-breakdown/
  breakdown.py`; the playbook PDF now opens each formation section with a page
  listing its plays grouped by disguise family with each play's call %.
  Exposed as `playbook_call_breakdown`.
- **Install schedule** — new `tools/playbook-install-schedule/schedule.py`;
  PDF gains an Install Schedule page (Day 1 / Week 1 / Week 2 / mid-season).
  Exposed as `playbook_install_schedule` (playbook-generation-mcp now 16 tools).
- **Phase A research corpus** — `research_artifacts/` (19,389 files) is
  git-ignored; `tools/ingest-research/parse_xlsx.py` reads the 26 structured
  xlsx without openpyxl. Findings in `docs/playbookgamer-pdf-integration.md`.
- 266 tests pass (was 257).

**In progress / next step:** Phase B of the research corpus — the 559 docx
turned out to be per-team / per-defense PLAYBOOK documents (not game manuals),
largely redundant with the Phase A xlsx. Decide whether docx extraction is
worth the effort before launching subagents.

**Blockers / waiting on:** user decision on (1) committing this session's
work, (2) Phase B direction.

**Uncommitted state:** everything above is uncommitted, on top of the large
pre-existing uncommitted tree. Nothing committed this session.

## 2026-05-15 — Playbook schema + first HS playbook + audible/counter system

**Active thread:** designing the playbook data layer and authoring the first
playbook (high-school base). Driven by the spec in auto-memory
`project_first_playbook_hs.md`.

**Landed this session:**
- `schemas/playbook.schema.json` — new. Hybrid sections (explicit formation
  sections + tag-driven situational views). Play entries carry role (10
  structural values), install_order, expected_calls_per_game, share_of_section_pct,
  practice_reps. Formation sections carry target_snap_share_pct + formation_usage_split.
  Top-level `audibles` (exactly 5). Play entries carry `counter_responses`.
- `schemas/play.schema.json` — added `defensive_counters` array, then reshaped
  it to an ALIGNMENT model: each counter is a pre-snap look the QB scans
  (pre_snap_look, qb_key, read_category enum [box-count/safety-shell/
  dl-alignment/lb-depth/cb-leverage], why). NOT post-snap movement — post-snap
  is handled by run_reads / QB read progression. counter_ids are stable keys.
- `data/playbooks/hs-base.yaml` — new. 36 plays across 4 formation sections
  (I-Form 40%, Singleback 30%, Shotgun 27%, Goal Line 3%) + 2 situational
  sections. Plays sorted by call frequency. 5 audibles. All 36 plays have
  counter_responses wired to audible slots.
- All 36 plays in the playbook now have `defensive_counters` (108 entries).
- `tools/validate-playbook/validate.py` — new. 11 checks incl. share-math
  rollups, audible integrity, counter_ref resolution.

**Fill-in plays (done 2026-05-15):** authored 5 new play YAMLs —
`i-formation-trap`, `singleback-ace-outside-zone`, `singleback-ace-pa-boot`,
`singleback-ace-stick`, `singleback-ace-smash` (each with alignment-model
defensive_counters). Wired all into hs-base.yaml with rebalanced section
shares; Singleback split moved to 45/55 ace/trio. Playbook now 41 plays,
validator green. I-Form 6-run spec met; Singleback Ace developed (6 plays).

**Mirrors + PDF smoke-test (done 2026-05-15):**
- Ran `tools/generate-mirror-plays/generate.py` — created `-left` mirrors for
  all 5 new plays (coordinate-flipped, validated).
- Smoke-tested `tools/print-playbook-detailed/`. Found + fixed two bugs:
  (1) color-map regex matched `#666` inside `#666666` → corrupt `#aaaaaa666`;
  fixed with a trailing hex negative-lookahead. (2) `_field_bounds` included
  the full-canvas off-editor green, shrinking diagrams to nothing; now crops
  to the editor field only. Also trimmed the notes right-column back to spec
  (reads + coaching notes; dropped the strengths/weaknesses/etc. dump that
  overstuffed it). Tool now renders clean 2-up teaching pages.

**SVG palette update (done 2026-05-15):** both print tools (`print-playbook`
and `print-playbook-detailed`) are now palette-agnostic. `_load_svg_print`
only color-remaps legacy dark SVGs (detected via `#1a1a1a`/`#1b5e20`/
`#2e7d32` markers); current light SVGs load as-is. `_field_bounds` now finds
the editor field as the largest STROKED rect (works for both palettes — old
green-field-white-stroke and new white-field-dark-stroke). Verified both
tools render both palettes correctly.

**Counter Trey demoted (done 2026-05-15):** per coaching feedback, a counter
shouldn't be the #2 call. Counter Trey moved to the #4 run option in
I-Formation (share 15→9, install-day-2→install-week-2, calls 5-8→3-5/game).
Run hierarchy is now Power-O / Iso / Lead-Toss / Counter-Trey / Trap / Veer.

**PLAY FAMILIES — definition nailed down + exemplar built (2026-05-15):**
A "play family" = a DISGUISE GROUPING: plays that show the defense the same
pre-snap look AND the same first ~1-2 seconds of action, then diverge. Soft
rule, not pixel-identical — wrinkles (e.g. a zebra/fake-drag route) are fine.
NOT a formation grouping — confirmed the existing 41 plays mostly do NOT share
initial action, so real families need plays authored as mutual disguise twins.

Exemplar built — **I-Formation Power family** (`data/play-families/
i-formation-power-family.yaml`): base `i-formation-power-o` + 2 NEW twin plays
`i-formation-power-pass` (pocket PA) and `i-formation-power-boot` (PA boot).
Both authored so QB/HB/FB/LG initial path waypoints are byte-identical to
Power-O through the mesh (verified). `-left` mirrors generated. Validator gained
a self-containment check (check #10): every playbook play that is a family
companion must have ≥1 of its families' base_play_id present — proven with
good/bad synthetic playbooks.

Larger model also surfaced (deferred): plays should be COMPOSITIONS of
concepts (the repo already has `data/concepts/pass-concepts/` + `run-concepts/`,
~30 authored incl. Smash). A 5-WR play = Smash-left + Spacing-right + QB-run =
3 concepts in one play. The play schema only allows ONE concept_ref today —
multi-concept composition is its own future architecture change.

**`zebra` route authored (2026-05-15):** `data/routes/zebra.yaml` — a fake-drag
(3 steps outside, pivot inside, cross underneath like a drag). Path
`[[0,0],[-3,3],[17,5]]`. Validates. A disguise wrinkle, drop-in for `drag`.

**Power family folded into hs-base.yaml (2026-05-15):** bootleg-flat → power-boot,
pa-cross → power-pass (the true disguise twins replaced the old non-twin PA
plays), audible slot 5 → power-boot. Self-containment check now fires on real
data and passes.

**6 more disguise families built + verified (2026-05-15):** 3 agents authored,
following the Power template — i-formation-toss, goal-line-power,
singleback-ace-zone, singleback-trio-zone, shotgun-2x2-qb-power,
shotgun-trips-counter. 12 new twin plays + 6 family files in
`data/play-families/`. Verified clean: all schema-valid, labels/motions match
base, defensive_counters alignment-model, and the disguise holds — every twin's
QB/HB/FB first-2 path waypoints are byte-identical to its base (0 breaks).
`-left` mirrors generated for all 12. NOT yet folded into hs-base.yaml.

**Disguise families expanded to 10 + flip_reads added (2026-05-15):**
- All 7 original families extended with counter + screen (or boot/keep) twins;
  3 new families built — shotgun-2x2-jet, i-formation-counter, shotgun-2x2-
  quick-game. **10 families total, ~36 companion plays.** ~22 new twin plays
  authored by 4 parallel agents, all verified (schema-valid, disguise holds —
  QB/HB/FB first-2 waypoints byte-identical to base, 0 breaks). `-left`
  mirrors generated.
- `flip_reads` added to `play.schema.json` — a sibling of `defensive_counters`
  for the run-direction / formation-flip pre-snap tell. Each entry:
  pre_snap_look, qb_key, read_category, `flip_to` (mirror-play | mirror-
  formation), why. Demonstrated on power-o, lead-toss, shotgun-2x2-qb-power.
  NOT yet backfilled to all plays.
- `data/plays/CATALOG.md` — generated index (`tools/play-catalog/generate.py`)
  grouping plays by family / formation / un-familied. Plays stay flat on disk.
  Library is now 125 base plays + 101 mirrors, 10 families, 79 un-familied.

**West Coast / Run-and-Shoot expansion (2026-05-15):** researched Walsh/
Belichick/West Coast/Run-and-Shoot. Built 2 new families + extended 1:
- **run-and-shoot-family** — Switch/Choice/Go/Screen/Draw, 10-personnel
  `run-and-shoot` formation, shared jet-style motion + identical QB drop.
- **shotgun-2x2-drive-family** — West Coast Drive concept (shallow + dig
  hi-lo): drive / drive-pa / drive-hilo / drive-shot / drive-screen.
- **shotgun-2x2-quick-game-family** extended with West Coast quick game
  (slant-flat, quick-hitch, quick-out).
13 new plays, all verified (disguise holds across all 12 families now),
mirrors generated, catalog regenerated. Library: 136 base plays, 12 families.
Belichick/Erhardt-Perkins finding: EP's concept-based, formation-agnostic,
two-concepts-per-call design IS the multi-concept-composition feature — user
chose to do that NEXT.

**Multi-concept play composition started (2026-05-15):** added a `concepts`
array to `play.schema.json` — a play can carry multiple concepts, each
foreign-keying a concept and naming the players that run it (concept_ref,
concept_type, players, field_area, is_primary). The single run_concept_ref /
pass_concept_ref still work for single-concept plays; multi-concept plays use
`concepts` instead. Demonstrated: authored `data/concepts/pass-concepts/
spacing.yaml` + `data/plays/empty-smash-spacing.yaml` (Spacing field-side +
Smash boundary-side in one empty-formation play). The mirror tool now flips
each concept's `field_area` left<->right. All validates; catalog regenerated
(137 base plays).

**play-library-mcp extended (2026-05-15):** audited it — the MCP predated
this session's entire data layer (0 references to families/counters/flip_reads/
concepts[]). Extended `mcps/play-library-mcp/server.py`: 4 new tools —
`list_families`, `get_family`, `get_disguise_twins`, `scout_play`; updated
`find_plays_by_concept` (now searches concept refs incl. the multi-concept
`concepts[]`) and `validate_play` (concepts[] integrity + dc/flip id-uniqueness
lints). 21 tools total. Tested via the repo `.venv` (python3.11 — the system
python is 3.9 and can't import the mcp SDK). README + manifest updated.

**playbook-generation-mcp extended (2026-05-15):** CORRECTION — an earlier
session-log note wrongly called this MCP "scaffolded-empty." It was NOT: all
13 MCP dirs under `mcps/` have working servers. playbook-generation-mcp had a
5-tool server (assemble/suggest/list tools) since May 1; it just predated the
`data/playbooks/` layer. Extended it to 12 tools — added `list_playbooks`,
`get_playbook`, `get_playbook_section`, `get_audibles`, `get_play_in_playbook`,
`validate_playbook` (shells out to validate.py), `playbook_call_sheet`. Tested
via the `.venv`.

**MCP documentation-accuracy pass (2026-05-15):** all 13 MCP READMEs audited —
8+ had wrong tool counts (mostly omitting `manifest`; formation-library also
had a wrong defense-formations claim). All 13 READMEs + `manifest()` tool
lists now match their servers exactly (verified: README count == `@mcp.tool()`
count for all 13). `docs/using-the-mcps.md` rewritten — it claimed "two MCP
servers" (there are 13); now an accurate 13-server overview that points to
each MCP's README for the tool catalog.

**In progress / next step:** still open — (1) only the Power family is folded
into hs-base.yaml; (2) flip_reads backfill; (3) more multi-concept plays;
(4) the concept-library MCP (the other justified MCP per the audit).

NOTE for future sessions: MCP servers need Python 3.10+ — use the repo
`.venv/bin/python` (3.11), not the system `python3` (3.9). And all 13 `mcps/*`
dirs have real servers — check before assuming any is empty.

**Blockers / waiting on:** none.

**Uncommitted state:** all of the above is uncommitted, sitting in the tree
with the large pre-existing uncommitted work. User prefers explicit commit
asks (auto-memory `feedback_no_auto_commit.md`).

## 2026-05-14 — Session-log convention established

**Active thread:** user asked "where did we leave off before the machine died?" — I could only reconstruct from `git status` timestamps. We decided to fix the gap by adopting this file.

**Landed this session:**
- Created `docs/session-log.md` (this file) with template + conventions.

**In progress / next step:** pick up the pre-crash thread — generating the **Singleback Trio** play family diagrams (May 2 work, all uncommitted). Check `examples/play-diagrams/singleback-trio-*` and the family in `docs/pending-queue.md` "More plays" section. Also: stray `check_this.png` at repo root — user may want eyes on it.

**Blockers / waiting on:** none for the log itself. The crash-recovered thread may have unresolved questions — re-ask the user before diving in.

**Uncommitted state:** large pre-existing uncommitted tree (Phase 5 MCP scaffolds, new schemas, new docs, ~140 new SVG diagrams, big edits to `tools/draw-play/draw.py` and `mcps/play-library-mcp/server.py`). Not yet committed — user prefers explicit commit asks (see auto-memory `feedback_no_auto_commit.md`).
