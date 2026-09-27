# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository state

The repository is **in active implementation**. It has a working set of MCP servers under `mcps/`, JSON schemas under `schemas/`, a large play / formation / route / concept dataset under `data/`, supporting scripts under `tools/`, and a test suite. `plan.md` holds the original phased design and is still the design reference, but the codebase — not `plan.md` — is the source of truth for what currently exists.

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

## MCP servers and their documentation

The project's functionality is exposed through a set of narrow, single-responsibility MCP servers under `mcps/`. `docs/using-the-mcps.md` is the cross-server index and registration guide.

**Each server is documented by its own `README.md`** at `mcps/<name>-mcp/README.md`. That README is the authoritative tool catalog for the server: it must list every tool the server exposes, and the tool count it states must equal the number of `@mcp.tool()` decorators in `server.py`.

- **A new MCP server is not complete without its `README.md`.** Commit the README in the same change that adds the server — never the server alone. Also add the server to the `docs/using-the-mcps.md` index.
- **When you add, remove, or change a tool on an existing server, update that server's `README.md` in the same change.** Code and README must never drift.
- **Before using an MCP in a task, consult its `README.md`** (or call its `manifest()` tool) to confirm which tools exist and what they cover — do not assume a tool's behavior.
- **Whenever an MCP returns game-specific data, check its `verification_status`** (`verified` / `unverified` / `inferred`) and surface that uncertainty. Never present an `unverified` or `inferred` game capability as established fact — see "Working with game-specific claims" above.

## Keeping the pending queue current

`docs/pending-queue.md` is the living list of open work. Keep it current as a matter of course — **without being asked**:

- When work lands, move the matching item to the file's `## Done` section (or delete it once it is no longer useful context).
- When new open work surfaces — a follow-up, a bug, a deferred idea — add it as a terse one-line entry under the right category.
- Do this in the same change as the work itself, so the queue never drifts.

A stale queue is worse than none — it has previously listed long-shipped MCPs and schemas as "pending." Updating it is part of finishing a task, not a separate chore.

## Phasing

`plan.md` lays out the original phased build. The early phases — the core MCP servers, the schemas, and the starter dataset — are done; current work is mostly dataset expansion and refinement.

Still: **don't broaden scope unprompted** — adding a new game, formation, concept, or MCP server is a deliberate decision, not a side effect. When you do add an MCP server, follow the documentation rules above.

## Build, test, run

- **Runtime:** Python. The MCP servers require Python 3.10+ (the `mcp` SDK); the repo `.venv` is built with `python3.11`. Use `.venv/bin/python` for anything that imports `mcp`, `pyyaml`, or `jsonschema` — the system `python3` may be too old.
- **Setup:** `python3.11 -m venv .venv && .venv/bin/pip install -r requirements.txt`.
- **Tests:** `./run-tests.sh` runs the full suite (`python -m unittest discover -s tests`).
- **Tools:** the standalone scripts under `tools/` are run with `.venv/bin/python tools/<name>/<script>.py`.
