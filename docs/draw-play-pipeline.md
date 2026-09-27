# draw-play coordinate pipeline

`draw-play` transforms a play through **three coordinate spaces** before producing SVG output. This doc walks through each space, shows the math, and works one full example end-to-end.

For the project-wide universal coordinate convention (the "what does X positive mean" question), see [coordinate-systems.md](coordinate-systems.md). This document is the *implementation* layer.

## The three spaces

```
   universal yards          grid cells              SVG pixels
   ───────────────  ──────  ──────────  ──────────  ──────────
   real football    universal_to_grid    grid_to_pixel
   (game-agnostic)  → editor cells  →    image coords
                    (per-game)           (with Y inverted)
```

| Space | Origin | Units | Defined by |
|-------|--------|-------|------------|
| **Universal yards** | Center of ball at LOS | Real yards | The football itself |
| **Grid cells** | `profile.grid.origin` (a cell index pair) | Editor cells | The game's editor profile |
| **SVG pixels** | Top-left of SVG canvas | Pixels | `FIELD_MARGIN_PX`, `PIXELS_PER_CELL`, plus Y-inversion |

Why three? Because the renderer must answer two independent questions:
1. *Which editor cell does this player snap to?* Answered by universal → grid.
2. *Where on the SVG canvas is that cell drawn?* Answered by grid → pixel.

Each game has its own grid (Madden 05 is 21×7 cells, NCAA 14 is different), but every SVG is drawn the same way (32 px per cell, 40 px field margin). Splitting the transform makes the per-game logic local to one function.

## Stage 1 — universal yards → grid cells

Defined in `universal_to_grid(x_yd, y_yd, profile)`:

```python
gx = origin.x + x_yd / scale.x_yards_per_cell
gy = origin.y + y_yd / scale.y_yards_per_cell
```

The result is **fractional** — these aren't editor cell indices yet, they're real-valued positions on the grid. Caller decides whether to round.

For Madden 05 (`data/games/madden-05-ps2/editor-grid.yaml`):
- `origin.x = 10`, `origin.y = 5`
- `scale.x_yards_per_cell = 1.667`
- `scale.y_yards_per_cell = 2.0`

The center of the ball at the LOS (`0, 0`) maps to grid cell `(10, 5)`. A WR split 15 yards right (`x = +15`) lands at column `10 + 15/1.667 = 19.0`. A QB 2 yards behind the LOS (`y = -2`) lands at row `5 + (-2)/2.0 = 4.0`.

### Snapping (the `snap_to_cells: true` case)

When the profile has `snap_to_cells: true`, fractional cells are rounded to integers in `assign_cells_for_formation`. There are two complications:

**Tight cluster.** Five interior linemen plus a TE / wing within 3.5 yards of the OL block don't get their natural rounded cells — they get **sequential integer cells centered on the C**. Without this, two linemen with the same rounded X would collide. With it, the C is always at `origin.x` and LT/LG/RG/RT/TE/etc. take ±1, ±2, ±3 from there.

**Conflict resolution.** If two non-cluster players round to the same cell, `_bfs_nearest_free_cell` searches outward in expanding rings (`BFS_MAX_RINGS = 25`) for the nearest free cell, with a side-aware penalty — defenders prefer to bump downfield, offense prefers backfield, neither crosses the LOS without a heavy penalty.

If BFS exhausts without finding a free cell, the function raises `CellAssignmentError`. In practice this only happens on absurdly small profiles or 22-on-1-cell formations.

## Stage 2 — grid cells → SVG pixels

Defined in `grid_to_pixel(gx, gy, total_cells)`:

```python
px = FIELD_MARGIN_PX + gx * PIXELS_PER_CELL
py = FIELD_MARGIN_PX + (total_cells - gy) * PIXELS_PER_CELL
```

Two things to notice:

1. **Y is inverted.** Higher grid row (deeper downfield) means *smaller* pixel Y (closer to the top of the SVG). This matches user expectation ("downfield is at the top of the page") but is the opposite of the universal Y convention.
2. **`total_cells` includes the downfield extension.** The editor itself is `grid.height` cells tall, but `draw-play` adds a downfield viewing area (`FIELD_LONG_EXTRA_YD = 30` yards, or `FIELD_SHORT_EXTRA_YD = 15` for `--field short`). `total_cells = grid.height + ceil(extra_yd / scale.y_yards_per_cell)`.

