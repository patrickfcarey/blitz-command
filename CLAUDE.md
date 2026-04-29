# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository state

This repository is **pre-implementation**. No source code, build system, MCPs, schemas, or data files exist yet — only `README.md`, `plan.md`, and this file. The full design is in `plan.md`; treat it as the source of truth for scope and structure, and expand the codebase incrementally along the phases it describes.

## Project purpose

A collection of MCP servers, datasets, and schemas that help AI agents design custom football formations and plays for NCAA and Madden games across PS1, PS2, and PS3 eras.

The system is built around three layers that must stay cleanly separated:

1. **Football truth** — real-world formations, routes, blocking schemes, offensive/defensive concepts. Game-agnostic.
2. **Game truth** — what each title's editor can and cannot represent (grid limits, route options, motion rules, engine quirks). Game-specific.
3. **Coordinate translation** — converts the universal football model into each game's editor grid via per-game translation profiles.

Real football knowledge lives in reusable concept files; game-specific editor limits live in game profiles; the translation layer bridges the two. This separation is what lets the system stay useful as new games are added later.

## Architectural rules

- **Many narrow MCPs, not one giant MCP.** Each MCP under `mcps/` owns a single responsibility (e.g., game knowledge, coordinate translation, formation library, route tree, blocking schemes, play variants, validation, playbook generation). Don't merge responsibilities to "save effort" — the boundaries are the design.
- **Schema-first data.** Every data file under `data/` must validate against a JSON schema in `schemas/`. AI-generated data without schema enforcement drifts into inconsistency.
- **Universal internal coordinate system:**
  - Origin: center of the ball at the line of scrimmage
  - X positive = offense's right, X negative = offense's left
  - Y positive = downfield, Y negative = offensive backfield
  - Units are real yards; per-game profiles convert to editor grid units
- **Plays belong to families.** A play should be designed as part of a 2–5 play family that shares a pre-snap look but attacks different areas (e.g., base run + counter + play-action + screen + bootleg). Don't generate one-off plays.
- **Every formation must support coordinate translation** — specify player positions in the universal coordinate system, not in narrative form.
- **Every generated play must include a validation result** (valid / valid-with-warnings / invalid / needs-game-compromise).

## Working with game-specific claims

Editor capabilities, route limits, formation limits, and engine/AI quirks for any specific title MUST carry:

- A **verification status** (`verified` / `unverified` / `inferred`)
- A **source or test note**

Do not invent game-specific capabilities. When information is incomplete, add explicit uncertainty fields rather than guessing. PS1 titles should default to being treated as more limited than PS2/PS3 titles unless verified otherwise.

When modifying existing data files, preserve prior notes — append, don't overwrite.

## Phasing

The plan is explicitly phased. The first MVP targets only **NCAA 06 PS2** and **Madden 04 PS2**, with a small starter set of formations, routes, and concepts. Don't broaden scope unprompted — adding a new game, formation, concept, or MCP is a deliberate decision, not a side effect.

When building MCPs, implement them one at a time in the order in `plan.md`. **`coordinate-translation-mcp` comes first**, because most other MCPs depend on its output.

## Build, test, run

Not yet established. When the first MCP is added, decide on language/runtime/test framework and update this section.
