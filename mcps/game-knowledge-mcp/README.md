# game-knowledge-mcp

MCP server exposing blitz-command's game profile database (45 titles: PS1/PS2/PS3 Madden + NCAA) and the real-game team playbook catalog. **11 tools.**

## Tools

- **`list_games(cursor=None, limit=50)`** — all 45 game profiles with id, name, year, platform, era, custom_play_support, verification_status. Paginated
- **`get_game(game_id)`** — full YAML: grid, scale, limits, playbook_caps, engine_quirks, default_playbooks
- **`compare_games(game_id_1, game_id_2)`** — capability diff (grid, route depth, motion options, playbook caps)
- **`find_games_supporting(feature)`** — boolean flag filter (`custom_play_support`, `custom_formation_support`)
- **`find_games_by_era(era)`** — `ps1` / `ps2` / `ps3`
- **`translate_position(game_id, x_yd, y_yd)`** — convert a universal `(x_yd, y_yd)` point to a game's editor grid `(col, row)`
- **`translate_formation(game_id, formation_id)`** — translate all 11 player positions for a formation into editor cells
- **`translate_play(game_id, play_id)`** — translate all assignment paths for a play into per-waypoint editor cells
- **`find_team_playbooks(game_id, style=None, formation_family=None, limit=10)`** — find real team playbooks matching a style or formation emphasis; use to ground generated playbooks in what a game actually contained
- **`get_team_playbook(game_id, team_name)`** — full formation list for one team (partial name match ok)
- **`manifest()`** — this server's purpose, tool list, and worked examples

## Data sources

- `data/games/*/editor-grid.yaml` (45 files) validated against `schemas/game.schema.json`
- `data/games/*/team-playbooks.yaml` — per-team formation catalog derived from the Playbook Gamer research corpus (verification_status: unverified). Available for: madden-04-ps2, madden-05-ps2, madden-07-ps2, ncaa-04-ps2, ncaa-06-ps2, ncaa-07-ps2.
