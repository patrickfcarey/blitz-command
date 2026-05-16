# Matchup: `i-formation-power-o` vs `defense-4-2-5-cover-2`

**Rating:** neutral  •  **Best read:** None

**Rationale:** Play's best_vs_defense matches: ['any defense with predictable LB flow'] | Defense's vulnerable_to matches play type/tags: ['Heavy run formations (only 6 in the box pre-snap)'] | Defense's best_against matches play type/tags: ['RPO concepts (NB is a true coverage defender, not LB in conflict)']

---

# Recreate "Power O (Strong)" in `madden-05-ps2`

**Formation:** `i-formation`  •  **Type:** run  •  **Ball carrier:** HB
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
| `QB` | (10, 4) | QB | no | (0.0, -2.0) |
| `FB` | (10, 3) | FB | no | (0.0, -4.5) |
| `HB` | (10, 2) | HB | no | (0.0, -7.0) |

## Step 2 — set motion

- `Z` — short-across (optional) to cell (5, 4)
  - Z shifts to weak-side slot to occupy the backside safety.

## Step 3 — QB drop / handoff path

`QB`: (10, 4) → (9, 4) → (9, 4)

## Step 4 — ball-carrier / lead-block paths

- `FB` (lead_block): (10, 3) → (12, 4) → (12, 6)
  - Lead through the hole; isolate the playside LB or kickout the strong safety.
- `HB` (ball_carrier): (10, 2) → (12, 3) → (12, 6)
  - Take the handoff, hit the off-tackle hole, follow the pulling LG.

## Step 5 — blocking assignments

- `LT`: down-block → backside-3-tech
  - Down block on the backside DT; create the backside hinge.
- `LG`: pull-around → playside-LB
  - Pull around the C, lead through the hole, kickout or wrap on the playside LB.
- `C`: gap-block → backside-A-gap
  - Help LG with backside scoop, then climb to the backside LB.
- `RG`: down-block → playside-DT
- `RT`: down-block → playside-5-tech
  - Down block on the playside DE / 5-tech to seal the C-gap.
- `TE`: kickout → edge-defender
  - Kick the EDGE defender out — creates the off-tackle hole.
- `X`: stalk → cornerback
- `Z`: stalk → cornerback

## Notes

Canonical Power play. The "O" suffix denotes the Off-tackle hole (between
the playside tackle and TE). Some teams call this "Power" or "Counter Lead";
the difference is in pull mechanics — true Counter has the BACKSIDE guard
and tackle (or TE) pulling, while Power has only the backside guard pulling.
