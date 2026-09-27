# MCP Roadmap

A multi-year arc for evolving blitz-command's MCP servers from "useful for one game, one design loop" to "the best-in-class football design + analysis platform for the PS1/PS2/PS3 era." Phases are sized by what they ship, not by month — actual cadence depends on contribution rate. Each phase declares its goal, deliverable, dependencies, and what it unblocks.

For the rolling near-term backlog see [`pending-queue.md`](pending-queue.md). This doc is the long arc.

## Vision

The blitz-command MCP suite should let any AI agent — from frontier models to small local ones — design football plays end-to-end, port them across game editor grids, and reason about them like a coordinator would. The data layer should be exhaustively complete (every formation, every reasonable concept, every era of NCAA/Madden), the authoring tools should be rich enough that an AI never has to guess, and the analysis tools should answer real coordinator questions ("what should I call on 3rd-and-7 vs cover-3 in 11 personnel?").

We're nowhere near that today. We have the spine — author/validate/render/save/mirror, plus discovery and matchup analysis. The roadmap below is what fills out the rest.

## Where we are

- **90 MCP tools** across 13 servers (play-library, formation-library, route-library, coverage, run-concept, pass-concept, blocking-scheme, pass-protection, philosophy, game-knowledge, validation, play-variant, playbook-generation)
- **144 plays / 54 formations / 18 routes / 8 concept templates / 45 game profiles**
- Authoring loop is complete: scaffold → fill → validate → render → save → mirror
- Discovery, pairwise analysis, matchup prediction, and playbook assembly: working
- One game profile (`madden-05-ps2`) partially measured; others are placeholder
- `formation-library-mcp` serves offense only; `coverage-mcp` owns all defensive formations
- `playbook-generation-mcp` owns all collection-level reasoning; `play-library-mcp` owns single-play authoring and analysis

---

## Year 1 — Complete the loop, deepen for one game

The goal of year 1 is to make the MCPs feel **complete** as a design tool for the primary target (Madden 05 PS2 + NCAA 06 PS2), with rich enough analysis that a smaller AI can actually call good plays.

### Phase 1 — Write-tool symmetry + workflow polish

**Goal**: close the asymmetry where only `save_play` exists. Make every authoring path go through the MCP.

Deliverable:
- `save_formation(formation_data, overwrite=False)`
- `save_route(route_data, overwrite=False)`
- `update_play(play_id, patch)` — JSON-patch-style incremental edits (avoids re-authoring whole YAMLs)
- `update_formation(formation_id, patch)` and `update_route(route_id, patch)`
- `manifest()` per server — returns purpose, tool list with one-liners, and 1-2 worked example tool-call sequences
- Pagination on `list_plays` / `list_formations` / `find_plays_*` (cursor-based, default 50/page)
- `list_routes()` and `get_route()` — basic route discovery (currently zero route discovery tools)

Unblocks: external contributors authoring through the MCP without dropping to file edits; smaller AIs that need bite-sized list responses.

Size: 1-2 weeks.

### Phase 2 — Concept libraries

**Goal**: make blocking schemes, run concepts, pass protections, and philosophies first-class data instead of repeating descriptions in every play file.

Deliverable:
- `data/concepts/blocking-schemes/` — each scheme as a YAML (man, zone, gap, pull, slide, max, hinge, fan, slide-half) with assignments per OL position, common variants, what they pair with
- `data/concepts/run-concepts/` — Power, Counter, IZ, OZ, Trap, Draw, Sweep, Stretch, Veer, Buck, Wham as reusable abstractions (defines blocking + read tree; plays foreign-key into them)
- `data/concepts/pass-protections/` — full slide protection, half-slide, max protect, BOSS, big-on-big with per-position rules
- `data/concepts/philosophies/` — West Coast, Air Raid, Spread Option, Power Run, Pro-Style, Veer Option, Wing-T, Run-and-Shoot, Smashmouth as named philosophies with default tendencies + canonical concepts
- New schemas for each
- Plays gain optional `concept_ref` field that foreign-keys into a concept; validator enforces resolution

