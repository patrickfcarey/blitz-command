# playbook-generation-mcp

MCP server for **assembling** custom playbooks from the library and for **working with authored playbooks** in `data/playbooks/` — their sections, audible systems, counter-responses, and validation. **12 tools.**

**Boundary rule**: this server owns collection-level reasoning — anything that treats a *set* of plays as a unit. Single-play analysis (compare two plays, predict a matchup, scout a play, query a disguise family) belongs in `play-library-mcp`.

## Tools

### Playbook assembly — build a book from the library

- **`assemble_playbook_simple(formation_constraint, play_count, philosophy, game_id, play_type_mix)`** — select N plays matching constraints, respecting game editor caps and play-type distribution targets
- **`suggest_complementary_plays(seed_play_ids, max_results=5, require_same_formation=False)`** — given plays already in a playbook, recommend what's missing (type gaps, ball-carrier gaps, PA/fake gap)
- **`list_formations_with_plays()`** — formation IDs with at least one play in the library
- **`list_philosophies_with_plays()`** — philosophy IDs represented in play files

### Authored playbooks — `data/playbooks/` (sections, audibles, counter_responses)

- **`list_playbooks()`** — every authored playbook with section + play counts
- **`get_playbook(playbook_id)`** — a playbook's full record: sections, play entries, audibles, counter_responses
- **`get_playbook_section(playbook_id, section_id)`** — one formation_section or situational_section
- **`get_audibles(playbook_id)`** — the audible system (a global pool, or per-formation pools, depending on `audible_mode`)
- **`get_play_in_playbook(playbook_id, play_id)`** — a play's *entry* in the playbook (role, install_order, call shares, counter_responses) — distinct from the football play itself (`play-library-mcp` `get_play`)
- **`validate_playbook(playbook_id)`** — full validation via `tools/validate-playbook/validate.py`: schema, share-math rollups, audible integrity, counter_ref resolution, disguise-family self-containment
- **`playbook_call_sheet(playbook_id)`** — every play with its derived total snap share (`section target_snap_share_pct × play share_of_section_pct`), sorted — the coach's-eye call sheet

### Meta

- **`manifest()`** — this server's purpose, tool list, and worked examples

## Phase 7 additions (planned)

- `assemble_playbook(philosophy, formations, target_size, game_id)` — full optimizer with play-family balance, disguise scoring, and constraint-satisfaction

## Run standalone

Requires **Python 3.10+** (mcp SDK). Use the repo `.venv` (created with `python3.11`):

```bash
.venv/bin/python mcps/playbook-generation-mcp/server.py
```
