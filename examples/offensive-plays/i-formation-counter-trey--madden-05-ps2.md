# Recreate "Counter Trey (Strong)" in `madden-05-ps2`

**Formation:** `i-formation`  •  **Type:** run  •  **Ball carrier:** HB
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
| `X` | (1, 5) | WR | yes | (-15.0, 0.0) |
| `Z` | (17, 4) | WR | no | (12.0, -1.0) |
| `QB` | (10, 4) | QB | no | (0.0, -2.0) |
| `FB` | (10, 3) | FB | no | (0.0, -4.5) |
| `HB` | (10, 2) | HB | no | (0.0, -7.0) |

## Step 2 — QB drop / handoff path

`QB`: (10, 4) → (9, 4) → (9, 4)

## Step 3 — ball-carrier / lead-block paths

- `FB` (lead_block): (10, 3) → (12, 4) → (12, 6)
  - FB leads through the playside hole; iso a free defender at the second level.
- `HB` (ball_carrier): (10, 2) → (9, 2) → (12, 4) → (12, 6)
  - Counter step LEFT first (sell run away from playside), then plant and run
RIGHT through the off-tackle hole behind the pulling LG and LT.


## Step 4 — blocking assignments

- `LT`: pull-around → edge-defender
  - PULL — backside tackle pulls and kicks out the playside EDGE.
- `LG`: pull-around → playside-LB
  - PULL — backside guard pulls around C, leads through the off-tackle hole onto the playside LB.
- `C`: gap-block → backside-A-gap
- `RG`: down-block → playside-3-tech
- `RT`: down-block → playside-DT
- `TE`: down-block → playside-LB
  - TE down-blocks at the second level.
- `X`: stalk → cornerback
- `Z`: stalk → cornerback

## Notes

Counter Trey: backside guard AND tackle pull (two pullers). HB takes a
counter step opposite the playside to sell the misdirection, then plants
and runs behind the pullers. The "Trey" comes from the BSG+BST pull
combination. Mirror to "Counter Trey Weak" by reversing direction.
