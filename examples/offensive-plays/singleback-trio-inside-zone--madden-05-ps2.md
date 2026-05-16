# Recreate "Inside Zone" in `madden-05-ps2`

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

`QB`: (10, 4) → (9, 4) → (9, 3)

## Step 3 — ball-carrier / lead-block paths

- `HB` (ball_carrier): (10, 2) → (11, 4) → (12, 6)
  - Aim point is the playside A or B gap (terminology varies — Shanahan-tree
tradition uses B-gap, others use A). Read the playside DT/G combo:
- BANG (playside A or B gap) if the playside DT is reached cleanly
- BEND (cut back behind C / backside G) if DT sheds playside
- BOUNCE (outside the playside tackle) if the front crashes inside


## Step 4 — blocking assignments

- `LT`: zone-step-playside
  - Backside tackle: zone step playside; if uncovered, climb to backside LB.
- `LG`: zone-combo → backside-DT-then-LB
  - Combo with C on backside DT, climb when DT secured.
- `C`: zone-combo → 0-or-1-tech
  - Combo with LG (or RG depending on shade) on the playside or backside DT.
- `RG`: zone-combo → 3-tech-then-PSLB
  - Combo with RT on playside DT, climb to playside LB.
- `RT`: zone-combo → 3-tech-or-EDGE
- `TE`: zone-step-playside → edge-defender
- `X`: stalk → cornerback
- `Z`: stalk → cornerback
- `SLOT`: stalk → nickel-defender

## Notes

The "rules-based" run play. Every OL has a zone step and a defender to
account for, but no individual defender must be blocked specifically. HB
reads the playside guard/tackle combo to pick his lane. The bang/bend/
bounce decision is the hallmark of inside zone.
