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

## 2026-05-20 (cont.) — vision pilot resumed + socket-drop root cause

**Active thread:** picking up `tools/playbook-vision-pilot/` (the hybrid-vs-cold
vision extraction study). Prior session died to mid-turn API socket drops with
no log trail.

**Landed this session:**
- Diagnosed the recurring `socket connection was closed unexpectedly` errors:
  user's VPN is in the route to api.anthropic.com (eth2, MTU 1441) and WSL
  default `tcp_keepalive_time=7200s` means long Claude turns idle past the
  VPN's TCP idle cutoff. User confirmed VPN was on — disabling resolves it.
- Locked the run-log + session-log laws into project memory
  (`feedback_run_log_law.md`, `feedback_session_log_law.md`). Both are now
  read at session start.
- Rebuilt the pilot pipeline artifacts (lost because they wrote to `/tmp`
  which WSL wiped): 50-play stratified sample, 50 cropped panels, 31/50
  decoded priors. Sources (`.docx-cache-m25-plays/`, M25 Playbooks docx)
  all intact.
- **Corrected OL-identification rule.** Prior run-log claimed
  "C = circle, OG/OT = squares" — WRONG. Correct rule: all 5 OL are
  circles; C is a bare circle; OG/OT are circles with a teardrop showing
  the initial step (forward = run drive-block, backward = pass-pro
  kickslide). QB is always behind C (wildcat: RB at QB position).
  Draw/play-action footwork may not be reliable.

**In progress / next step:** built a visual taxonomy from Singleback Ace
(known 2-TE set). Confirmed rules:
- C is always rendered as a white SQUARE, dead center of the LOS cluster
  (the prior "C is a circle" rule was wrong).
- 4 OG/OT are circles with a downward stub on the LOS row.
- TEs are circle-glyphs adjacent to the OL cluster (no gap).
- WRs are circle-glyphs split out from the cluster (visible gap).
- On PASS plays the 4 eligible receivers (+ HB if checkdown) wear PS
  button glyphs (□ purple, △ green, ⊗ blue, ⊙ red, also L1/R1). RUN
  plays leave skill players as plain circles — UNLESS the play is an
  RPO, which can color the eligible RPO target.
- Color-vs-monochrome distinguishes pass-vs-run reliably (per user).

**Locked rules (confirmed by user against Singleback Ace HB Dive
+ Z Spot, ~7.5x LOS-zoom crops with cyan LOS line through C-square):**

1. C = white square dead center of LOS cluster (always).
2. OL = C + 4 plain-white circles flanking.
3. TE = circle adjacent to OL cluster, no gap from OT.
4. WR = circle (run) or PS-button-color glyph (pass), separated
   from the OL/TE cluster by a visible gap.
5. PS buttons: □ purple, △ green, ⊗ blue, ⊙ red, L1/R1 also possible.
6. Pass plays color all eligible receivers with PS buttons; run plays
   leave them mono (RPO is the exception).
7. Pass-pro signature: OL circles' y-centers sit BELOW the LOS
   line through C-square center. Run plays: OL circles sit AT the
   line. (NOT teardrop direction — the stubs are stance icons,
   constant down regardless of play type.)
8. QB always lined up directly behind C in non-shotgun. Wildcat = RB
   at QB position.

**Rules verified across all 4 starting formations (Singleback Ace,
Singleback Jumbo, Singleback Y-Trips TE Slot, GUN Ace Twins).**
Confirmed: C-square anchor, OL-offset run-vs-pass signal, TE/WR by
adjacency-vs-gap, PS-button glyphs on pass eligibles. Route colors:
red = primary route OR run path (disambig by play_type), yellow =
standard route, blue/cyan = block-then-release. Dashed lines may be
option routes / motion (not yet enumerated; pilot will surface).

**Taxonomy verified across 15 distinct formations** spanning all major
personnel groupings: Singleback (Ace, Jumbo, Y-Trips), GUN (Ace
Twins, Empty, Bunch), I-Form (Pro), Strong, Weak, Goal Line, Pistol
(Strong), Wildcat. Backfield-composition rule added per formation
family. The cyan LOS line + yellow C-box annotations are now part
of the crop format and the subagent prompt accounts for them.

