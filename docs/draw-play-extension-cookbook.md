# draw-play extension cookbook

Copy-pasteable patches for the most common changes to `tools/draw-play/draw.py`. Each entry has:

1. **Goal** — what change you're making, in one sentence
2. **Files touched** — every file that changes
3. **Diff** — the actual code change
4. **Test pattern** — where to add a regression test
5. **Pitfalls** — common mistakes

For module-wide architecture, see [`draw-play-architecture.md`](draw-play-architecture.md). For coordinate-system math, see [`draw-play-pipeline.md`](draw-play-pipeline.md). For the public-API contract that other modules rely on, see [`draw-play-consumers.md`](draw-play-consumers.md).

---

## 1. Add a new game profile

**Goal:** support a new game (e.g. `madden-25-ps5`) so plays can be rendered against its editor grid.

**Files touched:**
- `data/games/<game-id>/editor-grid.yaml` — new
- (optional) `tools/draw-play/draw.py:hash_spec_for_profile` — only if the game uses a non-NFL/NCAA/HS hash convention

**YAML template:**

```yaml
# data/games/<game-id>/editor-grid.yaml
game_id: <game-id>
name: "<Display Name>"
release_year: <YYYY>
developer: "<...>"
publisher: "<...>"
platform: <ps2|ps3|ps5|...>
era: <ps2|ps3|ps5|...>
custom_play_support: true
custom_formation_support: false   # most games are false; verify by measurement
grid:
  width: 21          # editor grid columns
  height: 7          # editor grid rows
  origin: { x: 10, y: 5 }   # cell of the LOS center
scale:
  x_yards_per_cell: 1.667    # measure: WR split / cells used
  y_yards_per_cell: 2.0      # measure: backfield depth / cells used
snap_to_cells: true          # null/false for fractional cells
limits:
  max_route_depth_yd: 20
  max_player_split_yd: 15
  max_backfield_depth_yd: 7.5
verification_status: unverified   # "verified" only after physical measurement
```

**Hash override (only if needed):**

```python
# In hash_spec_for_profile() if the game's hash spacing is non-standard:
if game_id.startswith("xfl"):
    return (-XFL_HASH_DIST_YD, XFL_HASH_DIST_YD)
```

Plus a `XFL_HASH_DIST_YD: Final[float] = ...` constant in section 2a.

**Test pattern:**

The `tests/test_draw_unit.py::TestCellAssignment::test_snapping_profiles_no_overlaps_and_integer_cells` test auto-discovers any new profile under `data/games/`. As long as your YAML validates, it's tested. To explicitly verify your new profile is in the sweep:

```bash
python3 -m unittest tests.test_draw_unit -v 2>&1 | grep test_snapping
```

**Pitfalls:**
- `snap_to_cells: null` (YAML for None) is treated as "do not snap." Don't forget to set it explicitly to `true` if you want integer cells.
- The `grid.origin` is in *cells*, not yards. A 21x7 grid with origin (10, 5) puts the LOS at row 5 from the bottom (so 5 cells of backfield) and the ball at column 10 (so 10 cells on each side).
- Measure `scale.x_yards_per_cell` from a known split (e.g. "I see a WR at +15 yd land at column 19") rather than guessing. Off-by-10% scale is the most common bug.
- Add a measurement note in `engine_quirks` so the next person knows where you got the numbers.

---

## 2. Add a new defensive coverage role

**Goal:** support a new coverage variant the renderer should draw distinctly (e.g. `match-zone`, `pattern-match`).

**Files touched:**
- `tools/draw-play/draw.py` — section 3a (enum), section 3b (category), and possibly section 14c (`_zone_drop_geometry`)

**Diff for a zone-family role with hook-like geometry:**

```python
# Section 3a — add to CoverageRole enum
class CoverageRole(str, Enum):
    # ...
    MATCH = "match"   # ← new

# Section 3b — add to ZONE_ROLES (always) and HOOK_LIKE_ROLES (if hook-shaped)
ZONE_ROLES: Final[frozenset[str]] = frozenset({
    # ...
    CoverageRole.MATCH,
})
HOOK_LIKE_ROLES: Final[frozenset[str]] = frozenset({
    # ...
    CoverageRole.MATCH,
})
```

