# CLAUDE.md — Claude Code shim for `blitz-command`

This file loads automatically. **AGENTS.md is NOT auto-loaded** — this
shim exists so the operating manual is reached on the first turn.

## ► FIRST: read [AGENTS.md](AGENTS.md)

@AGENTS.md

Canonical rules live in `AGENTS.md`. Everything below is a pointer
or a rule important enough to state twice.

## Quick reminders (see AGENTS.md for the full rules)

- **Commit identity (H-1):** author AND committer = `Patrick Carey
  <patrickfcarey@gmail.com>`; never "Claude Code", no
  `Co-Authored-By` trailer.
- **Three layers stay separate:** football truth, game truth,
  coordinate translation.
- **Many narrow MCPs, schema-first data.** A new MCP is not complete
  without its `README.md` in the same change.
- **Do not invent game-specific capabilities.** Every such claim
  carries `verified` / `unverified` / `inferred` plus a source.
- **Don't broaden scope unprompted.** Keep `docs/pending-queue.md`
  current in the same change as the work.
- **Tests:** `./run-tests.sh`. Runtime: `.venv/bin/python`.
- **Git:** work on `dev`. If origin is ahead or the branch has
  diverged, stop. Add files by name. Do not push unless asked.

## When in doubt

Read `AGENTS.md`. Anything not in this file is governed by it.
