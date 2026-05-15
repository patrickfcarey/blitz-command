# Session Log

Append-only handoff log. The newest session goes at the **top**. The point is so a fresh Claude session (or a human returning after a crash) can answer "where did we leave off?" without reconstructing from `git status` timestamps.

## Conventions

- One entry per working session. Append at the top, under the heading below.
- Date is ISO (`YYYY-MM-DD`). Use `date +%Y-%m-%d`, don't guess.
- Keep entries short. Link to docs/files rather than re-describing them.
- Trim entries older than ~30 days when they stop being load-bearing — git history is the long-term archive.

### Entry template

```markdown
## YYYY-MM-DD — <one-line thread title>

**Active thread:** what we were actually working on this session.

**Landed this session:**
- bullet
- bullet

**In progress / next step:** the single most useful thing for the next session to pick up. Be specific (filename + what to do, not "continue work").

**Blockers / waiting on:** external dependencies, user input needed, decisions deferred. Omit the section if none.

**Uncommitted state:** one line on whether work is committed or sitting in the tree, and whether that's intentional.
```

---

## 2026-05-14 — Session-log convention established

**Active thread:** user asked "where did we leave off before the machine died?" — I could only reconstruct from `git status` timestamps. We decided to fix the gap by adopting this file.

**Landed this session:**
- Created `docs/session-log.md` (this file) with template + conventions.

**In progress / next step:** pick up the pre-crash thread — generating the **Singleback Trio** play family diagrams (May 2 work, all uncommitted). Check `examples/play-diagrams/singleback-trio-*` and the family in `docs/pending-queue.md` "More plays" section. Also: stray `check_this.png` at repo root — user may want eyes on it.

**Blockers / waiting on:** none for the log itself. The crash-recovered thread may have unresolved questions — re-ask the user before diving in.

**Uncommitted state:** large pre-existing uncommitted tree (Phase 5 MCP scaffolds, new schemas, new docs, ~140 new SVG diagrams, big edits to `tools/draw-play/draw.py` and `mcps/play-library-mcp/server.py`). Not yet committed — user prefers explicit commit asks (see auto-memory `feedback_no_auto_commit.md`).
