# Recreate "Mesh" in `madden-05-ps2`

**Formation:** `singleback-trio`  •  **Type:** pass  •  **Ball carrier:** QB
**Snap rule:** integer cells only

## Read tree

- **Primary:** `TE`
- **Secondary:** `SLOT`
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

- `SLOT` — short-across (optional) to cell (13, 4)
  - Optional: tighten the mesh point by motioning SLOT toward strong side.

## Step 3 — draw routes

| Player | Route | Depth | Waypoints (cells) | Notes |
|--------|-------|-------|-------------------|-------|
| `TE` ★ | drag | 6 yd | (12, 5) → (12, 8) → (0, 8) | Drag from strong-to-weak at 6 yards; meets SLOT around the C — that's the mesh p |
| `X` | comeback | 14 yd | (1, 5) → (1, 12) → (0, 11) | Backside comeback — opens late if mesh is covered. |
| `Z` | clear-out-go | 25 yd | (17, 4) → (17, 17) | Vertical clear-out to remove the playside corner from the mesh window. |
| `SLOT` | drag | 6 yd | (5, 4) → (5, 7) → (17, 7) | Drag from weak-to-strong at 6 yards; passes underneath TE at the mesh point. |

## Step 4 — QB drop / handoff path

`QB`: (10, 4) → (10, 3) → (10, 2)

## Step 5 — blocking assignments

- `LT`: man-protection
- `LG`: man-protection
- `C`: man-protection
- `RG`: man-protection
- `RT`: man-protection
- `HB`: man-protection
  - Pass-protect first; release as a checkdown if pressure clears.

## Notes

Two drag routes from opposite sides cross at the same depth (~5 yds) in
the middle of the field — the "mesh point." Crossing receivers can rub
each other (legal pick) or pass close enough to act as a natural pick on
man defenders. Read tree puts TE first because he's coming open into the
QB's face from the strong side.
