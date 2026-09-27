"""Per-game export format adapters for play instructions.

Each game era uses slightly different editor terminology and UI conventions.
Register new games by subclassing BaseFormatter and adding to GAME_FORMATTERS.

Usage:
    from tools.export_instructions.formatters import get_formatter
    fmt = get_formatter('madden-05-ps2')
    instructions = fmt.format_instructions(play, formation, profile, cells)
"""
from __future__ import annotations

from typing import Any


class BaseFormatter:
    """Generic formatter — used as fallback for unregistered games."""

    game_id_pattern: str = ""  # substring match; '' matches everything

    def player_label(self, label: str) -> str:
        """Translate universal player label to game-specific UI label."""
        return label

    def position_label(self, x_cell: int, y_cell: int) -> str:
        """Format a grid cell as a human-readable position string."""
        return f"column {x_cell}, row {y_cell}"

    def route_label(self, route_name: str) -> str:
        """Translate a route name to the game's menu label."""
        return route_name.replace("-", " ").title()

    def blocking_scheme_label(self, scheme: str) -> str:
        """Translate a blocking scheme to the game's label."""
        return scheme.replace("-", " ").replace("_", " ").title()

    def motion_label(self, motion_type: str) -> str:
        """Translate a motion type to the game's label."""
        return motion_type.replace("-", " ").title()

    def header(self, play_name: str, game_name: str, formation_id: str) -> str:
        return (
            f"# Recreate \"{play_name}\" in {game_name}\n\n"
            f"**Formation:** {formation_id}  \n"
            f"**Editor:** Create-A-Play mode\n\n"
        )

    def footer(self, notes: list[str]) -> str:
        if not notes:
            return ""
        return "\n## Notes\n\n" + "\n".join(f"- {n}" for n in notes) + "\n"

    def format_player_positions(self, player_cells: dict[str, tuple[int, int]]) -> str:
        lines = ["## Pre-snap player positions\n", "| Player | Cell (col, row) |", "|--------|-----------------|"]
        for label, (col, row) in sorted(player_cells.items()):
            game_label = self.player_label(label)
            lines.append(f"| {game_label} | ({col}, {row}) |")
        return "\n".join(lines) + "\n"

    def format_routes(self, routes: list[dict[str, Any]]) -> str:
        if not routes:
            return ""
        lines = ["## Routes\n"]
        for r in routes:
            player = self.player_label(r.get("player", "?"))
            route = self.route_label(r.get("route_name", "?"))
            depth = r.get("depth_yd")
            depth_str = f" (~{depth:.0f} yd)" if depth else ""
            lines.append(f"- **{player}**: {route}{depth_str}")
        return "\n".join(lines) + "\n"

    def format_blocking(self, blocking: list[dict[str, Any]]) -> str:
        if not blocking:
            return ""
        lines = ["## Blocking\n"]
        for b in blocking:
            player = self.player_label(b.get("player", "?"))
            scheme = self.blocking_scheme_label(b.get("scheme", "block"))
            target = b.get("target", "")
            target_str = f" → {target}" if target else ""
            lines.append(f"- **{player}**: {scheme}{target_str}")
        return "\n".join(lines) + "\n"

    def format_reads(self, reads: dict[str, str]) -> str:
        if not reads:
            return ""
        lines = ["## Read tree\n"]
        for label, player in reads.items():
            if player:
                lines.append(f"- **{label.replace('_', ' ').title()}**: {self.player_label(player)}")
        return "\n".join(lines) + "\n"


