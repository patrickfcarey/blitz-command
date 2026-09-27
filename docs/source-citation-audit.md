# Source Citation Audit Report

Generated 2026-04-30. This report identifies YAML files with weak or missing source citations that should be improved to meet the "Web validated YYYY-MM-DD — <Source Name> (<URL>): <summary>" format.

## Summary

| Category | Count | Status |
|----------|-------|--------|
| concepts | 1 | Minimal — mostly complete |
| formations | 47 | Needs improvement — many lack URLs |
| games | 4 | Needs review — some game profiles incomplete |
| measurements | 1 | Needs detail |
| plays | 122 | Major work — most lack detailed citations |
| routes | 18 | Needs improvement — generic format |
| **TOTAL** | **193** | **Moderate to high priority** |

## Details by Category

### Concepts (1 file)
- `concepts/play-templates.yaml` — No source_notes at all

### Formations (47 files)
These are primarily defensive and offensive formation profiles. Most lack full "Web validated" citations and instead use informal descriptions or coach-lineage notes. Examples:

- `formations/defense-*.yaml` — Typically have notes like "Standard [formation] alignment; documented across [coach names]" without URLs
- `formations/empty*.yaml`, `formations/big-i*.yaml`, `formations/i-formation*.yaml` — Generic descriptions of formation concepts without cited sources
- All mirror variants (e.g., `*-left.yaml`) lack distinct citations, just note "Mirror of [base file]"

**Recommended action:** For each formation, add at least 1-2 web-cited sources from coaching sites (X&O Labs, Throw Deep Publishing, YouTube tutorials, Wikipedia coach pages).

### Games (4 files)
- `games/*/editor-grid.yaml` — Some game profiles (typically PS1-era) lack the minimum 2 sources or have incomplete validation dates

**Recommended action:** Run a quick audit on all 45 game profiles to ensure each has ≥2 web-cited entries.

### Measurements (1 file)
- `measurements/unknown` — Likely an incomplete file from earlier exploratory work

**Recommended action:** Review and complete or delete.

### Plays (122 files)
The largest category needing work. Most play YAML files either:
1. Lack `source_notes` entirely
2. Have informal notes (e.g., "designed as a [concept] variant" without citation)
3. Reference other plays without citing foundational sources

**Examples:**
- Plays using generic templates like "Singleback Trio" formation often just note the formation origin, not the play itself
- Many pass plays lack citations to passing-concept sources (Air Raid, West Coast, Coryell, etc.)
- Run plays sometimes reference run concepts but not the foundational sources for those concepts

**Recommended action:** 
- Add concept_ref links to existing concept files (which DO have proper citations) to leverage transitive source trust
- For plays without clear sourcing, note "derived from [concept_id] + [formation_id]" + infer status
- For canonical plays extracted from games, eventually add game-specific validation notes

### Routes (18 files)
Routes in `data/routes/` are mostly lacking detailed source citations. Notes are often brief descriptions rather than web-cited references.

**Examples:**
- `routes/dig.yaml`, `routes/slant.yaml` — Generic descriptions without URLs

**Recommended action:** Link to passing-concept sources or coaching sites that document specific route trees.

## Priority Tiers

### Tier 1 (Must fix)
- [ ] Concepts: `play-templates.yaml` — add source_notes
- [ ] Games: audit all 45 profiles for ≥2 sources per file
- [ ] Plays: establish a pattern for "derived from [concept]" + infer / verify status

### Tier 2 (Should fix)
- [ ] Formations: add at least 1 web-cited source per formation
- [ ] Routes: link to passing-concept sources or route-tree documentation
- [ ] Measurements: investigate and complete or delete

### Tier 3 (Nice to have)
- [ ] Add coach-specific Wikipedia citations for famous formations/philosophies
- [ ] Link plays to canonical in-game extractions (Phase 8 work)
- [ ] Create a shared `tools/web-research/` helper to standardize citations (CC-T01)

## Suggested Citation Pattern

For files currently using informal notes, adopt this format:

```yaml
source_notes:
  - "Web validated 2026-04-30 — Throw Deep Publishing (https://throwdeeppublishing.com/...): describes [specific claim]."
  - "Inferred from [related concept/formation] with [reason]."
```

Or for plays:
```yaml
source_notes:
  - "Derived from pass_concept_ref: mesh and formation_ref: singleback-trio (see concept + formation source_notes for primary citations)."
  - "Web validated 2026-04-30 — [Coach/Site]: [specific variation detail]."
```

## Related Tasks

- **CC-T01:** Build a `tools/web-research/fetch.py` helper to standardize citations across the library
- **CC-T03:** Schema-coverage audit — ensure every file validates against its corresponding schema
- **P8-T05:** Per-game default-playbook research — document playbook provenance per game
- **P8-T06:** Canonical-play extraction — systematic extraction of in-game plays with proof-of-concept screenshots

---

**Last updated:** 2026-04-30  
**Prepared by:** Haiku phase 8 audit task (CC-T02)
