# Recreate "Wildcat Power" in `madden-05-ps2`

**Formation:** `wildcat`  •  **Type:** run  •  **Ball carrier:** RB1
**Snap rule:** integer cells only

## Step 1 — set player cells

| Player | Cell (col, row) | Position | On line | Universal yds |
|--------|-----------------|----------|---------|---------------|
| `LT` | (8, 5) | LT | yes | (-2.0, 0.0) |
| `LG` | (9, 5) | LG | yes | (-1.0, 0.0) |
| `C` | (10, 5) | C | yes | (0.0, 0.0) |
| `RG` | (11, 5) | RG | yes | (1.0, 0.0) |
| `RT` | (12, 5) | RT | yes | (2.0, 0.0) |
| `TE` | (13, 5) | TE | yes | (3.5, 0.0) |
| `QB-WR` | (1, 5) | QB | yes | (-15.0, 0.0) |
| `Z` | (18, 4) | WR | no | (14.0, -1.0) |
| `SLOT` | (14, 4) | WR | no | (6.0, -1.0) |
| `RB1` | (10, 2) | HB | no | (0.0, -5.0) |
| `RB2` | (9, 2) | HB | no | (-2.5, -5.0) |

## Step 2 — draw routes

| Player | Route | Depth | Waypoints (cells) | Notes |
|--------|-------|-------|-------------------|-------|
| `QB-WR` | stalk-or-route | 0 yd |  | Original QB lined up wide as WR — stalks or runs decoy route. |

## Step 3 — ball-carrier / lead-block paths

- `RB1` (ball_carrier): (10, 2) → (12, 4) → (12, 7)
  - Direct snap, take a quick read step, hit off-tackle behind RT/TE/pulling LG.

## Step 4 — blocking assignments

- `LT`: down-block → backside-DE
- `LG`: pull-around → playside-LB
  - PULL — backside guard pulls around C, leads through the off-tackle hole.
- `C`: gap-block → backside-A-gap
- `RG`: down-block → playside-3-tech
- `RT`: down-block → playside-DE
- `TE`: kickout → edge-defender
- `Z`: stalk → cornerback
- `SLOT`: stalk → nickel-defender

## Notes

Wildcat Power. Same blocking scheme as Power O (down blocks playside,
backside guard pulls), but the snap goes directly to RB1 (no QB
intermediary). RB2 lines up beside RB1 to fake/lead. Original QB
is split as a WR (covered or running a decoy route).
