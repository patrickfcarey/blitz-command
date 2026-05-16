# Matchup: `singleback-trio-hb-draw` vs `defense-4-3-cover-2`

**Rating:** neutral  •  **Best read:** None

**Rationale:** Play's best_vs_defense matches: ['cover-2/3 with LBs in deep drops', 'pass-rushing 4-3'] | Defense's vulnerable_to matches play type/tags: ['Heavy run sets — only 7 in box if both safeties stay deep'] | Defense's best_against matches play type/tags: ['Outside running plays (corners run-support)']

---

# Recreate "Singleback Trio HB Draw" in `madden-05-ps2`

**Formation:** `singleback-trio`  •  **Type:** run  •  **Ball carrier:** HB
**Snap rule:** integer cells only

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
| `TE` | drag | 8 yd | (12, 5) → (12, 8) → (0, 8) | TE releases as window-dressing pass route. |
| `X` | clear-out-go | 22 yd | (1, 5) → (1, 18) | Clear-out fly — pulls weak-side corner deep. |
| `Z` | clear-out-go | 22 yd | (17, 4) → (17, 17) | Clear-out fly — pulls strong-side corner deep. |
| `SLOT` | comeback | 12 yd | (5, 4) → (5, 12) → (4, 10) | Slot comeback — sells full-pass concept. |

## Step 3 — QB drop / handoff path

`QB`: (10, 4) → (10, 3) → (10, 2)

## Step 4 — ball-carrier / lead-block paths

- `HB` (ball_carrier): (10, 2) → (10, 2) → (11, 4) → (11, 7)
  - Pass-set look for 1 count, take handoff at -5 depth, hit playside A/B gap.

## Step 5 — blocking assignments

- `LT`: invite-rusher
  - Pass-set initially (3-4 steps), then drive-block once HB takes the handoff.
- `LG`: invite-rusher
- `C`: invite-rusher
- `RG`: invite-rusher
- `RT`: invite-rusher
