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
