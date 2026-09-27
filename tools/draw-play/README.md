# draw-play

Render a play as it would appear in a target game's editor grid. Output is SVG.

Use it to compare a designed play to what you'd actually draw in the in-game custom-play editor — then copy it in.

## How it works

1. Loads the play YAML from `data/plays/<play-id>.yaml`
2. Loads the formation it references from `data/formations/<formation-id>.yaml`
3. Loads the target game's editor-grid profile from `data/games/<game-id>/editor-grid.yaml`
4. Loads the route library from `data/routes/`
5. Renders an SVG showing:
   - The editor's grid (cell lines)
   - Players snapped to grid cells (color-coded: orange = ball carrier, cyan = primary read, white = other, **red = outside editor limits**)
   - Routes as polylines (mirror-aware: a slant from the left side breaks right; from the right side, breaks left)
   - LOS as a yellow horizontal line
   - Max route depth as a red dashed ceiling line
   - Title strip with play / game metadata
   - Warnings strip listing any editor-limit violations

## Setup

Same Python venv as the other tools (Python 3.11+):

```
pip install pyyaml
```

## Usage

```
python3.11 tools/draw-play/draw.py <play-id> <game-id> -o <output.svg>
```

Example:

```
python3.11 tools/draw-play/draw.py i-formation-power-o ncaa-06-ps2 \
    -o examples/play-diagrams/i-formation-power-o--ncaa-06-ps2.svg
```

Without `-o`, SVG is printed to stdout.

## What's drawn

- **Players**: circles with position labels, snapped to editor grid cells. Out-of-bounds players show in red.
- **Routes**: polylines drawn from the receiver's start position through the route's waypoints. Routes are mirror-aware so the same route file (e.g. `slant`) renders correctly for both left-side and right-side receivers.
- **Editor limits**: max route depth as a dashed ceiling line; player split / backfield depth violations recorded in the warnings strip.
- **Game grid**: the editor's actual cell count and scale (yards per cell), so different games render at different visual densities.

## Not yet drawn

- Blocking arrows (need defensive players to draw block targets)
- Motion arrows (curved dashed lines for pre-snap motion)
- Defensive overlay (need defensive formations first)
- Animation
- Annotations for option routes (snag, stick — show both branches)

These are roadmap items.

## Quality caveat

The diagrams are only as accurate as the game profile they target. Right now most game profiles are placeholder (`verification_status: inferred` or `unverified`). When you measure a game per `docs/game-editor-measurement-protocol.md` and update its `editor-grid.yaml`, the diagrams against that game become directly usable as in-game-entry guides.
