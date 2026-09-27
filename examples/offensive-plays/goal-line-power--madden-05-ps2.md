# Recreate "Goal Line Power" in `madden-05-ps2`

**Formation:** `goal-line`  •  **Type:** run  •  **Ball carrier:** HB
**Snap rule:** integer cells only

## Step 1 — set player cells

| Player | Cell (col, row) | Position | On line | Universal yds |
|--------|-----------------|----------|---------|---------------|
| `LT` | (8, 5) | LT | yes | (-2.0, 0.0) |
| `LG` | (9, 5) | LG | yes | (-1.0, 0.0) |
| `C` | (10, 5) | C | yes | (0.0, 0.0) |
| `RG` | (11, 5) | RG | yes | (1.0, 0.0) |
| `RT` | (12, 5) | RT | yes | (2.0, 0.0) |
| `TE-L` | (7, 5) | TE | yes | (-3.5, 0.0) |
| `TE-R` | (13, 5) | TE | yes | (3.5, 0.0) |
| `WR` | (14, 4) | WR | no | (6.0, -1.0) |
| `QB` | (10, 4) | QB | no | (0.0, -2.0) |
| `FB` | (10, 3) | FB | no | (0.0, -3.5) |
| `HB` | (10, 2) | HB | no | (0.0, -6.0) |

## Step 2 — QB drop / handoff path

`QB`: (10, 4) → (11, 4) → (9, 4)

## Step 3 — ball-carrier / lead-block paths

- `FB` (lead_block): (10, 3) → (12, 4) → (12, 6)
  - Lead through the hole; iso the playside LB or kick out the strong safety.
- `HB` (ball_carrier): (10, 2) → (12, 3) → (12, 4)
  - Take handoff, hit off-tackle behind RT/TE-R/pulling LG. Lower shoulder — goal-line power requires contact-finishing.

## Step 4 — blocking assignments

- `LT`: down-block → backside-3-tech
  - Down block on backside DT to seal the cutback.
- `LG`: pull-around → playside-LB
  - PULL — backside guard pulls around C, leads through the off-tackle hole.
- `C`: gap-block → backside-A-gap
- `RG`: down-block → playside-3-tech
- `RT`: down-block → playside-DE
- `TE-L`: down-block → backside-edge
  - TE-L seals backside edge to prevent backside crash.
- `TE-R`: kickout → edge-defender
  - TE-R kicks out the playside EDGE — creates the off-tackle hole.
- `WR`: stalk → cornerback
  - Stalk the corner; goal line means he's likely close to LOS.

## Notes

Goal-line variant of Power O. Same blocking scheme as standard Power O
but with the jumbo formation's extra blocker (TE-L on the line) for
added playside surface and backside seal.