Unblocks: removes ~40% of the duplication in current play files; concept-level analysis tools (Phase 5); concept MCPs (Phase 3).

Size: 4-6 weeks (data work is the bulk).

### Phase 3 — Concept MCP servers

**Goal**: each concept library gets a dedicated discovery MCP, mirroring the play-library / formation-library pattern.

Deliverable:
- `route-library-mcp` — list/get/find by category (vertical, in-breaking, out-breaking, underneath), find by `beats_coverage`, find by depth range
- `run-concept-mcp` — list/get; find concepts that fit a formation; find concepts by philosophy
- `blocking-scheme-mcp` — list/get; find schemes that fit a play
- `coverage-mcp` — list defensive coverages with their structure (zones, man assignments, weaknesses)
- `philosophy-mcp` — list philosophies with their canonical concepts and tendencies
- Cross-MCP composition: `play-library` calls into `run-concept-mcp` to enrich `get_play()` output with concept details

Unblocks: AI agents can build plays bottom-up from concepts ("give me a Counter Trey concept, applied to Wing-T") instead of starting from a free-form scaffold.

Size: 3-4 weeks.

### Phase 4 — Per-game knowledge MCP

**Goal**: encode every editor's capabilities + limits + quirks as queryable data, replacing the placeholder game profiles.

Deliverable:
- `game-knowledge-mcp` — exposes `get_game(game_id)` (full profile), `list_games()`, `compare_games(id1, id2)` (highlight capability differences), `find_games_supporting(feature)` (e.g., RPO mechanics, jet motion, wildcat)
- Verified editor profiles for the primary targets — Madden 05 PS2, NCAA 06 PS2 (full measurement protocol per `docs/game-editor-measurement-protocol.md`)
- Per-game **quirk database** — known engine bugs, AI limitations, route-tree gaps (e.g., "this game's editor has only 8 motion options, not 10")
- `validate_play(play, game_id)` — game-aware variant that flags plays exceeding any specific game's limits

Unblocks: a play designed in the universal coordinate system can be validated against a specific game's grid before saving. Critical for "will this even work in Madden 05?" questions.

Size: 2-3 weeks (coding); 4-8 weeks (measurement, blocked on user testing).

### Phase 5 — Matchup analysis depth

**Goal**: extend `predict_matchup` from best/neutral/worst into real coordinator-grade analysis.

Deliverable:
- `predict_matchup` v2 returns: rating, rationale, **expected yards range** (heuristic from play type + matchup), best read **with route-by-route open-window estimates**, worst case (TFL / sack risk by play type), exploit hints
- `find_play_for_situation(down, distance, formation_constraint=None, defense_id, philosophy=None)` — multi-MCP join: filter by situational tags + matchup rating + game capability
- `evaluate_playbook(playbook_ids, defense_library)` — given N plays + M defenses, compute coverage matrix (which plays beat which defenses, which defenses beat which plays)
- `find_complementary_defense(play_id)` — for AI defensive coordinators: what defense breaks this play
- `analyze_play_against_all_defenses(play_id)` — full matchup row for one play

Unblocks: the AI becomes a real coordinator companion, not just a designer. "What should I call here?" becomes a one-call MCP question.

Size: 3-4 weeks.

### Phase 6 — Rendering depth

**Goal**: visualizations that match what coaches and game editors actually need.

Deliverable:
- `render_play` motion arrows (curved dashed lines for pre-snap motion)
- Option-route branching (snag/stick/choice routes show all branches with priority labels)
- Animation mode (`render_play(..., animate=True)` returns SVG with `<animate>` for route progression — preview-able in browser)
- `render_defense(defense_id, game_id, play_id=None)` — defense-only rendering, no `play_id` required (closes the "MCP can't render defense alone" gap)
- `render_playbook(play_ids, game_id, layout='grid')` — multi-play grid render for a full playbook on one canvas
- `render_matchup(play_id, defense_id, game_id)` — overlays the matchup analysis on the play diagram (highlights open windows, threatened reads)
- Configurable color schemes (high-contrast for accessibility; print-friendly black-on-white)

