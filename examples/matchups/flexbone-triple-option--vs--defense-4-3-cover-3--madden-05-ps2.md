# Matchup: `flexbone-triple-option` vs `defense-4-3-cover-3`

**Rating:** neutral  •  **Best read:** FB

**Rationale:** Play's best_vs_defense matches: ['cover-3 with run-fit ILBs', '4-3 base with predictable EDGE play', 'any defense unprepared for option football', 'speed-flow defenses that over-pursue'] | Play's worst_vs_defense matches: ['disciplined option-fit defenses (academies, prep matters)'] | Defense's vulnerable_to matches play type/tags: ["RPO bubble (apex-conflict — SS can't be in run-fit AND flat)"] | Defense's best_against matches play type/tags: ['Inside running concepts (dive, ISO, power)']

---

# Recreate "Triple Option Veer (Strong)" in `madden-05-ps2`

**Formation:** `flexbone`  •  **Type:** run  •  **Ball carrier:** QB
**Snap rule:** integer cells only

## Read tree

- **Primary:** `FB`

## Step 1 — set player cells

| Player | Cell (col, row) | Position | On line | Universal yds |
|--------|-----------------|----------|---------|---------------|
| `LT` | (8, 5) | LT | yes | (-2.0, 0.0) |
| `LG` | (9, 5) | LG | yes | (-1.0, 0.0) |
| `C` | (10, 5) | C | yes | (0.0, 0.0) |
| `RG` | (11, 5) | RG | yes | (1.0, 0.0) |
| `RT` | (12, 5) | RT | yes | (2.0, 0.0) |
| `TE` | (13, 5) | TE | yes | (3.5, 0.0) |
| `SE` | (1, 5) | WR | yes | (-15.0, 0.0) |
| `QB` | (10, 4) | QB | no | (0.0, -2.0) |
| `FB` | (10, 3) | FB | no | (0.0, -4.5) |
| `SLOT-L` | (6, 4) | HB | no | (-7.0, -1.0) |
| `SLOT-R` | (14, 4) | HB | no | (7.0, -1.0) |

## Step 2 — QB drop / handoff path

`QB`: (10, 4) → (11, 4) → (12, 6) → (13, 6)

## Step 3 — ball-carrier / lead-block paths

- `FB` (ball_carrier): (10, 3) → (10, 4) → (11, 5) → (11, 6)
  - Dive path: receive QB read, hit between RG and RT (B-gap aim point).
- `SLOT-R` (lead_block): (14, 4) → (17, 5) → (18, 6) → (20, 8)
  - Pitch back — runs at full speed, stays 4 yards behind and outside the QB. Receives pitch if QB reads keep-or-pitch correctly.

## Step 4 — blocking assignments

- `LT`: down-block → backside-DT
- `LG`: down-block → backside-1-tech
- `C`: zone-step-playside
- `RG`: zone-combo → 3-tech-then-PSLB
  - Veer combo with RT on playside DT, climb to playside ILB.
- `RT`: zone-combo → 3-tech-or-EDGE
  - Veer combo. PLAYSIDE EDGE IS UNBLOCKED — he is the dive read defender.
- `TE`: zone-step-playside → playside-LB
  - Climb to playside ILB at the second level.
- `SE`: stalk → backside-cornerback
- `SLOT-L`: arc-block → backside-safety
  - Backside slot arcs to seal the FS / backside safety.

## Notes

Flexbone Inside Veer Triple Option. Same triple mechanic as wishbone
triple but with the slot-backs at slot depth (faster pitch + better
arc-block angles). The playside EDGE is the dive read; the playside
force defender is the pitch read. QB makes two decisions in sequence.

Mirror by flipping all x.
