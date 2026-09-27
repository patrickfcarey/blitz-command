# Matchup: `singleback-trio-stick` vs `defense-4-3-cover-3`

**Rating:** neutral  •  **Best read:** SLOT

**Rationale:** Play's best_vs_defense matches: ['cover-3 (sit between the curl and flat defender)', 'any defense with predictable underneath spacing'] | Play's worst_vs_defense matches: ['any defense with a hot underneath defender on the slot'] | Defense's vulnerable_to matches play type/tags: ["RPO bubble (apex-conflict — SS can't be in run-fit AND flat)"]

---

# Recreate "Stick (Strong)" in `madden-05-ps2`

**Formation:** `singleback-trio`  •  **Type:** pass  •  **Ball carrier:** QB
**Snap rule:** integer cells only

## Read tree

- **Primary:** `SLOT`
- **Secondary:** `TE`
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

## Step 2 — set motion

- `SLOT` — short-across (mandatory) to cell (14, 4)
  - SLOT motions across to become the strong-side inner slot at snap.

## Step 3 — draw routes

| Player | Route | Depth | Waypoints (cells) | Notes |
|--------|-------|-------|-------------------|-------|
| `TE` | flat | 3 yd | (12, 5) → (15, 6) | TE releases to the strong-side flat as the LO option. |
| `X` | comeback | 14 yd | (1, 5) → (1, 12) → (0, 11) | Backside comeback for late-window throw if strong-side covered. |
| `Z` | clear-out-go | 25 yd | (17, 4) → (17, 17) | Vertical to clear the strong-side corner out of the stick window. |
| `SLOT` ★ | stick | 6 yd | (5, 4) → (5, 8) | Option route: push to 6 yds and: |

## Step 4 — QB drop / handoff path

`QB`: (10, 4) → (10, 4) → (10, 3)

## Step 5 — blocking assignments

- `LT`: man-protection
- `LG`: man-protection
- `C`: man-protection
- `RG`: man-protection
- `RT`: man-protection
- `HB`: man-protection
  - Pass-protect; release as checkdown only if pressure clears.

## Notes

Stick is an option route — the slot reads coverage and either sits (vs
zone) or breaks out (vs man). The mandatory SLOT motion across creates
a strong-side stick concept; without the motion the play would have to
fire to the weak-side slot.