class Madden05PS2Formatter(BaseFormatter):
    """Madden NFL 2005 PS2 — confirmed 21×7 grid. Uses 'Receiver 1/2/3' labels in UI."""

    game_id_pattern = "madden-05-ps2"

    _PLAYER_MAP = {
        "X": "WR1",
        "Z": "WR2",
        "SLOT": "WR3",
        "TE": "TE",
        "HB": "HB",
        "FB": "FB",
        "QB": "QB",
    }

    def player_label(self, label: str) -> str:
        return self._PLAYER_MAP.get(label, label)

    def position_label(self, x_cell: int, y_cell: int) -> str:
        return f"Grid {x_cell},{y_cell}"

    def header(self, play_name: str, game_name: str, formation_id: str) -> str:
        return (
            f"# Recreate \"{play_name}\" in {game_name}\n\n"
            f"**Formation:** {formation_id}  \n"
            f"**How to open editor:** Press START → My Playbook → Create-A-Play\n\n"
            f"> Grid is 21 columns × 7 rows. Origin (QB under center) = column 10, row 5.\n\n"
        )


class Madden10PS2Formatter(BaseFormatter):
    """Madden NFL 10 PS2 — same 21×7 grid, slightly different UI text from Madden 05."""

    game_id_pattern = "madden-10-ps2"

    def header(self, play_name: str, game_name: str, formation_id: str) -> str:
        return (
            f"# Recreate \"{play_name}\" in {game_name}\n\n"
            f"**Formation:** {formation_id}  \n"
            f"**How to open editor:** START → Playbooks → My Plays → Create New Play\n\n"
            f"> Grid is 21 columns × 7 rows. Center of field = column 10, row 5.\n\n"
        )


class Madden10PS3Formatter(BaseFormatter):
    """Madden NFL 10 PS3 — expanded 25×9 grid, richer route menu."""

    game_id_pattern = "madden-10-ps3"

    _ROUTE_MAP = {
        "slant": "Slant",
        "drag": "Drag",
        "post": "Post",
        "corner": "Corner",
        "go": "Streak",
        "fade": "Fade",
        "out": "Out",
        "in": "In",
        "dig": "Dig",
        "comeback": "Comeback",
        "hitch": "Hitch",
        "flat": "Flat",
        "seam": "Seam",
        "wheel": "Wheel",
        "snag": "Snag",
        "stick": "Stick",
        "sail": "Sail",
        "deep-cross": "Post Cross",
    }

    def route_label(self, route_name: str) -> str:
        return self._ROUTE_MAP.get(route_name.lower(), route_name.replace("-", " ").title())

    def header(self, play_name: str, game_name: str, formation_id: str) -> str:
        return (
            f"# Recreate \"{play_name}\" in {game_name}\n\n"
            f"**Formation:** {formation_id}  \n"
            f"**How to open editor:** Main Menu → Playbooks → Create-A-Play\n\n"
            f"> Grid is 25 columns × 9 rows. Origin = column 12, row 6. More depth available than PS2.\n\n"
        )


class NCAA06PS2Formatter(BaseFormatter):
    """NCAA Football 06 PS2 — same 21×7 grid as Madden PS2."""

    game_id_pattern = "ncaa-06-ps2"

    def header(self, play_name: str, game_name: str, formation_id: str) -> str:
        return (
            f"# Recreate \"{play_name}\" in {game_name}\n\n"
            f"**Formation:** {formation_id}  \n"
            f"**How to open editor:** Main Menu → My Playbook → Create A Play\n\n"
            f"> Grid is 21 columns × 7 rows. Same layout as Madden 05 PS2.\n\n"
        )


# Registry: checked in order, first match wins; BaseFormatter is the fallback
_FORMATTERS: list[BaseFormatter] = [
    Madden05PS2Formatter(),
    Madden10PS2Formatter(),
    Madden10PS3Formatter(),
    NCAA06PS2Formatter(),
]

_FALLBACK = BaseFormatter()


def get_formatter(game_id: str) -> BaseFormatter:
    """Return the best formatter for the given game_id.

    Falls back to BaseFormatter if no game-specific formatter is registered.

    Args:
        game_id: e.g. 'madden-05-ps2', 'ncaa-06-ps2'.
    """
    for fmt in _FORMATTERS:
        if fmt.game_id_pattern and fmt.game_id_pattern in game_id:
            return fmt
    return _FALLBACK


def list_registered_games() -> list[str]:
    """Return all game_id patterns with dedicated formatters."""
    return [f.game_id_pattern for f in _FORMATTERS if f.game_id_pattern]
