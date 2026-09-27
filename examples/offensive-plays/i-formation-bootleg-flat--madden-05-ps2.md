# Recreate "Bootleg Flat" in `madden-05-ps2`

**Formation:** `i-formation`  •  **Type:** play-action  •  **Ball carrier:** QB
**Snap rule:** integer cells only

## Read tree

- **Primary:** `TE`
- **Secondary:** `FB`
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
| `QB` | (10, 4) | QB | no | (0.0, -2.0) |
| `FB` | (10, 3) | FB | no | (0.0, -4.5) |
| `HB` | (10, 2) | HB | no | (0.0, -7.0) |

## Step 2 — draw routes

| Player | Route | Depth | Waypoints (cells) | Notes |
|--------|-------|-------|-------------------|-------|
| `TE` ★ | drag | 8 yd | (12, 5) → (12, 8) → (0, 8) | TE crosses at 8–10 yards; QB throws on the move. |
| `X` | comeback | 14 yd | (1, 5) → (1, 12) → (0, 11) |  |
| `Z` | deep-cross | 18 yd | (17, 4) → (17, 14) → (4, 14) | Z runs a deep cross strong-to-weak — the kill shot if the safety bites on the fa |
| `FB` | flat | 3 yd | (10, 3) → (7, 4) | FB chip-releases to the bootleg-side flat as the checkdown. |

## Step 3 — QB drop / handoff path

`QB`: (10, 4) → (8, 4) → (7, 4) → (6, 4)

## Step 4 — blocking assignments

- `LT`: half-roll-protection
  - Slide protection toward the bootleg side.
- `LG`: half-roll-protection
- `C`: half-roll-protection
- `RG`: half-roll-protection
- `RT`: half-roll-protection
  - Backside RT — releases late as the QB clears, scoops backside contain if possible.

## Notes

Mirror to bootleg right by flipping all coordinates. QB leaves the pocket
toward the side opposite the run fake. TE drag is the bread-and-butter
read; the deep cross from Z is the kill shot if the safety bites.
