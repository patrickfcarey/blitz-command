# Recreate "Lead Toss (Strong)" in `madden-05-ps2`

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

`QB`: (10, 4) → (9, 4) → (8, 4)

## Step 3 — ball-carrier / lead-block paths

- `FB` (lead_block): (10, 3) → (13, 4) → (15, 5)
  - Lead through the perimeter; kickout the corner if needed.
- `HB` (ball_carrier): (10, 2) → (12, 2) → (14, 4) → (16, 6)
  - Receive the toss while moving laterally; gain ground toward the
playside corner; turn upfield once the perimeter is sealed by FB
and pulling RG.


## Step 4 — blocking assignments

- `LT`: drive-block → backside-DE
- `LG`: drive-block → backside-DT
- `C`: drive-block → 0-or-1-tech
- `RG`: pull-around → playside-LB
  - PULL — playside guard pulls and leads up to the playside LB.
- `RT`: down-block → playside-DE
  - Down-block on playside DE — seal him inside.
- `TE`: kickout → edge-defender
  - Kick out the EDGE / force defender — opens the perimeter.
- `X`: stalk → cornerback
- `Z`: crack → outside-LB-or-S
  - Crack-block back inside — pick off the alley defender.

## Notes

Lead Toss to the strong side. RG pulls and leads through the perimeter;
FB also leads. Z cracks back to help seal the alley. HB receives the
toss on the move and gets to the corner. Mirror to "Lead Toss Weak" by
reversing all coords.
