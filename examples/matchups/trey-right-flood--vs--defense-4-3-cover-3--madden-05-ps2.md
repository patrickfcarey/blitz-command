# Matchup: `trey-right-flood` vs `defense-4-3-cover-3`

**Rating:** best  •  **Best read:** TE-R

**Rationale:** Play's best_vs_defense matches: ['cover-3 (the textbook beater)', 'base 4-3 / 3-4 (matchup advantages on TE-R)', 'any zone defense rotating to trey side'] | Defense's vulnerable_to matches play type/tags: ['Flood / sail concepts (3-on-2 stretch on the underneath defenders)', "RPO bubble (apex-conflict — SS can't be in run-fit AND flat)"]

---

# Recreate "Flood (Trey Right)" in `madden-05-ps2`

**Formation:** `trey-right`  •  **Type:** pass  •  **Ball carrier:** QB
**Snap rule:** integer cells only

## Read tree

- **Primary:** `TE-R`
- **Secondary:** `Z`
- **Checkdown:** `SLOT`

## Step 1 — set player cells

| Player | Cell (col, row) | Position | On line | Universal yds |
|--------|-----------------|----------|---------|---------------|
| `LT` | (8, 5) | LT | yes | (-2.0, 0.0) |
| `LG` | (9, 5) | LG | yes | (-1.0, 0.0) |
| `C` | (10, 5) | C | yes | (0.0, 0.0) |
| `RG` | (12, 5) | RG | yes | (1.0, 0.0) |
| `RT` | (13, 5) | RT | yes | (2.0, 0.0) |
| `TE-L` | (7, 5) | TE | yes | (-3.5, 0.0) |
| `TE-R` | (14, 5) | TE | yes | (3.5, 0.0) |
| `Z` | (19, 4) | WR | no | (15.0, -1.0) |
| `SLOT` | (15, 4) | WR | no | (9.0, -1.0) |
| `QB` | (11, 4) | QB | no | (0.0, -1.5) |
| `HB` | (10, 2) | HB | no | (0.0, -6.0) |

## Step 2 — draw routes

| Player | Route | Depth | Waypoints (cells) | Notes |
|--------|-------|-------|-------------------|-------|
| `TE-L` | drag | 5 yd | (8, 5) → (8, 8) → (20, 8) | Backside drag — late outlet if flood bracketed. |
| `TE-R` ★ | sail | 12 yd | (12, 5) → (12, 11) → (14, 12) | TE-R sails out at 12 yards — the intermediate level. Primary read. |
| `Z` | clear-out-go | 25 yd | (19, 4) → (19, 17) | Strong outer Z: deep clear — pulls the corner/safety out of the flood. |
| `SLOT` | flat | 3 yd | (15, 4) → (18, 6) | Strong inner slot: shoot to the flat. The LO of the 3-level stretch. |

## Step 3 — QB drop / handoff path

`QB`: (10, 4) → (10, 3) → (10, 2)

## Step 4 — blocking assignments

- `LT`: man-protection
- `LG`: man-protection
- `C`: man-protection
- `RG`: man-protection
- `RT`: man-protection
- `HB`: man-protection
  - Pass-protect against weak-side blitz; stays in unless pressure clears.

## Notes

Same flood structure as Shotgun Trips Right Flood, but with TE-R as the
sail receiver instead of a pure WR. The TE-R matchup advantage (vs LB
or nickel) plus the 12-personnel run threat makes this a high-leverage
call.