**Smoke test ran on prompt v3 with Haiku 4.5 → caching still failed
(Haiku 4.5 doesn't yet support prompt caching, even with a 3303-
token system block). Haiku also mislabeled the isolated WRs as OL.**

**Switched smoke test to Sonnet 4.5** to debug caching infrastructure
and check vision quality:
- Caching CONFIRMED working: cold call cache_creation_input=3303,
  primed call cache_read_input=3303. Wiring is correct.
- Sonnet's extraction is COMPLETE: found all 11 players (5 OL + 1 TE
  + 2 WR + QB/FB/HB stacked). I-Form Pro is canonically 11-personnel
  with 1 TE (my earlier 2-TE eyeball count was wrong).
- Minor: cold vs primed differ on which side the TE attaches; pixel
  coordinates drift ~50–100 px between calls. Counts are stable.
- Cost: Sonnet+cache ≈ $0.022/call → ~$2.20 for 100-call pilot.
  Haiku no-cache ≈ $0.010 but produces mislabeled output.

**Full pilot ran end-to-end on Sonnet 4.5 + caching.**
- 100 extractions (50 plays × 2 arms) in 5.3 min wall time, $2.16
  actual cost (matched estimate).
- 100/100 JSON-parseable, 0 errors, 50/50 play_type agreement.
- Cold: avg 1068 output tokens, 10.7 players found.
- Primed: avg 1046 output tokens, 10.6 players found.
- Δ output tokens: **−2.0%** (t = −2.41, Cohen's d = −0.34, 95% CI
  [−0.625, −0.055] — statistically significant but small).
- Δ cost/call: primed is +1.5% MORE expensive (prior text in user
  message adds input cost above the output savings).

**Pilot decision: DROP the hybrid priming pipeline.** Sub-15%
reduction means priming isn't worth the engineering complexity. Scale
up to full M25 extraction (~14,000 plays) with cold-only Sonnet 4.5 +
caching, estimated ~$308 total.

Pilot results: `/tmp/pilot-work/pilot-results/report.md` +
`pairs.json`.

Pilot artifacts in `tools/playbook-vision-pilot/` (sample-crops/,
dispatch-crops/, the scripts) — all still untracked, intentional
until a follow-up commit captures the pilot as a unit.

**In progress / next step:** decide whether to commit the pilot
work and proceed with full M25 extraction, or shelve until later.

## 2026-05-21 — Vision pilot cost optimization: $330 → $19.71

**Active thread:** drove the full M25 vision extraction cost down by
~17× from the original Sonnet baseline, with materially better
extraction quality than v4.

**Landed this session:**

- **Lever A (compact v5 schema):** dropped xy/glyph/button/los_y/play_id
  echo from output. Output tokens fell from ~1100 → ~150 avg.
- **Lever B (`play_concepts.py` + blockers-implicit):** Python concept
  classifier with 80+ patterns covering 97% of unique plays. For runs
  with blockers implicit, LLM emits empty routes. Run output dropped
  to ~60 tokens.
- **Lever C (route templates):** 10 well-known pass concepts (Mesh,
  Smash, Stick, Four Verts, Quick Slants, Curl Flat, Flood, Levels,
  Drags, All Streaks) with route templates baked into the cached system
  prompt. LLM emits `"routes":"std"` when diagram matches. Validated
  against user football coaching corrections.
- **Formation personnel hints (filename tag):** `formation_personnel.py`
  decodes `(RB, FB, TE, WR)` from formation name. `tag_crops_with_personnel.py`
  renames crops to embed `r#f#t#w#` in filename — LLM reads personnel
  from path with zero extra prompt cost.
- **Python `target_gap`:** deterministic gap classifier from C-square +
  red-arrow LOS-crossing. 3/3 ground-truth correct, beats LLM.
- **Family normalization:** I-FORM/I_FORM/I FOR/I FO merged in dedup.
  7,365 → 7,300 unique plays.