If the new role needs custom drop geometry (different push depth, radius, or color), add a branch to `_zone_drop_geometry`:

```python
def _zone_drop_geometry(role, defender):
    dx, dy = defender["x"], defender["y"]
    if role == CoverageRole.DEEP_ZONE:
        return ((dx, max(dy, DEEP_ZONE_MIN_DEPTH_YD) + DEEP_ZONE_PUSH_YD),
                DEEP_ZONE_RX_YD, DEEP_ZONE_RY_YD, COLOR_DEEP_ZONE)
    if role == CoverageRole.MATCH:   # ← new branch
        return ((dx, max(dy + MATCH_PUSH_YD, MATCH_MIN_DEPTH_YD)),
                MATCH_RX_YD, MATCH_RY_YD, COLOR_MATCH)
    # ...
```

Plus geometry constants in section 2h:

```python
MATCH_PUSH_YD: Final[float] = 4.0
MATCH_MIN_DEPTH_YD: Final[float] = 8.0
MATCH_RX_YD: Final[float] = 5.0
MATCH_RY_YD: Final[float] = 3.0
COLOR_MATCH: Final[str] = "#abc123"   # in section 2i, "Defensive coverage"
```

**Diff for a non-zone role (rush/man/spy variant):**

Just adding the enum member + the matching category set is enough; the dispatcher in `_render_defender_coverage` already routes by category.

```python
class CoverageRole(str, Enum):
    GREEN_DOG = "green-dog"   # blitz variant

RUSH_ROLES: Final[frozenset[str]] = frozenset({
    CoverageRole.RUSH, CoverageRole.BLITZ, CoverageRole.GREEN_DOG,
})
```

**Test pattern:** add a single test in `tests/test_draw_render_components.py::TestDefensiveCoverage`:

```python
def test_match_zone_uses_match_color(self):
    defender = {"label": "MLB", "position": "LB", "x": 0.0, "y": 4.0}
    defense = _defense_with((defender, {"role": "match"}))
    svg, _ = _render(defense=defense)
    self.assertIn(f'fill="{_DRAW.COLOR_MATCH}"', svg)
```

**Pitfalls:**
- A coverage role NOT in any of the four `*_ROLES` sets is silently ignored by the dispatcher — no warning, no draw. If your role doesn't render, check that you added it to the correct category.
- `ZONE_ROLES` ⊇ `HOOK_LIKE_ROLES`. The hook-like set is for "drop X yards behind defender, fixed radius" geometry. Deep zones and flats are zone roles but NOT hook-like.
- Don't add a role to multiple categories — the dispatcher checks them in a fixed order (rush → man → spy → zone) and the first match wins, which can produce surprising precedence.

---

## 3. Add a new offensive assignment role

**Goal:** support a new role string for offensive players (e.g. `motion-block`, `release`).

**Files touched:**
- `tools/draw-play/draw.py` — section 3a (enum), section 12 (`explicit_path_style` dispatch table)

**Diff for a fixed-style role:**

```python
# Section 3a — extend AssignmentRole
class AssignmentRole(str, Enum):
    # ...
    RELEASE = "release"

# Section 12 — add to dispatch table
_SIMPLE_ROLE_STYLES: Final[dict[str, tuple[str, float, str, bool]]] = {
    AssignmentRole.LEAD_BLOCK: (COLOR_FB_LEAD,    STROKE_LEAD_BLOCK, MARKER_FB_LEAD,    False),
    AssignmentRole.FAKE:       (COLOR_FAKE_PATH,  STROKE_FAKE_PATH,  MARKER_FAKE,       True),
    AssignmentRole.PASS_BLOCK: (COLOR_PASS_BLOCK, STROKE_PASS_BLOCK, MARKER_PASS_BLOCK, False),
    AssignmentRole.RELEASE:    (COLOR_RELEASE,    STROKE_RELEASE,    MARKER_RELEASE,    False),  # new
}
```

Plus a color, stroke width, and marker constant. For a new arrow-head color, also add a `<marker>` in `_render_marker_defs()`:

```python
# Section 14a — _render_marker_defs
markers = [
    # ...
    (MARKER_RELEASE, COLOR_RELEASE),   # add this
]
```

