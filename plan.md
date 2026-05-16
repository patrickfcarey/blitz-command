# Football Playcraft MCP Repo Plan

> **This document is the original spec** (Phase 1-8 design). For the live arc going forward see [`docs/roadmap.md`](docs/roadmap.md). For the rolling near-term backlog see [`docs/pending-queue.md`](docs/pending-queue.md). The status block below summarizes what's actually implemented vs planned.

## Implementation status (last refresh: 2026-05-01)

**What's live:**

- **12 MCP servers, 78 tools combined** (exceeds the 9 originally planned):
  - `play-library-mcp` — 17 tools: full discovery, authoring, analysis, export, and `manifest()`. All `list_*` tools paginated (cursor/limit).
  - `formation-library-mcp` — 5 tools: `list_formations`, `get_formation`, `find_formations_by_tag`, `find_formations_by_concept`, `manifest()`. Paginated.
  - `route-library-mcp` — 6 tools: `list_routes`, `get_route`, `find_routes_by_category`, `find_routes_by_coverage`, `find_routes_by_depth`, `manifest()`. Paginated.
  - `coverage-mcp` — 6 tools: `list_coverages`, `get_coverage`, `find_coverage_by_shell`, `find_coverage_by_front`, `find_coverage_vulnerable_to`, `manifest()`. Paginated.
  - `run-concept-mcp` — 6 tools: `list_run_concepts`, `get_run_concept`, `find_run_concepts_by_category`, `find_run_concepts_by_aim_point`, `find_run_concepts_pairs_with`, `manifest()`. Paginated.
  - `blocking-scheme-mcp` — 6 tools: `list_blocking_schemes`, `get_blocking_scheme`, `find_schemes_by_category`, `find_schemes_that_defeat`, `find_schemes_vulnerable_to`, `manifest()`. Paginated.
  - `pass-protection-mcp` — 5 tools: `list_pass_protections`, `get_pass_protection`, `find_protections_by_type`, `find_protections_vulnerable_to`, `manifest()`. Paginated.
  - `philosophy-mcp` — 6 tools: `list_philosophies`, `get_philosophy`, `find_philosophies_by_era`, `find_philosophies_by_originator`, `find_philosophies_by_tendency`, `manifest()`. Paginated.
  - `game-knowledge-mcp` — 6 tools: `list_games`, `get_game`, `compare_games`, `find_games_supporting`, `find_games_by_era`, `manifest()`. Paginated.
  - `validation-mcp` — 7 tools: `validate_play`, `validate_formation`, `validate_route`, `validate_concept`, `validate_game_profile`, `lint_play`, `manifest()`.
  - `play-variant-mcp` — 4 tools: `mirror_play_variant`, `flip_strength`, `generate_play_family_stub`, `manifest()`.
  - `playbook-generation-mcp` — 4 tools: `assemble_playbook_simple`, `list_available_formations`, `list_available_philosophies`, `manifest()`.
- **144 plays / 54 formations / 18 routes / 8 concept templates** in the data library
- **Concept libraries** as first-class data: `data/concepts/run-concepts/`, `data/concepts/blocking-schemes/`, `data/concepts/pass-protections/`, `data/concepts/philosophies/` — all with schemas; plays foreign-key into them via `run_concept_ref`, `pass_concept_ref`, `pass_protection_ref`, `philosophy_ref`
- **45 game profiles** spanning PS1, PS2, and PS3 era Madden + NCAA — Madden 05 PS2 is the most measured; the rest are placeholder pending user measurement
- **Defensive side**: 9 defensive formations with fronts + coverage shells + per-defender responsibilities (`vulnerable_to`/`best_against` arrays)
- **Drawing tool**: green field, NFL/NCAA hash marks, defensive coverage rendering (zones / man / rush / spy), 4 visibility modes, short/long field, cell-snap + BFS overlap avoidance
- **Schemas**: `play.schema.json` (with concept FK fields + `verified_in_games`), `formation.schema.json`, `route.schema.json`, `blocking-scheme.schema.json`, `run-concept.schema.json`, `pass-protection.schema.json`, `pass-concept.schema.json`, `philosophy.schema.json`, `game.schema.json`, `play-family.schema.json`, `canonical-play-extraction.schema.json`
- **Tests**: 68 in `tests/` covering schemas, drawing modes, every MCP tool, concept FK validation, and pagination coverage

