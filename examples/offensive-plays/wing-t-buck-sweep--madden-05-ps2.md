# Recreate "Buck Sweep" in `madden-05-ps2`

**Formation:** `wing-t`  •  **Type:** run  •  **Ball carrier:** HB
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
| `WING` | (14, 4) | TE | no | (5.0, -1.0) |
| `QB` | (10, 4) | QB | no | (0.0, -2.0) |
| `FB` | (10, 3) | FB | no | (0.0, -4.5) |
| `HB` | (9, 2) | HB | no | (-2.0, -5.5) |

## Step 2 — QB drop / handoff path

`QB`: (10, 4) → (9, 4) → (9, 3)

## Step 3 — ball-carrier / lead-block paths

- `HB` (ball_carrier): (9, 2) → (11, 3) → (13, 4) → (15, 7)
  - Take the handoff, follow the two pulling guards around the playside edge — get to the corner.

## Step 4 — blocking assignments

- `LT`: down-block → backside-DT
- `LG`: pull-around → playside-LB
  - PULL — both guards pull around the C, leading the HB to the perimeter.
- `C`: gap-block → backside-A-gap
- `RG`: pull-around → playside-cornerback
  - PULL — second pulling guard, sealing the corner / kicking out edge defender.
- `RT`: down-block → playside-DT
- `TE`: down-block → edge-defender-or-LB
  - TE down-blocks the EDGE defender, securing the playside hinge.
- `WING`: kickout → cornerback
  - WING kicks out the playside corner / force defender.
- `X`: stalk → backside-cornerback

## Notes

Wing-T's signature play. Two pulling guards (LG and RG) is unusual for any
modern run scheme but is the defining feature here. The QB reverse-out and
FB belly fake are critical — without them, the LBs scrape and kill the
play. Mirror to "Buck Sweep Left" by flipping all x; the play swaps which
guard pulls first and which side gets the WING.