For Madden 05 with `--field long`:
- `grid.height = 7`, `scale.y = 2.0`, `extra_yd = 30`
- `total_cells = 7 + ceil(30/2.0) = 7 + 15 = 22`

The LOS row (gy=5) sits at `40 + (22-5)*32 = 584` px. The downfield max-route-depth limit (gy=5+20/2.0=15) sits at `40 + (22-15)*32 = 264` px — higher up the SVG, as expected.

The convenience helper `universal_to_pixel()` chains both stages.

## Worked example

Render a TE attached to the right of the RT in Singleback Trio on Madden 05.

**Input** (from `data/formations/singleback-trio.yaml`):
```yaml
- { label: TE, position: TE, x: 3.5, y: 0.0, on_line: true }
```

**Profile** (from `data/games/madden-05-ps2/editor-grid.yaml`):
```yaml
grid:   { width: 21, height: 7, origin: { x: 10, y: 5 } }
scale:  { x_yards_per_cell: 1.667, y_yards_per_cell: 2.0 }
snap_to_cells: true
```

**Stage 1: universal_to_grid(3.5, 0.0, profile)**
```
gx = 10 + 3.5  / 1.667 ≈ 12.10
gy = 5  + 0.0  / 2.0   = 5.0
```

But TE is in the **tight cluster** (within `CLUSTER_X_TOLERANCE_YD = 3.5` of the OL block). So the cluster-snap path overrides the X. Sorted by x, the cluster is `[LT, LG, C, RG, RT, TE]` with C at index 2 and TE at index 5. The snapped X is:
```
snapped_x = origin.x + (p_index - c_index) = 10 + (5 - 2) = 13
```
Y is unchanged (5.0). After `round`, the snapped cell is `(13, 5)`.

**Stage 2: grid_to_pixel(13, 5, total_cells=22)**
```
px = 40 + 13 * 32 = 456
py = 40 + (22 - 5) * 32 = 584
```

So the TE marker is centered at SVG `(456, 584)`. Run the renderer and inspect:

```bash
python3 tools/draw-play/draw.py singleback-trio-mesh madden-05-ps2 -o /tmp/out.svg
grep '>TE</text>' /tmp/out.svg | head -1
```

Output (with my baseline check):
```svg
<text x="456" y="588" text-anchor="middle" font-size="11" fill="black" font-weight="bold">TE</text>
```

The text Y is `py + PLAYER_LABEL_Y_OFFSET_PX = 584 + 4 = 588` (the offset centers the text inside the marker square). Match.

## Round-trip math

The transforms are exactly invertible (within float precision):

```python
gx = origin.x + x_yd / scale.x_yards_per_cell    # forward
x_yd = (gx - origin.x) * scale.x_yards_per_cell  # inverse

px = FIELD_MARGIN_PX + gx * PIXELS_PER_CELL                       # forward
gx = (px - FIELD_MARGIN_PX) / PIXELS_PER_CELL                     # inverse

py = FIELD_MARGIN_PX + (total_cells - gy) * PIXELS_PER_CELL       # forward
gy = total_cells - (py - FIELD_MARGIN_PX) / PIXELS_PER_CELL       # inverse
```

The property tests in `tests/test_draw_properties.py::TestCoordinateRoundTrip` verify this with 200 random points per direction — the round-trip error is below 1e-6 yards.

The one-way `assign_cells_for_formation` round trip (universal → snapped grid → universal via `player_effective_xy`) is **not** identity in general, because snapping is lossy. A TE authored at `x = 3.5` snaps to grid column 13, which corresponds to `(13 - 10) * 1.667 = 5.001` yards — not 3.5. This is intentional: routes drawn from the TE's snapped cell start at the visible marker, not at the original universal coordinate, so route arrows connect cleanly to the marker rather than floating to a nearby wrong cell.

## The route-mirror special case