**Diff for a conditional-style role** (one that picks color based on player position, like the existing pulling-guard logic):

Add a branch in `explicit_path_style` itself, before the `_SIMPLE_ROLE_STYLES.get` fallthrough.

**Test pattern:** in `tests/test_draw_render_components.py::TestOffensivePathStyling`:

```python
def test_release_role_uses_release_color(self):
    formation = _offense_with()
    play = _play_with([
        {"player": "TE", "role": "release", "path": [[0, 0], [3, 5]]},
    ])
    svg, _ = _render(play=play, formation=formation)
    self.assertIn(f'stroke="{_DRAW.COLOR_RELEASE}"', svg)
    self.assertIn(f'marker-end="url(#{_DRAW.MARKER_RELEASE})"', svg)
```

**Pitfalls:**
- A role added to the enum but NOT to `_SIMPLE_ROLE_STYLES` falls through to the route default (cyan polyline) — no warning. Check both places.
- The marker `<defs>` block is built once at SVG header time; if you add a new marker color but forget to register it in `_render_marker_defs`, the polyline references a nonexistent `#marker-id` and the arrow head won't draw.
- `AssignmentRole.ROUTE` is special: it doesn't use `explicit_path_style`. Routes go through `_render_route_assignment` which uses `style_for_player_read`. Don't try to add a route variant by extending the dispatch table.

---

## 4. Add a new color / font / stroke constant

**Goal:** introduce a new visual token (e.g. a brand color for a specific play type).

**Files touched:**
- `tools/draw-play/draw.py` — section 2i (color), 2e (font), or 2f (stroke)

**Rule:** every literal in render code must be a named constant. If you find yourself writing `"#ff8c00"` or `12` inside a `_render_*` function, stop and add a constant.

```python
# Section 2i — colors are grouped by purpose
COLOR_RPO_HIGHLIGHT: Final[str] = "#ffe066"   # bright yellow for RPO read flag
```

**Pitfalls:**
- Don't reuse an existing color "because it's close enough." If two visual concepts happen to share a hex value today, they'll drift in the future and you'll have a bug.
- Document the *purpose* in a comment, not the value: `# RPO read flag` is useful, `# yellow` is not.

---

## 5. Add a new SVG element type

**Goal:** the renderer needs to emit a new SVG element kind (e.g. `<path>`, `<defs>` content, `<filter>`).

**Files touched:**
- `tools/draw-play/draw.py` — section 11 (SVG primitives)

**Pattern:** every primitive is a small function that returns a string with assertion-checked inputs. Follow the existing `svg_rect` / `svg_circle` / `svg_line` shape:

```python
def svg_path(d: str, *, fill: str, stroke: str | None = None,
             stroke_width: float | None = None) -> str:
    """Emit a `<path>` element string."""
    assert d, "svg_path: d (path data) must be non-empty"
    assert fill, "svg_path: fill must be a non-empty color string"
    attrs = [f'd="{d}"', f'fill="{fill}"']
    if stroke is not None:
        attrs.append(f'stroke="{stroke}"')
    if stroke_width is not None:
        attrs.append(f'stroke-width="{stroke_width}"')
    return f"<path {' '.join(attrs)} />"
```

**Pitfalls:**
- Always assert at least one precondition (NASA rule 5; see existing primitives for the pattern).
- Optional attributes use `None` sentinels and are conditionally appended — don't emit `stroke-width="None"`.
- If your element contains user-provided text, run it through `xml_escape` before interpolating into the body.

---

## 6. Add a new chrome strip (alongside title / legend / warnings / notes)

**Goal:** add a new horizontal band to the SVG (e.g. a "diff vs canonical" strip).

**Files touched:**
- `tools/draw-play/draw.py` — section 2c (height constant), 13 (Layout NamedTuple + `_compute_layout`), 14e (renderer), 15 (orchestrator wiring)

**Steps:**

