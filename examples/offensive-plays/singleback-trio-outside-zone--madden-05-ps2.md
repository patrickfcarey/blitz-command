# Recreate "Outside Zone (Stretch)" in `madden-05-ps2`

**Formation:** `singleback-trio`  •  **Type:** run  •  **Ball carrier:** HB
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
| `SLOT` | (5, 4) | WR | no | (-8.0, -1.0) |
| `QB` | (10, 4) | QB | no | (0.0, -2.0) |
| `HB` | (10, 2) | HB | no | (0.0, -6.0) |

## Step 2 — QB drop / handoff path

`QB`: (10, 4) → (11, 4) → (8, 4) → (8, 4)

## Step 3 — ball-carrier / lead-block paths

- `HB` (ball_carrier): (10, 2) → (12, 2) → (14, 4) → (15, 6)
  - Three reads off the EDGE block:
- PRIMARY (orange) — BOUNCE outside if EDGE is reached
- SECONDARY (blue) — BANG off-tackle if EDGE crashes inside
- TERTIARY (lavender) — CUTBACK if defense overflows playside


## Step 4 — blocking assignments

- `LT`: zone-reach-playside
  - Reach step playside; if backside DE crashes, scoop to backside LB.
- `LG`: zone-reach-playside → 1-or-3-tech
- `C`: zone-reach-playside → backside-A-gap
- `RG`: zone-reach-playside → 3-tech
  - Reach the 3-tech; if reached, climb to playside LB.
- `RT`: zone-reach-playside → 5-tech-or-EDGE
- `TE`: reach-block → edge-defender
  - Critical block — reach the EDGE to seal him inside, opening the bounce.
- `X`: stalk-or-crack → cornerback
- `Z`: stalk-or-crack → cornerback
- `SLOT`: stalk → nickel-defender

## Notes

Companion play to inside zone. OL all step playside as a unit; HB stretches
the run to the perimeter and reads the EDGE block. The bootleg PA off this
look is one of the most lethal tendency-breakers in football.