Unblocks: visual coaching aids, exportable playbook documents, AI-generated training material.

Size: 3-4 weeks.

---

## Year 2 — Scale across games, deepen the data

Year 2 expands the library across more games and adds playbook-level abstractions. By the end, the MCP should support 15+ games and reason about multi-play playbooks as first-class objects.

### ✅ Phase 6.5 — Close the concept MCP gap

**Goal**: the 16 pass-concept files in `data/concepts/pass-concepts/` have no dedicated discovery MCP. An agent designing a pass play has to infer pass concepts from play tags or philosophy refs — there's no first-class query surface.

Deliverable:
- `pass-concept-mcp` — mirrors `run-concept-mcp` exactly: `list_pass_concepts`, `get_pass_concept`, `find_concepts_by_category`, `find_concepts_best_vs_coverage`, `find_concepts_pairs_with`, `manifest()`
- Schema: `schemas/pass-concept.schema.json` already exists
- Data: `data/concepts/pass-concepts/` already has 16 files
- Categories: timing-route, area-read, option-route, horizontal-stretch, vertical-stretch, shot-play, screen-game, quick-game, motion-based, etc.

Unblocks: agents can browse pass concepts the same way they browse run concepts; plays can suggest concepts bottom-up ("which pass concept fits mesh?") rather than top-down only.

Size: 1-2 days (data exists, pattern is established).

### ✅ Phase 6.6 — Coordinate translation in game-knowledge-mcp

**Goal**: the universal → game-grid translation currently lives only inside `draw.py` and `tools/coordinate-translator/`. An agent that wants to know "what cell does x=10, y=5 map to in madden-05-ps2?" must render an SVG to get the answer. That's the wrong tool for the job.

Deliverable:
- `translate_position(game_id, x_yd, y_yd)` added to `game-knowledge-mcp` — converts a universal-coordinate point to that game's editor grid cell, using the profile's scale and origin
- `translate_formation(game_id, formation_id)` — returns all 11 player positions translated to editor cells for a given game
- `translate_play(game_id, play_id)` — returns per-assignment cell sequences (the data that `export_play_instructions` currently derives internally via draw.py)

Unblocks: agents can do coordinate-aware play design without rendering; `export_play_instructions` in play-library-mcp can delegate translation to game-knowledge-mcp instead of importing draw.py.

Dependencies: `game-knowledge-mcp` (Phase 4 — done), `draw.py` profile loader (extract the pure math, no SVG dependency).

Size: 1-2 weeks.

### Phase 7 — PS2-era game expansion

**Goal**: every PS2-era NCAA and Madden has a verified editor profile with quirks documented.

Deliverable:
- Verified editor profiles for: Madden 02, 03, 04, 06-11; NCAA 02-11 (all PS2)
- Per-title quirk database (engine bugs, AI behaviors, missing features)
- Game-specific play-translation warnings — when porting a Madden-08 play to NCAA-04, flag the differences
- `find_game_with_capability(feature)` queries (e.g., "which games support the option toss?")

Unblocks: cross-game playbook portability; AI agents can recommend the best target game for a given playbook style.

Size: 6-12 weeks (mostly user-blocked on measurement).

### Phase 8 — PS1 + PS3 era support

**Goal**: extend the architecture beyond PS2 — the bookends in the project's stated scope.

Deliverable:
- PS1 game profiles: Madden 96-01, NCAA 98-01 (much smaller editor grids; significant capability differences)
- PS3 game profiles: Madden 07-13, NCAA 07-14 (larger grids, more features)
- Era-aware concept filtering ("only suggest plays that work in 1990s Madden")
- PS1 fallback heuristics — for plays that overflow the small grid, suggest scheme adaptations

Unblocks: complete coverage of the project's stated scope (PS1/PS2/PS3 NCAA + Madden).

Size: 6-12 weeks (measurement + per-era schema extensions).

### Phase 9 — Playbook as a first-class object

**Goal**: playbooks aren't just lists of play_ids — they have structure, balance, and identity.

