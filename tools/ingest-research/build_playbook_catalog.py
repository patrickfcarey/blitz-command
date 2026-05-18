#!/usr/bin/env python3
"""Build a per-team formation catalog (team-playbooks.yaml) from Playbook Gamer xlsx data.

Reads one or more xlsx sources for a game and writes
data/games/<game_id>/team-playbooks.yaml — the lookup table that lets the
MCP answer "which real team playbook from game X fits this style?"

Supported source formats (auto-detected from column headers):

  ROW format — PLAYBOOK | FORMATION [| PERSONNEL | PSL]
    Used by: Madden 04/05/07, NCAA 04/07 (Formation List sheet)

  MATRIX format — formation×team matrix where cells are "X" or blank
    Used by: NCAA 04/06/07 Playbook Database (Playbooks sheet)

  STYLE format — PLAYBOOK | STYLE | ... formation-family counts
    Used by: NCAA 04 Formation Type sheet (adds playbook_style; merged with row data)

Usage:
    python3 tools/ingest-research/build_playbook_catalog.py \\
        --game ncaa-06-ps2 \\
        --xlsx "research_artifacts/PS2/NCAA Football 06-.../Spreadhseets/NCAA Football 06 Playbook Database.xlsx" \\
        [--style-xlsx "...NCAA Football 2004 Offensive Formation List.xlsx"]

    python3 tools/ingest-research/build_playbook_catalog.py \\
        --game madden-04-ps2 \\
        --xlsx "research_artifacts/PS2/Madden NFL 04-.../Madden NFL 2004 Offensive Formation List.xlsx"

Writes data/games/<game_id>/team-playbooks.yaml. Safe to re-run; overwrites.
"""
from __future__ import annotations

import argparse
import re
import sys
from collections import defaultdict
from datetime import date
from pathlib import Path

# Allow running from repo root without installing.
sys.path.insert(0, str(Path(__file__).parent))
from parse_xlsx import read_xlsx  # noqa: E402

REPO_ROOT = Path(__file__).parent.parent.parent
DATA_GAMES = REPO_ROOT / "data" / "games"

# Formation-name prefix → family slug
FORMATION_FAMILY_PATTERNS: list[tuple[str, str]] = [
    (r"^singleback", "singleback"),
    (r"^i.form|^i form|^near|^far", "i_form"),
    (r"^shotgun|^gun", "shotgun"),
    (r"^pistol", "pistol"),
    (r"^weak.i|^full.?house", "i_form"),
    (r"^flexbone|^flex.?bone", "flexbone"),
    (r"^wishbone", "wishbone"),
    (r"^power.?t|^power.i", "power_i"),
    (r"^ace\b", "ace"),
    (r"^split.?backs?|^pro.form|^pro set", "pro_set"),
    (r"^double.wing|^single.wing", "wing"),
    (r"^bunch", "bunch"),
    (r"^spread", "spread"),
    (r"^empty", "empty"),
    (r"^trips", "trips"),
    (r"^wildcat", "wildcat"),
]


def _family(formation_name: str) -> str:
    """Return the formation-family slug for a formation name."""
    lowered = formation_name.lower()
    for pattern, family in FORMATION_FAMILY_PATTERNS:
        if re.match(pattern, lowered):
            return family
    return "other"


def _team_id(name: str) -> str:
    """Slugify a team/school name."""
    slug = name.lower()
    slug = re.sub(r"[^a-z0-9]+", "_", slug)
    return slug.strip("_")


def _parse_personnel(raw: str) -> str | None:
    """Normalise a personnel code: '11.0' → '11', '' → None."""
    cleaned = raw.strip()
    if not cleaned:
        return None
    try:
        code = int(float(cleaned))
        return str(code)
    except ValueError:
        return cleaned or None