```python
# Section 2c — height constant
DIFF_STRIP_HEIGHT_PX: Final[int] = 60

# Section 13 — Layout NamedTuple gets a new top-y field
class Layout(NamedTuple):
    # ...
    diff_top_y: int   # new
    diff_h: int       # new (could be 0 when no diff to show)

# Section 13 — _compute_layout wires the offset
def _compute_layout(profile, play, field, note_rows):
    # ...
    diff_top_y = warnings_top_y + WARNINGS_STRIP_HEIGHT_PX
    notes_top_y = diff_top_y + DIFF_STRIP_HEIGHT_PX     # was: notes_top_y = warnings_top_y + WARNINGS_STRIP_HEIGHT_PX
    total_h = (
        dims.field_h + TITLE_STRIP_HEIGHT_PX + WARNINGS_STRIP_HEIGHT_PX
        + LEGEND_STRIP_HEIGHT_PX + DIFF_STRIP_HEIGHT_PX + notes_h
    )
    return Layout(
        # ...
        diff_top_y=diff_top_y, diff_h=DIFF_STRIP_HEIGHT_PX,
    )

# Section 14e — renderer
def _render_diff_strip(layout, diff_lines):
    # ... emit a <rect> + <text>s for each diff line

# Section 15 — render() orchestrator inserts the call after warnings strip
parts.extend(_render_diff_strip(layout, diff_lines))
```

**Pitfalls:**
- `Layout` is a frozen NamedTuple. Adding a field requires updating EVERY callsite that constructs a Layout (currently only `_compute_layout`).
- `total_h` must include the new strip's height. Forgetting this clips the strip off the bottom of the SVG.
- The notes box is the bottom-most strip and its height varies; make sure your new strip sits between fixed-height strips, not after the notes box.

---

## 7. Add a new warning kind

**Goal:** detect a new soft-validation issue and surface it to the user.

**Files touched:**
- `tools/draw-play/draw.py` — wherever the relevant invariant is checked (often `_check_player_bounds` or `_render_route_assignment`)

**Pattern:** push a string to the `warnings` list. The warnings strip auto-truncates to `MAX_WARNINGS_DISPLAYED` (5) for display; the full list is still returned to the caller.

```python
# Inside _check_player_bounds
max_motion = limits.get("max_motion_yd")
if max_motion is not None and motion_distance > max_motion:
    warnings.append(
        f"{label} motion distance {motion_distance:.1f} yd > "
        f"editor max ({max_motion} yd)"
    )
```

**Test pattern:** in `tests/test_draw_render_components.py::TestWarnings`:

```python
def test_motion_distance_warning_emitted(self):
    profile = self._profile_with_limits(max_motion_yd=10.0)
    formation = _offense_with(SLOT={"motion_distance": 12.0})
    _, warnings = _render(profile=profile, formation=formation)
    self.assertTrue(any("motion distance" in w for w in warnings))
```

**Pitfalls:**
- "Hard" failures should raise an exception, not append a warning. The split rule: if the renderer can produce sensible output despite the issue, it's a warning; if the output would be wrong, it's an exception.
- Check `MAX_WARNINGS_DISPLAYED` if you're adding a category that produces many warnings — only the first 5 render in the strip; the rest are silent in the SVG (still in the returned list, though).

---

## 8. Add a new `--show` value

**Goal:** add a new render mode (e.g. `--show route-only`).

**Files touched:**
- `tools/draw-play/draw.py` — section 3a (enum), section 14b–d (gating dispatchers)

**Diff:**

```python
# Section 3a
class Show(str, Enum):
    # ...
    ROUTE_ONLY = "route-only"

# Section 14d — _render_play_overlay (the offensive dispatcher)
def _render_play_overlay(play, formation, route_lib, show, profile, layout, warnings):
    if play is None or formation is None or route_lib is None:
        return []
    if show not in (Show.OFFENSE, Show.BOTH, Show.ROUTE_ONLY):   # ← include new value
        return []
    # ...

# Section 14c — _render_defense (the defensive dispatcher)
def _render_defense(defense, formation, profile, layout, show):
    # ... defense markers always render, but coverage gates on:
    if show not in (Show.DEFENSE, Show.BOTH):
        return parts
    # If your new mode wants defense markers but no coverage, no change here.
```

`_VALID_SHOW_VALUES` and the argparse `choices=` both auto-update because they derive from `Show`.

**Test pattern:** in `tests/test_draw_cli.py::TestCliFlags`:

