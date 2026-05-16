# Recreate "Snag (Trips Right)" in `madden-05-ps2`

**Formation:** `shotgun-trips-right`  •  **Type:** pass  •  **Ball carrier:** QB
**Snap rule:** integer cells only

## Read tree

- **Primary:** `WR2`
- **Secondary:** `WR1`
- **Checkdown:** `WR3`

## Step 1 — set player cells

| Player | Cell (col, row) | Position | On line | Universal yds |
|--------|-----------------|----------|---------|---------------|
| `LT` | (8, 5) | LT | yes | (-2.0, 0.0) |
| `LG` | (9, 5) | LG | yes | (-1.0, 0.0) |
| `C` | (10, 5) | C | yes | (0.0, 0.0) |
| `RG` | (11, 5) | RG | yes | (1.0, 0.0) |
| `RT` | (12, 5) | RT | yes | (2.0, 0.0) |
| `TE` | (7, 5) | TE | yes | (-3.5, 0.0) |
| `WR1` | (19, 5) | WR | yes | (15.0, 0.0) |
| `WR2` | (16, 4) | WR | no | (10.0, -1.0) |
| `WR3` | (13, 4) | WR | no | (5.0, -1.0) |
| `QB` | (10, 2) | QB | no | (0.0, -5.0) |
| `HB` | (9, 2) | HB | no | (-2.5, -5.0) |

## Step 2 — draw routes

| Player | Route | Depth | Waypoints (cells) | Notes |
|--------|-------|-------|-------------------|-------|
| `TE` | drag | 5 yd | (8, 5) → (8, 8) → (20, 8) | Backside TE drag — outlet if trips side fully covered. |
| `WR1` | snag | 5 yd | (19, 5) → (19, 8) | Outer trips WR: shallow snag — settle vs zone (sit in soft spot), work back to s |
| `WR2` ★ | corner | 12 yd | (16, 4) → (16, 10) → (18, 13) | Middle trips WR: 12-yd corner — the HI of the snag triangle. Primary read. |
| `WR3` | flat | 3 yd | (13, 4) → (16, 6) | Inner trips WR: shoot to the flat. The LO that puts the flat defender in conflic |

## Step 3 — QB drop / handoff path

`QB`: (10, 2) → (10, 2) → (10, 2)

## Step 4 — blocking assignments

- `LT`: man-protection
- `LG`: man-protection
- `C`: man-protection
- `RG`: man-protection
- `RT`: man-protection
- `HB`: man-protection
  - Pass-protect against weak-side blitz; stays in unless pressure clears.

## Notes

Snag from a true trips formation creates a true 3-on-2 underneath stretch.
Some teams swap the routes (outer runs corner, middle runs snag) — the
important thing is one route at each level (deep, middle, short) on the
trips side. With WR1 on the line and WR2/WR3 off, this configuration is
spacing-correct without motion.