- **Cross-family smoke test:** all 18 formation families pass.
- **Multi-concept schema:** `concept` (dominant) + `concepts[]` (all
  visible) for plays that combine concepts (e.g., Smash + Curl-Flat).
- **Persistent output:** `data/games/madden-25-ps3/play-geometry/`.

**Cost trajectory:**
| Step | Cost |
|---|---:|
| Sonnet 4.5, unduped (start) | $330 |
| Haiku 4.5 + Python gap + dedup | $59 |
| + compact schema (Lever A) | $25 |
| + play_concepts + blockers-implicit (Lever B) | $20 |
| + validated route templates (Lever C) | $19 |
| + family normalization | **$19.71** |

**Full extraction ran 2026-05-21→22.** 7,300/7,300 extracted, 100%
JSON-parseable, $12.88 total (overnight run + 3 mop-up passes after
adding exponential-backoff retry — the API threw 2,603 529-Overloaded
errors overnight). Output: `data/games/madden-25-ps3/play-geometry/`.

## 2026-05-22 — Hand-review FAILED validation; pivoting to Python route geometry

**Tier-1 hand review failed.** User reviewed 18 of a 150-play sample:
3 correct / 10 partial / 5 wrong (~17% clean).
- **Routes are the core failure** — the LLM defaults to "streak".
  Dataset-wide, 26% of route labels are streak/seam; breaking routes
  are starved. A cheap-fix test (route-shape prompt + full resolution)
  also failed — the LLM still mislabels. It's a perception limit: the
  LLM cannot trace thin overlapping route arrows from the screenshot.
- Secondary: player errors (phantom TEs, RB-as-TE, wrong personnel
  counts, missed backfield backs).

**Decision: build a deterministic Python route-geometry extractor.**
Design doc: `tools/playbook-vision-pilot/ROUTE-GEOMETRY-DESIGN.md`.
Approach — per-receiver arrow tracing → geometry → route-tree
classification. The 18 hand-reviewed plays
(`/mnt/c/Users/root/Downloads/hand_review_results.json`) are the
validation gate.

**Dataset status:** the 7,300-play v1 has reliable `ball_carrier`/
`target_gap`/`concept`/`personnel` but **unreliable `routes`** — it is
NOT validation-passed. Treat as a foundation, not a finished product.

**In progress / next step:** route-geometry build, tasks #30–#34 —
(30) regenerate crops with non-route annotation color, (31) color
isolation + button/border filtering, (32) per-receiver tracing,
(33) geometry→route classifier, (34) integrate + re-test the 18.

## 2026-05-22 evening — PIVOT to clustering (CV tracing abandoned, route problem solvable)

Six iterations of CV tracing never converged — every fix broke
something else (final test: 1 of 5 routes traced + a border artifact).

**Reframe:** M25 diagrams are GAME-RENDERED — the same route is
pixel-identical every time. So fingerprint + cluster, don't trace.

**Proven on the red primary route:**
- v1 (all play_types): 7,289 red routes → 209 clusters, 98% in clusters
  of ≥3. Top: 1528 / 1227 / 964 / 534 / 445 plays.
- v2 (pass-only, side-aware): 5,313 routes → 224 clusters, 97% in
  clusters of ≥3.

**Labelling ~200 templates (not 7,300 plays) is the deterministic
deliverable.** Every play's red route maps to a cluster by exact pixel
match — no per-play guessing.

**v1 review (`red_cluster_labels_v1.json`):** user reviewed top 33
clusters. Verified findings:
1. v1 wrongly mixed pass-route primaries with run-play ball-carrier
   paths → v2 filters `play_type == "pass"` only.
2. Mirror dependency: same shape from a left-receiver = post, from
   right = corner. v2 records side per cluster member.
