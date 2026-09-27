# Route-geometry build — design

## Why this exists

The M25 vision pilot extracts per-play geometry. Most fields are solid:

- `ball_carrier` + `target_gap` — Python-deterministic, hand-verified 3/3.
- `concept` — Python-deterministic via `play_concepts.py`.
- `personnel` — formation-derived (imperfect, see "Known gaps").

The failure is **routes**. The hand-review of 18 plays (2026-05-22) found
the LLM systematically mislabels routes — ~26% of all route entries are
`streak`/`seam` (vertical) when the real route is a hitch, dig, post,
comeback, etc. A follow-up test added a detailed route-shape guide to the
prompt AND ran at full resolution — the LLM *still* called the flagged
routes `streak`. Conclusion: **the LLM cannot reliably trace thin,
overlapping route arrows from the screenshot.** It is a perception limit,
not an instruction limit.

Decision: build a deterministic Python route-geometry extractor. The LLM
keeps the jobs it is good at (concept naming, edge cases); Python owns
route shape.

## The input

Each canonical crop is a wide LOS-zoom of one M25 play panel. Routes are
drawn as colored arrows:

- **RED** — the primary route (pass) or ball-carrier path (run). Exactly one.
- **YELLOW** — standard receiver routes.
- **CYAN/BLUE** — block-then-release routes (chip, delayed release, RB
  swing after pass-pro, some motion).

Each route starts at a receiver glyph on the LOS row and ends in an
arrowhead.

## The hard parts (from the probe, 2026-05-22)

