# Universal Football Coordinate System

All formations, plays, routes, and player positions in `blitz-command` use a single coordinate system, independent of any game's editor grid. Per-game **translation profiles** convert these coordinates to each title's editor units. This document is the spec.

## Axes

| Axis | Meaning | Sign |
|------|---------|------|
| X    | Field width (sideline to sideline) | Positive = offense's right, negative = offense's left |
| Y    | Field depth (LOS to end zones)     | Positive = downfield (toward defensive end zone), negative = offensive backfield |

## Origin

The origin `(0, 0)` is the **center of the football at the line of scrimmage** (LOS).

- The center's hands are at the origin at the snap.
- The LOS itself is `y = 0`.
- Anything in front of the LOS (defense's side) has `y > 0`.
- Anything behind the LOS (offense's side) has `y < 0`.

Because positions are stored relative to the ball, formation coordinates do not change when the LOS moves up or down the field, or when the ball is on a hash mark vs. centered.

## Units

Real **yards**. A halfback 7 yards behind the LOS is `y = -7`. A receiver split 15 yards from the ball is `x = ±15`.

Sub-yard precision is fine; use as many decimal places as the situation needs (e.g. `x = 0.67` for a guard's typical split from center).

## Field bounds

| Measurement | Value |
|-------------|-------|
| Width (sideline to sideline) | 53⅓ yards (160 ft) |
| Length between goal lines    | 100 yards |
| End zone depth               | 10 yards |
| Total field length           | 120 yards |

When the ball is centered between the sidelines, the X range available to players is approximately `[-26.67, +26.67]`. When the ball is on a hash mark, that range shifts asymmetrically; the universal system still describes positions relative to the ball, so no formation coordinates change — only the practical room before a player runs out of bounds.

## Hash marks

| Code | Hash spacing | Hash to nearest sideline |
|------|--------------|--------------------------|
| NFL  | 18 ft 6 in (≈ 6.17 yd) | ~70 ft 9 in (≈ 23.58 yd) |
| NCAA | 40 ft (≈ 13.33 yd) | ~60 ft (≈ 20.0 yd) |
| HS   | 53 ft 4 in (≈ 17.78 yd) | ~53 ft 4 in (≈ 17.78 yd) |

Hash placement matters for play design (the wide "field" side has more room than the short "boundary" side) but does not change the coordinate system itself.

## Conventions for player records

Every player in a formation file carries:

- `x`, `y` — universal coordinates, in yards
- `on_line` — boolean, whether the player is on the LOS

Legality check: an offensive formation must have **exactly 7 players with `on_line: true`** (typically 5 OL + TE + one WR; a TE off the line means a WR must come on, etc.).

## Translation to a game grid

Each game in `data/games/` has an editor profile that validates against `schemas/coordinate-map.schema.json`. A profile defines:

- grid dimensions (cells)
- where universal `(0, 0)` lands on that grid
- yards per grid cell in X and Y
- editor limits (max route depth, max split, allowed motion, etc.)
- known engine quirks

The translator (in `tools/`) takes a universal `(x, y)` plus a profile and returns the editor-grid coordinate, plus warnings when the position falls outside what the editor can represent.

## Source data

Concrete numeric values used by the system live in `data/measurements/field-dimensions.yaml` so they can be referenced programmatically. This document is the human-readable spec; the YAML is the machine-readable source of truth.
