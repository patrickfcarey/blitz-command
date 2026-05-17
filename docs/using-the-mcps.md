# Using the MCPs

blitz-command ships **13 MCP servers** under `mcps/`. Each owns one narrow responsibility; together they expose the play library, formations, concepts, playbooks, and game knowledge to AI agents.

| Server | Purpose | Tools |
|--------|---------|-------|
| [`play-library-mcp`](../mcps/play-library-mcp/README.md) | Plays + disguise families — discovery, authoring, validation, rendering, scouting, pairwise analysis | 21 |
| [`playbook-generation-mcp`](../mcps/playbook-generation-mcp/README.md) | Assembling playbooks + working with authored playbooks (sections, audibles, counter-responses, validation, glossary) | 13 |
| [`game-knowledge-mcp`](../mcps/game-knowledge-mcp/README.md) | Per-game editor capabilities + universal→editor coordinate translation | 9 |
| [`formation-library-mcp`](../mcps/formation-library-mcp/README.md) | Offensive formations — discovery + inspection | 7 |
| [`validation-mcp`](../mcps/validation-mcp/README.md) | Standalone validation of plays / formations / routes / concepts / game profiles | 7 |
| [`coverage-mcp`](../mcps/coverage-mcp/README.md) | Defensive formations / coverage shells | 6 |
| [`route-library-mcp`](../mcps/route-library-mcp/README.md) | The route library | 6 |
| [`run-concept-mcp`](../mcps/run-concept-mcp/README.md) | Run concepts (power, counter, inside-zone, …) | 6 |
| [`pass-concept-mcp`](../mcps/pass-concept-mcp/README.md) | Pass concepts (mesh, smash, drive, …) | 6 |
| [`blocking-scheme-mcp`](../mcps/blocking-scheme-mcp/README.md) | Blocking schemes | 6 |
| [`philosophy-mcp`](../mcps/philosophy-mcp/README.md) | Offensive philosophies | 6 |
| [`pass-protection-mcp`](../mcps/pass-protection-mcp/README.md) | Pass protections | 5 |
| [`play-variant-mcp`](../mcps/play-variant-mcp/README.md) | Play mirroring, strength-flip, family stubs | 4 |

Each server's `mcps/<name>-mcp/README.md` (linked above) is the authoritative tool catalog. Every server also exposes a `manifest()` tool that returns its own purpose + current tool list.

All speak MCP over stdio. Any MCP-aware client can use them: Claude Desktop, Claude Code, custom clients via the `mcp` SDK.

## Registering with a client

Every server registers the same way — the venv Python plus the server script, both as **absolute paths**. Add the servers you need to your client's MCP config (`~/.config/claude/claude_desktop_config.json` for Claude Desktop, `.mcp.json` in a Claude Code project root, or equivalent):

```json
{
  "mcpServers": {
    "play-library": {
      "command": "/abs/path/to/blitz-command/.venv/bin/python",
      "args": ["/abs/path/to/blitz-command/mcps/play-library-mcp/server.py"]
    },
    "playbook-generation": {
      "command": "/abs/path/to/blitz-command/.venv/bin/python",
      "args": ["/abs/path/to/blitz-command/mcps/playbook-generation-mcp/server.py"]
    }
  }
}
```

Repeat the pattern for any of the 13 servers — swap the key and the `mcps/<name>-mcp/server.py` path. Absolute paths matter: clients launch servers from arbitrary working directories. The servers require **Python 3.10+**; the repo `.venv` (created with `python3.11`) satisfies that.

After registering, restart your client.

## Verifying registration

Ask the client *"List the play-library MCP tools"*, or call `manifest()` on any server. If nothing appears, check the client's MCP logs for server stderr — most commonly the wrong Python interpreter, or `mcp`/`pyyaml`/`jsonschema` missing from the venv.

## Tool catalogs

The per-tool catalog for each server lives in its `README.md` (`mcps/<name>-mcp/README.md`) and stays in sync with the code. `manifest()` returns the same list at runtime. The worked examples below cover the two servers most agents start with.

## Worked examples

### 1. Author a new play end-to-end (play-library-mcp)

