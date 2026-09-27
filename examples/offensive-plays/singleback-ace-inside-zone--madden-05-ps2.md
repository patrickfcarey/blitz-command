# Recreate "Inside Zone" in `madden-05-ps2`

**Formation:** `singleback-ace`  •  **Type:** run  •  **Ball carrier:** HB
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
| `X` | (1, 4) | WR | no | (-15.0, -1.0) |
| `Z` | (19, 4) | WR | no | (15.0, -1.0) |
| `QB` | (10, 4) | QB | no | (0.0, -2.0) |
| `HB` | (10, 2) | HB | no | (0.0, -6.0) |

## Step 2 — QB drop / handoff path

`QB`: (10, 4) → (9, 4) → (9, 3)

## Step 3 — ball-carrier / lead-block paths

- `HB` (ball_carrier): (10, 2) → (11, 4) → (12, 6)
  - BANG/BEND/BOUNCE per inside zone rules; aim point is playside A or B gap.

## Step 4 — blocking assignments

- `LT`: zone-step-playside
- `LG`: zone-combo
- `C`: zone-combo → 0-or-1-tech
- `RG`: zone-combo → 3-tech-then-PSLB
- `RT`: zone-combo
- `TE-L`: backside-zone-step
  - Backside TE — zone step; helps seal cutback.
- `TE-R`: zone-step-playside → edge-defender
  - Playside TE — seal the edge.
- `X`: stalk → cornerback
- `Z`: stalk → cornerback

## Notes

Inside Zone from the 12-personnel symmetric singleback. With 2 TEs flanking,
both edges have a sealing blocker. HB reads playside DT/G combo and takes
bang/bend/bounce per standard IZ rules.