Deliverable:
- `playbook.schema.json` — id, name, philosophy, formations[], plays[] (typically 80-150), situation_tags
- `data/playbooks/` library — seed with 10-15 named playbooks (Air Raid Base, Spread Power, West Coast, Pro-Style, Wing-T HS, etc.)
- `playbook-library-mcp` — list/get/find_by_philosophy/find_by_concept/find_by_formation
- `save_playbook(playbook_data)` and `validate_playbook(playbook_data)` — concept lints (does this playbook have a goal-line package? a 2-minute drill? a counter to its base?)
- `compare_playbooks(playbook_id1, playbook_id2)` — what does each have that the other doesn't?
- `assemble_playbook(philosophy, formation_constraints, target_size, game_id=None)` — generate a balanced playbook from the library

Unblocks: end-users (and AIs) can think in playbooks instead of plays. "Build me a 100-play Spread Option playbook for NCAA 06" becomes a single MCP call.

Size: 4-6 weeks.

### Phase 10 — Game-canonical play extraction

**Goal**: distinguish generic-football plays from plays extracted from a specific game's built-in playbook (per `docs/play-data-provenance.md`).

Deliverable:
- `source_provenance` schema additions — `source_game`, `source_playbook`, `source_play_call`, `source_references[]`
- Tooling for screenshot-based extraction (OCR + manual review) of built-in plays from PS2-era titles
- Seed extraction for canonical playbooks from 3-5 games (e.g., Madden 05 Patriots playbook, NCAA 06 USC playbook)
- `find_canonical_plays(game_id, playbook_name=None)` — query plays that are documented as in-game canonical
- Provenance-aware suggestions: when a user asks for a play, the MCP can offer "this is the canonical Madden 05 version" vs "this is the generic football concept"

Unblocks: nostalgia / authenticity use cases ("recreate the Patriots playbook from Madden 05") + a verifiable golden truth dataset for evaluating AI-designed plays.

Size: 8-16 weeks (manual extraction is slow).

### Phase 11 — AI evaluation harness

**Goal**: measure how well different LLMs do on the design loop, so improvements are data-driven.

Deliverable:
- `tests/eval/` — evaluation suite that runs the same design tasks against multiple models (Sonnet, Haiku, GPT-4o-mini, Gemini Flash, etc.) and scores their outputs
- Eval tasks: "design a PA pass for singleback-trio that beats cover-3", "build a 7-play playbook for west-coast philosophy", "predict the matchup for play X vs defense Y and explain"
- Scoring: schema validity, concept accuracy (vs golden answers), efficiency (tool calls used), latency
- Regression tests for MCP improvements — when a tool changes, re-run the eval to confirm it doesn't degrade smaller-model quality
- Public eval results — benchmark scores per model

Unblocks: confident iteration on the MCP — every change is measured against actual model behavior, not assumed to help.

Size: 3-4 weeks (infra) + ongoing.

### Phase 12 — Cross-game translation MCPs

**Goal**: port a play designed for one game's editor into another, accounting for quirks.

