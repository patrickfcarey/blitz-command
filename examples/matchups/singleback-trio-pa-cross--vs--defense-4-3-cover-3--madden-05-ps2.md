# Matchup: `singleback-trio-pa-cross` vs `defense-4-3-cover-3`

**Rating:** neutral  •  **Best read:** TE

**Rationale:** Play's best_vs_defense matches: ['cover-3 with run-fit LBs (PA holds them, TE drag underneath, X cross over)', 'any defense aggressively run-fitting after IZ/OZ tendency established'] | Play's worst_vs_defense matches: ['pass-only defenses ignoring PA'] | Defense's vulnerable_to matches play type/tags: ["RPO bubble (apex-conflict — SS can't be in run-fit AND flat)"] | Defense's best_against matches play type/tags: ['PA shots (single-high stays back)']

---

# Recreate "PA Cross" in `madden-05-ps2`

**Formation:** `singleback-trio`  •  **Type:** play-action  •  **Ball carrier:** QB
**Snap rule:** integer cells only

## Read tree

- **Primary:** `TE`
- **Secondary:** `X`
- **Tertiary:** `Z`
- **Checkdown:** `SLOT`

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
| `TE` ★ | drag | 8 yd | (12, 5) → (12, 8) → (0, 8) | Strong-side TE delays one count (sells block), then drag at 8 yds. Primary read  |
| `X` | deep-cross | 18 yd | (1, 5) → (1, 14) → (14, 14) | Backside X runs deep cross at 18 yds — secondary read; opens late if FS bites TE |
| `Z` | post | 16 yd | (17, 4) → (17, 10) → (15, 13) | Strong-side Z post — pulls FS away from middle so X cross is open. |
| `SLOT` | flat | 4 yd | (5, 4) → (2, 6) | Quick flat — checkdown / hot read vs blitz. |

## Step 3 — QB drop / handoff path

`QB`: (10, 4) → (9, 4) → (10, 2) → (10, 2)

## Step 4 — blocking assignments

- `LT`: man-protection
  - Sell run-block 1 count, then pass-set.
- `LG`: man-protection
  - Sell run-block 1 count, then pass-set.
- `C`: man-protection
  - Sell run-block 1 count, then pass-set.
- `RG`: man-protection
  - Sell run-block 1 count, then pass-set.
- `RT`: man-protection
  - Sell run-block 1 count, then pass-set.