**Completed planned work (from this doc):**
- ✅ Phase 1 — Repo Skeleton
- ✅ Phase 2 — Universal Football Coordinate System
- ⚠️ Phase 3 — Game Knowledge Database (45 game profiles exist; Madden 05 PS2 is partially measured, rest are placeholder — blocked on user measurement)
- ✅ Phase 4 — Formation Library (54 formations, far beyond the original 12)
- ✅ Phase 5 — Route library (18 routes), blocking-scheme, run-concept, pass-protection, and philosophy libraries all shipped as first-class data with schemas
- ✅ Phase 6 — All 12 MCP servers shipped with full tool sets, `manifest()` on every server, cursor-based pagination on all `list_*` tools
- ⚠️ Phase 7 — Play Family Generator: `generate_play_family_stub` stub shipped (returns scaffold); full procedural generator not built. Manually-authored families exist.
- ⚠️ Phase 8 — Game-Specific Export: `export_play_instructions` (markdown) shipped; per-game profiles other than Madden 05 are still placeholder so cell coordinates are only verified for that title

**Most-recent additions** (chronological — full changelog in `docs/pending-queue.md` Done section):
- All 10 new MCP servers (route-library, coverage, run-concept, blocking-scheme, pass-protection, philosophy, game-knowledge, validation, play-variant, playbook-generation)
- `manifest()` tool on every MCP server — purpose, tool list, worked examples
- Cursor-based pagination on all `list_*` tools across all 12 MCPs (`{items, next_cursor}`)
- Concept FK fields on `play.schema.json` (`run_concept_ref`, `pass_concept_ref`, `pass_protection_ref`, `philosophy_ref`, `verified_in_games`)
- `play-family.schema.json` and `canonical-play-extraction.schema.json` — new schemas
- `tools/migrate-add-concept-refs/` — inference migration tool, 88% run / 80% pass coverage across 144 plays
- `tools/export-instructions/formatters.py` — per-game export formatter (Madden 05/10 PS2, Madden 10 PS3, NCAA 06 PS2)
- `validation-mcp` concept FK cross-reference checks + route-name cross-reference checks

## Goal

Create a repo containing multiple MCP servers, tools, datasets, schemas, and documentation to help AI agents like Codex, Claude, or ChatGPT design custom football formations and plays for NCAA and Madden games across PS1, PS2, and PS3 eras.

The system should help an AI agent understand:

- Differences between NCAA and Madden games
- Differences between PS1, PS2, and PS3 football engines/editors
- In-game formation/play editor grid systems
- Real football field measurements and how to translate them to game-grid coordinates
- Classical football formations
- Blocking schemes
- Passing concepts
- Handoffs and run fits
- Route trees
- Offensive philosophies
- How one base play can branch into 2–5 related plays
- How to build coherent mini-playbooks

---

## Repo Name

**blitz-command**

Names considered:

- football-command
- playbook-command
- gridiron-command
- formation-lab
- audible-lab
- football-mcp-lab
- audible-ops
- field-command
- trench-command
- formation-ops

---

## Core Architecture

Use multiple MCPs with separate responsibilities.

Do not make one giant MCP that knows everything.

The repo should be split into:

1. Knowledge MCPs
2. Translation MCPs
3. Design MCPs
4. Validation MCPs
5. Generation MCPs

---

## Top-Level Folder Structure

```
blitz-command/
├── README.md
├── plan.md
├── docs/
├── mcps/
├── data/
├── schemas/
├── tools/
├── examples/
├── tests/
├── playbooks/
├── formations/
├── concepts/
├── games/
└── prompts/
```

---

## Folder Purposes

### docs/

Human-readable documentation.

Examples:

```
docs/
├── architecture.md
├── football-theory.md
├── game-editor-notes.md
├── coordinate-systems.md
├── mcp-design-rules.md
├── play-design-rules.md
└── ai-agent-guidelines.md
```

---

### mcps/

Each MCP server lives here.

Recommended MCPs:

```
mcps/
├── game-knowledge-mcp/
├── coordinate-translation-mcp/
├── formation-library-mcp/
├── play-concept-mcp/
├── route-tree-mcp/
├── blocking-scheme-mcp/
├── play-variant-mcp/
├── validation-mcp/
└── playbook-generation-mcp/
```

