# Recreate "Power O (Strong)" in `madden-05-ps2`

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

`QB`: (10, 4) → (9, 4) → (9, 4)

## Step 3 — ball-carrier / lead-block paths

- `HB` (ball_carrier): (10, 2) → (12, 3) → (12, 6)
  - Take handoff at depth, hit off-tackle hole between RT and TE-R,
follow pulling LG through to the second level. No FB lead in this
12P version — pulling LG IS the lead blocker.


## Step 4 — blocking assignments

- `LT`: down-block → backside-3-tech
- `LG`: pull-around → playside-LB
  - PULL — backside guard pulls around C, leads through the off-tackle hole.
- `C`: gap-block → backside-A-gap
- `RG`: down-block → playside-3-tech
- `RT`: down-block → playside-DT
- `TE-L`: backside-cutoff → backside-edge
  - TE-L cuts off backside; prevents pursuit through the cutback.
- `TE-R`: kickout → edge-defender
  - TE-R kicks out the playside EDGE — opens the off-tackle hole.
- `X`: stalk → cornerback
- `Z`: stalk → cornerback

## Notes

Singleback-ace (12 personnel) version of Power O. Same blocking principles
as the I-Formation Power O but without the FB lead — the pulling LG
becomes the lead blocker. TE-L provides backside cutoff; TE-R kicks out
the playside EDGE.