```python
def test_show_route_only_omits_defense_coverage(self):
    result = _run_cli(
        "--play", FIXTURE_PLAY, "--game", FIXTURE_GAME,
        "--vs", FIXTURE_DEFENSE, "--show", "route-only",
    )
    self.assertEqual(result.returncode, 0)
    # No man-coverage rings (the defender's <circle stroke-dasharray="4,3" />)
    self.assertNotIn('stroke-dasharray="4,3"', result.stdout)
```

**Pitfalls:**
- Every dispatcher that gates on `show` must be updated. Currently there are three: `_render_play_overlay`, `_render_defense`, `_render_legend`. Search for `show in (` to find them all.
- The legend strip filters its items by `show`. A new mode might want a different legend; check `_legend_items`.

---

## 9. Add a new `--field` length

**Goal:** add a new downfield viewing length (e.g. `--field full` for LOS+50yd).

**Files touched:**
- `tools/draw-play/draw.py` — section 3a (enum), section 2c (constant), section 13 (`_compute_field_dims` dispatch)

**Diff:**

```python
# Section 3a
class Field(str, Enum):
    # ...
    FULL = "full"

# Section 2c
FIELD_FULL_EXTRA_YD: Final[int] = 50

# Section 13 — _compute_field_dims
def _compute_field_dims(profile, field):
    if field == Field.LONG:
        extra_yd = FIELD_LONG_EXTRA_YD
    elif field == Field.SHORT:
        extra_yd = FIELD_SHORT_EXTRA_YD
    else:  # Field.FULL
        extra_yd = FIELD_FULL_EXTRA_YD
    # ... rest unchanged
```

`_VALID_FIELD_VALUES` and argparse `choices=` auto-update.

**Test pattern:** in `tests/test_draw_cli.py::TestCliFlags`:

```python
def test_field_full_taller_than_long(self):
    long_result = _run_cli("--play", FIXTURE_PLAY, "--game", FIXTURE_GAME, "--field", "long")
    full_result = _run_cli("--play", FIXTURE_PLAY, "--game", FIXTURE_GAME, "--field", "full")
    self.assertGreater(len(full_result.stdout), len(long_result.stdout))
```

**Pitfalls:**
- The provisional-width helper `_provisional_total_w` only depends on grid width, so adding a field length doesn't affect it. But every renderer that uses `layout.total_cells` (most of them) automatically picks up the new height.
- The `_field_tag` helper formats the subtitle's "(long)" / "(short)" suffix. Update it if you want the new mode to display correctly.

---

## 10. Refresh the provenance comment

**Goal:** the SVG header banner shows version + git rev + timestamp + input identifiers. To add or remove a field:

**Files touched:**
- `tools/draw-play/draw.py` — `_render_provenance_comment` (section 14a)

**Diff to add a field (e.g. user/host):**

```python
import getpass, socket   # at module top

def _render_provenance_comment(profile, play, formation, defense):
    fields = [
        f"draw-play v{__version__}",
        f"git={_git_rev()}",
        f"generated={datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')}",
        f"by={getpass.getuser()}@{socket.gethostname()}",   # ← new
        f"game={profile.get('game_id', '?')}",
        # ...
    ]
```

**Test pattern:** update `tests/test_draw_properties.py::TestRenderStructuralProperties::test_provenance_comment_contains_required_fields`:

```python
for required in ("draw-play v", "git=", "generated=", "by=", "game="):
    self.assertIn(required, body)
```

**Pitfalls:**
- The comment can never contain `--`; the existing code rewrites any to em-dash. If you add a free-form input field, double-check it doesn't introduce `--` (e.g. user-supplied filenames).
- Determinism tests strip the provenance line before comparing. Adding new time- or environment-dependent fields is fine. Adding fields that depend on input *content* should still be reproducible — those go in the comparable portion.

---

## How to find an extension point you don't see here

`docs/draw-play-architecture.md` has a "Where to add things" table. If your task is there but not here, the architecture doc tells you which section of `draw.py` to edit. Then come back here for the detail.

If your task is *not* in either doc, the change is novel and worth recording — once you've done it, add an entry here so the next person doesn't have to figure it out from scratch.
