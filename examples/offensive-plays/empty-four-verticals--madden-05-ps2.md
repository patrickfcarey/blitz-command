# Recreate "Empty Four Verticals" in `madden-05-ps2`

**Formation:** `empty`  •  **Type:** pass  •  **Ball carrier:** QB
**Snap rule:** integer cells only

## Read tree

- **Primary:** `SLOT-L`
- **Secondary:** `TE`
- **Tertiary:** `Z`
- **Checkdown:** `SLOT-R`

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
| `Z` | (18, 4) | WR | no | (14.0, -1.0) |
| `SLOT-L` | (5, 4) | WR | no | (-8.0, -1.0) |
| `SLOT-R` | (15, 4) | WR | no | (8.0, -1.0) |
| `QB` | (10, 2) | QB | no | (0.0, -5.0) |

## Step 2 — draw routes

| Player | Route | Depth | Waypoints (cells) | Notes |
|--------|-------|-------|-------------------|-------|
| `TE` | seam | 16 yd | (12, 5) → (12, 9) → (11, 13) | TE works into the strong-side seam (between hash and numbers). |
| `X` | go | 25 yd | (1, 5) → (1, 18) | Outer-left vertical 2 yds inside sideline. |
| `Z` | go | 25 yd | (18, 4) → (18, 17) | Outer-right vertical 2 yds inside sideline. |
| `SLOT-L` | seam | 16 yd | (5, 4) → (5, 8) → (6, 12) | SLOT-L works into weak-side seam — primary read vs single-high. |
| `SLOT-R` | seam | 14 yd | (15, 4) → (15, 8) → (14, 12) | SLOT-R works into the strong-side seam (option route inside). |

## Step 3 — QB drop / handoff path

`QB`: (10, 2) → (10, 2) → (10, 2)

## Step 4 — blocking assignments

- `LT`: max-protection
- `LG`: max-protection
- `C`: max-protection
- `RG`: max-protection
- `RT`: max-protection