def _build_team_entry(name: str,
                      formations: list[dict],
                      style: str | None) -> dict:
    """Assemble one team_playbook dict from its raw formation list."""
    # Personnel breakdown (only when codes are present)
    has_personnel = any(f.get("personnel") for f in formations)
    personnel_breakdown: dict[str, int] | None = None
    if has_personnel:
        counts: dict[str, int] = defaultdict(int)
        for f in formations:
            key = f.get("personnel") or "unknown"
            counts[key] += 1
        personnel_breakdown = dict(sorted(counts.items()))

    # Formation-family breakdown
    fam_counts: dict[str, int] = defaultdict(int)
    for f in formations:
        fam_counts[_family(f["name"])] += 1

    return {
        "team_id": _team_id(name),
        "name": name,
        "playbook_style": style,
        "formation_count": len(formations),
        "formations": formations,
        "personnel_breakdown": personnel_breakdown,
        "formation_families": dict(sorted(fam_counts.items())),
    }


# ---------------------------------------------------------------------------
# Format parsers
# ---------------------------------------------------------------------------

def _parse_row_format(rows: list[list[str]]) -> tuple[dict[str, list[dict]], dict[str, str]]:
    """Parse PLAYBOOK | FORMATION [| STYLE | PERSONNEL | PSL] rows.

    Returns (teams_dict, styles_dict):
      teams_dict  — {team_name: [{name, personnel}, ...]}
      styles_dict — {team_name: style}  (empty dict when no STYLE column)
    """
    if not rows:
        return {}, {}
    header = [c.strip().upper() for c in rows[0]]
    try:
        playbook_col = next(i for i, h in enumerate(header) if "PLAYBOOK" in h)
        formation_col = next(i for i, h in enumerate(header) if "FORMATION" in h)
    except StopIteration:
        raise ValueError(f"Row-format sheet missing PLAYBOOK/FORMATION columns; header={header}")

    # Personnel column can be PERSONNEL or PSL
    personnel_col: int | None = None
    for i, h in enumerate(header):
        if h in ("PERSONNEL", "PSL"):
            personnel_col = i
            break

    # STYLE column present in Formation Finder sheets (e.g. NCAA 06)
    style_col: int | None = next((i for i, h in enumerate(header) if h == "STYLE"), None)

    teams: dict[str, list[dict]] = defaultdict(list)
    styles: dict[str, str] = {}
    for row in rows[1:]:
        if not row:
            continue
        team = row[playbook_col].strip() if playbook_col < len(row) else ""
        formation = row[formation_col].strip() if formation_col < len(row) else ""
        if not team or not formation:
            continue
        personnel: str | None = None
        if personnel_col is not None and personnel_col < len(row):
            personnel = _parse_personnel(row[personnel_col])
        teams[team].append({"name": formation, "personnel": personnel})
        if style_col is not None and style_col < len(row):
            style_val = row[style_col].strip()
            if style_val:
                styles[team] = style_val
    return dict(teams), styles


def _parse_matrix_format(rows: list[list[str]]) -> dict[str, list[dict]]:
    """Parse a formation×team matrix (X = team has this formation).

    Header structure varies; the parser looks for the row where team names
    appear and treats subsequent rows as formation rows.

    Returns {team_name: [{name, personnel}, ...]}
    """
    if not rows:
        return {}

    # Locate the header row: the first row that has more than 2 non-empty
    # non-numeric cells (i.e. team names, not totals or codes).
    header_row_idx = 0
    for idx, row in enumerate(rows):
        nonempty = [c for c in row if c.strip() and not re.match(r"^[0-9.]+$", c.strip())]
        if len(nonempty) > 3:
            header_row_idx = idx
            break

    header_row = rows[header_row_idx]
    # Team names start at column 2+ (col 0 is often total/PSL, col 1 is
    # formation name, col 2+ are team name or abbreviation columns).
    # We skip the first two columns (they're meta-columns).
    team_columns: list[tuple[int, str]] = []
    for col_idx, cell in enumerate(header_row):
        team_name = cell.strip()
        if col_idx >= 2 and team_name and not re.match(r"^[0-9.]+$", team_name):
            team_columns.append((col_idx, team_name))

    teams: dict[str, list[dict]] = defaultdict(list)
    # The row immediately after the header row that contains PSL codes (if
    # present) tells us personnel for each formation — but only NCAA 04 has a
    # PSL column (column 1 in the data rows).  Skip that secondary header if
    # it looks like all-numbers.
    data_start = header_row_idx + 1
    # Sometimes row header_row_idx+1 is an additional header (like PSL codes);
    # skip it if column 1 is blank or a label (e.g. "PSL").
    if data_start < len(rows):
        probe = rows[data_start]
        first_cell = probe[0].strip() if probe else ""
        if re.match(r"^[A-Z]+$", first_cell) or first_cell == "":
            data_start += 1

    for row in rows[data_start:]:
        if not row:
            continue
        # Formation name is in column 1 (after total count in col 0)
        formation_name = row[1].strip() if len(row) > 1 else ""
        if not formation_name or re.match(r"^[0-9.]+$", formation_name):
            continue
        # PSL in col 0 (may be absent / numeric)
        psl_raw = row[0].strip() if row else ""
        personnel = _parse_personnel(psl_raw) if re.match(r"^[0-9]+\.?[0-9]*$", psl_raw) else None
        for col_idx, team_name in team_columns:
            if col_idx < len(row) and row[col_idx].strip() in ("X", "x", "✓", "1"):
                teams[team_name].append({"name": formation_name, "personnel": personnel})

    return dict(teams)


