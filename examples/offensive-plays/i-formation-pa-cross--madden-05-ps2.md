# Recreate "Play-Action Y-Cross" in `madden-05-ps2`

**Formation:** `i-formation`  •  **Type:** play-action  •  **Ball carrier:** QB
**Snap rule:** integer cells only

## Read tree

- **Primary:** `TE`
- **Secondary:** `Z`
- **Checkdown:** `FB`

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

## Step 2 — set motion

- `Z` — short-across (optional) to cell (5, 4)
  - Optional motion to constrain the safety; can also reveal coverage rotation.

## Step 3 — draw routes

| Player | Route | Depth | Waypoints (cells) | Notes |
|--------|-------|-------|-------------------|-------|
| `TE` ★ | deep-cross | 18 yd | (12, 5) → (12, 14) → (-1, 14) | Y-Cross: TE breaks across the field at 18 yards; throw on the move toward the op |
| `X` | comeback | 14 yd | (1, 5) → (1, 12) → (0, 11) |  |
| `Z` | post | 16 yd | (17, 4) → (17, 10) → (15, 13) | Post route forces the FS to choose between Z and the TE crossing. |
| `FB` | flat | 4 yd | (10, 3) → (7, 4) | FB releases to the strong-side flat as the checkdown. |

## Step 4 — QB drop / handoff path

`QB`: (10, 4) → (9, 4) → (10, 2) → (10, 2)

## Step 5 — blocking assignments

- `LT`: man-protection
- `LG`: man-protection
- `C`: man-protection
- `RG`: man-protection
- `RT`: man-protection

## Notes

Y-Cross is a Coryell concept: the TE (Y) runs a deep crossing route that
breaks at 18 yards, paired with a backside post (Z) to force the safety to
pick. Bootleg version of this play has the QB rolling out instead of
dropping back; see i-formation-bootleg-flat.yaml for the rollout cousin.