---

## MCP Responsibilities

### 1. game-knowledge-mcp

Purpose:

Know the differences between NCAA and Madden games across PS1, PS2, and PS3.

It should track:

- Game title
- Year
- Platform
- Editor limitations
- Formation editor support
- Custom play editor support
- Roster limitations
- Playbook limitations
- AI behavior quirks
- Animation/engine limitations
- What can and cannot be edited

Example questions it should answer:

- "What can NCAA 06 PS2 custom plays do that Madden 04 PS2 cannot?"
- "Does this game support custom formations?"
- "How many route options can I assign?"
- "What are the editor grid limitations?"

---

### 2. coordinate-translation-mcp

Purpose:

Translate between real football measurements and in-game editor grids.

It should understand:

- Football field dimensions
- Yard lines
- Hash marks
- Sidelines
- Line of scrimmage
- Backfield depth
- Receiver splits
- Offensive line spacing
- Defensive alignment landmarks
- Game-specific grid coordinates

It should support conversions like:

- Real yards to game-grid units
- Game-grid units to real yards
- Formation depth to editor coordinates
- Receiver split to editor coordinates
- Route break depth to grid location

This is one of the most important MCPs.

---

### 3. formation-library-mcp

Purpose:

Store and retrieve real-world football formations.

It should know:

- I-Formation
- Strong I
- Weak I
- Ace
- Singleback
- Shotgun
- Pistol
- Split Backs
- Wishbone
- Flexbone
- Wing-T
- Trips
- Bunch
- Empty
- Goal Line
- Nickel
- Dime
- 3-4
- 4-3
- 4-2-5
- 3-3-5

Each formation should include:

- Personnel
- Player alignment
- Strength
- Common uses
- Run concepts
- Pass concepts
- Constraint plays
- Game compatibility notes

---

### 4. play-concept-mcp

Purpose:

Understand offensive and defensive football concepts.

Offensive examples:

- Inside zone
- Outside zone
- Power
- Counter
- Trap
- Iso
- Toss
- Dive
- Draw
- Play action
- Mesh
- Slants
- Smash
- Flood
- Four Verticals
- Stick
- Curl Flat
- Levels
- Y-Cross
- RPO-style concepts where possible

Defensive examples:

- Cover 0
- Cover 1
- Cover 2
- Cover 3
- Cover 4
- Tampa 2
- Man blitz
- Zone blitz
- Spy
- Contain
- Gap control
- Run fit

---

### 5. route-tree-mcp

Purpose:

Understand route running and passing trees.

It should know:

- Flat
- Slant
- Hitch
- Curl
- Comeback
- Out
- Dig
- Post
- Corner
- Streak
- Fade
- Wheel
- Angle
- Texas
- Seam
- Drag
- Shallow cross
- Deep cross
- Choice route, if supported by the game

It should also track:

- Break depth
- Timing
- Spacing
- Best defensive coverage to attack
- Game editor limitations

---

### 6. blocking-scheme-mcp

Purpose:

Understand blocking assignments.

It should know:

- Man blocking
- Zone blocking
- Gap blocking
- Pulling guards
- Double teams
- Lead blocks
- Fullback iso blocks
- Pass protection
- Slide protection
- Max protect
- Screen blocking
- Option blocking
- Read-option approximations

It should help answer:

- "How should this play be blocked?"
- "Can this blocking scheme be represented in Madden 2004?"
- "What is the closest possible approximation?"

---

### 7. play-variant-mcp

Purpose:

Take one play and create related plays.

Example:

Base play:

- I-Form Power O

Variants:

- Power O
- Power O Play Action
- Power O Counter
- Power O Toss
- Power O Bootleg
- Power O Screen

It should create families of plays that look similar pre-snap but attack different areas.

This MCP should understand:

- Constraint plays
- Complementary plays
- Formation tags
- Motion tags
- Run/pass conflict
- Same-look play design
- How to build 2–5 related plays from one idea

---

### 8. validation-mcp

Purpose:

Check whether a play is physically, strategically, and game-editor valid.

It should validate:

