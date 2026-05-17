# Playbook Gamer PDF Integration — Plan

Plan for ingesting the team-playbook PDFs from the Playbook Gamer Vault into
the toolkit as reference material.

**Status: blocked on the user for Phase 1.**

## Source

Playbook Gamer (https://playbookgamer.com/playbooks/) publishes per-team
playbook PDFs for ~19 Madden and NCAA titles. The files are distributed
through the creator's Ko-fi "Vault" (https://ko-fi.com/s/b969c58608) and
require the user's own Ko-fi access — the toolkit's tools cannot reach them.

These PDFs are the creator's compiled work. Treat them as a **read-only
reference source** — never republished, never copied verbatim into project
data. Anything extracted from them carries a `source_notes` credit to
Playbook Gamer and a `verification_status` of `unverified` (third-party
sourced, not in-game-verified).

## Phase 1 — Acquisition (user)

The user downloads the Vault files and unzips them into
`reference/playbookgamer/`, ideally one subfolder per game
(e.g. `reference/playbookgamer/madden-nfl-25-2013/`).

`reference/` is git-ignored — a few hundred binary PDFs are local source
material, not version-controlled project data.

## Phase 2 — Inventory + extraction

1. A tool walks `reference/playbookgamer/` and produces an inventory: per
   game, the playbooks/teams covered, file and page counts; flags gaps.
2. A PDF-reading tool (`pymupdf` is already in the venv) extracts each PDF's
   structured content — per playbook, the formations and plays it lists —
   into a staging directory, one record per source playbook.

Extraction quality depends on whether the PDFs are text or image-based. Text
PDFs parse directly; scanned/image PDFs would need OCR (a later decision).

## Phase 3 — Integration

Map the extracted data into the toolkit:

- **Game truth.** Which playbooks and formations each real title shipped
  feeds the `data/games/<id>/` profiles and the game-truth layer.
- **Authoring source.** The real playbooks become a sourced reference for
  authoring and validating the toolkit's own plays and formations — every
  claim drawn from them cites the PDF.

The PDFs do NOT get copied into `data/plays/`. The toolkit's plays are its
own football-truth model; the PDFs corroborate and inform, they are not
imported wholesale.

## Open questions

- PDF structure (text vs scanned) — sets the extraction approach.
- Granularity per team — full play diagrams, or just formation lists.
- Whether to model a new `data/reference/` dataset, or fold findings
  directly into the existing game profiles.
