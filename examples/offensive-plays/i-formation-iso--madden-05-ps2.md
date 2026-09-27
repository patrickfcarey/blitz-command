# Recreate "ISO (Lead)" in `madden-05-ps2`

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

- `FB` (lead_block): (10, 3) → (11, 4) → (11, 5)
  - FB hits the playside A-gap LB — that's the ISOLATED defender the play is named for.
- `HB` (ball_carrier): (10, 2) → (11, 4) → (11, 6)
  - Square handoff, hit the A or B gap depending on FB's read.

## Step 4 — blocking assignments

- `LT`: drive-block → backside-DE
- `LG`: drive-block → backside-DT
- `C`: drive-block → 0-or-1-tech
- `RG`: combo-block → 3-tech-then-PSLB
  - Combo with RT on the playside DT, climb to playside LB.
- `RT`: combo-block → 3-tech-then-PSLB
- `TE`: drive-block → edge-defender
- `X`: stalk → cornerback
- `Z`: stalk → cornerback

## Notes

Simplest power run in football. The play's name describes the FB's job:
"isolate" the playside A-gap LB so the HB can pick a side off the FB block.