- Player spacing
- Illegal formations
- Overlapping routes
- Impossible handoffs
- Bad blocking logic
- Broken timing
- Game editor limitations
- Whether a concept fits the selected game

Example validation output:

- Valid
- Valid with warnings
- Invalid
- Needs game-specific compromise

---

### 9. playbook-generation-mcp

Purpose:

Generate coherent playbooks.

It should organize:

- Formations
- Base plays
- Constraint plays
- Short-yardage plays
- Red-zone plays
- Third-down plays
- Goal-line plays
- Two-minute offense
- Run-heavy packages
- Pass-heavy packages
- Option-style packages
- West Coast packages
- Spread packages
- Power run packages

---

## Data Folder

```
data/
├── games/
├── formations/
├── plays/
├── routes/
├── blocking/
├── measurements/
├── editor-grids/
└── philosophies/
```

Use JSON or YAML for structured data.

Example:

```
data/games/ncaa-06-ps2.yaml
data/games/madden-04-ps2.yaml
data/formations/i-formation.yaml
data/routes/slant.yaml
data/concepts/inside-zone.yaml
```

---

## Schema Folder

```
schemas/
├── game.schema.json
├── formation.schema.json
├── play.schema.json
├── route.schema.json
├── blocking.schema.json
├── coordinate-map.schema.json
└── playbook.schema.json
```

Every data file should validate against a schema.

This is important because AI agents will otherwise create messy inconsistent files.

---

## Example Formation Schema

A formation should include:

- name
- side
- personnel
- platform compatibility
- player alignments
- real-world measurements
- game-grid coordinates
- notes
- common plays
- weaknesses
- tags

---

## Example Play Schema

A play should include:

