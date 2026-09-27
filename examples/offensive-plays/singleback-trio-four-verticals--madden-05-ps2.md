# Recreate "Four Verticals" in `madden-05-ps2`

**Formation:** `singleback-trio`  •  **Type:** pass  •  **Ball carrier:** QB
**Snap rule:** integer cells only

## Read tree

- **Primary:** `SLOT`
- **Secondary:** `TE`
- **Tertiary:** `Z`
- **Checkdown:** `HB`

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

## Step 2 — draw routes

| Player | Route | Depth | Waypoints (cells) | Notes |
|--------|-------|-------|-------------------|-------|
| `TE` | seam | 16 yd | (12, 5) → (12, 9) → (11, 13) | TE pushes vertical at 16 yds, then bends into the strong-side seam (between hash |
| `X` | go | 25 yd | (1, 5) → (1, 18) | Outside vertical — stay 2 yds inside the sideline. |
| `Z` | go | 25 yd | (17, 4) → (17, 17) | Outside vertical — stay 2 yds inside the sideline. |
| `SLOT` ★ | seam | 16 yd | (5, 4) → (5, 8) → (6, 12) | SLOT pushes vertical and works into the weak-side seam. Primary read against sin |

## Step 3 — QB drop / handoff path

`QB`: (10, 4) → (10, 3) → (10, 2)

## Step 4 — blocking assignments

- `LT`: max-protection
- `LG`: max-protection
- `C`: max-protection
- `RG`: max-protection
- `RT`: max-protection
- `HB`: man-protection
  - Stay in for max-protection; release only if uncovered.

## Notes

Four Verticals is an answer to single-high coverage. The two seam routes
(TE strong-side, SLOT weak-side) split the deep middle, while the outside
go routes pin the corners. Against cover-3, the SLOT seam between the FS
and the playside hook defender is the kill shot. Against cover-1, the
SLOT just runs past the FS.
