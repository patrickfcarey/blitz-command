# Game Editor Measurement Protocol

Step-by-step guide for collecting accurate data from a football game's play / formation editor. The output goes into:

- `data/games/<game-id>/game.yaml` — what the game can do (validated by `schemas/game.schema.json`)
- `data/games/<game-id>/editor-grid.yaml` — how the editor's grid maps to real yards (validated by `schemas/coordinate-map.schema.json`)

You only need to do this once per game. After it's done, every formation and play we design for that title can be translated automatically.

## Before you start

- Pick a `game_id` (lowercase kebab-case, e.g. `ncaa-06-ps2`). Match the directory under `data/games/`.
- Boot the game, get to the play / formation editor with a default formation loaded.
- Have a way to capture screenshots — visuals beat written descriptions when in doubt.

---

## Part 1 — Editor existence (`game.yaml` → `editors`)

For each editor, decide: **present**, **absent**, **limited**, or **unknown**.

| Editor | What "present" means |
|--------|----------------------|
| `custom_play` | You can draw new routes / blocking assignments and save the result |
| `custom_formation` | You can reposition players and save the resulting formation |
| `custom_playbook` | You can assemble a playbook from existing or custom plays |
| `custom_roster` | Edit player attributes, names, etc. |
| `custom_team` | Create a new team (logo, name, uniform) |

Use **`limited`** when the editor exists but with significant constraints (e.g. "can edit routes on existing plays but not create plays from scratch"; "save cap of 5 custom plays"). Describe the constraints in `notes`.

---

## Part 2 — Editor field landmarks

Open the play editor with a default formation loaded. Note:

1. **Orientation** — Is it top-down? Side-on? Which way is downfield?
2. **Visible markings** — Tick all that apply: LOS line, yard lines (every 5? every 10?), hash marks, sidelines, end zones.
3. **Default ball position** — Left hash / center / right hash?
4. **Coordinate readout** — Does the editor show numeric coordinates as you move a player? If yes, in what units (cells, pixels, yards)?

Take a screenshot of the empty editor with a default formation loaded. Save it as `data/games/<game-id>/screenshots/editor-default.png` (create the directory).

---

## Part 3 — Grid measurements (`editor-grid.yaml`)

These give us the conversion between universal yards (per `docs/coordinate-systems.md`) and editor units.

### A. Origin

Place a player at the **center of the formation, on the LOS** (the C position). Note the editor's coordinate readout for that player. If no readout, take a screenshot — we'll measure pixels off the image.

→ Records `grid.origin.x` and `grid.origin.y`.

### B. Width scale

Slide the same player horizontally to the **nearest sideline**. Record:
- Editor coordinate at the sideline, OR
- Number of discrete moves (if the editor snaps to a grid)

The sideline is **26.67 yards** from the ball when the ball is centered (less when on a hash; if you can't center the ball, note the hash distance instead).

→ `scale.x_yards_per_cell = 26.67 / (cells moved from center to sideline)`

### C. Depth scale

Place a player on the LOS, then move them straight back to the **5-yard mark behind the LOS** (the first yard line in the offensive backfield). Record cells moved or coordinate change.

→ `scale.y_yards_per_cell = 5 / (cells moved from LOS to 5-yards-back)`

If yard lines aren't visible in the editor, use any depth you can measure (e.g. "moved a player from LOS to where you know the 7-yard QB shotgun depth is") and tell me what landmark you used.

### D. Grid bounds

Move a player to each editor extreme — max left, max right, max forward, max back — and record the editor coordinate at each. This sets `grid.width` and `grid.height`.

---

## Part 4 — Position and editor limits (`game.yaml.limits`, `editor-grid.yaml.limits`)

Test each:

| Limit | How to test | Goes in |
|-------|-------------|---------|
| `max_player_split_yd` | Drag a WR as wide as the editor allows. Convert with Part 3 scale. | `editor-grid.yaml.limits` |
| `max_backfield_depth_yd` | Drag a RB as deep as allowed. Convert. | `editor-grid.yaml.limits` |
| `max_route_depth_yd` | Draw a streak as long as allowed. Convert. | `editor-grid.yaml.limits` |
| `max_route_segments` | Add break points to a route until the editor stops you. | `game.yaml.limits` |
| `max_routes_per_play` | How many of the 5 eligibles can run a route vs being forced to block? | `game.yaml.limits` |
| `max_plays_per_playbook` | Add custom plays to a playbook until it caps. | `game.yaml.limits` |
| `max_custom_plays_total` | Save custom plays until the save cap is hit. | `game.yaml.limits` |
| `max_custom_formations_total` | Same for formations, if supported. | `game.yaml.limits` |

---

## Part 5 — Motion options (`editor-grid.yaml.limits.allowed_motion`)

List every pre-snap motion type the editor offers. Common categories:

- `short_across` — 1–3 yard sideways shift
- `long_across` — full-formation sideways
- `fly` — full-speed across, snap before motion ends
- `jet` — full speed, snap **on** the motion (motion player is moving at snap)
- `short_forward` / `short_backward`
- `bunch` — multiple players motion together

If a category is absent, that's worth recording too — the play designer needs to know what *can't* be drawn.

---

## Part 6 — Quirks and gotchas (`game.yaml.ai_quirks`, `known_limitations`)

Free-form list. Anything weird about this title:

- Routes that don't behave as drawn ("drag routes always sit down at 5 yards regardless of editor depth")
- AI defenses ignoring concepts ("zone defenders never carry a wheel")
- Engine behaviors ("FB lead block always loops outside, even on inside runs")
- Save / load issues ("custom plays don't save when assigned to certain formations")

Split between `ai_quirks` (defensive/offensive AI behavior) and `known_limitations` (editor/engine constraints).

---

## Reporting back

Send everything in one block per game. No need to format YAML — dump the answers and I'll structure them. Start with the `game_id` so I can route the data to the right files.

Example dump:

```
game_id: ncaa-06-ps2

Part 1 — Editors:
- custom_play: present, can draw routes & blocking
- custom_formation: limited, can move players within preset formations only
- custom_playbook: present, ~75 play cap
- custom_roster: present
- custom_team: absent

Part 2:
- top-down view, downfield is up
- LOS visible, 5-yard lines visible, hashes visible (NCAA-width)
- ball defaults to left hash
- coordinate readout: yes, in cells (e.g. "X: 50, Y: 40")

Part 3:
- C placed → coords (50, 40)
- Sideline (left) → coords (8, 40), so 42 cells = 26.67 yd → 0.635 yd/cell
- 5 yd back → coords (50, 32), so 8 cells = 5 yd → 0.625 yd/cell
- Max bounds: X 0-100, Y 0-80

Part 4:
- max_player_split_yd: ~22 (WR couldn't go wider than coords X=15 from center)
- max_route_depth_yd: ~30
- max_routes_per_play: 5 (all WRs/TEs/RB-out-of-backfield)
- max_plays_per_playbook: 75

Part 5:
- short across, long across, fly. No jet motion. No bunch motion.

Part 6:
- Drag routes always break flat at ~4 yd regardless of editor depth setting
- Zone defenders never sink with a vertical from the slot
```

Once I have a dump like that, I'll update `game.yaml` and `editor-grid.yaml` and you can spot-check.

Verification tag for each field defaults to **`verified`** when it comes from your in-game testing.