- play name
- formation
- personnel
- game target
- play type
- motions (each tagged `mandatory` or `optional`, with the player's pre-snap path)
- assignments
- routes
- blocking rules
- ball carrier
- primary read
- secondary read
- timing
- compatible variants
- validation status
- tags (level / era / philosophy — e.g. `high-school`, `college`, `nfl`, `west-coast`, `air-raid`, `modern`, `throwback`)

---

## Coordinate System Design

The repo should define a universal internal coordinate system.

Recommended:

- X axis: horizontal field width
- Y axis: depth from line of scrimmage
- Origin: center of the ball at the line of scrimmage
- Positive Y: offense moving forward
- Negative Y: offensive backfield
- X negative: left side of offense
- X positive: right side of offense

Example:

Center:
x: 0
y: 0

Quarterback under center:
x: 0
y: -1

Halfback in I-Formation:
x: 0
y: -7

Split end wide left:
x: -18
y: 0

Flanker right:
x: 15
y: -1

Then each game/editor gets a translation profile.

---

## Game Translation Profiles

Each game should have a coordinate translation profile.

Example:

games/ncaa-06-ps2/editor-grid.yaml

Should define:

- grid width
- grid height
- origin point
- scale factor
- max route depth
- max player split
- allowed motion
- route editor limits
- formation editor limits
- known quirks

---

## Play Design Philosophy

The system should not generate random plays.

Every play should belong to a family.

Example family:

Formation:
I-Form Normal

Base identity:
Power run

Play family:

1. Power O
2. Counter
3. Iso
4. Play Action Cross
5. Bootleg Flat
6. HB Screen

The AI should explain:

- What the defense sees pre-snap
- What area of the field is attacked
- Why the play complements the others
- What user skill/timing is required
- Whether the game engine can actually support it

---

## Offensive Philosophy Modules

```
concepts/philosophies/
├── west-coast.yaml
├── air-raid.yaml
├── spread-option.yaml
├── power-run.yaml
├── pro-style.yaml
├── veer-option.yaml
├── wing-t.yaml
├── run-and-shoot.yaml
└── smashmouth.yaml
```

Each philosophy should include:

- Core formations
- Core run plays
- Core pass plays
- Constraint plays
- Preferred personnel
- Strengths
- Weaknesses
- Best matching games
- Editor limitations

---

## Testing Strategy

Every MCP should have tests.

```
tests/
├── coordinate-tests/
├── formation-tests/
├── play-validation-tests/
├── game-compatibility-tests/
└── generation-tests/
```

Example tests:

- Convert 5 real yards to NCAA 06 PS2 grid units
- Validate I-Formation player spacing
- Generate 5 variants from Power O
- Reject impossible route overlap
- Confirm Madden 2004 PS2 limitation notes are applied
- Confirm PS1 games are treated as more limited than PS2/PS3 games

---

## AI Agent Rules

AI agents working in this repo must follow these rules:

1. Do not invent game-specific editor capabilities without marking them as unverified.
2. Every game-specific claim needs a source note or testing note.
3. Prefer structured YAML/JSON over prose when encoding knowledge.
4. Keep real football knowledge separate from game-specific limitations.
5. Every generated play must include validation.
6. Every play should belong to a family.
7. Every formation should support coordinate translation.
8. Every MCP should have a narrow responsibility.
9. Never overwrite existing data without preserving notes.
10. Add uncertainty fields where information is incomplete.

---

## Implementation Phases

### Phase 1: Repo Skeleton

Create:

- README.md
- plan.md
- docs/
- mcps/
- data/
- schemas/
- tools/
- tests/
- examples/

No advanced logic yet.

---

### Phase 2: Universal Football Coordinate System

Build:

- coordinate schema
- field measurement docs
- universal coordinate model
- sample formation coordinates
- basic coordinate translator

This is the foundation.

---

### Phase 3: Game Knowledge Database

Add structured files for:

- Madden PS1 games
- Madden PS2 games
- Madden PS3 games
- NCAA PS1 games
- NCAA PS2 games
- NCAA PS3 games

Start with conservative fields:

- title
- platform
- year
- custom play support
- custom formation support
- known limitations
- source notes
- verification status

---

### Phase 4: Formation Library

Add core formations:

- I-Form
- Strong I
- Weak I
- Singleback
- Shotgun
- Goal Line
- Split Backs
- Wishbone
- Flexbone
- Trips
- Bunch
- Empty

Each should use the universal coordinate system.

---

### Phase 5: Route and Blocking Libraries

Add:

- Route tree
- Route timing
- Route spacing
- Blocking schemes
- Run concepts
- Pass protection concepts

---

### Phase 6: MCP Tooling

Implement MCP servers one at a time:

1. coordinate-translation-mcp
2. game-knowledge-mcp
3. formation-library-mcp
4. play-concept-mcp
5. validation-mcp
6. play-variant-mcp
7. playbook-generation-mcp

Do not build all MCPs at once.

---

### Phase 7: Play Family Generator

Build a tool that takes:

- formation
- base play
- target game
- offensive philosophy
- number of variants

And returns:

- base play
- related plays
- why they fit together
- editor feasibility
- validation warnings

---

### Phase 8: Game-Specific Export

Eventually support exporting plays into human-readable instructions for each game.

Example:

- NCAA 06 PS2 editor instructions
- Madden 04 PS2 editor instructions
- Madden 12 PS3 editor instructions

The first version should not try to automate game files.

Start with readable manual-entry guides.

---

## Recommended First MVP

The first useful MVP should support only:

- NCAA 06 PS2
- Madden 04 PS2
- Universal coordinate system
- I-Formation
- Shotgun Trips
- 10 common routes
- 5 run concepts
- 5 pass concepts
- Play family generation
- Manual-entry editor instructions

Do not start with every game.

Start narrow, then expand.

---

## MVP Example Prompt

"Create a 6-play I-Formation power run family for NCAA 06 PS2. Include real football spacing, in-game editor grid estimates, blocking assignments, routes, and validation warnings."

Expected output:

1. Power O
2. Counter
3. Iso
4. Toss
5. Play Action Cross
6. Bootleg Flat

Each play should include:

- Formation
- Personnel
- Assignments
- Grid placement
- Real-world intent
- Game editor compromise
- Validation result

---

## Long-Term Goal

The final system should act like a football play-design lab.

It should let an AI agent:

1. Pick a game
2. Pick a football philosophy
3. Pick a formation
4. Generate a play family
5. Translate it to that game's editor grid
6. Validate whether the play is realistic and game-compatible
7. Produce manual-entry instructions
8. Build a full custom playbook

---

## Design Principle

Separate football truth from game truth.

Real football knowledge should live in reusable concept files.

Game-specific editor limits should live in game profiles.

Coordinate translation should bridge the two.

This keeps the system useful even when new games are added later.