def _parse_style_sheet(rows: list[list[str]]) -> dict[str, str]:
    """Parse PLAYBOOK | STYLE | ... → {team_name: style}."""
    if not rows:
        return {}
    header = [c.strip().upper() for c in rows[0]]
    playbook_col = next((i for i, h in enumerate(header) if "PLAYBOOK" in h), None)
    style_col = next((i for i, h in enumerate(header) if h == "STYLE"), None)
    if playbook_col is None or style_col is None:
        return {}
    styles: dict[str, str] = {}
    for row in rows[1:]:
        if not row:
            continue
        team = row[playbook_col].strip() if playbook_col < len(row) else ""
        style = row[style_col].strip() if style_col < len(row) else ""
        if team and style:
            styles[team] = style
    return styles


# ---------------------------------------------------------------------------
# Top-level catalog builder
# ---------------------------------------------------------------------------

def build_catalog(game_id: str,
                  xlsx_path: str,
                  style_xlsx_path: str | None = None) -> dict:
    """Parse xlsx data and return a team-playbooks dict ready for YAML serialisation."""
    sheets = read_xlsx(xlsx_path)

    # Determine format by trying both parsers.
    teams_by_name: dict[str, list[dict]] = {}
    styles: dict[str, str] = {}

    for sheet_name, rows in sheets.items():
        non_empty = [r for r in rows if r]
        if not non_empty:
            continue
        header = [c.strip().upper() for c in non_empty[0]]
        has_playbook = any("PLAYBOOK" in h for h in header)
        has_formation = any("FORMATION" in h for h in header)
        has_style = any(h == "STYLE" for h in header)

        if has_playbook and has_style and not has_formation:
            # Style-only sheet (e.g. NCAA 04 Formation Type: PLAYBOOK | STYLE | family counts)
            styles.update(_parse_style_sheet(non_empty))
        elif has_playbook and has_formation:
            # Row-format formation list; may also carry a STYLE column
            parsed, row_styles = _parse_row_format(non_empty)
            teams_by_name.update(parsed)
            styles.update(row_styles)
        else:
            # Try matrix format if this looks like a playbook database
            sheet_lower = sheet_name.lower()
            if "playbook" in sheet_lower or "formation" in sheet_lower or "matrix" in sheet_lower:
                parsed = _parse_matrix_format(non_empty)
                if parsed:
                    # Matrix results supplement (don't overwrite row-format results)
                    for team, formations in parsed.items():
                        if team not in teams_by_name:
                            teams_by_name[team] = formations

    # If a separate style xlsx was provided (e.g. NCAA 04 Formation Type)
    if style_xlsx_path:
        style_sheets = read_xlsx(style_xlsx_path)
        for _, rows in style_sheets.items():
            non_empty = [r for r in rows if r]
            if non_empty:
                styles.update(_parse_style_sheet(non_empty))

    if not teams_by_name:
        raise ValueError(f"No formation data found in {xlsx_path}")

    teams = []
    for team_name in sorted(teams_by_name):
        formations = teams_by_name[team_name]
        style = styles.get(team_name)
        teams.append(_build_team_entry(team_name, formations, style))

    return {
        "game_id": game_id,
        "source": "Playbook Gamer",
        "verification_status": "unverified",
        "generated_date": str(date.today()),
        "notes": f"Derived from {Path(xlsx_path).name}. "
                 "Per layering rules: game-truth data; not in-game-verified.",
        "teams": teams,
    }


