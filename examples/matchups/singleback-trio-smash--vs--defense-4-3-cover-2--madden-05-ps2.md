# Matchup: `singleback-trio-smash` vs `defense-4-3-cover-2`

**Rating:** neutral  •  **Best read:** SLOT

**Rationale:** Play's best_vs_defense matches: ['cover-2 (the textbook beater)', 'cover-2 invert', 'any defense with a flat-zone corner'] | Play's worst_vs_defense matches: ['cover-2 robber'] | Defense's vulnerable_to matches play type/tags: ["Smash concept (hi-lo on the corner — corner CAN'T cover both)"]

---

# Recreate "Smash (Weak)" in `madden-05-ps2`

**Formation:** `singleback-trio`  •  **Type:** pass  •  **Ball carrier:** QB
**Snap rule:** integer cells only

## Read tree

- **Primary:** `SLOT`
- **Secondary:** `X`
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
| `TE` | drag | 5 yd | (12, 5) → (12, 8) → (0, 8) | Strong-side drag — backside outlet. |
| `X` | hitch | 6 yd | (1, 5) → (1, 8) | The LO of the hi-lo: hitch at 6 yards. |
| `Z` | comeback | 14 yd | (17, 4) → (17, 12) → (18, 10) | Strong-side comeback; opens if defense rotates weak. |
| `SLOT` ★ | corner | 12 yd | (5, 4) → (5, 10) → (3, 13) | The HI of the hi-lo: 12-yard corner route over the X hitch. Primary read. Some t |

## Step 3 — QB drop / handoff path

`QB`: (10, 4) → (10, 3) → (10, 2)

## Step 4 — blocking assignments

- `LT`: man-protection
- `LG`: man-protection
- `C`: man-protection
- `RG`: man-protection
- `RT`: man-protection
- `HB`: man-protection
  - Pass-protect; release as checkdown if pressure clears.

## Notes

Smash is a Hi-Lo concept on the playside corner: a hitch at 6 yards
beneath a corner route at 14 yards. With my SLOT on the weak side,
this fires to the WEAK side without motion (X hitch + SLOT corner).
Strong-side smash would need the SLOT to motion across, OR run with
TE corner over Z hitch (in-line TE running corner is tighter).
