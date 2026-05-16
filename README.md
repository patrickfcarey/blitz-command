# blitz-command

A library of MCP servers, datasets, schemas, and tools for designing custom football formations and plays — built so AI agents (Claude, GPT, Gemini, smaller models like Sonnet / Haiku) can author plays end-to-end and translate them into the editor grids of NCAA / Madden games across PS1, PS2, and PS3 eras.

## What this is

Three layers, kept cleanly separate:

1. **Football truth** (`data/formations/`, `data/plays/`, `data/routes/`) — real-world formations, plays, and routes. Game-agnostic. Universal coordinate system: x right is positive, y downfield is positive, units in real yards, origin at the ball on the LOS.
2. **Game truth** (`data/games/<game-id>/editor-grid.yaml`) — what each title's editor can actually represent (grid dimensions, unit scale, max route depth, motion options).
3. **Coordinate translation** (`tools/draw-play/`, the per-game profiles) — converts the universal model into per-game editor coordinates and renders it.

This separation is what lets the system stay useful as new games get added.

## Library snapshot

- **54 formations** (offense + 9 defense fronts/coverages: 4-3 C2/C3, 3-4 C3, 4-2-5 C2, Nickel C1, Dime C4, 46 Bear C0, Goal-Line 6-2, Prevent 3-2-6)
- **144 plays** (right-side originals + auto-generated left mirrors), including all the option families: Wishbone triple, Flexbone triple + midline, Pistol IZ-read / OZ-read / Power-Read / Zone-Read-RPO, Wildcat speed option, designed QB Power / QB Counter, classic Houston Veer, RPO bubble + slant
- **18 routes** in the route library
- **3 game profiles** — `madden-04-ps2`, `madden-05-ps2`, `ncaa-06-ps2`
- **2 MCP servers** with **17 tools combined** for AI-driven authoring + analysis
- **50 tests** covering schemas, drawing, and every MCP tool

## Quick start

```bash
# One-time setup (Python 3.11+ required for the mcp SDK)
python3.11 -m venv .venv
.venv/bin/pip install -r requirements.txt

# Run the test suite
./run-tests.sh

# Render a play to SVG
.venv/bin/python tools/draw-play/draw.py \
    --play singleback-trio-mesh \
    --defense defense-4-3-cover-3 \
    --game madden-05-ps2 \
    -o mesh-vs-c3.svg
```

See [docs/setup.md](docs/setup.md) for full setup notes.

## Using the MCPs

The two MCP servers (`play-library-mcp` and `formation-library-mcp`) expose every play and formation to AI agents over stdio. See [docs/using-the-mcps.md](docs/using-the-mcps.md) for client registration, tool catalog, and worked examples.

The play-library MCP supports the full author → validate → render → save loop:

```python
# Authoring loop (smaller AIs especially benefit from this)
scaffold = build_starter_play('singleback-trio', 'play-action', philosophy='west-coast')
# AI fills in routes / depths / read tree
result = validate_play(scaffold)         # check schema + concept lints
svg = render_play(scaffold['play_id'])   # see it in the editor grid
save_play(scaffold)                      # persist to data/plays/
mirror_play(scaffold['play_id'])         # auto-create the -left mirror
```

Plus discovery / analysis composition tools:

```python
find_plays_by_concept('triple-option')              # cross-field search
compare_plays([id1, id2, ...])                      # disguise / diversity scorecard
suggest_complementary_plays([seed_id, ...])         # what's missing from a playbook
predict_matchup(play_id, defense_id)                # best/neutral/worst rating + rationale
```

## Repository layout

```
data/
  formations/          # universal-coord formations (offense + defense)
  plays/               # play YAMLs (assignments, motions, paths, reads, strengths, ...)
  routes/              # route library (depths, breakpoints, beats_coverage)
  games/<game-id>/     # per-game editor-grid profile
schemas/               # JSON schemas validated against every YAML
mcps/
  play-library-mcp/    # 13 tools — discovery + authoring + analysis
  formation-library-mcp/  # 4 tools — formation discovery
tools/
  draw-play/           # SVG renderer (offense + defense + multiple modes)
  generate-mirror-plays/  # right→left play mirror generator
  generate-mirrors/    # right→left formation mirror generator
  coordinate-translator/  # universal yards → editor grid cells
docs/
  setup.md             # venv + dependency setup
  using-the-mcps.md    # MCP registration + tool catalog
  play-data-provenance.md   # generic vs Madden-canonical plays
  formation-roadmap.md, formation-rules.md, ...
tests/                 # unittest suite (schemas, drawing, MCPs)
```

## Architectural rules

- **Many narrow MCPs, not one giant MCP.** Each MCP owns a single responsibility.
- **Schema-first data.** Every YAML validates against a JSON schema in `schemas/`.
- **Universal internal coordinate system.** Origin at the ball, x+ right, y+ downfield, units in real yards. Per-game profiles convert.
- **Plays belong to families.** A play should pair with 2-5 related variants under the same pre-snap look.
- **Every formation must support coordinate translation** (universal coords on every player).
- **Game-specific claims need verification status + source notes.** Don't invent editor capabilities.

## Status

Pre-1.0. Most-used path (author plays + render in Madden 05 PS2 grid) is fully working with tests. Per-game measurements for other titles are still placeholders pending in-game verification (see [docs/game-editor-measurement-protocol.md](docs/game-editor-measurement-protocol.md)).

See [docs/pending-queue.md](docs/pending-queue.md) for the open backlog.