```python
# Step 1: pick a formation
formations = list_formations()
# pick singleback-trio for an 11-personnel under-center look

# Step 2: scaffold the play
play = build_starter_play(
    formation_id='singleback-trio',
    play_type='play-action',
    philosophy='west-coast',
    play_name='PA Cross',
)
# play is a dict with all 11 assignments — OL pre-set as pass_block,
# skill players have placeholder route_name='TODO-fill-in', HB auto-set to fake

# Step 3: fill in the routes
te = next(a for a in play['assignments'] if a['player'] == 'TE')
te.update({'route_name': 'drag', 'depth_yd': 8, 'is_primary': True})
# ... fill in X, Z, SLOT, QB path, etc.

# Step 4: validate
result = validate_play(play)
if not result['valid']:
    print('Errors:', result['errors'])
# Warnings allowed (TODOs flagged) but errors block save

# Step 5: visualize
svg = render_play(play['play_id'], 'madden-05-ps2', defense_id='defense-4-3-cover-3')
# Save / inspect the SVG to verify the play looks right

# Step 6: persist + mirror
save_play(play)
mirror_play(play['play_id'])
```

### 2. Build a balanced playbook from one formation (play-library + playbook-generation)

```python
# Find what's available (play-library-mcp)
plays_in_formation = find_plays_by_formation('singleback-trio')

# Score a candidate set for disguise quality (play-library-mcp)
candidates = [
    'singleback-trio-inside-zone',
    'singleback-trio-outside-zone',
    'singleback-trio-power',
    'singleback-trio-mesh',
    'singleback-trio-pa-cross',
]
analysis = compare_plays(candidates)
# analysis.disguise_score == 1.0 — same formation, multiple play types, has a fake

# Find what's missing (playbook-generation-mcp)
suggestions = suggest_complementary_plays(candidates, max_results=3)
# Returns ranked list with reasons like "adds rpo (missing from seed)"
```

### 3. Work with an authored playbook (playbook-generation-mcp)

```python
# What playbooks exist?
books = list_playbooks()                       # → [{playbook_id: 'hs-base-2026', ...}]

# Pull the call sheet — every play ranked by derived snap share
sheet = playbook_call_sheet('hs-base-2026')

# Validate it end-to-end (schema, share math, audibles, family self-containment)
report = validate_playbook('hs-base-2026')      # → {valid: True, report: '...'}

# Inspect how the playbook uses a play (role, install, counter_responses)
entry = get_play_in_playbook('hs-base-2026', 'i-formation-power-o')
```

### 4. Scout a play and its disguise family (play-library-mcp)

```python
# How does a defense beat this play, and when do you flip it?
scout = scout_play('i-formation-power-o')       # → defensive_counters + flip_reads

# What other plays look identical to it through the first ~1.5 seconds?
twins = get_disguise_twins('i-formation-power-o')
```

## render_play modes

The `render_play` tool exposes 4 visibility modes via `show=`:

| `show=` | What renders |
|---------|-------------|
| `both` *(default)* | Offense + defense + all assignments (offensive routes/runs + defensive coverage zones/man/rush) |
| `offense` | Both teams visible, only offensive routes/runs drawn (no defensive coverage) |
| `defense` | Both teams visible, only defensive coverage drawn (no offensive routes) |
| `none` | Both teams visible, no assignments at all (just the pre-snap alignment) |

Plus `field='short'` (LOS + 15 yd — deep DBs still visible) or `field='long'` (LOS + 30 yd, default).

For defense-only rendering (no offensive play), use the standalone CLI:
```bash
.venv/bin/python tools/draw-play/draw.py --defense defense-4-3-cover-3 --game madden-05-ps2 -o def.svg
```
That mode isn't exposed through the MCP yet — the MCP `render_play` requires a `play_id`.

## Troubleshooting

- **"No module named 'mcp'"** — wrong Python interpreter. The `mcp` SDK needs Python 3.10+; use the `.venv/bin/python` in the absolute paths.
- **"Schema validation failed"** at server startup — a YAML in `data/` doesn't validate. Run `./run-tests.sh` to see which file. The server logs the offending file to stderr.
- **"No play with id 'foo'"** with a "Did you mean: [...]?" suggestion — check spelling. The error includes close matches.
- **Mirror generation skips a play** — either the mirror already exists (delete it first, or pass `overwrite=True`) or the mirror formation isn't built yet.