1. **Annotation pollution.** The crops carry a cyan LOS line and a yellow
   C-box drawn by the pipeline. Cyan line == cyan route color; yellow box
   == yellow route color. → FIX: regenerate crops with gray annotations
   (non-route color) or none. (Task #30)
2. **Button-glyph pollution.** PS-button receiver glyphs (red ⊙, blue ⊗,
   etc.) are colored compact blobs that register as route pixels. → FIX:
   filter by shape — routes are thin/elongated (low fill density), buttons
   are compact filled blobs (~40-60px, high density). (Task #31)
3. **Overlapping same-color routes.** All yellow routes share one yellow.
   When two routes cross or touch, `findContours` fuses them into one
   blob. → FIX: per-receiver tracing (see below). (Task #32)

## Approach — per-receiver route tracing

Rather than segment the route mask top-down, trace bottom-up from each
receiver:

1. **Anchor on receivers.** Receiver positions are known approximately —
   they sit on the LOS row, and personnel (`r#f#t#w#`) says how many.
   Each route originates at a receiver.
2. **Color-isolate** the route mask (red / yellow / cyan), with button
   and border pollution removed.
3. **For each receiver**, start a walk at its position and follow the
   colored pixels outward. At a crossing (junction with another route),
   prefer the branch that continues the current heading — routes cross,
   they don't usually turn 90° at another route's line.
4. **Stop at the arrowhead** — the widest cluster of route pixels, or the
   path's far endpoint.
5. The traced polyline IS the route geometry.

## Geometry → route name (Task #33)

From a traced polyline, measure:

- **stem**: direction + length of the initial segment off the LOS.
- **break point**: where the heading changes sharply (if any).
- **break angle**: ~45° (slant/post/corner) vs ~90° (in/dig/out).
- **break direction**: toward the middle, toward the sideline, or back
  toward the LOS.
- **depth**: shallow / intermediate / deep (total downfield distance).

Classification table (see also the route-shape guide in
`subagent-prompt.md`):

| Route     | Stem | Break | Notes |
|-----------|------|-------|-------|
| streak/go | straight, deep | none | perfectly vertical |
| seam      | straight, deep | none | inner receiver, slight inward lean |
| slant     | short | immediate ~45° inward | shallow |
| drag      | — | — | shallow, horizontal across field |
| hitch     | short (~5yd) | stops / back to QB | arrowhead near stem end |
| curl      | medium (~12yd) | curls back to QB | |
| comeback  | deep (~15yd) | sharp back to sideline+down | |
| out       | medium | ~90° to sideline | |
| in/dig    | medium | ~90° to middle | |
| corner    | deep | ~45° to sideline | continues deep |
| post      | deep | ~45° to middle | continues deep |
| wheel     | lateral then vertical | L/J shape | up the sideline |
| flat      | — | — | quick shallow to sideline |

## Output

`route_geometry.py` emits, per play:

```json
{
  "routes": [
    {"color": "red|yellow|cyan",
     "origin_xy": [x, y],
     "polyline": [[x,y], ...],
     "stem_dir": "...", "break_dir": "...", "break_angle_deg": N,
     "depth": "shallow|intermediate|deep",
     "route": "<classified name>",
     "confidence": "high|medium|low"}
  ],
  "primary_route_index": <int>   // which route is red
}
```

## Integration (Task #34)

Two modes, decided by how well the classifier performs on the 18-play
re-test:

- **Authoritative** — if classification is reliable, Python's route names
  go straight into the extraction; the LLM does not touch routes.
- **Hint** — if classification is medium-reliable, Python's geometry is
  passed to the LLM as `py_route_geometry` hints (the prompt already
  references this), and the LLM makes the final call.

The 18 hand-reviewed plays (`hand_review_results.json`) are the gate.
No full re-run until route accuracy on those 18 clearly beats the
current ~17%.

## Iteration-1 findings (2026-05-22)

`route_geometry.py` iteration 1 — `clean_crop()` + `isolate_routes()` —
is working. Findings from the first debug run (`PA Ctr Waggle`):

- **`clean_crop()` works** — generates an annotation-free full-res crop
  straight from the docx, so there's no cyan-line / yellow-box pollution.
  This supersedes task #30 (no need to regenerate the stored crops; the
  CV generates clean ones on demand).
- **The color model is richer than assumed.** A single play draws routes
  in red, yellow, green, cyan, blue AND white/gray — M25 colors each
  receiver's route distinctly. `ROUTE_COLORS` extended to 5 hue families;
  white/gray routes still TODO (they collide with the white player
  glyphs, so need shape disambiguation).
- **Banner pollution fixed** — the bottom-left "RUN"/"PASS" label was
  being picked up; mask now zeroes the bottom-left quadrant.
- **Button-glyph filter** (`_is_button_glyph`) works — compact filled
  blobs are dropped, thin route lines kept.
- **Green routes render thin/faint** — current detection gets only
  speckle fragments. Needs a lower saturation floor or morphological
  bridging.

Next: white/green tuning, then per-receiver tracing (#32).

## Iteration-2 status (2026-05-22)

Full pipeline built: `clean_crop` → `isolate_routes` → `trace_route`
(skeletonize + double-BFS longest path) → `classify_route` (geometry →
route tree). Plus a noise guard: a traced polyline that never goes
meaningfully downfield (`max_depth < 40px`) is rejected as not-a-route.

**Test (`test_route_geometry.py`) — the stated bar was "identify a curl
and an in/dig route in isolation":**

| Play          | Expect | Result |
|---------------|--------|--------|
| Zona Curls    | curl   | PASS — curl ×2 |
| Inside Dig    | in     | PASS |
| WR Deep In    | in     | PASS ×2 |
| Deep X Dig    | in     | PASS |
| Zona Dbl Curls| curl   | MISS — curls read as `post` |

4/5 — the shape-classification engine works.

**Known gap before this can replace the dataset `routes` field:**

- **Route fragmentation.** One route can split into 2-3 contours (anti-
  alias gaps, crossings). E.g. `Inside Dig` shows the single red primary
  route as 3 red contours, each classified separately. → de-fragmentation
  layer needed (task #35): morphological close + merge contour pieces
  with colinear nearby endpoints, so one route = one polyline.
- **Per-receiver assignment.** Routes still need mapping to receiver
  roles (WR_X etc.).
- **Classifier tuning** — the `post` vs `curl` boundary on break-and-
  extend routes (Zona Dbl Curls miss).

## Iteration-3 — de-fragmentation (task #35, 2026-05-22)

`isolate_routes()` now de-fragments: a morphological CLOSE bridges the
intra-route gaps that split one route into multiple color blobs, then
connected-components yields one component per route. RED is collapsed to
a single route (M25 draws exactly one red/primary route) and closed with
a larger kernel since there is no second red route to wrongly merge.

Result — route counts went from **9–18 fragments/play to 4–5 real
routes/play**, and the shape test is **5/5** (was 4/5):

| Play | Expect | Result |
|------|--------|--------|
| Zona Curls / Zona Dbl Curls | curl | PASS |
| Inside Dig / WR Deep In / Deep X Dig | in | PASS |

**Verified:** for YELLOW — the multi-route colour, the genuinely hard
case — each route is now exactly one connected component. The
fragmentation is fixed for the general case.

**Known residual — the RED primary route.** M25 renders the red arrow
with internal colour variation: chunks of it fall outside the red HSV
band, leaving gaps >80px that even the aggressive red close cannot
bridge. Widening the HSV band floods the maroon panel background (75k →
360k px), so it is not recoverable that way. The red route therefore
still traces via largest-skeleton-component and can miss a break on a
detached arrowhead (e.g. Inside Dig's red out-route reads as `streak`).
A naive nearest-endpoint stitch was tried and rejected — it produced
zigzag polylines (`cameback` > `max_depth`). Reuniting the red pieces
needs a colinearity-aware stitch — deferred.

## Iteration-4 — the PIVOT: cluster, don't trace (2026-05-22)

Tracing (iterations 1-3) never converged — every fix for one failure
(fragmentation, over-merge, spurs, under-detection) broke another. The
junction-aware walk re-test produced 1 good route + a border artifact
on a 5-route play. Tracing arbitrary curves is the wrong frame.

**The right frame: these diagrams are GAME-RENDERED.** The same route is
drawn pixel-identical every time it appears. So the problem is not
tracing — it is **clustering**: fingerprint every route, group identical
renderings, and the dataset collapses to a small template set. Label the
templates once; every route maps to a cluster deterministically.

**Proven on the RED primary route** (`cluster_red_routes.py`):
- Fingerprint = red mask, button/border removed, dilated to absorb
  edge jitter, centroid-normalized (receiver alignment irrelevant),
  downsampled to a 40×40 grid.
- Match = min mean-abs-difference over small translations (shift-
  tolerant, so JPEG/anti-alias jitter doesn't split identical routes).
- Result: **7,289 red routes → 209 clusters. 98% of routes in clusters
  of ≥3.** Top clusters: 1528 / 1227 / 964 / 534 / 445 plays.

`build_cluster_gallery.py` renders `red-route-clusters.html` — every
template as an image, sorted by frequency with running coverage. The
review/label job is ~209 templates, not 7,300 plays.

Next: label the red templates; extend the fingerprint-and-cluster method
to non-red routes (per receiver). `route_geometry.py`'s tracer is kept
but is NOT the path — clustering is.

## Iteration-5 — v2 gallery fixes from user feedback (2026-05-22)

User reviewed v1 gallery top ~33 clusters and gave critical feedback:

1. **Red mixes runs and passes** — on a pass play red = primary route,
   on a run play red = ball-carrier path. v1 conflated them; v2 filters
   to `play_type == "pass"` only. Run plays' red is captured by
   `target_gap`, not the route extraction.
2. **Mirror dependency (post vs corner)** — the same shape from a left
   vs right receiver has different names. Side must be recorded per
   cluster member.
3. **Magenta overlay confused reviewers** — they read it as a drawn
   route. v2 drops the overlay; only the real red route is shown.
4. **Screen routes dropped as "not_a_route"** — `max_depth < 40` noise
   guard wrongly nukes them. v2 leaves proposed label blank for short
   routes rather than emitting "not_a_route".

Side-detection bug found and fixed: v2 first used the red mask's
*centroid*, which gets pulled in the route's direction of travel and
gives the wrong side for inward-breaking routes. Corrected to anchor on
the red ⊙ button (when visible) or the route's bottommost-bbox-bottom
component — both of which sit at the receiver, not in the route's body.
Uses `cv2.connectedComponentsWithStats` only; an earlier `np.where(labels==i)`
implementation was 10× too slow.

**New vocabulary the user contributed** (now in the LLM-label prompt):
`fade`, `quick_slants`, `hb_texas` (sideways-V below the LOS),
`screen`, `wheel/flare_out`, `double_move`, `block_release_drag`.

v2 = `cluster_red_routes.py` (pass-only, button-anchored side) +
`build_cluster_gallery.py` (LLM-proposed labels via Haiku 4.5 with the
new vocabulary, parallelized 6-way). Cost ~$0.20 per gallery build.

User's v1 labels preserved in `red_cluster_labels_v1.json`. Last
reviewed cluster was v1 #33 — everything past that in v1 is unreviewed.

## Status

The route problem has a proven deterministic solution: cluster +
template-label. v2 red-route gallery is the active review surface.
Next: user labels v2 → all red pass primaries deterministically mapped
→ extend fingerprint-and-cluster to other route colors (per receiver).
Iteration 1-3 tracer is superseded.
