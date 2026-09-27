# Recreate "RPO Slant (Strong)" in `madden-05-ps2`

**Formation:** `shotgun-2x2`  •  **Type:** rpo  •  **Ball carrier:** QB
**Snap rule:** integer cells only

## Read tree

- **Primary:** `Z`

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

## Step 2 — draw routes

| Player | Route | Depth | Waypoints (cells) | Notes |
|--------|-------|-------|-------------------|-------|
| `X` | clear-out-go | 18 yd | (1, 5) → (1, 18) | Backside clear-out — pull weak-side corner deep. |
| `Z` ★ | slant | 5 yd | (18, 4) → (18, 5) → (16, 7) | Strong-side slant — RPO primary throw. Breaks at 5 yds, runs through the soft sp |

## Step 3 — QB drop / handoff path

`QB`: (10, 2) → (11, 2) → (10, 2)

## Step 4 — ball-carrier / lead-block paths

- `HB` (ball_carrier): (9, 2) → (8, 2) → (8, 3) → (9, 5)
  - Step to mesh at (-1,-1), take handoff, attack playside A/B gap. If QB pulls and throws, HB has executed his fake.

## Step 5 — blocking assignments

- `LT`: zone-step-playside
  - Run block — OL stays at LOS (RPO: no downfield release).
- `LG`: zone-combo
- `C`: zone-combo
- `RG`: zone-combo
- `RT`: zone-combo
- `TE`: zone-step-playside → edge-defender
- `SLOT-W`: stalk
  - Weak-side slot stalk-blocks if QB hands off; otherwise becomes outlet.

## Notes

RPO = Run-Pass Option. Same play architecture as Pistol RPO Bubble but
with a slant route instead of a bubble. Slant favors a quick-throw
rhythm; bubble favors a horizontal stretch. Choose based on defensive
apex / nickel tendencies.
