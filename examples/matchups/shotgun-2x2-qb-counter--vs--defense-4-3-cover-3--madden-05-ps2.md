# Matchup: `shotgun-2x2-qb-counter` vs `defense-4-3-cover-3`

**Rating:** neutral  •  **Best read:** None

**Rationale:** Play's best_vs_defense matches: ['cover-3 with run-fit LBs', '4-3 base with predictable EDGE / over-front', 'any defense over-pursuing the HB (zone-read tendency)'] | Defense's vulnerable_to matches play type/tags: ["RPO bubble (apex-conflict — SS can't be in run-fit AND flat)"] | Defense's best_against matches play type/tags: ['Inside running concepts (dive, ISO, power)']

---

# Recreate "QB Counter (Strong)" in `madden-05-ps2`

**Formation:** `shotgun-2x2`  •  **Type:** run  •  **Ball carrier:** QB
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
| `SLOT-W` | (5, 4) | WR | no | (-8.0, -1.0) |
| `Z` | (18, 4) | WR | no | (14.0, -1.0) |
| `QB` | (10, 2) | QB | no | (0.0, -5.0) |
| `HB` | (9, 2) | HB | no | (-2.5, -5.0) |

## Step 2 — QB drop / handoff path

`QB`: (10, 2) → (9, 2) → (12, 4) → (12, 6)

## Step 3 — ball-carrier / lead-block paths

- `HB` (fake): (9, 2) → (8, 2) → (7, 2)
  - Sell a backside zone-read fake — holds backside DE and LBs from chasing the QB run.

## Step 4 — blocking assignments

- `LT`: pull-around → edge-defender
  - PULL — backside tackle pulls and kicks out the playside EDGE.
- `LG`: pull-around → playside-LB
  - PULL — backside guard pulls around C, leads through the off-tackle hole on the playside ILB.
- `C`: gap-block → backside-A-gap
- `RG`: down-block → playside-3-tech
- `RT`: down-block → playside-DT
- `TE`: down-block → playside-LB
  - TE down-blocks at the second level.
- `X`: stalk → backside-cornerback
- `Z`: stalk → playside-cornerback
- `SLOT-W`: stalk → nickel-defender

## Notes

QB Counter is the modern designed QB run — counter-trey blocking scheme
(BST kickout + BSG lead) with the QB as the ball-carrier instead of
the HB. HB executes a fake to hold the backside of the defense,
but there's no real give read — this is a designed-QB-run.

Best with mobile QB. Mirror by flipping all x.
