# Phase 5–8 Task Handoff

Detailed tasks for Phases 5 through 8 of the implementation plan, sized and scoped for handoff to smaller AI assistants (Haiku, Sonnet, GPT-5-mini, etc).

## How to use this doc

Each task is self-contained: it has a clear input (files to read, schemas to follow, templates to mimic), a clear output (files to create or modify), and an acceptance criterion (a command to run that proves it's done).

Tasks are tiered by AI suitability:

- **🟢 HAIKU** — pure research + fill-the-template work. Web scraping, YAML authoring from a known schema, transcribing facts from sources. No code changes.
- **🟡 SONNET** — code work, schema design, MCP server scaffolding, simple algorithms, integration. Small surface area, well-defined.
- **🔴 OPUS** — anything left ambiguous below, plus architectural decisions, breaking-change migrations, or cross-phase coordination. Mostly already handled — this column is for callouts.

Each task ID looks like `P5-T03` (Phase 5, Task 3). Tasks with prefix-letters (e.g. `P5-T04a`) are parameterized — the same task body but applied to N different inputs.

Run tests after each task: `./run-tests.sh` (the suite is the contract).

---

## Haiku prerequisites — read these before starting any 🟢 task

These rules apply to **every** 🟢 task. If a task body conflicts with this section, the task body wins; otherwise default to the rules here.

### Pre-flight checks

Before starting any data-authoring task:

1. **Verify schemas exist.** A task that says "validate against `schemas/X.schema.json`" assumes the schema file exists. Run:
   ```bash
   ls schemas/<schema-name>.schema.json
   ```
   If missing, the task is **blocked**. Stop and report — don't author the YAML against a guess.

2. **Verify the output directory exists.** If the task writes to `data/concepts/blocking-schemes/`, run:
   ```bash
   mkdir -p data/concepts/blocking-schemes/
   ```
   Do this every time, harmless if already there.

3. **Read at least one existing same-type file** to see the actual style used. For game profiles, read `data/games/madden-05-ps2/editor-grid.yaml`. For routes, read `data/routes/drag.yaml`. These are the reference style.

### Date handling

When a template shows `YYYY-MM-DD`, replace it with the **current date** in ISO format. Get it with:

```bash
date +%Y-%m-%d
```

**Always quote the date in YAML** — bare `2026-04-30` parses as a Date object and breaks schema validation:

```yaml
# WRONG (bare date — YAML auto-parses):
release_year: 2026-04-30

# RIGHT (quoted string):
release_year: "2026-04-30"
```

For numeric years (`release_year: 2007`), bare integers are fine.

### Source-citation format

Every `source_notes` entry follows this exact format:

```
"Web validated YYYY-MM-DD — <Source Name> (<URL>): <one-sentence summary of what this source confirmed>"
```

Examples:
```yaml
source_notes:
  - "Web validated 2026-05-01 — Wikipedia 'Madden NFL 05' (https://en.wikipedia.org/wiki/Madden_NFL_05): release year 2004, developer EA Tiburon, custom-play support confirmed."
  - "Web validated 2026-05-01 — Operation Sports forum thread (https://forums.operationsports.com/forums/madden-nfl-football/...): community confirms 21x7 editor grid, max 30 plays per playbook."
  - "Web validated 2026-05-01 — Throw Deep Publishing 'Power Run Concept' (https://throwdeeppublishing.com/...): canonical Power blocking is down-block backside + pull BSG."
```

**Each task requires at least 2 web-cited sources** unless the task body says otherwise. If you can find only 1, mark `verification_status: inferred` and add an entry like:

```yaml
  - "Could not find a second independent source for <specific claim>; <field> is inferred from <similar known game/concept>."
```

### Known good URL patterns

When in doubt, try these URL patterns first (most are reliably indexed):

- Wikipedia: `https://en.wikipedia.org/wiki/<Title_With_Underscores>` (e.g., `Madden_NFL_2008`)
- Wikipedia game lists: `https://en.wikipedia.org/wiki/Madden_NFL`, `https://en.wikipedia.org/wiki/NCAA_Football_(video_game_series)`
- Operation Sports forums: `https://forums.operationsports.com/`
- GameFAQs: `https://gamefaqs.gamespot.com/<platform>/<game-slug>`
- Pro Football Reference: `https://www.pro-football-reference.com/`
- Football coaching content: X&O Labs (`https://www.xandolabs.com/`), Throw Deep Publishing (`https://throwdeeppublishing.com/blogs/football-glossary/`), CougCenter (`https://www.cougcenter.com/`), Glazier Clinics (`https://www.glazierclinics.com/`), AFCA Insider (`https://insider.afca.com/`), Coach Tube
- Wikipedia coaches: `https://en.wikipedia.org/wiki/<Coach_Name>` (e.g., `Bill_Walsh_(American_football_coach)`)

### "Field doesn't apply" — fallback rules

YAML doesn't have a "this field is irrelevant" marker. Use these conventions:

| Situation | What to put |
|-----------|-------------|
| Field is explicitly **N/A** for this entity (e.g., `lead_blocker` on Inside Zone, no FB) | **Omit the field entirely** (don't write `lead_blocker: null`) |
| Field's value is **unknown but applicable** | Write `null` and add a `source_notes` entry explaining |
| Array field with no entries | Write `[]` (empty list) |
| Optional field that you do know | Always include it — completeness > brevity |
| `verification_status` you're not sure of | Default to `unverified`. Use `inferred` only if you reasoned from related data. Never claim `verified` from web research alone. |

### YAML pitfalls to avoid

1. **Unquoted dates** parse as Date objects. Always quote: `"2026-05-01"`.
2. **Strings starting with special characters** (`-`, `?`, `!`, `*`, `&`, `>`, `|`, `{`, `[`) need quoting.
3. **Strings containing `:` or `#`** need quoting (`#` becomes a comment).
4. **`yes` / `no` / `on` / `off` / `y` / `n`** parse as booleans in YAML 1.1. If you mean the string, quote it.
5. **Numeric strings with leading zeros** (`"08"`) parse as numbers (8) unless quoted.
6. **Multi-line strings** use `|` (preserve newlines) or `>` (fold). Use `|` for `description:` and `notes:` blocks.

### Game profiles specifically: PS1 era short-circuit

**Most PS1-era Madden and NCAA games do NOT have a create-a-play editor.** Madden 96 through Madden 2002 PS1 — none has a play editor in the modern sense. NCAA pre-2002 PS1 — same.

For these games, the YAML should still be authored, but:
- `custom_play_support: false`
- `custom_formation_support: false`
- `grid`, `scale`, `snap_to_cells`, `limits`, `playbook_caps` → all `null`
- `engine_quirks` → mention "no create-a-play editor in this title"
- `default_playbooks` → still researchable from manuals / Wikipedia / GameFAQs
- `verification_status` → `verified` if you found explicit confirmation that no editor exists

This is a valid 'short' profile and is acceptable. The MCP can filter games by `custom_play_support: true` to find designable ones.

### Common Haiku mistakes — don't do these

- **Don't invent fields** that aren't in the schema. If you think a new field is needed, report it; don't add it.
- **Don't combine multiple games into one file.** One game = one YAML.
- **Don't paraphrase source URLs** — copy them exactly.
- **Don't claim `verified` status** without explicit "I tested this in-game" provenance.
- **Don't write `tags: [pass, pa, west-coast]`** — some YAMLs prefer block style:
  ```yaml
  tags:
    - pass
    - pa
    - west-coast
  ```
  Match the style of the `data/plays/` examples.
- **Don't leave any field as a literal `?` or `<placeholder>`** — replace with real value, `null`, or omit.
- **Don't skip the validation command** — run it and report the result. If it fails, fix and re-run.

---

## Phase 5 — Concept libraries

**Goal**: blocking schemes, run concepts, pass protections, and offensive philosophies become first-class data instead of free-text duplication across play files. Plays gain optional `concept_ref` fields that foreign-key into them.

**Why this matters**: removes ~40% of the duplication in play files; unlocks concept-level analysis tools (Phase 6); unblocks the future concept MCPs.

**Order to execute**: schemas first, then data files, then plays migrate to foreign-keys.

### P5-T01 🟡 Blocking-scheme schema

**Goal**: define `schemas/blocking-scheme.schema.json` so every blocking scheme YAML can validate.

**Inputs to read**:
- `schemas/route.schema.json` (a small reference for the YAML schema style)
- 5 existing plays in `data/plays/` to see what `blocking_scheme:` values appear today (`grep -roh "blocking_scheme: [a-z-]*" data/plays/ | sort -u`)

**Output**: `schemas/blocking-scheme.schema.json`

Required fields:
- `scheme_id` (kebab-case, e.g. `man-protection`)
- `name` (human-readable)
- `category` (enum: `pass-protection` / `run-blocking` / `pull-block` / `combo`)
- `assignments_by_position` — object mapping OL/TE/FB labels to short rule strings
- `description` (1-paragraph textual)
- `verification_status` (`unverified` | `verified` | `inferred`)
- `source_notes` (array of strings)

Optional:
- `pairs_with` (array of run/pass concept ids)
- `defeats` (array of defensive scheme names this is good against)
- `vulnerable_to` (array)
- `tags`

**Acceptance**:
- `python3 -c "import json,jsonschema; jsonschema.Draft7Validator.check_schema(json.load(open('schemas/blocking-scheme.schema.json')))"` exits 0.
- A hand-written test fixture validates clean.

### P5-T02 🟡 Run-concept schema

**Goal**: `schemas/run-concept.schema.json` — captures Power, Counter, Iso, IZ, OZ etc as reusable abstractions.

**Required fields**:
- `concept_id` (kebab-case)
- `name`
- `category` (enum: `gap-scheme` / `zone-scheme` / `option` / `man-blocking-scheme` / `misdirection`)
- `description`
- `aim_point` (string: e.g. `playside A-gap`, `outside the playside C-gap`)
- `read_tree` (array of `{phase: int, defender: string, decision: string}`)
- `blocking_scheme_ref` (foreign key into `data/concepts/blocking-schemes/`)
- `verification_status`
- `source_notes`

**Optional**: `pairs_with`, `pulls_required` (array of OL labels), `lead_blocker`, `tags`.

**Acceptance**: schema validates + a fixture validates.

### P5-T03 🟡 Pass-protection schema

`schemas/pass-protection.schema.json` — like blocking-scheme but specific to pass-pro.

Required fields: `scheme_id`, `name`, `description`, `protection_type` (enum: `5-man` / `6-man` / `7-man` / `slide` / `half-slide` / `boss` / `big-on-big`), `assignments_by_position`, `vulnerable_to`, `verification_status`, `source_notes`.

**Acceptance**: schema validates.

### P5-T04 🟡 Philosophy schema

`schemas/philosophy.schema.json` — captures West Coast, Air Raid, etc.

Required fields: `philosophy_id`, `name`, `description`, `era`, `originators`, `canonical_run_concepts` (array), `canonical_pass_concepts` (array), `formation_preferences`, `tendency_profile` (run% / pass% / PA% / RPO% / screen%), `verification_status`, `source_notes`.

**Acceptance**: schema validates.

### P5-T05a..h 🟢 Author each blocking scheme

8 tasks, one per scheme. Each is identical work — copy the template below, fill in the body from research.

**Schemes to write** (one task each):
- `man-protection`
- `slide-protection`
- `half-slide-protection`
- `max-protection`
- `boss-protection`
- `big-on-big`
- `zone-blocking`
- `gap-blocking`

**Output path**: `data/concepts/blocking-schemes/<scheme_id>.yaml`

**Template** (copy and fill):
```yaml
scheme_id: man-protection
name: Man Protection
category: pass-protection
description: |
  <2-3 sentences explaining the scheme — what each OL is responsible for,
  who picks up blitzers, when this scheme is used.>
assignments_by_position:
  LT: "Block the LDE / EMOL on the weak side."
  LG: "Block the 1-tech or weak-side DT."
  C: "Block the NT (0/1-tech)."
  RG: "Block the 3-tech."
  RT: "Block the RDE / EMOL on the strong side."
  HB: "Check release; pick up first uncovered LB if blitzing, else release as outlet."
  TE: "If in pass-pro, chip-and-release on EDGE; else release as a route."
pairs_with:
  - mesh
  - smash-strong
  - snag-strong
defeats:
  - "single-DE rush"
  - "predictable 4-man front"
vulnerable_to:
  - "double-A-gap blitz"
  - "stunts that overload weak-side"
tags:
  - pass-protection
  - man
  - any-level
verification_status: unverified
source_notes:
  - "Web validated YYYY-MM-DD — <source URL with description>"
```

**Research sources to consult** (Haiku-friendly):
- X&O Labs articles on protections (`https://www.xandolabs.com/`)
- Throw Deep Publishing protection guides (`https://throwdeeppublishing.com/blogs/football-glossary/`)
- Glazier Clinics articles (`https://www.glazierclinics.com/`)
- AFCA Insider (`https://insider.afca.com/`)
- Football coaching texts cited via Wikipedia / coaching wikis

Each scheme should cite **at least 2 web sources** in `source_notes`.

**Fully-worked example** — copy this and adapt for the next scheme:

```yaml
scheme_id: man-protection
name: Man Protection
category: pass-protection
description: |
  Each offensive lineman is responsible for one specific defender (man-on-man).
  This is the simplest pass protection — no slides, no zone hand-offs. The
  HB stays in to scan for blitzers and picks up the most dangerous unblocked
  defender. Used when the offense expects a 4-man rush and wants maximum
  pre-snap clarity.
assignments_by_position:
  LT: "Block the LDE / EMOL on the weak side. Set vertical, mirror the rusher."
  LG: "Block the 1-tech or weak-side DT. Punch and anchor."
  C: "Block the NT (0/1-tech). Slide-step to whichever shade he aligns to."
  RG: "Block the 3-tech. Punch and anchor."
  RT: "Block the RDE / EMOL on the strong side. Set vertical."
  HB: "Check release; scan for first uncovered LB if blitzing, else release as outlet."
  TE: "Optional: chip-and-release on EDGE if in pass-pro; release as a route otherwise."
pairs_with:
  - mesh
  - smash-strong
  - snag-strong
defeats:
  - "single-DE rush"
  - "predictable 4-man front"
  - "vanilla 4-3 pass coverage"
vulnerable_to:
  - "double-A-gap blitz (overloads C+G)"
  - "stunts that overload weak-side"
  - "delayed LB blitz that beats HB scan"
tags:
  - pass-protection
  - man
  - any-level
  - high-school
  - college
  - nfl
verification_status: unverified
source_notes:
  - "Web validated 2026-05-01 — Throw Deep Publishing 'Pass Protection Schemes' (https://throwdeeppublishing.com/blogs/football-glossary/pass-protection-schemes): confirmed man protection assigns each OL one defender, HB scans for late blitz."
  - "Web validated 2026-05-01 — X&O Labs 'Man-Free Pass Protection' (https://www.xandolabs.com/the-lab/offense/protections/): confirmed standard 5-man + HB scan structure."
```

**Per-scheme guidance** (use these as your starting `description` paragraph):

| scheme_id | one-line gist |
|-----------|---------------|
| `man-protection` | Each OL has one defender; HB scans for blitz. |
| `slide-protection` | All 5 OL slide one direction (left or right); RB picks up backside C-gap. |
| `half-slide-protection` | 3 OL slide one way, 2 OL man-block the other; RB picks up frontside backer. |
| `max-protection` | 7-man protection: keep TE and HB in, no checkdown. Used on deep shots. |
| `boss-protection` | "Big-On-Big" — OL blocks every DL, HB scans backers; common spread variant. |
| `big-on-big` | Same as `boss-protection` but with a different read priority for the HB. |
| `zone-blocking` | OL blocks zones (gaps), not specific defenders; combo blocks at the LOS. |
| `gap-blocking` | OL blocks the gap to their playside (down-block + pull); used in Power, Counter. |

**Acceptance** (per task):
- File exists at the right path
- Validates against the schema:
  ```bash
  .venv/bin/python -c "import json,yaml,jsonschema; jsonschema.validate(yaml.safe_load(open('data/concepts/blocking-schemes/<scheme_id>.yaml')), json.load(open('schemas/blocking-scheme.schema.json')))"
  ```
  Exit code 0 means pass.
- ≥2 web-cited entries in `source_notes`, each with the format described in the prerequisites
- All player labels in `assignments_by_position` are real OL/skill labels (LT/LG/C/RG/RT/TE/HB/FB only — no invented labels)

### P5-T06a..o 🟢 Author each run concept

15 tasks, one per concept. Same structure as P5-T05.

**Concepts to write**:
- `power` (gap scheme, 1 puller)
- `counter-trey` (gap scheme, 2 pullers)
- `iso` (man scheme, FB lead)
- `inside-zone` (zone, B-gap aim)
- `outside-zone` (zone, perimeter)
- `trap` (gap, BSG pulls trap-block)
- `draw` (constraint, OL pass-sets then drives)
- `lead-toss` (perimeter, FB lead)
- `sweep` (perimeter, both Gs pull)
- `stretch` (zone, full-perimeter)
- `wham` (FB blocks back across, surprise OL release)
- `pin-and-pull` (zone hybrid)
- `crack-toss` (WR cracks, perimeter run)
- `triple-option-veer` (option, EDGE read)
- `midline-option` (option, NT read)

**Fully-worked example** (Power):

```yaml
concept_id: power
name: Power
category: gap-scheme
description: |
  Gap-blocking run scheme with the playside OL down-blocking and the backside
  guard pulling around the center to lead through the off-tackle hole. The
  playside TE kicks out the EDGE defender, creating a defined hole between RT
  and TE. The HB takes a delivered handoff and follows the puller through.
  Variants include Counter Trey (two pullers) and Power-O (the canonical form).
aim_point: "Off-tackle gap, between playside RT and TE"
read_tree:
  - phase: 1
    defender: playside EDGE / OLB
    decision: "If TE seals EDGE clean → run inside the kick-out. If EDGE wins → bounce around."
  - phase: 2
    defender: playside ILB
    decision: "Pulling guard takes him; HB reads the LG's path and finds the crease."
blocking_scheme_ref: gap-blocking
pulls_required:
  - LG  # backside guard pulls around C
lead_blocker: FB  # in I-Form variants; spread variants substitute the pulling LG as the lead
pairs_with:
  - counter-trey
  - iso
  - i-formation
  - singleback-trio
tags:
  - run
  - power-run
  - gap-scheme
  - any-level
  - high-school
  - college
  - nfl
verification_status: unverified
source_notes:
  - "Web validated 2026-05-01 — Throw Deep Publishing 'Complete Guide to the Power Play' (https://throwdeeppublishing.com/blogs/football-glossary/the-complete-guide-to-the-power-play): confirmed three core elements — double-team at point of attack, kick-out of EMOL, lead block through the hole."
  - "Web validated 2026-05-01 — vIQtory Sports 'Install Power' (https://www.viqtorysports.com/running-the-power-play-in-spread-power-offenses/): backside guard pull described identically; aim point off-tackle confirmed."
```

**Per-concept guidance** — use as your starting point:

| concept_id | category | Summary |
|------------|----------|---------|
| `power` | gap-scheme | Down-block playside, pull BSG, FB lead. Off-tackle aim. |
| `counter-trey` | gap-scheme | Down-block playside, pull BOTH BSG + BST. Counter-step from HB. Off-tackle. |
| `iso` | man-blocking-scheme | Drive-block double-team on playside DT, FB isolates the playside ILB, HB hits A-gap. |
| `inside-zone` | zone-scheme | OL takes a playside zone-step, combo-blocks DL, climbs to LBs. HB reads BANG/BEND/BOUNCE. B-gap aim. |
| `outside-zone` | zone-scheme | OL takes a wider zone-step (reach-block), HB stretches the perimeter. C-gap or wider. |
| `trap` | gap-scheme | Playside guard does NOT block the playside DT (lets him rush upfield); BSG pulls and traps him from the side. A-gap quick hit. |
| `draw` | misdirection | OL pass-sets for 1 count to sell pass, then drives. QB takes a pass-drop, late handoff. Punishes pass-rushing fronts. |
| `lead-toss` | man-blocking-scheme | QB pitches HB on the move, FB and PSG lead through the perimeter. Outside-zone-ish but with a pitch. |
| `sweep` | man-blocking-scheme | Both guards pull around the perimeter. WR cracks back. HB follows pullers wide. |
| `stretch` | zone-scheme | Even wider than outside-zone — full perimeter stretch. HB attacks the sideline. |
| `wham` | misdirection | FB blocks across the formation as a surprise — OL releases as if it's a pass. |
| `pin-and-pull` | zone-scheme | Hybrid: playside OL "pin" (down-block) the closest defender; backside OL pull around. |
| `crack-toss` | man-blocking-scheme | WR cracks back inside (cracks the playside safety/OLB), HB follows pullers wide. |
| `triple-option-veer` | option | Inside-veer triple. QB reads playside EDGE for dive (FB), then pitch defender for keep/pitch. |
| `midline-option` | option | Triple option but reads the NT instead of the EDGE. FB dives at A-gap. |

**`category` enum values**: `gap-scheme`, `zone-scheme`, `option`, `man-blocking-scheme`, `misdirection`. Pick the closest match.

**`blocking_scheme_ref` rules**: must be one of the schemes from P5-T05 (e.g., `gap-blocking`, `zone-blocking`, `man-protection`). If P5-T05 hasn't been completed yet, the foreign-key check will fail — that's acceptable; just include the most plausible value and the validator will only warn.

**Acceptance**:
- Schema-valid YAML
- ≥1 web-cited source in `source_notes` (preferably 2)
- `aim_point` is a specific gap or zone (not vague like "playside"); use letter-gap notation (`A`, `B`, `C`, `D`-gap) or specific descriptors ("off-tackle", "perimeter")
- `pulls_required` lists actual OL labels (`LG`, `RG`, `LT`, `RT`) — empty list `[]` if none

### P5-T07a..e 🟢 Author each pass-protection scheme

5 tasks. Like P5-T05 but specific to pass-pro.

**Protections to write** (one task each):
- `full-slide-left`
- `full-slide-right`
- `half-slide-protect`
- `max-protection-7-man`
- `boss-pickup` (Big-on-Big with HB scan)

Schema: `schemas/pass-protection.schema.json`. Output path: `data/concepts/pass-protections/<id>.yaml`.

**Fully-worked example** (full-slide-left):

```yaml
scheme_id: full-slide-left
name: Full Slide Left
description: |
  All 5 OL slide one cell to the LEFT (offense's left, defense's right). Used
  to combat heavy weak-side pressure or stunts. The HB MUST stay in to pick
  up the backside C-gap rusher (the unblocked man on the right). Releases the
  playside (left) flat as a hot read if pressure beats the slide.
protection_type: 5-man
assignments_by_position:
  LT: "Slide left — block whatever shows in the leftmost gap (could be wide-9 EDGE)."
  LG: "Slide left — block 5-tech if there, otherwise climb."
  C: "Slide left — block weakside 1-tech / 0-tech."
  RG: "Slide left — block playside NT (now the C's old assignment from his right)."
  RT: "Slide left — block playside 3-tech."
  HB: "REQUIRED: scan the right C-gap. Pick up the most dangerous unblocked rusher coming off the right edge."
  TE: "Optional: stay in for chip-and-release on the unblocked playside EDGE."
vulnerable_to:
  - "double-A-gap blitz that overloads C+RG slide direction"
  - "twist stunt that exchanges 3-tech and EDGE — the slide can lose track"
  - "delayed LB blitz from the slide direction"
pairs_with:
  - bootleg-strong  # roll-out away from the slide
  - flood-strong
  - mesh
tags:
  - pass-protection
  - slide
  - any-level
  - high-school
  - college
  - nfl
verification_status: unverified
source_notes:
  - "Web validated 2026-05-01 — Throw Deep Publishing 'Pass Protection — Slide Schemes' (https://throwdeeppublishing.com/blogs/football-glossary/pass-protection-slide): confirmed 5-OL slide structure with HB picking up the backside edge."
  - "Web validated 2026-05-01 — X&O Labs 'Slide Protection Variations' (https://www.xandolabs.com/the-lab/offense/protections/slide-protections/): confirmed full slide is 5-man, leaves backside C-gap to the HB."
```

**Per-protection guidance**:

| scheme_id | protection_type | Summary |
|-----------|----------------|---------|
| `full-slide-left` | 5-man | All 5 OL slide left; HB scans backside (right). |
| `full-slide-right` | 5-man | All 5 OL slide right; HB scans backside (left). |
| `half-slide-protect` | 5-man | 3 OL slide one way, 2 OL man-block the other. HB scans backside flow. |
| `max-protection-7-man` | 7-man | OL + TE + HB all stay in to block. No checkdown. Used on deep shots. |
| `boss-pickup` | 6-man | "Big-On-Big" — OL blocks every DL, HB scans LBs. 6th protector is the HB. |

**Acceptance** (per task):
- Schema-valid
- ≥2 web-cited source_notes
- `protection_type` enum value matches schema
- `assignments_by_position` covers all 5 OL plus HB (+ TE if it's part of the protection)

### P5-T08a..l 🟢 Author each philosophy

12 tasks, one per philosophy.

**Philosophies to write**:
- `west-coast` (Bill Walsh)
- `air-raid` (Mumme/Leach)
- `spread-option` (Rich Rodriguez / Malzahn)
- `power-run` (smashmouth)
- `pro-style` (generic NFL pro-style)
- `veer-option` (Bill Yeoman)
- `wing-t` (Tubby Raymond)
- `run-and-shoot` (Mouse Davis / June Jones)
- `coryell` (Don Coryell)
- `erhardt-perkins` (Erhardt + Perkins)
- `shanahan-zone` (Mike + Kyle Shanahan)
- `mcvay-rams` (Sean McVay / Wide Zone)

**Fully-worked example** (West Coast):

```yaml
philosophy_id: west-coast
name: West Coast
description: |
  Pass-first offense built around precise short-to-intermediate timing routes
  (mesh, drag, slant, flat) used to set up the run. Originated with Bill
  Walsh at the San Francisco 49ers in 1979 as an adaptation of Paul Brown's
  Cincinnati Bengals system. Emphasizes high-completion-percentage throws,
  yards after catch, and protection of the QB. Less vertical than Coryell;
  less spread than Air Raid.
era: "1979–present"
originators:
  - "Bill Walsh (San Francisco 49ers, 1979–1988)"
  - "Paul Brown (Cincinnati Bengals — Walsh's mentor)"
canonical_run_concepts:
  - inside-zone
  - outside-zone
  - power
  - draw
canonical_pass_concepts:
  - mesh
  - stick
  - flood
  - smash
  - bootleg-flat
formation_preferences:
  - i-formation
  - singleback-trio
  - singleback-ace
  - shotgun-2x2
tendency_profile:
  run_pct: 0.45
  pass_pct: 0.40
  pa_pct: 0.10
  rpo_pct: 0.0
  screen_pct: 0.05
notable_practitioners:
  - "Bill Walsh"
  - "Mike Holmgren"
  - "Andy Reid"
  - "Mike Shanahan"
  - "Sean Payton"
  - "Kyle Shanahan"
tags:
  - philosophy
  - west-coast
  - pass-first
  - timing-based
  - any-level
  - college
  - nfl
verification_status: unverified
source_notes:
  - "Web validated 2026-05-01 — Wikipedia 'West Coast offense' (https://en.wikipedia.org/wiki/West_Coast_offense): confirmed Bill Walsh / 49ers origin in 1979, derived from Paul Brown's Cincinnati system."
  - "Web validated 2026-05-01 — Wikipedia 'Bill Walsh' (https://en.wikipedia.org/wiki/Bill_Walsh_(American_football_coach)): confirmed Walsh as primary originator; coaching tree includes Holmgren / Shanahan / Reid / Payton."
  - "Web validated 2026-05-01 — Pro Football Reference team pages (https://www.pro-football-reference.com/teams/sfo/1984.htm): 1984 49ers run/pass split ~45/55 used as basis for tendency_profile."
```

**Per-philosophy guidance** — quick-start descriptions:

| philosophy_id | One-line gist | Era |
|---------------|---------------|-----|
| `west-coast` | Pass-first timing offense, short-intermediate, set up run by passing. Bill Walsh 49ers. | 1979– |
| `air-raid` | Pass-heavy, 4-WR shotgun, mesh + 4-verts. Mumme/Leach. | Mid-1990s– |
| `spread-option` | Spread the field with WRs to open run lanes; QB option. Rich Rodriguez / Malzahn. | 2000s– |
| `power-run` | Run-first, downhill, gap schemes (Power, Counter), play-action off the run. | Pre-WW2 to today |
| `pro-style` | Generic NFL pro-style: 21/12 personnel, balanced run/pass, deep playbook. | 1960s–today |
| `veer-option` | Triple-option from under-center (FB dive + QB keep + HB pitch). Bill Yeoman / Houston. | 1965– |
| `wing-t` | Misdirection-heavy, 21/22-personnel, Buck Sweep / Belly / Trap as the "big three". HS staple. | 1950s–today (HS) |
| `run-and-shoot` | 4-WR no-TE, choice routes, every receiver reads coverage. Mouse Davis / June Jones. | 1980s-90s |
| `coryell` | Vertical pass-first ("Air Coryell"), deep posts/digs, route trees by number. Don Coryell. | 1970s-80s |
| `erhardt-perkins` | Concept-based pass game (the same play has multiple names per formation). Patriots era staple. | 1970s– |
| `shanahan-zone` | Outside-zone run + bootleg play-action. Mike & Kyle Shanahan / Atlanta / 49ers. | 1990s– |
| `mcvay-rams` | Wide-zone + jet motion + condensed sets. Sean McVay's Rams. | 2017– |

**Tendency-profile derivation rules**:

- The 5 percentages must sum to 1.0 (±0.02).
- For each percentage, find at least ONE source confirming the rough split. Sources ranked by reliability:
  1. **Pro Football Reference team pages** (e.g., `https://www.pro-football-reference.com/teams/sfo/1984.htm`) — exact run/pass ratios for NFL teams in any year. Use a representative season for the philosophy's peak.
  2. **Sharp Football** / Football Outsiders articles — modern tendency analysis.
  3. **Coach's published interviews** describing their own balance.
  4. **Wikipedia philosophy pages** — give qualitative ranges only.
- If exact data isn't findable, use these conservative defaults and mark `verification_status: inferred`:

| Philosophy type | run_pct | pass_pct | pa_pct | rpo_pct | screen_pct |
|-----------------|---------|----------|--------|---------|------------|
| Pass-heavy modern (Air Raid, McVay) | 0.30 | 0.50 | 0.10 | 0.05 | 0.05 |
| Balanced (West Coast, Pro-Style) | 0.45 | 0.40 | 0.10 | 0.00 | 0.05 |
| Run-first modern (Wing-T, Power Run) | 0.65 | 0.20 | 0.10 | 0.00 | 0.05 |
| Triple-option (Veer, Flexbone-style) | 0.85 | 0.10 | 0.05 | 0.00 | 0.00 |
| Spread-option (modern RPO-heavy) | 0.40 | 0.25 | 0.05 | 0.25 | 0.05 |

**Acceptance**:
- Schema-valid
- ≥2 web-cited source_notes
- `tendency_profile` sums to 1.0 ± 0.02
- `originators` and `notable_practitioners` cite real coaches with year ranges
- `canonical_*_concepts` arrays use kebab-case ids matching files in `data/concepts/run-concepts/` and `data/concepts/pass-concepts/` (foreign-key check will warn if a referenced concept hasn't been authored yet — that's OK)

### P5-T09 🟡 Migrate existing plays to use concept_ref

**Goal**: add an optional `concept_ref` field to every play that maps to a known run concept, blocking scheme, or pass concept. Update `schemas/play.schema.json` to add the optional fields.

**Inputs**:
- All ~144 play files
- The newly-built concept libraries (after P5-T05/T06/T07/T08)

**Steps**:
1. Add to `schemas/play.schema.json`:
   - `run_concept_ref` (optional string, foreign key)
   - `pass_concept_ref` (optional string)
   - `pass_protection_ref` (optional string)
   - `philosophy_ref` (optional string — also bumps the existing `philosophy` field to optional)
2. Write a migration script `tools/migrate-add-concept-refs/migrate.py` that walks every play and infers the refs from existing fields (e.g., a play tagged `power-run` gets `run_concept_ref: power`).
3. Run the script. Spot-check 10 random plays to confirm correct inference.

**Acceptance**: every existing play still validates; >80% of run plays have `run_concept_ref`; >80% of pass plays have `pass_concept_ref`.

### P5-T10 🟡 Validate concept_ref foreign keys in `validate_play`

**Goal**: when a play declares `run_concept_ref: power`, `validate_play` should check that `data/concepts/run-concepts/power.yaml` exists.

**Output**: a small extension to `validate_play` in `mcps/play-library-mcp/server.py`. Add a section after the route foreign-key check:

```python
# Concept foreign-key check
for ref_field, dir_name in (
    ("run_concept_ref", "run-concepts"),
    ("pass_concept_ref", "pass-concepts"),
    ("pass_protection_ref", "pass-protections"),
    ("philosophy_ref", "philosophies"),
):
    ref = play_data.get(ref_field)
    if ref:
        target = REPO_ROOT / "data" / "concepts" / dir_name / f"{ref}.yaml"
        if not target.exists():
            warnings.append(f"{ref_field} '{ref}' not found at {target}")
```

**Acceptance**: a test in `tests/test_mcp_tools.py` injects a bad `run_concept_ref` and asserts the warning fires.

### P5-T11 🟡 Pass-concept library

**Goal**: like run-concepts, but for passing concepts (mesh, smash, snag, stick, flood, etc).

**Steps**:
1. Reuse `schemas/run-concept.schema.json` if you can, or create `schemas/pass-concept.schema.json` (minor variation).
2. Author 12-15 pass concept files.

**Concepts**: mesh, smash, snag, stick, flood, four-verticals, drive, hi-lo, levels, dagger, sail, post-corner, slant-flat, double-slant, switch.

This task overlaps with the existing concept templates in `data/concepts/play-templates.yaml` — extract the route info from there into per-concept files and add depth + read tree.

---

## Phase 6 — MCP Tooling

**Goal**: ship the remaining MCP servers from the original 9 planned, now that the data they wrap exists.

**State today**: 2 of 9 shipped (`play-library-mcp`, `formation-library-mcp`). 7 to go.

The data each MCP needs comes from Phase 5 (concept libraries) and Phase 8 (game profiles). For MCPs whose data isn't ready, mark them `blocked: <phase>` and skip until prereqs land.

### P6-T01 🟡 route-library-mcp scaffold

**Goal**: a tiny MCP that wraps the existing `data/routes/` library. The data has been there for months — this just exposes it.

**Steps**:
1. Copy `mcps/formation-library-mcp/` to `mcps/route-library-mcp/`. Rename references from "formation" to "route" throughout.
2. Wire up these tools:
   - `list_routes()` — id, name, aliases, category, beats_coverage
   - `get_route(route_id)` — full file
   - `find_routes_by_category(category)` — vertical/in-breaking/out-breaking/underneath
   - `find_routes_by_coverage(coverage)` — `man` / `zone` / `both`
   - `find_routes_by_depth(min_yd, max_yd)`
3. Update `requirements.txt` (same deps).
4. Write 6 tests in `tests/test_mcp_tools.py` mirroring the formation MCP test pattern.
5. Update `docs/using-the-mcps.md` to register the new MCP.

**Acceptance**: `./run-tests.sh` passes; `list_routes()` returns ≥18 routes.

### P6-T02 🟡 coverage-mcp scaffold

**Goal**: wraps the 9 defensive formations as if they were a coverage library.

**Tools**:
- `list_coverages()` — id, name, front, coverage_shell, tags
- `get_coverage(id)` — full defense file
- `find_coverage_by_shell(shell)` — `cover-3`, `cover-2`, etc.
- `find_coverage_by_front(front)` — `4-3`, `3-4`, `4-2-5`, etc.
- `find_coverage_vulnerable_to(concept)` — searches `vulnerable_to` lists

**Source data**: `data/formations/defense-*.yaml` (already exists).

**Acceptance**: 5 tests pass, all 9 defenses discoverable.

### P6-T03 🟡 run-concept-mcp scaffold

**Depends on**: P5-T06 (run-concept files exist).

**Tools**:
- `list_run_concepts()`, `get_run_concept(id)`, `find_run_concepts_by_category(cat)`, `find_run_concepts_by_aim_point(aim)`, `find_run_concepts_pairs_with(other)`

**Acceptance**: standard MCP test suite + ≥15 concepts discoverable.

### P6-T04 🟡 blocking-scheme-mcp scaffold

**Depends on**: P5-T05 (blocking scheme files exist).

Same pattern. Tools: list/get/find by category, find by `defeats`, find by `vulnerable_to`.

### P6-T05 🟡 pass-protection-mcp scaffold

**Depends on**: P5-T07.

Same pattern.

### P6-T06 🟡 philosophy-mcp scaffold

**Depends on**: P5-T08.

Tools: list/get/find by era, find by originator, find by tendency (e.g., "find pass-heavy philosophies with run% < 0.40").

### P6-T07 🟡 game-knowledge-mcp scaffold

**Depends on**: Phase 8 game profile measurements.

**Tools**:
- `list_games()` — id, name, year, platform, custom_play_support, verification_status
- `get_game(game_id)` — full profile
- `compare_games(id1, id2)` — capability diff (grid size, max route depth, motion options)
- `find_games_supporting(feature)` — boolean queries on capability flags
- `find_games_by_era(era)` — era enum: `ps1` / `ps2` / `ps3`

**Acceptance**: tests pass, all currently-built profiles discoverable.

### P6-T08 🟡 validation-mcp scaffold

**Goal**: extract `validate_play` and the cross-reference checks into a dedicated MCP server. The existing `validate_play` in play-library stays as a convenience but delegates to the new MCP.

**New tools**:
- `validate_play(play_data, strict=False)`
- `validate_formation(formation_data, strict=False)`
- `validate_route(route_data, strict=False)`
- `validate_concept(concept_data, kind, strict=False)` (kind: run / pass / blocking / pass-protection / philosophy)
- `validate_game_profile(profile_data, strict=False)`
- `lint_play(play_data)` — concept-level checks only (no schema)

**Acceptance**: every existing test that calls `validate_play` still passes; new tests for the dedicated MCP.

### P6-T09 🟡 play-variant-mcp scaffold

**Goal**: stub MCP that becomes the home for `generate_play_family` (Phase 7) and other variant-generation tools. Ship the scaffold even if the algorithms come later.

**Tools (initial)**:
- `mirror_play_variant(play_id)` — already exists in play-library; thin re-export
- `flip_strength(play_id)` — flip a strong/weak variant of an existing play
- `placeholder for Phase 7 generators`

**Acceptance**: scaffold works, 1-2 simple tools shipped.

### P6-T10 🟡 playbook-generation-mcp scaffold

**Goal**: stub MCP for the eventual playbook-optimizer (Phase 7+). Ship the scaffold; flesh out tools in Phase 7.

**Tools (initial)**:
- `assemble_playbook_simple(formation_constraint, play_count, philosophy=None)` — naive: pick N plays from the constraint
- Reserve namespace for Phase 7's optimizer

**Acceptance**: scaffold works.

### P6-T11 🟡 Cross-MCP composition: `manifest()`

**Goal**: every server gets a `manifest()` tool returning purpose + tool list + 1-2 worked examples. Lets a new AI session ask "what does this MCP do?"

**Steps**:
1. Add `manifest()` to each of the now-9 MCP servers
2. Update `docs/using-the-mcps.md` to mention `manifest()` as the introspection entry point

**Acceptance**: each MCP tested for `manifest()` output.

### P6-T12 🟡 Pagination on `list_*` tools

**Goal**: `list_plays` returns ~144 entries; smaller AIs choke on large responses. Add pagination.

**Pattern**:
```python
def list_plays(cursor: str | None = None, limit: int = 50) -> dict:
    """Returns {items: [...], next_cursor: str | None}"""
```

Apply to: `list_plays`, `list_formations`, `list_routes`, `list_run_concepts`, `list_coverages`, etc.

**Acceptance**: tests verify cursor-based iteration covers the full set.

---

## Phase 7 — Play Family Generator

**Goal**: given a base play, automatically derive 4-7 complementary plays that share its pre-snap look but attack different things (run / counter / PA / screen / bootleg).

**State**: nothing built. The existing `suggest_complementary_plays` does the discovery half but doesn't generate.

**Order**: define the family schema → write the algorithm → ship the MCP tool → curate generated families.

### P7-T01 🟡 play-family schema

**Goal**: `schemas/play-family.schema.json`.

Required fields:
- `family_id`
- `name`
- `description`
- `formation_id`
- `philosophy`
- `base_play_id`
- `companion_play_ids` (array of 3-7 ids)
- `tags`
- `verification_status`
- `source_notes`

**Optional**:
- `disguise_score` (computed from `compare_plays`)
- `defensive_coverage_matrix` (which defenses each play exploits / struggles)

**Acceptance**: schema-valid.

### P7-T02 🔴 Family generator algorithm design

**Goal**: design the algorithm. Inputs: base play. Outputs: a ranked list of candidate companion plays.

**Approach** (sketch):
1. Compute base play's pre-snap fingerprint (formation + motion + OL action)
2. Find candidate plays in the same formation
3. Score by: play_type diversity vs base, ball_carrier diversity, mechanic diversity (read vs no-read, fake vs no-fake, perimeter vs interior)
4. Pick top 5-7 to maximize a diversity objective
5. Optionally generate new plays from concept templates if too few candidates exist

**Output**: `docs/play-family-algorithm.md` — design doc.

**Caller**: this task is OPUS-grade — needs design judgment.

### P7-T03 🟡 Family generator implementation

**Depends on**: P7-T02.

**Tool**: `generate_play_family(base_play_id, family_size=5, allow_new_plays=False)` in play-variant-mcp.

**Returns**:
```python
{
    "family_id": "...",
    "base_play_id": "...",
    "companions": [
        {"play_id": "...", "score": 0.87, "reason": "different play_type, same formation"},
        ...
    ],
    "disguise_score": 0.92,
}
```

**Acceptance**: 3-5 tests on canonical bases (Mesh → suggests Power, Smash, PA Cross, etc).

### P7-T04 🟢 Curate 10-15 named families

**Goal**: hand-curate canonical play families and save them to `data/play-families/`.

Each family is a YAML matching `schemas/play-family.schema.json`. Examples:
- "Singleback Trio Disguise" (the 7-play playbook from earlier dogfood)
- "I-Form Power Family" (Power-O + Counter Trey + ISO + Lead Toss + PA Cross)
- "Air Raid Base" (Mesh + 4-Verts + Stick + Smash + Y-Cross)
- "Wing-T Big Three + Companions" (Buck Sweep + Belly + Trap + Waggle + Boot)
- "Flexbone Triple-Option Family" (Triple + Midline + Pitch + PA Bootleg + Counter Option)

**Acceptance**: ≥10 families validated; `compare_plays` returns disguise_score > 0.7 for each.

### P7-T05 🟡 playbook-generation-mcp `assemble_playbook` v1

**Goal**: assemble_playbook(philosophy, formations, target_size, game_id=None) returns a balanced playbook.

**Algorithm sketch** (Sonnet-friendly):
1. Filter library by philosophy match
2. Filter by formation_constraint
3. Apply game_id capability filter (skip plays exceeding the editor)
4. Select to hit target play type distribution (45% run / 35% pass / 10% PA / 5% RPO / 5% screen)
5. Select to hit family balance (every base run has its counter; every PA has the run it cross-references)

**Returns**: the playbook + rationale per pick.

**Acceptance**: 3 tests on canonical philosophies (Air Raid, Power Run, Spread Option). Output validates against playbook schema (Phase 8) once that exists.

---

## Phase 8 — Game Knowledge + Per-Game Export

**Goal**: every NCAA + Madden game from PS1/PS2/PS3 has a verified editor profile. Per-game text export of plays so users can manually-type recreate plays in any era's editor.

**State**: 3 game profiles, only Madden 05 measured. The other ~30 are placeholders or missing.

**Order**: research-heavy YAML authoring (Haiku-perfect work), then export-format adapters per game.

### P8-T01 🟡 Game-profile schema upgrade

**Goal**: extend `schemas/game.schema.json` with the fields the new MCPs need.

**Fields to add**:
- `release_year` (int)
- `developer` (string)
- `publisher` (string)
- `platform` (enum: `ps1` / `ps2` / `ps3` / `pc` / `xbox` / `gamecube`)
- `era` (enum: `ps1` / `ps2` / `ps3`)
- `custom_play_support` (bool)
- `custom_formation_support` (bool)
- `editor_grid` (already exists — `grid` field)
- `editor_route_support` (object — what route mechanics are supported)
- `editor_motion_support` (object — what motion options exist)
- `playbook_caps` (object — `max_plays_total`, `max_plays_per_personnel`, etc.)
- `engine_quirks` (array of free-text)
- `default_playbooks` (array of playbook names that ship with the game)
- `verification_status`
- `source_notes`

**Acceptance**: schema validates + existing 3 game profiles re-validate (after backfilling missing fields).

### P8-T02 🟡 Game-profile measurement protocol upgrade

**Goal**: extend `docs/game-editor-measurement-protocol.md` with the new fields. Document how to gather each.

For each new field, list:
- Where to look in-game (Edit Mode → New Play → ...)
- What to count / measure
- Acceptable approximations
- Web-research alternatives if game isn't available

**Acceptance**: a contributor without the game can fill out a profile from the protocol alone.

### P8-T03a..ad 🟢 Per-game profile YAMLs (~30 tasks)

**This is the big Haiku batch.** 30 tasks, one per game. Each is identical research work.

Output path: `data/games/<game-id>/editor-grid.yaml`

**Games to research** (organized by era):

**PS1 era** (8 games):
- `madden-96-ps1`, `madden-97-ps1`, `madden-98-ps1`, `madden-99-ps1`, `madden-2000-ps1`, `madden-2001-ps1`, `madden-2002-ps1`, `ncaa-99-ps1`, `ncaa-2000-ps1`, `ncaa-2001-ps1`

**PS2 era** (~12 games):
- `madden-02-ps2`, `madden-03-ps2`, `madden-06-ps2`, `madden-07-ps2`, `madden-08-ps2`, `madden-09-ps2`, `madden-10-ps2`, `madden-11-ps2`
- `ncaa-02-ps2`, `ncaa-03-ps2`, `ncaa-04-ps2`, `ncaa-05-ps2`, `ncaa-07-ps2`, `ncaa-08-ps2`, `ncaa-09-ps2`, `ncaa-10-ps2`, `ncaa-11-ps2`

**PS3 era** (12 games):
- `madden-07-ps3`, `madden-08-ps3`, `madden-09-ps3`, `madden-10-ps3`, `madden-11-ps3`, `madden-12-ps3`, `madden-13-ps3`
- `ncaa-07-ps3`, `ncaa-08-ps3`, `ncaa-09-ps3`, `ncaa-10-ps3`, `ncaa-11-ps3`, `ncaa-12-ps3`, `ncaa-13-ps3`, `ncaa-14-ps3`

**IMPORTANT pre-flight checks**:

1. **First**, check if the game even has a play editor. PS1 Madden games (Madden 96 through Madden 2002 PS1) and PS1 NCAA games (NCAA 99-2001) generally do NOT have create-a-play. If your assigned game is on the no-editor list below, use the **PS1 short profile** template instead of the full template.
2. **Verify** `data/games/<game-id>/` directory exists; create it if not (`mkdir -p data/games/<game-id>/`).
3. **Read** the existing `data/games/madden-05-ps2/editor-grid.yaml` for reference style.
4. **Read** `docs/game-editor-measurement-protocol.md` if available — it has the in-game measurement procedure.
5. **Check schema** exists at `schemas/game.schema.json`. If it's been upgraded by P8-T01, follow the new fields.

**Games that DO have create-a-play** (use the FULL template):
- All PS2 Madden (02-11) and PS2 NCAA (02-11)
- All PS3 Madden (07-13) and PS3 NCAA (07-14)
- A few late PS1 titles — verify per-game

**Games with NO create-a-play** (use the SHORT template):
- All PS1 Madden (96, 97, 98, 99, 2000, 2001, 2002) — most do NOT have an editor; verify per game
- All PS1 NCAA (98-2001) — none has an editor

---

#### Full template (use for games WITH create-a-play)

Fully-worked example — Madden 08 PS2, derived from period reviews:

```yaml
game_id: madden-08-ps2
name: "Madden NFL 08"
release_year: 2007
developer: "EA Tiburon"
publisher: "EA Sports"
platform: ps2
era: ps2
custom_play_support: true
custom_formation_support: false  # Madden didn't add custom-formation editor until later
grid:
  width: 21      # PS2-era Madden grid is consistently 21x7 per period docs
  height: 7
  origin:
    x: 10
    y: 5
scale:
  x_yards_per_cell: 1.667    # inferred from confirmed Madden 05 spec; PS2-era titles share the engine
  y_yards_per_cell: 2.0
snap_to_cells: true
limits:
  max_route_depth_yd: 20     # confirmed for Madden 05; assumed unchanged
  max_player_split_yd: 15
  max_backfield_depth_yd: 7.5
  allowed_motion:
    - short
    - long
    - across
playbook_caps:
  max_plays_total: 75        # PS2-era Madden custom playbook cap; verify per source
  max_plays_per_personnel: null  # not documented; mark null + quirk
engine_quirks:
  - "PS2-era Madden custom playbook cap of 75 plays — verify against in-game testing."
  - "max_plays_per_personnel not documented in available sources."
default_playbooks:
  - "Bill Belichick (Patriots)"
  - "Bill Parcells (Cowboys)"
  - "Tony Dungy (Colts)"
  # ... continue with the full set if findable; otherwise note "list incomplete" in source_notes
verification_status: inferred   # bump to 'verified' only after in-game measurement
source_notes:
  - "Web validated 2026-05-01 — Wikipedia 'Madden NFL 08' (https://en.wikipedia.org/wiki/Madden_NFL_08): release year 2007, developer EA Tiburon, custom-play feature confirmed."
  - "Web validated 2026-05-01 — GameFAQs Madden NFL 08 PS2 (https://gamefaqs.gamespot.com/ps2/938669-madden-nfl-08): custom playbook + create-a-play features listed."
  - "Web validated 2026-05-01 — Operation Sports forum thread (https://forums.operationsports.com/...): 75-play custom playbook cap mentioned by community."
  - "Inferred from Madden 05 PS2 known specs (grid 21x7, scale 1.667/2.0); engine assumed unchanged across PS2 generation."
```

---

#### Short template (use for games WITHOUT create-a-play)

Fully-worked example — Madden 99 PS1:

```yaml
game_id: madden-99-ps1
name: "Madden NFL 99"
release_year: 1998
developer: "EA Tiburon (with Visual Concepts)"
publisher: "EA Sports"
platform: ps1
era: ps1
custom_play_support: false      # PS1 Madden has no create-a-play editor
custom_formation_support: false
grid: null                       # no editor grid because no editor
scale: null
snap_to_cells: null
limits: null
playbook_caps: null
engine_quirks:
  - "No create-a-play editor in this title — all plays are built-in."
  - "Limited audible system; no playbook customization."
default_playbooks:
  - "All 30 NFL teams (1998 season rosters)"
  # If individual playbook names are documented, list them; else describe like above
verification_status: verified    # 'no editor' is reliably documentable
source_notes:
  - "Web validated 2026-05-01 — Wikipedia 'Madden NFL 99' (https://en.wikipedia.org/wiki/Madden_NFL_99): release year 1998; no create-a-play feature listed."
  - "Web validated 2026-05-01 — GameFAQs Madden NFL 99 PS1 (https://gamefaqs.gamespot.com/ps/197384-madden-nfl-99): custom-playbook absence confirmed by review of feature list."
```

---

#### Per-game starter information

Fill in these starter facts for each game as a "you can rely on these" baseline. Beyond this, web-research the rest:

| game_id | release_year | platform | era | custom_play_support | grid (if known) |
|---------|--------------|----------|-----|---------------------|-----------------|
| `madden-96-ps1` | 1995 | ps1 | ps1 | false (no editor) | n/a |
| `madden-97-ps1` | 1996 | ps1 | ps1 | false | n/a |
| `madden-98-ps1` | 1997 | ps1 | ps1 | false | n/a |
| `madden-99-ps1` | 1998 | ps1 | ps1 | false | n/a |
| `madden-2000-ps1` | 1999 | ps1 | ps1 | false | n/a |
| `madden-2001-ps1` | 2000 | ps1 | ps1 | false (verify) | n/a |
| `madden-2002-ps1` | 2001 | ps1 | ps1 | false (verify) | n/a |
| `madden-02-ps2` | 2001 | ps2 | ps2 | true | likely 21×7 (verify against Madden 05) |
| `madden-03-ps2` | 2002 | ps2 | ps2 | true | likely 21×7 |
| `madden-04-ps2` | 2003 | ps2 | ps2 | true | likely 21×7 |
| `madden-05-ps2` | 2004 | ps2 | ps2 | true | **21×7 confirmed** |
| `madden-06-ps2` | 2005 | ps2 | ps2 | true | likely 21×7 |
| `madden-07-ps2` | 2006 | ps2 | ps2 | true | likely 21×7 |
| `madden-08-ps2` | 2007 | ps2 | ps2 | true | likely 21×7 |
| `madden-09-ps2` | 2008 | ps2 | ps2 | true | likely 21×7 |
| `madden-10-ps2` | 2009 | ps2 | ps2 | true | likely 21×7 |
| `madden-11-ps2` | 2010 | ps2 | ps2 | true | likely 21×7 |
| `madden-07-ps3` | 2006 | ps3 | ps3 | true | likely larger than PS2 (verify) |
| `madden-08-ps3` | 2007 | ps3 | ps3 | true | larger grid (verify) |
| `madden-09-ps3` | 2008 | ps3 | ps3 | true | verify |
| `madden-10-ps3` | 2009 | ps3 | ps3 | true | verify |
| `madden-11-ps3` | 2010 | ps3 | ps3 | true | verify |
| `madden-12-ps3` | 2011 | ps3 | ps3 | true | verify |
| `madden-13-ps3` | 2012 | ps3 | ps3 | true | verify |
| `ncaa-99-ps1` | 1998 | ps1 | ps1 | false | n/a |
| `ncaa-2000-ps1` | 1999 | ps1 | ps1 | false | n/a |
| `ncaa-2001-ps1` | 2000 | ps1 | ps1 | false | n/a |
| `ncaa-02-ps2` | 2001 | ps2 | ps2 | true | likely similar to Madden 02 PS2 |
| `ncaa-03-ps2` | 2002 | ps2 | ps2 | true | similar to NCAA 02 |
| `ncaa-04-ps2` | 2003 | ps2 | ps2 | true | verify |
| `ncaa-05-ps2` | 2004 | ps2 | ps2 | true | verify |
| `ncaa-06-ps2` | 2005 | ps2 | ps2 | true | placeholder profile already exists |
| `ncaa-07-ps2` | 2006 | ps2 | ps2 | true | verify |
| `ncaa-08-ps2` | 2007 | ps2 | ps2 | true | verify |
| `ncaa-09-ps2` | 2008 | ps2 | ps2 | true | verify |
| `ncaa-10-ps2` | 2009 | ps2 | ps2 | true | verify |
| `ncaa-11-ps2` | 2010 | ps2 | ps2 | true | verify |
| `ncaa-07-ps3` | 2006 | ps3 | ps3 | true | verify |
| `ncaa-08-ps3` | 2007 | ps3 | ps3 | true | verify |
| `ncaa-09-ps3` | 2008 | ps3 | ps3 | true | verify |
| `ncaa-10-ps3` | 2009 | ps3 | ps3 | true | verify |
| `ncaa-11-ps3` | 2010 | ps3 | ps3 | true | verify |
| `ncaa-12-ps3` | 2011 | ps3 | ps3 | true | verify |
| `ncaa-13-ps3` | 2012 | ps3 | ps3 | true | verify |
| `ncaa-14-ps3` | 2013 | ps3 | ps3 | true | verify |

Treat the "likely" / "verify" cells as starting hypotheses — confirm or refute with web research.

**Research sources** (Haiku-friendly, in priority order):
1. **Wikipedia game pages** — release year, developer, publisher, platforms, feature list, modes
2. **GameFAQs game pages** — custom playbook + custom-play feature presence, manual reference
3. **Operation Sports forums** (`https://forums.operationsports.com/`) — community-documented engine quirks, playbook caps
4. **YouTube create-a-play tutorials** for specific titles — visual confirmation of grid dimensions (count cells in the screenshot)
5. **IGN / GameSpot reviews** — high-level features
6. **EA Sports Madden Wiki** (`https://madden.fandom.com/`) — community-curated game details

**Acceptance** (per task):
- File exists at `data/games/<game-id>/editor-grid.yaml`
- Schema validates:
  ```bash
  .venv/bin/python -c "import json,yaml,jsonschema; jsonschema.validate(yaml.safe_load(open('data/games/<game-id>/editor-grid.yaml')), json.load(open('schemas/game.schema.json')))"
  ```
  Exit code 0.
- ≥2 web-cited entries in `source_notes` with the standard format (date, source name, URL, what was confirmed)
- `verification_status` honestly set:
  - `verified` — direct in-game measurement OR explicit "no editor" confirmation in a published review
  - `inferred` — derived from related games' specs + reasonable assumptions
  - `unverified` — most fields are guesses
- Every `null` field has a corresponding `engine_quirks` entry explaining WHY it's null
- For PS1 short profiles: `custom_play_support: false`, all editor-related fields `null`, status `verified`

### P8-T04 🟡 Per-game export-format adapter framework

**Goal**: refactor `export_play_instructions` to support per-game format adapters. The current markdown format is generic; some games might benefit from game-specific terminology ("Receiver position 1" vs "X" depending on era).

**Output**: `tools/export-instructions/` — a small framework where each game can register a custom formatter.

**Acceptance**: at least 2 game-specific formatters (e.g., a "Madden 2005" formatter and a "Madden 2010" formatter) that produce subtly different markdown.

### P8-T05 🟢 Per-game default-playbook research

**Goal**: for each PS2-era game, document what playbooks shipped with it.

Output: `data/games/<game-id>/default-playbooks.yaml` — list of playbook names + per-playbook play counts where known.

**Acceptance**: ≥10 PS2-era games have this file.

### P8-T06 🟡 Per-game canonical-play extraction tooling

**Goal**: build a workflow for extracting actual built-in plays from games (per `docs/play-data-provenance.md`).

**Steps**:
1. Define a "canonical play extraction" YAML format that captures: source_game, source_playbook, source_play_call, screenshot reference, transcribed assignments
2. Document the manual workflow (screenshot → transcribe → validate → save)
3. Seed extraction for 1 playbook (e.g., Madden 05 Patriots) as a proof of concept

**Acceptance**: 5-10 canonical plays extracted from at least one game.

### P8-T07 🟢 Cross-game compatibility report

**Goal**: for each play in `data/plays/`, generate a compatibility matrix showing which games can render it (within editor capability).

Output: `docs/play-game-compatibility.md` — large table.

**Acceptance**: covers all 144 plays × all measured games; generates from data, not hand-typed.

### P8-T08 🟡 Verification protocol with screenshots

**Goal**: extend the verification status. A play marked `verified` for a specific game means: a contributor recreated it in that game and it works as designed.

**Steps**:
1. Add `verified_in_games` array to play schema
2. Document the screenshot-based verification workflow
3. Build a contributor-facing tool to submit verification with proof

---

## Cross-cutting / shared tasks

These help all phases.

### CC-T01 🟡 Shared web-research helper

**Goal**: a reusable `tools/web-research/fetch.py` that the AI assistants use to consistently format their `source_notes`.

**Output**: a function that takes a URL + brief description, fetches it, extracts metadata (title, publication date), and returns a properly-formatted source_notes entry.

**Acceptance**: replaces ad-hoc `source_notes` strings across the library with consistent format.

### CC-T02 🟢 Source-citation audit

**Goal**: walk every YAML file in `data/`, flag entries with weak source_notes (no URL, no date, no description).

Output: `docs/source-citation-audit.md` — list of YAMLs needing better citations.

### CC-T03 🟡 Schema-coverage audit

**Goal**: every YAML in `data/` should validate against a schema. Find any that don't.

Acceptance: a test in `tests/test_schemas.py` that walks every dir under `data/` and reports unvalidated files.

---

## Estimated AI workload distribution

If we assume ~100 tasks total (rough breakdown):

| Tier | Count | Suitable AI | Total effort |
|------|-------|-------------|--------------|
| 🟢 HAIKU (research + YAML authoring) | ~60 tasks | Haiku | ~60-90 hours |
| 🟡 SONNET (code + integration) | ~30 tasks | Sonnet | ~40-60 hours |
| 🔴 OPUS (architecture / design judgment) | ~5-10 tasks | Opus | ~10-15 hours |

The **Haiku tasks dominate** — they're mostly Phase 5's concept-library research (35 tasks) and Phase 8's per-game profile research (30 tasks). These are perfect for parallel sub-agents because each task is fully independent.

### Recommended Haiku batch ordering

Best to dispatch in this order so dependencies resolve:

1. **First wave (Phase 5 schemas)**: P5-T01, T02, T03, T04 — design the four new concept schemas (Sonnet for these)
2. **Second wave (Phase 5 data)**: P5-T05a-h, T06a-o, T07a-e, T08a-l — 40 parallel tasks, all Haiku
3. **Third wave (Phase 6 MCP scaffolding)**: P6-T01 through T10 — Sonnet, sequential
4. **Fourth wave (Phase 8 profiles)**: P8-T03a-ad — 30 parallel tasks, all Haiku
5. **Fifth wave (Phase 7)**: P7-T01 through T05 — mostly Sonnet, T02 is Opus

### Parallel-safety notes

Phase 5 and Phase 8 data tasks are **fully parallel-safe** — each task writes to its own file, no shared state. You can dispatch 30 Haiku tasks at once and they won't collide.

Phase 6 MCP tasks should be **sequential per-MCP** (a single MCP's scaffold + tools + tests should be one task or sequenced tasks). Different MCPs in parallel is fine.

Phase 7 tasks are **mostly sequential** (algorithm before implementation before tests).

---

## Acceptance criteria for "phase done"

A phase is done when:

- All scheduled tasks pass acceptance individually
- The full test suite (`./run-tests.sh`) passes
- The schema validation pass covers every YAML in `data/`
- `docs/pending-queue.md` Done section is updated with the phase's completion date
- `plan.md` implementation status is bumped from ⚠️ to ✅
- A worked-example tool-call sequence demonstrating the phase's value is added to `examples/play-design-walkthroughs/` (creating that directory if it doesn't exist)

---

## How to dispatch a task to a Haiku/Sonnet agent

### Standard dispatch prompt

```
You are working in the blitz-command repo at /mnt/c/GitHub/madden_playgen_mcps.

Your task is <TASK_ID> from docs/phase-task-handoff.md.

REQUIRED FIRST STEP: read the "Haiku prerequisites" section at the top of
docs/phase-task-handoff.md before doing anything else. It contains
date-handling, YAML pitfalls, source-citation format, and "field doesn't
apply" rules that apply to your task.

Then:
1. Read the spec for <TASK_ID> in full
2. Read the inputs listed (schemas, reference files, etc)
3. Run pre-flight checks: do the schema files exist? does the output
   directory exist? read at least one same-type file as a style reference
4. Produce the output(s) at the paths specified
5. Verify the acceptance criterion (run the validation command exactly
   as written; report the exit code)
6. Report back with: file(s) created, any source URLs cited, any
   issues or ambiguities you encountered

Hard rules:
- Don't invent schema fields. If you think a new field is needed, REPORT IT
  and stop — don't add it.
- Don't claim verification_status: verified from web research alone.
  Use 'inferred' or 'unverified'.
- Don't leave placeholder text like "<TODO>" or "?" in the output.
  Use null + a source_notes explanation if you don't know.
- Don't paraphrase URLs — copy exactly.
- ALWAYS run the acceptance validation command before reporting done.

If you can't complete the task (missing prereq, schema gap, can't find
sources), STOP and report — don't substitute guesses.
```

### Research-task add-on prompt (append for Haiku data tasks)

```
For source citations, you MUST WebFetch at least 2 sources from these
priority-ordered candidates:

GAME RESEARCH:
  1. Wikipedia (https://en.wikipedia.org/wiki/<Game_Title_With_Underscores>)
  2. GameFAQs (https://gamefaqs.gamespot.com/<platform>/<game-slug>)
  3. Operation Sports forums (https://forums.operationsports.com/)
  4. EA Sports Madden Wiki (https://madden.fandom.com/)
  5. IGN / GameSpot reviews

CONCEPT RESEARCH (blocking schemes / run concepts / pass protections):
  1. Throw Deep Publishing (https://throwdeeppublishing.com/blogs/football-glossary/)
  2. X&O Labs (https://www.xandolabs.com/)
  3. CougCenter Air Raid playbook (https://www.cougcenter.com/)
  4. Glazier Clinics (https://www.glazierclinics.com/)
  5. AFCA Insider (https://insider.afca.com/)

PHILOSOPHY RESEARCH:
  1. Wikipedia philosophy pages (https://en.wikipedia.org/wiki/<Philosophy>_offense)
  2. Wikipedia coach pages (https://en.wikipedia.org/wiki/<Coach_Name>_(American_football_coach))
  3. Pro Football Reference team-season pages (for tendency_profile data)
  4. Coach biography articles

For the current date in source_notes entries, run: date +%Y-%m-%d
(That's a literal command — execute it and use the output, not the string
"YYYY-MM-DD").

Each source_notes entry has this exact format:
"Web validated <YYYY-MM-DD> — <Source Name> (<URL>): <one-sentence summary
of the specific claim this source confirmed>"

Examples:
  - "Web validated 2026-05-01 — Wikipedia 'Madden NFL 08' (https://en.wikipedia.org/wiki/Madden_NFL_08): release year 2007, developer EA Tiburon, custom-play support confirmed."
  - "Web validated 2026-05-01 — Throw Deep Publishing 'Power Run Concept' (https://throwdeeppublishing.com/blogs/football-glossary/the-complete-guide-to-the-power-play): confirmed Power scheme = down-block + pull BSG + lead through off-tackle."
```

### Quality-check prompt (for the dispatcher, not the worker)

When a Haiku/Sonnet returns a completed task, run this verification:

```bash
# 1. The file exists at the right path
ls <output-path>

# 2. The schema validates
.venv/bin/python -c "import json,yaml,jsonschema; jsonschema.validate(yaml.safe_load(open('<output-path>')), json.load(open('<schema-path>')))"
echo "exit code: $?"

# 3. source_notes has ≥2 entries (or 1 + an inferred-status explanation)
.venv/bin/python -c "import yaml; d=yaml.safe_load(open('<output-path>')); n=len(d.get('source_notes') or []); print(f'source_notes count: {n}')"

# 4. No literal placeholder strings
grep -E "(<TODO>|<source>|YYYY-MM-DD|\\?\\?\\?|\\?$)" <output-path> || echo "no placeholders — clean"

# 5. The full test suite still passes
./run-tests.sh
```

If any check fails, the task isn't done — send back with the failure for the worker to address.

That's the contract. Hand it off, verify, repeat.