Deliverable:
- `coordinate-translator-mcp` (extracted from current `tools/coordinate-translator/`) — translate a play from universal coords into game-X cells
- `port_play(play_id, source_game, target_game)` — full port with translation report (what changed, what couldn't be preserved, what alternative routes were substituted)
- `auto_adapt_play(play_id, target_game)` — when target game lacks a feature (e.g., no jet motion), suggest the closest-equivalent play from the library
- Translation cache — playbooks pre-translated to all supported games

Unblocks: a play designed for Madden 05 can show up as a port-ready play for Madden 03 or NCAA 06 with one MCP call.

Size: 3-4 weeks.

---

## Year 3 — Sophistication, novelty, exports

Year 3 is about the MCP doing things humans can't easily do: optimizing playbooks against full defense libraries, generating play families, exporting professional-looking artifacts.

### Phase 13 — Play-family generator

**Goal**: given a base play, automatically derive 4-7 complementary plays that share its pre-snap look but attack different things.

Deliverable:
- `generate_play_family(base_play_id, family_size=5)` — returns suggested companion plays (run + counter + PA + screen + bootleg, or analogous patterns) generated procedurally from the base
- Each generated play is a full saved play (validates clean, mirrors generated)
- Family-aware playbook construction — when assembling a playbook, pull whole families instead of individual plays

Unblocks: rapid playbook expansion — one base call generates a coherent 5-play unit instead of one play.

Size: 4-6 weeks.

### Phase 14 — Playbook optimization

**Goal**: solver-based playbook construction under constraints — "give me the optimal 80-play book for 11 personnel that beats the typical NCAA 06 defensive playbook."

Deliverable:
- `playbook-optimizer-mcp` — takes constraints (philosophy, personnel, target size, game capability budget, must-include plays, must-exclude formations) and returns a Pareto-optimal playbook
- Coverage objective: maximize matchup-rating sum across a defense library, subject to balance constraints (X% run, Y% pass, Z% PA, etc.)
- Diversity objective: maximize disguise_score across formation groupings
- Cost objective: minimize editor-grid usage when game-targeted
- Multi-objective tradeoff explorer ("show me 3 playbooks: most balanced, most explosive, most reliable")

Unblocks: AI coordinators can ask "build me the perfect playbook" and get a defensible answer with rationale.

Size: 6-10 weeks (optimization heuristics are non-trivial).

### Phase 15 — Visual exports

**Goal**: generate human-coach-grade output artifacts.

Deliverable:
- `export_playbook(playbook_id, format='pdf', game_id=None)` — full playbook as a PDF, one page per play with diagram + read tree + key blocks
- `export_call_sheet(playbook_id, situation_groupings)` — coordinator's call sheet (situation → recommended plays)
- `export_animation(play_id, format='mp4'|'gif', game_id=None)` — animated play as a video file
- `export_play_card(play_id, game_id, format='png')` — single-play "card" image for printing or screen-share
- Theming: dark / light / print-friendly / accessibility-high-contrast

Unblocks: real-world utility — a coach (or fan) can actually print a playbook and use it.

Size: 4-6 weeks.

### Phase 16 — Community contribution pipeline

**Goal**: let external users contribute plays, formations, and concepts safely.

Deliverable:
- Contribution submission API — POST a candidate play, get a validation report
- Auto-PR workflow — validated submissions auto-open a GitHub PR with the new YAML + auto-generated mirrors + test coverage
- Attribution tracking — `contributed_by` field on every play / formation / concept
- Trust tiers — different validation strictness for first-time vs trusted contributors
- Moderation queue — contributions visible in a queue, contributors can review each other
- License clarification — explicit terms for contributed content

Unblocks: library scales beyond the maintainer's bandwidth.

Size: 3-4 weeks (pipeline) + ongoing moderation.

### Phase 17 — Real-time game companion

**Goal**: turn the MCPs into a live in-game companion (not in-engine — alongside it).

Deliverable:
- `live-game-mcp` — stateful (per session): tracks down/distance, score, time remaining, current playbook, recently called plays
- `recommend_call(game_state)` — "given this state, what should I call?" returns ranked plays with reasoning
- `track_play_outcome(play_id, yards_gained, result)` — records actual results, updates session-level success-rate tracking
- Tendency tracker — flags when the user is becoming predictable ("you've called 5 inside zones in a row")
- Defensive-tendency observer — when user reports defensive looks, build a session-specific defense profile

Unblocks: the MCP isn't just a design tool — it's a play-time companion. Pairs nicely with streaming/voice interfaces.

Size: 4-6 weeks.

### Phase 18 — Defensive coordinator companion

**Goal**: symmetric to the offensive design tools — let an AI build defensive playbooks and game plans.

Deliverable:
- `defensive-playbook-library-mcp` — defensive playbooks as first-class objects (mirroring offensive playbook MCP)
- `assemble_defensive_game_plan(opponent_offensive_playbook_id, target_size)` — generate a defensive call sheet that counters a specific offensive playbook
- `predict_call(offensive_tendency, situation)` — given offensive tendency data, predict the most likely call (defensive AI's job)
- `find_blitz_for_protection(protection_scheme)` — what blitzes break a specific pass protection
- `generate_defensive_family(base_defense_id, family_size=3)` — counter-call families (base + blitz + coverage rotation)

Unblocks: the entire defensive side becomes as rich as the offensive side. Two-AI matchup simulation becomes possible.

Size: 8-12 weeks (depends heavily on Phases 9-12).

---

## Year 4+ — Stretch / exploratory

Phases here are speculative — they're worth doing only if the prior phases stick the landing and there's appetite to keep going.

### Phase 19 — ML-assisted novel play design

**Goal**: train a model on the library to generate genuinely novel plays that are still football-correct.

Deliverable:
- Training pipeline — fine-tune a small model on (formation + situation → play) examples from the library
- `suggest_novel_play(formation_id, constraint, philosophy)` — returns 3-5 generated plays that don't already exist in the library
- Quality gates — generated plays go through standard validate_play + a novelty check (not duplicating existing plays)
- Human-in-the-loop curation — promising generated plays get flagged for human review before joining the library

Unblocks: library expansion beyond what humans manually author. Risky — generative plays may be subtly wrong in ways humans don't catch.

Size: 12-20 weeks (research-grade work).

### Phase 20 — Multi-sport architecture

**Goal**: prove the universal-coordinate / per-game-translation pattern generalizes.

Deliverable:
- Basketball variant: `data/sports/basketball/` with formations, plays, defensive systems
- Sport-aware routing in MCPs — `play-library-mcp` learns to filter by sport
- Hockey or soccer as a third validation case

Unblocks: nothing within the football scope. Worth doing only as architectural validation or as a side project.

Size: 12-16 weeks per additional sport.

### Phase 21 — Live broadcast / scouting tools

**Goal**: tools for analyzing live football (NFL games on TV, college games, high school film).

Deliverable:
- `analyze_play_film(formation_screenshot, play_outcome)` — given a still + outcome, identify the formation and best-fit play in our library
- Tendency aggregation across film (when 100 plays from one team are loaded)
- Opposing-team scouting reports

Unblocks: real-world coaching / analysis use cases entirely outside the original "design plays for old games" scope.

Size: depends entirely on integration scope.

---

## Cross-cutting concerns (every phase)

These items deserve attention throughout, not as separate phases:

- **Performance**: every MCP tool should respond in <100ms for cached calls. Watch p95 latencies as the library grows.
- **Test coverage**: each new tool needs unit tests + at least one integration test. The eval harness from Phase 11 should be extended for every new tool.
- **Docs**: every tool needs a docstring with worked examples. `using-the-mcps.md` stays current. Per-MCP READMEs stay current.
- **Backwards compatibility**: tools added in early phases shouldn't get incompatible signatures later. Deprecate explicitly, never silently remove.
- **AI onboarding**: `examples/play-design-walkthroughs/` should grow with each phase — concrete tool-call sequences for every new capability.
- **Provenance**: every authored play / formation / concept records who/what/when/why authored it. Critical once external contributions land (Phase 16).

## Phasing rationale

The ordering reflects three principles:

1. **Build the spine before scaling.** Year 1 finishes the design loop and concept libraries before year 2 expands across games — it's wasteful to extend a half-finished tool to 15 game profiles.
2. **Capture provenance before generation.** Phase 10 (canonical extraction) lands before Phase 19 (ML novel generation) so we have a golden truth dataset for evaluation.
3. **Optimize after measuring.** Phase 11 (eval harness) lands mid-year-2 so all later phases can be measured against actual model behavior instead of assumed benefits.

## Adjusting this doc

The roadmap is a living document. As phases complete, mark them `## Done` (with date) at the bottom. As new ideas surface, slot them into the appropriate year — earlier years get priority over later ones unless explicitly re-prioritized. Don't shrink or skip phases without an explicit note about what changed.

---

## Done

(Move completed phases here with date.)

(Pre-roadmap: 17 MCP tools live across 2 servers, author/validate/render/save/mirror loop complete with 8 concept templates and 56 tests passing — see `pending-queue.md` Done section for the granular changelog from the build-up.)