# ---------------------------------------------------------------------------
# YAML writer (no pyyaml dependency needed — hand-write it)
# ---------------------------------------------------------------------------

def _yaml_str(value: str) -> str:
    """Wrap a string value for YAML — quotes if it contains special chars."""
    if not value:
        return '""'
    if any(ch in value for ch in (': ', '#', '[', ']', '{', '}', ',', '&', '*', '!', "'", '"', '\n')):
        return '"' + value.replace('\\', '\\\\').replace('"', '\\"') + '"'
    return value


def _write_yaml(catalog: dict, path: Path) -> None:
    """Write the catalog dict to a YAML file."""
    lines: list[str] = []
    lines.append(f"game_id: {catalog['game_id']}")
    lines.append(f"source: {_yaml_str(catalog['source'])}")
    lines.append(f"verification_status: {catalog['verification_status']}")
    lines.append(f"generated_date: \"{catalog['generated_date']}\"")
    lines.append(f"notes: {_yaml_str(catalog['notes'])}")
    lines.append("teams:")
    for team in catalog["teams"]:
        lines.append(f"  - team_id: {team['team_id']}")
        lines.append(f"    name: {_yaml_str(team['name'])}")
        style = team["playbook_style"]
        lines.append(f"    playbook_style: {_yaml_str(style) if style else 'null'}")
        lines.append(f"    formation_count: {team['formation_count']}")
        # Formation families
        lines.append("    formation_families:")
        for fam, count in (team["formation_families"] or {}).items():
            lines.append(f"      {fam}: {count}")
        # Personnel breakdown
        if team["personnel_breakdown"]:
            lines.append("    personnel_breakdown:")
            for code, count in team["personnel_breakdown"].items():
                lines.append(f"      \"{code}\": {count}")
        else:
            lines.append("    personnel_breakdown: null")
        # Formations list
        lines.append("    formations:")
        for f in team["formations"]:
            name_yaml = _yaml_str(f["name"])
            psl = f.get("personnel")
            if psl:
                lines.append(f"      - name: {name_yaml}")
                lines.append(f"        personnel: \"{psl}\"")
            else:
                lines.append(f"      - name: {name_yaml}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main(argv: list[str]) -> None:
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Build data/games/<game_id>/team-playbooks.yaml from an xlsx source.")
    parser.add_argument("--game", required=True,
                        help="Game ID matching data/games/<id>/ (e.g. madden-04-ps2)")
    parser.add_argument("--xlsx", required=True,
                        help="Path to the primary xlsx source")
    parser.add_argument("--style-xlsx",
                        help="Optional second xlsx that has a STYLE column (e.g. NCAA 04 Formation Type)")
    args = parser.parse_args(argv[1:])

    game_dir = DATA_GAMES / args.game
    if not game_dir.exists():
        print(f"ERROR: game directory not found: {game_dir}", file=sys.stderr)
        sys.exit(1)

    print(f"Parsing {args.xlsx} ...")
    catalog = build_catalog(args.game, args.xlsx, args.style_xlsx)
    out_path = game_dir / "team-playbooks.yaml"
    _write_yaml(catalog, out_path)
    team_count = len(catalog["teams"])
    formation_total = sum(t["formation_count"] for t in catalog["teams"])
    print(f"Wrote {out_path}")
    print(f"  {team_count} teams, {formation_total} formation entries")


if __name__ == "__main__":
    main(sys.argv)