Routes in `data/routes/*.yaml` are authored as right-hand-side breaks. A slant breaks toward the right hash; an out breaks toward the right sideline. When the same slant is run by a left-side WR, the X component of every waypoint is negated:

```python
mirror = -1 if receiver_x > ROUTE_MIRROR_X_THRESHOLD_YD else 1
waypoint = (receiver_x + dx * mirror, receiver_y + dy)
```

`ROUTE_MIRROR_X_THRESHOLD_YD = 0.1` is a small epsilon — a TE on the +0.0 yard line *does not* mirror, but a Z at +12 yards *does*. Without this, every route on the field would render the same direction.

## Sources of subtle precision differences

A few places where the same yard coordinate can produce different cells / pixels:

| Trigger | Effect |
|---------|--------|
| `snap_to_cells: false` profile (e.g. some PS1 titles) | `assign_cells_for_formation` returns float cells; no BFS, no cluster snapping. |
| Cluster vs non-cluster classification (`is_tight_cluster`) | A wing player at `x = 3.5, y = 0.5` is in-cluster; the same player at `y = 2.0` is not. The first gets sequential X; the second gets rounded X. |
| `extra_yd` from `--field` mode | Changes `total_cells`, which changes every Y pixel coordinate but not any X. |
| Hash-spec inference (`hash_spec_for_profile`) | NCAA profile vs Madden profile produces hash ticks at *different* pixel columns even though both use the same scale. |

When debugging "why is this player drawn at the wrong pixel?", walk through the three stages explicitly with `python3 -c "from draw_play import *; print(universal_to_grid(...))"`.

## Diagram (ASCII)

```
                  SVG canvas (FIELD_MARGIN_PX = 40 px around field)
       ┌──────────────────────────────────────────────────────┐
       │                                                       │
       │     downfield extension (light green)                │
       │     +30 yd: gy = 20  →  py = 40 + (22-20)*32 = 104 px │
       │                                                       │
       │     LOS row: gy = 5  →  py = 40 + (22-5)*32 = 584 px  │
   ────┤━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┝──── ← gold LOS line
       │     editor sub-region (grass green)                  │
       │     bottom: gy = 0  →  py = 40 + (22-0)*32 = 744 px  │
       └──────────────────────────────────────────────────────┘
        gx = 0          ↑                                  gx = 21
        px = 40         center column                      px = 40 + 21*32 = 712
                        gx = 10 (origin.x)
                        px = 40 + 10*32 = 360
```

Universal `(0, 0)` is the gold cross at the column center, on the LOS. Universal `(+15, +20)` (deep right comeback) is at grid `(19, 15)`, pixel `(648, 264)`.

## Constants reference

If you're tracing a coordinate by hand, these are the numbers you'll need (all from `draw.py`):

| Constant | Value | Purpose |
|----------|-------|---------|
| `PIXELS_PER_CELL` | 32 | One cell wide / tall in pixels |
| `FIELD_MARGIN_PX` | 40 | Padding around the playable field |
| `OFFENSE_MARKER_SIZE_PX` | 22 | Player rect / circle size |
| `DEFENSE_MARKER_SIZE_PX` | 20 | Defender marker size |
| `FIELD_LONG_EXTRA_YD` | 30 | Default downfield buffer |
| `FIELD_SHORT_EXTRA_YD` | 15 | `--field short` mode |
| `ROUTE_MIRROR_X_THRESHOLD_YD` | 0.1 | Mirror-or-not boundary |
| `CLUSTER_X_TOLERANCE_YD` | 3.5 | Tight-cluster X-distance threshold |
| `TIGHT_CLUSTER_LOS_TOLERANCE_YD` | 1.5 | Off-line-cluster Y-distance threshold |
| `BFS_MAX_RINGS` | 25 | Max BFS search radius |
| `BFS_VERTICAL_BIAS` | 2 | BFS row-delta cost multiplier |
| `BFS_LOS_CROSS_PENALTY` | 10 | Penalty for crossing the LOS during BFS |
| `MAJOR_GRID_INTERVAL_CELLS` | 5 | Every 5th gridline rendered thicker |
| `YARD_MARKER_INTERVAL_YD` | 5 | Yard-marker dashed lines every 5 yd |