3. Magenta tracer overlay confused reviewers ("you drew this on the
   play?"). v2 drops it.
4. Screen routes wrongly dropped as `not_a_route` by the noise guard.
   v2 leaves proposed label blank for short routes.

**New route vocabulary the user contributed** (now in the LLM-label
prompt): `fade`, `quick_slants`, `hb_texas` (sideways-V below LOS),
`screen`, `wheel/flare_out`, `double_move`, `block_release_drag`.

**v2 build (in flight as of this write):**
- `tools/playbook-vision-pilot/cluster_red_routes.py` — fingerprint +
  cluster, anchors side on the red ⊙ button glyph (compact red CC) or
  bottommost route-CC bbox-bottom. **Uses `cv2.CC_STAT_*` only** — an
  earlier `np.where(labels==i)` implementation took 1h+ on 5,300 routes.
- `tools/playbook-vision-pilot/build_cluster_gallery.py` — renders an
  exemplar per cluster (no overlay, green LOS line for reference) and
  LLM-labels each via Haiku 4.5 with the new vocabulary; 6-way
  parallel; ~$0.20 per build.
- Produces `red-route-clusters.html` (~5 MB, gitignored).

**Next steps for the session picking this up:**
1. Confirm `red_clusters.json` has `"play_type": "pass"` (the v2
   marker — distinguishes from v1's mixed clustering).
2. `.venv/bin/python tools/playbook-vision-pilot/build_cluster_gallery.py`
   → regenerates `red-route-clusters.html` with LLM labels.
3. Open the gallery in a browser. For each card: leave blank if "LLM
   says" matches the shape; type the correct route name if wrong. Save
   `red_cluster_labels.json` when done (or partway through — the user's
   last commented cluster id marks the end of review).
4. Author the per-play join (small script not yet written): for each
   play, find which cluster its red mask matches, look up the cluster's
   label, write that into the per-play extraction JSON.
5. Extend to non-red routes: same fingerprint-and-cluster pipeline,
   anchored per receiver (the colored button glyphs ⊙ □ △ ⊗ mark
   receivers explicitly on pass plays).

**Active artifacts:**
- `cluster_red_routes.py`, `build_cluster_gallery.py` — the deterministic
  route pipeline.
- `red_clusters.json` — cluster membership + side per member.
- `red_cluster_labels_v1.json` — user's v1 review (~34 verified labels
  in the top 33). Use as spot-check gold.
- `ROUTE-GEOMETRY-DESIGN.md` — full design + iteration history.
- `route_geometry.py` — the abandoned tracer. Kept; superseded by
  clustering. Don't try to use it for routes.

**Dataset status (unchanged):** the 7,300-play v1 dataset in
`data/games/madden-25-ps3/play-geometry/` still has reliable
`ball_carrier` / `target_gap` / `concept` / `personnel`. `routes` will
be replaced by the clustering output once v2 labels land.

**Uncommitted state:** all the new tooling (`formation_personnel.py`,
`play_concepts.py`, `tag_crops_with_personnel.py`, `smoke_test_cross_family.py`,
`validate_extractions.py`, `template-review.html`, `build_template_review.py`)
and edited dispatcher/prompt — ready to commit before launch.

**Uncommitted state:** `tools/playbook-vision-pilot/` is fully untracked.
sample-crops/ace-batch/ (12 panels at 3x) and sample-crops/los-zoom/
(2 LOS-only at ~7.5x) added this session.

---

## 2026-05-20 — Phase 3 xlsx-game play backfill (M04, M07, NCAA 06, NCAA 05)

**Active thread:** backfilling plays into the xlsx-sourced game catalogs that
landed at 0% play coverage after the formation-only ingest.

**Landed this session:**
- **Madden 07** play names — 38/38 teams, 701/809 formations matched (87%);
  first pass left 8 teams truncated, rerun via 2-chunk per-image observation
  pass brought them to 20+ formations each. (`40cfb89`, `12a9c2d`)
- **Madden 04** play names — 38/38 teams, 484/496 formations matched (97.6%).
  Used the chunked approach from the start; near-perfect coverage on a fresh
  game. (`2e934a7`)
- **NCAA 06** play names — 1119/1125 formation-entries matched (99.5%). The
  game ships a master `Offensive Plays.docx` grouped by Heading-1 paragraphs;
  a new `map_n06_images_to_formations.py` walks the docx body and produces an
  image-index → formation map so vision only has to read play names. (`760e18d`)
- **NCAA 05 formation library** — no per-team playbook xlsx exists for NCAA
  05 (just team ratings), so the data emits as
  `data/games/ncaa-05-ps2/formation-library.yaml`: 50 formations, 947 plays
  from the master Offensive Plays.docx. New artifact shape — a game-wide
  reference rather than a per-team catalog. (`<this session>`)
- Reusable infra: `extract_m04_play_names.py`, `extract_m07_play_names.py`,
  `extract_n06_play_names.py`, `build_n05_formation_library.py`,
  `map_n06_images_to_formations.py`. The chunked per-image observation
  pattern (chunks of ~40 images → combiner) is now the default for any
  per-team docx — single-shot caused subagent truncation at ~100 images.

**In progress / next step:** still source-blocked for `madden-05-ps2`,
`ncaa-04-ps2`, `ncaa-07-ps2` (catalogs exist at formation-only, no play list
in research artifacts). User asked to hunt for sources next — forum dumps,
manuals, community spreadsheets.

**Uncommitted state:** session-log + pending-queue updates not yet committed.

---

## 2026-05-19 — NCAA 14 play names complete (end of Phase 2)

**Active thread:** finishing the NCAA Football 14 play-name extraction (per-formation docx vision).

**Landed this session:**
- Processed the final 35 missing docx in 7 Haiku subagents (5/each), all verified on disk.
- `.docx-cache-ncaa14-plays/` now holds 243 distinct per-formation JSONs.
- `data/games/ncaa-14-ps3/team-playbooks.yaml` — 2,570 catalog formation-entries now carry `plays` (up from 2,483). Remaining ~514 unmatched entries are defensive formations (3-4 Over, 4-3 Stack, Nickel/Dime/etc.) — out-of-scope for the offensive Play Database docx.
- Schema valid; 266 tests pass.

**In progress / next step:** Phase 2 (Madden 25 + ESPN 2K5 + NCAA 14 play-name attachment) is now complete end-to-end. Next pending-queue items: Madden 01/03 PS2 catalogs, `_family()` classifier for xlsx games, AI onboarding doc, README refresh. Game-editor measurements still blocked on user.

**Uncommitted state:** committing the NCAA 14 catalog + this session-log entry now.

---

**REPO MOVED** — the working directory was renamed from `madden_playgen_mcps`
to `/mnt/c/GitHub/blitz-command` (matching the git remote / "blitz-command").
The harness still resets cwd to the old name each command — prefix every
Bash command with `cd /mnt/c/GitHub/blitz-command`.

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

**Play-name grind: Madden 25 COMPLETE** — 50/50 playbooks, 14,419 plays.

**NCAA Football 14 (PS3) formation catalog DONE** — 141 teams, 3084
formations, from the Formation List.xlsx via build_playbook_catalog.py (fixed
two bugs: team_id slugs like "3_3_5" parsed as ints — now quoted; numeric junk
rows filtered). Play names still pending — the Play Database is 371 docx organised
by formation (not per-team screenshots), so it needs a different pipeline than
extract_play_names.py. Original note: NCAA 14 added by the user at research_artifacts/PS3/
"NCAA Football 14-.../NCAA Football 14". Has a Formation List.xlsx (build the
formation catalog with build_playbook_catalog.py), a Playbooks.xlsx, and a
371-docx Play Database organized by formation family. data/games/ncaa-14-ps3/
exists (editor-grid.yaml). To do after Madden 25 play names finish. Per-team workflow:
extract docx images to /tmp/m25-img/<slug>/, launch 4 chunked Haiku subagents
(~40 imgs each) writing `.docx-cache-m25-plays/<Team>__chunkNN.json`, then
`extract_play_names.py --game madden-25-ps3 --cache-dir .docx-cache-m25-plays`.

**In progress / next step:** NCAA 14 play names — pipeline built (extract_ncaa14_play_names.py;
one docx per formation). 224 distinct formations cached (234 cache files; some name dedup); 2483
catalog formation-entries have plays. Loop continues docx-list.txt lines 226-244 (cache .docx-cache-ncaa14-plays/).
Defensive formations in the catalog stay unmatched by design (offense-only Play Database). + 34 espn-2k5 remain. Same
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
