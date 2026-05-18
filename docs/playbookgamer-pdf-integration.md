# Playbook Gamer Reference Corpus

The Playbook Gamer community corpus — read-only reference material for the
toolkit's game-truth and authoring layers.

**Status:** acquired. Files are in `research_artifacts/` (git-ignored).
Phase A tooling built; Phase B/C pending.

## Source + licensing

Playbook Gamer (https://playbookgamer.com/playbooks/) publishes per-team
playbook references for ~19 Madden and NCAA titles, distributed via the
creator's Ko-fi Vault. The user supplied the files directly.

This is the creator's compiled work — a **read-only reference source**. It is
never republished and never copied verbatim into project data. Anything the
toolkit derives from it carries a `source_notes` credit to Playbook Gamer and
`verification_status: unverified` (third-party sourced, not in-game-verified).
`research_artifacts/` is git-ignored; only *derived digests* are committed.

## The corpus — what's actually there

19,389 files under `research_artifacts/` (PS2 holds the bulk; PS3 has 87,
PS1 is empty):

| Type | Count | What it is |
|------|------:|-----------|
| `.jpg` | 18,134 | In-game play-select screenshots (~3 plays each) |
| `.docx` | 559 | Game manuals + playbook guides (text + embedded images) |
| `.pdf` | 213 | Prima guides, manuals |
| `.xlsx` | 26 | Structured databases — the highest-value, most tractable data |
| `.png` | 444 | Misc diagrams |

Games covered: ESPN NFL 2K5, Madden 01/03/04/05/07/25, NCAA 04/05/06/07,
Tecmo Super Bowl.

Tooling note: the venv has no `openpyxl` / `python-docx` / `tesseract`, but
`.xlsx` and `.docx` are zip+XML (parsed directly) and `.pdf` works via
`pymupdf`. Only the JPGs would need OCR — and they don't, because the xlsx
already hold the data the screenshots depict.

## Plan

### Phase A — xlsx (structured data) — tooling built

`tools/ingest-research/parse_xlsx.py` reads any `.xlsx` without openpyxl
(`read_xlsx(path) -> {sheet: rows}`, plus a CLI digest). ~15 of the 26
workbooks are formation/play/playbook data; the rest are roster/stadium/
recruiting noise.

### Phase B — docx/pdf manuals (subagents)

Triage the 559 docx + 213 pdf by filename, then fan out subagents to extract
game-truth (editor limits, motion rules, formation caps) with verification
status + source notes. Pending.

### Phase C — JPGs (on-demand reference)

The 18k screenshots are visual reference, read individually when a specific
play needs confirmation. Not bulk-processed — the xlsx cover the data.

## Phase A findings — what the workbooks hold

**Offensive Formation Lists** (Madden 04/05/07, NCAA 04/06/07) — per
team-playbook, the formations it carries. NCAA 04's has three sheets:
- *Formation List* — playbook → formation → personnel-grouping code.
- *Formation Type* — playbook → style + per-family formation counts.
- *Personnel* — playbook → formation counts by personnel grouping.

**Playbook Databases / Matrix** (NCAA 04/06, Madden 05) — formation×team
matrices: which playbook carries which formation, with totals.

**Play Charts** (Madden 07) — per-team play catalogs grouped by concept
series (Corner Series, Curl Series, Option Passes, Play Action), each play
tagged with its formation and key receiver.

**Call Sheets** (NCAA 06: Flexbone, I-Option) — real situational call sheets:
plays bucketed Option / Run / Pass / Situational, then sub-grouped (Triple
Option, FB Dive, Play Action, 3rd & Long, 3rd & Short).

### What this feeds

- **Game truth.** Formation rosters per game/playbook → `data/games/<id>/`.
  Personnel-grouping codes seen in NCAA 04 (00/10/11/12/13/20/21/22/30/31)
  match `data/concepts/personnel-groupings.yaml` — independent corroboration
  of that model. Playbook styles (Option / Pro Style / West Coast / Multiple)
  align with the philosophy layer.
- **Authoring + playbook structure.** Real play names and the Call Sheets'
  situational bucketing inform the playbook section model and the install
  schedule.
- **Scope.** Per `CLAUDE.md` the MVP is NCAA 06 + Madden 04 — only those
  games' rosters should be folded into `data/games/`; the rest stays
  digest-only until a game is deliberately added.

## Next steps

- Fold NCAA 06 + Madden 04 formation rosters into their `data/games/`
  profiles (scoped — not all 10 games).
- Phase B subagent triage of the docx/pdf manuals.
