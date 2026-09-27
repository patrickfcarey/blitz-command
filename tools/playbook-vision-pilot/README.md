# Playbook vision pilot — does hybrid extraction reduce vision cost?

Goal: measure whether priming a vision agent with a name-derived concept
prior **statistically significantly** reduces the cost of per-play geometry
extraction, vs. cold extraction without a prior. If yes, hybrid is worth
building out across all 14k+ Madden 25 plays. If no, skip hybrid and run
cold vision directly.

## Design

- **Population:** Madden 25 PS3 play-screen panels (~14,000 unique).
- **Sample:** 50 plays stratified by:
    - run vs pass (25 each)
    - name-decodes-cleanly vs generic-name (12 + 13 per axis)
    - across ≥5 source playbooks for formation/team diversity.
- **Conditions (within-subject, each play extracted twice):**
    - **cold:** vision agent sees the cropped panel + team + formation + play name. No prior.
    - **primed:** vision agent sees the same panel + a concept prior derived from the
      name parser + concept library (e.g. "this play is tagged: concept=iso, gap=A,
      direction=left, lead_blocker=FB, expected_blocking=down+kickout — emit deltas if
      the diagram disagrees").
- **Order:** randomized per play to control for any subagent-side caching.
- **Both arms emit the same geometry schema** so comparisons are apples-to-apples.

## Measurements (per subagent run)

| Metric | Source |
|---|---|
| tool_calls | subagent usage report |
| extraction completeness | number of players covered / 11 |
| run cost minutes | duration_ms |

## Analysis

- Paired t-test on log(tool_calls), cold vs primed.
- Effect size (Cohen's d), with 95% CI.
- Spot-check 5 plays per arm against the actual cropped panel (manual ground truth).

## Decision rule

- ≥15% reduction in tool_calls **and** no degradation in completeness → build hybrid.
- <15% reduction OR degraded completeness → drop hybrid, go straight to cold vision
  with a tighter extraction prompt.

## Pipeline

1. `sample_plays.py` — pick the 50 plays, write `pilot-sample.json`.
2. `crop_play_panels.py` — for each sampled play, crop the corresponding panel from
   the source screenshot into `pilot-work/crops/<id>.jpg`.
3. `name_to_prior.py` — name + formation → concept prior string (or null if no match).
4. Dispatch 100 subagents (50 cold + 50 primed) via the Agent tool, each emitting
   `pilot-work/extractions/<id>__<arm>.json` with the geometry schema below.
5. `analyze.py` — aggregate, run paired stats, write `pilot-results/report.md`.

## Geometry schema (both arms emit this)

```json
{
  "play_id": "indianapolis_colts__singleback-jumbo__hb_toss",
  "panel_index": 0,
  "players": [
    {"role": "LT",  "action": {"kind": "block", "target": "downfield"}},
    {"role": "LG",  "action": {"kind": "block", "target": "down"}},
    {"role": "C",   "action": {"kind": "block", "target": "playside_a"}},
    ...
    {"role": "HB",  "action": {"kind": "run",   "path": ["pitch_right", "edge_d_gap"]}},
    {"role": "WR_L","action": {"kind": "route", "waypoints": ["block_downfield"]}},
    ...
  ],
  "play_concept_observed": "outside_zone | toss | jet_sweep | ...",
  "notes": "optional freeform: anything the agent couldn't categorise"
}
```

Both arms use the same schema; primed agents will additionally fill a
`"agreed_with_prior": true|false` field plus a `"deltas"` list of any
disagreements with the supplied concept prior.
