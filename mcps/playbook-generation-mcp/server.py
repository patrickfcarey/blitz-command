#!/usr/bin/env python3
"""Playbook Generation MCP server.

Assembles custom playbooks from the blitz-command library. Owns all
collection-level reasoning: selecting plays, filling gaps in a playbook,
and (Phase 7) optimizing a full book for balance and disguise.

Boundary rule: this server reasons about *collections* of plays as a unit.
Single-play analysis (compare two plays, predict a matchup) belongs in
play-library-mcp.

Tools:
  Assembly (build a playbook from the library):
    - assemble_playbook_simple, suggest_complementary_plays,
      list_formations_with_plays, list_philosophies_with_plays
  Authored playbooks (data/playbooks/ — sections, audibles, counter_responses):
    - list_playbooks, get_playbook, get_playbook_section, get_audibles,
      get_play_in_playbook, validate_playbook, playbook_call_sheet,
      playbook_glossary, playbook_tendency_profile, playbook_call_breakdown,
      playbook_install_schedule

Requires Python 3.10+.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import yaml
from mcp.server.fastmcp import FastMCP

REPO_ROOT = Path(__file__).resolve().parents[2]
PLAYS_DIR = REPO_ROOT / "data" / "plays"
FORMATIONS_DIR = REPO_ROOT / "data" / "formations"
GAMES_DIR = REPO_ROOT / "data" / "games"
CONCEPTS_DIR = REPO_ROOT / "data" / "concepts"
PLAYBOOKS_DIR = REPO_ROOT / "data" / "playbooks"
VALIDATE_SCRIPT = REPO_ROOT / "tools" / "validate-playbook" / "validate.py"
GLOSSARY_SCRIPT = REPO_ROOT / "tools" / "compile-glossary" / "compile_glossary.py"
PROFILE_SCRIPT = REPO_ROOT / "tools" / "playbook-profile" / "profile.py"
BREAKDOWN_SCRIPT = REPO_ROOT / "tools" / "playbook-call-breakdown" / "breakdown.py"
SCHEDULE_SCRIPT = REPO_ROOT / "tools" / "playbook-install-schedule" / "schedule.py"

mcp = FastMCP("playbook-generation")


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _dir_mtime(directory: Path) -> float:
    if not directory.exists():
        return 0.0
    return directory.stat().st_mtime


_PLAYS_CACHE: dict[str, dict[str, Any]] | None = None
_PLAYS_CACHE_MTIME: float = 0.0


def _load_all_plays() -> dict[str, dict[str, Any]]:
    """Load every play file. Cached by directory mtime."""
    global _PLAYS_CACHE, _PLAYS_CACHE_MTIME
    current_mtime = _dir_mtime(PLAYS_DIR)
    if _PLAYS_CACHE is not None and current_mtime == _PLAYS_CACHE_MTIME:
        return _PLAYS_CACHE
    plays: dict[str, dict[str, Any]] = {}
    for path in sorted(PLAYS_DIR.glob("*.yaml")):
        try:
            with open(path) as f:
                data = yaml.safe_load(f)
            if data:
                plays[path.stem] = data
        except Exception:
            continue
    _PLAYS_CACHE = plays
    _PLAYS_CACHE_MTIME = current_mtime
    return plays


_FORMATIONS_CACHE: dict[str, dict[str, Any]] | None = None
_FORMATIONS_CACHE_MTIME: float = 0.0


def _load_all_formations() -> dict[str, dict[str, Any]]:
    """Load every formation file. Cached by directory mtime."""
    global _FORMATIONS_CACHE, _FORMATIONS_CACHE_MTIME
    current_mtime = _dir_mtime(FORMATIONS_DIR)
    if _FORMATIONS_CACHE is not None and current_mtime == _FORMATIONS_CACHE_MTIME:
        return _FORMATIONS_CACHE
    forms: dict[str, dict[str, Any]] = {}
    for fp in FORMATIONS_DIR.glob("*.yaml"):
        try:
            with open(fp) as f:
                data = yaml.safe_load(f)
            if data:
                forms[fp.stem] = data
        except Exception:
            continue
    _FORMATIONS_CACHE = forms
    _FORMATIONS_CACHE_MTIME = current_mtime
    return forms


_PLAYBOOKS_CACHE: dict[str, dict[str, Any]] | None = None
_PLAYBOOKS_CACHE_MTIME: float = 0.0
_PLAYBOOK_PATHS: dict[str, Path] = {}


def _load_all_playbooks() -> dict[str, dict[str, Any]]:
    """Load every playbook file from data/playbooks/, keyed by playbook_id.
    Cached by directory mtime; also records each playbook's file path."""
    global _PLAYBOOKS_CACHE, _PLAYBOOKS_CACHE_MTIME, _PLAYBOOK_PATHS
    current_mtime = _dir_mtime(PLAYBOOKS_DIR)
    if _PLAYBOOKS_CACHE is not None and current_mtime == _PLAYBOOKS_CACHE_MTIME:
        return _PLAYBOOKS_CACHE
    books: dict[str, dict[str, Any]] = {}
    paths: dict[str, Path] = {}
    if PLAYBOOKS_DIR.exists():
        for path in sorted(PLAYBOOKS_DIR.glob("*.yaml")):
            try:
                with open(path) as f:
                    data = yaml.safe_load(f)
                if data and data.get("playbook_id"):
                    books[data["playbook_id"]] = data
                    paths[data["playbook_id"]] = path
            except Exception:
                continue
    _PLAYBOOKS_CACHE = books
    _PLAYBOOK_PATHS = paths
    _PLAYBOOKS_CACHE_MTIME = current_mtime
    return books


def _load_formation(formation_id: str) -> dict[str, Any] | None:
    return _load_all_formations().get(formation_id)


def _load_game(game_id: str) -> dict[str, Any] | None:
    game_file = GAMES_DIR / game_id / "editor-grid.yaml"
    if not game_file.exists():
        return None
    with open(game_file) as f:
        return yaml.safe_load(f)


def _play_fits_game(play: dict[str, Any], game: dict[str, Any]) -> bool:
    """Return True if this play's assignments fall within the game's editor limits."""
    limits = game.get("limits") or {}
    max_depth = limits.get("max_route_depth_yd", 100)
    max_split = limits.get("max_player_split_yd", 100)
    max_backfield = limits.get("max_backfield_depth_yd", 100)

    for assign in play.get("assignments", []):
        for wp in assign.get("path") or []:
            if len(wp) < 2:
                continue
            x, y = wp[0], wp[1]
            if y > max_depth:
                return False
            if abs(x) > max_split:
                return False
            if y < 0 and abs(y) > max_backfield:
                return False
    return True


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------

@mcp.tool()
def assemble_playbook_simple(
    formation_constraint: str | None = None,
    play_count: int = 20,
    philosophy: str | None = None,
    game_id: str | None = None,
    play_type_mix: dict[str, float] | None = None,
) -> dict[str, Any]:
    """Assemble a simple playbook from library plays matching the constraints.

    Selects plays to hit a target play-type distribution (run/pass/play-action/
    screen/rpo). Does NOT optimize for play-family balance — use Phase 7's
    generate_play_family for that.

    Returns:
        {
          "plays":     [{"play_id": ..., "name": ..., "type": ..., "formation": ...}],
          "count":     int,
          "breakdown": {"run": N, "pass": N, "play-action": N, ...},
          "game_filter_applied": bool,
          "warnings":  list[str],
        }

    Args:
        formation_constraint: if set, only include plays from this formation
            (e.g., 'singleback-trio', 'i-formation'). Partial match allowed.
        play_count: target number of plays (default 20; capped at game's max_plays_total if game_id given).
        philosophy: if set, prefer plays tagged with this philosophy
            (e.g., 'west-coast', 'power-run', 'air-raid').
        game_id: if set, filter plays to only those within this game's editor limits
            AND cap play_count at the game's max_plays_total.
        play_type_mix: optional dict with target fractions for each play type
            (keys: 'run', 'pass', 'play-action', 'screen', 'rpo').
            Defaults to {'run': 0.45, 'pass': 0.40, 'play-action': 0.10, 'screen': 0.03, 'rpo': 0.02}.

    Example:
        >>> pb = assemble_playbook_simple(
        ...     formation_constraint='i-formation',
        ...     play_count=15,
        ...     philosophy='power-run',
        ...     game_id='madden-05-ps2',
        ... )
        >>> [p['play_id'] for p in pb['plays'][:3]]
        ['i-formation-counter-trey', 'i-formation-inside-zone', 'i-formation-power']
    """
    warnings: list[str] = []
    default_mix: dict[str, float] = {
        "run": 0.45, "pass": 0.40, "play-action": 0.10, "screen": 0.03, "rpo": 0.02,
    }
    mix = play_type_mix or default_mix

    game: dict[str, Any] | None = None
    game_max_plays: int | None = None
    if game_id:
        game = _load_game(game_id)
        if game is None:
            warnings.append(f"game_id '{game_id}' not found — no game filter applied")
        elif not game.get("custom_play_support"):
            warnings.append(f"game '{game_id}' has no play editor — game filter still applied for limits")
        else:
            caps = game.get("playbook_caps") or {}
            game_max_plays = caps.get("max_plays_total")

    if game_max_plays is not None and play_count > game_max_plays:
        warnings.append(f"play_count {play_count} exceeds game cap {game_max_plays}; capping")
        play_count = game_max_plays

    all_plays = list(_load_all_plays().values())

    if formation_constraint:
        fc_lower = formation_constraint.lower()
        filtered = [p for p in all_plays if fc_lower in (p.get("formation") or "").lower()]
        if not filtered:
            warnings.append(f"no plays found for formation_constraint '{formation_constraint}'")
            filtered = all_plays
        all_plays = filtered

    game_filter_applied = False
    if game and game.get("limits"):
        before = len(all_plays)
        all_plays = [p for p in all_plays if _play_fits_game(p, game)]
        after = len(all_plays)
        game_filter_applied = True
        if before != after:
            warnings.append(f"{before - after} plays excluded by game editor limits")

    if philosophy:
        phil_lower = philosophy.lower()
        def sort_key(p: dict) -> int:
            tags = [t.lower() for t in p.get("tags", [])]
            return 0 if phil_lower in tags or phil_lower == (p.get("philosophy") or "").lower() else 1
        all_plays = sorted(all_plays, key=sort_key)

    by_type: dict[str, list[dict]] = {}
    for p in all_plays:
        pt = p.get("play_type", "other")
        by_type.setdefault(pt, []).append(p)

    selected: list[dict[str, Any]] = []
    targets: dict[str, int] = {
        pt: round(frac * play_count) for pt, frac in mix.items()
    }
    total_targeted = sum(targets.values())
    if total_targeted < play_count:
        targets["run"] += play_count - total_targeted

    for pt, target_n in targets.items():
        available = by_type.get(pt, [])
        already_ids = {p["play_id"] for p in selected}
        pool = [p for p in available if p.get("play_id") not in already_ids]
        selected.extend(pool[:target_n])

    remaining_ids = {p["play_id"] for p in selected}
    extras = [p for p in all_plays if p.get("play_id") not in remaining_ids]
    while len(selected) < play_count and extras:
        selected.append(extras.pop(0))

    selected = selected[:play_count]

    breakdown: dict[str, int] = {}
    for p in selected:
        pt = p.get("play_type", "other")
        breakdown[pt] = breakdown.get(pt, 0) + 1

    return {
        "plays": [
            {
                "play_id": p.get("play_id"),
                "name": p.get("name"),
                "type": p.get("play_type"),
                "formation": p.get("formation"),
                "philosophy": p.get("philosophy"),
            }
            for p in selected
        ],
        "count": len(selected),
        "breakdown": breakdown,
        "game_filter_applied": game_filter_applied,
        "warnings": warnings,
    }


@mcp.tool()
def suggest_complementary_plays(
    seed_play_ids: list[str],
    max_results: int = 5,
    require_same_formation: bool = False,
) -> list[dict[str, Any]]:
    """Suggest plays that fill gaps in an in-progress playbook.

    Given a set of seed plays, finds candidates that:
        - share the dominant formation (preferred for disguise),
          OR a same-personnel formation (acceptable),
        - introduce a play_type the seed set is missing,
        - use a ball_carrier or mechanic the seed set lacks.

    Each suggestion includes a 'reason' string explaining why it was picked.

    Example:
        >>> seed = ['singleback-trio-inside-zone', 'singleback-trio-mesh']
        >>> suggest_complementary_plays(seed, max_results=3)
        [{'play_id': 'singleback-trio-pa-cross',
          'reason': 'adds play-action (missing from seed); same formation; uses fake'},
         {'play_id': 'singleback-trio-power',
          'reason': 'same formation; second run scheme — power vs zone'},
         ...]

    Args:
        seed_play_ids:           plays already in the playbook.
        max_results:             how many suggestions to return (default 5).
        require_same_formation:  if True, only suggest plays from the dominant
                                 formation. If False (default), allow other
                                 formations sharing the same personnel grouping.
    """
    all_plays = _load_all_plays()
    seed_set: dict[str, dict[str, Any]] = {pid: all_plays[pid] for pid in seed_play_ids if pid in all_plays}
    if not seed_set:
        raise ValueError("no valid seed_play_ids found in library")

    seed_formations: dict[str, int] = {}
    for p in seed_set.values():
        f = p.get("formation")
        if f:
            seed_formations[f] = seed_formations.get(f, 0) + 1
    dominant_formation = max(seed_formations, key=seed_formations.get)
    dominant_form_obj = _load_formation(dominant_formation) or {}
    dominant_personnel = dominant_form_obj.get("personnel")

    seed_play_types = {p.get("play_type") for p in seed_set.values() if p.get("play_type")}
    seed_ball_carriers = {p.get("ball_carrier") for p in seed_set.values() if p.get("ball_carrier")}
    seed_has_fake = any(
        any(a.get("role") == "fake" for a in (p.get("assignments") or []))
        for p in seed_set.values()
    )

    personnel_by_formation: dict[str, str | None] = {
        fid: f.get("personnel") for fid, f in _load_all_formations().items()
    }

    candidates: list[tuple[float, str, str]] = []
    for pid, p in all_plays.items():
        if pid in seed_set:
            continue
        if pid.endswith("-left"):
            continue
        fid = p.get("formation")
        same_form = (fid == dominant_formation)
        same_personnel = personnel_by_formation.get(fid) == dominant_personnel and dominant_personnel is not None
        if require_same_formation and not same_form:
            continue
        if not same_form and not same_personnel:
            continue
        score = 0.0
        reasons: list[str] = []
        if same_form:
            score += 1.0
            reasons.append("same formation")
        else:
            score += 0.4
            reasons.append(f"same personnel ({dominant_personnel}) from {fid}")
        ptype = p.get("play_type")
        if ptype and ptype not in seed_play_types:
            score += 1.5
            reasons.append(f"adds {ptype} (missing from seed)")
        bc = p.get("ball_carrier")
        if bc and bc not in seed_ball_carriers:
            score += 0.5
            reasons.append(f"new ball-carrier ({bc})")
        if not seed_has_fake:
            has_fake = any(a.get("role") == "fake" for a in (p.get("assignments") or []))
            if has_fake:
                score += 0.6
                reasons.append("introduces a fake/PA mechanic")
        candidates.append((score, pid, "; ".join(reasons)))

    candidates.sort(key=lambda x: -x[0])
    return [
        {"play_id": pid, "score": round(s, 3), "reason": reason}
        for s, pid, reason in candidates[:max_results]
    ]


@mcp.tool()
def list_formations_with_plays() -> list[str]:
    """Return a sorted list of formation IDs that have at least one play in the library.

    Returns only formations covered by play files — a subset of all formations
    in formation-library-mcp. Useful for discovering valid values for
    assemble_playbook_simple's formation_constraint parameter.

    Example:
        >>> list_formations_with_plays()
        ['big-i', 'empty', 'flexbone', 'i-formation', 'pistol', ...]
    """
    formations: set[str] = set()
    for path in PLAYS_DIR.glob("*.yaml"):
        try:
            with open(path) as f:
                data = yaml.safe_load(f)
            if data and data.get("formation"):
                formations.add(data["formation"])
        except Exception:
            continue
    return sorted(formations)


@mcp.tool()
def list_philosophies_with_plays() -> list[str]:
    """Return a sorted list of philosophy IDs that have at least one play in the library.

    Returns only philosophies represented in play files — a subset of all
    philosophies in philosophy-mcp. Useful for discovering valid values for
    assemble_playbook_simple's philosophy parameter.
    """
    philosophies: set[str] = set()
    for path in PLAYS_DIR.glob("*.yaml"):
        try:
            with open(path) as f:
                data = yaml.safe_load(f)
            if data and data.get("philosophy"):
                philosophies.add(data["philosophy"])
        except Exception:
            continue
    return sorted(philosophies)


@mcp.tool()
def list_playbooks() -> list[dict[str, Any]]:
    """List every authored playbook in data/playbooks/.

    A playbook is a curated collection of plays organized into formation
    sections + situational sections, with a designated audible system. Use
    get_playbook(id) for the full record.
    """
    out: list[dict[str, Any]] = []
    for pid, pb in sorted(_load_all_playbooks().items()):
        fsecs = pb.get("formation_sections") or []
        out.append({
            "playbook_id": pid,
            "name": pb.get("name"),
            "audience": pb.get("audience"),
            "audible_mode": pb.get("audible_mode"),
            "formation_sections": len(fsecs),
            "situational_sections": len(pb.get("situational_sections") or []),
            "play_count": sum(len(s.get("plays") or []) for s in fsecs),
        })
    return out


@mcp.tool()
def get_playbook(playbook_id: str) -> dict[str, Any]:
    """Return a playbook's full record — sections, play entries, audibles,
    counter_responses.

    Args:
        playbook_id: see list_playbooks().
    """
    books = _load_all_playbooks()
    pb = books.get(playbook_id)
    if pb is None:
        from difflib import get_close_matches
        return {"error": f"no playbook '{playbook_id}'",
                "did_you_mean": get_close_matches(playbook_id, list(books), n=3),
                "available": sorted(books)}
    return pb


@mcp.tool()
def get_playbook_section(playbook_id: str, section_id: str) -> dict[str, Any]:
    """Return one section of a playbook — a formation_section or a
    situational_section.

    Args:
        playbook_id: see list_playbooks().
        section_id:  the section's id.
    """
    pb = _load_all_playbooks().get(playbook_id)
    if pb is None:
        return {"error": f"no playbook '{playbook_id}'"}
    for sec in (pb.get("formation_sections") or []):
        if sec.get("section_id") == section_id:
            return {"kind": "formation_section", **sec}
    for sec in (pb.get("situational_sections") or []):
        if sec.get("section_id") == section_id:
            return {"kind": "situational_section", **sec}
    available = ([s.get("section_id") for s in (pb.get("formation_sections") or [])]
                 + [s.get("section_id") for s in (pb.get("situational_sections") or [])])
    return {"error": f"no section '{section_id}' in '{playbook_id}'", "available": available}


@mcp.tool()
def get_audibles(playbook_id: str) -> dict[str, Any]:
    """Return a playbook's audible system.

    In 'global' audible_mode there is one playbook-wide pool (the `audibles`
    array); in 'per-formation' mode each formation_section carries its own.

    Args:
        playbook_id: see list_playbooks().
    """
    pb = _load_all_playbooks().get(playbook_id)
    if pb is None:
        return {"error": f"no playbook '{playbook_id}'"}
    mode = pb.get("audible_mode")
    if mode == "per-formation":
        pools = {s.get("section_id"): (s.get("audibles") or [])
                 for s in (pb.get("formation_sections") or [])}
        return {"audible_mode": mode, "per_formation_pools": pools}
    return {"audible_mode": mode, "audibles": pb.get("audibles") or []}


@mcp.tool()
def get_play_in_playbook(playbook_id: str, play_id: str) -> dict[str, Any]:
    """Return a play's ENTRY within a playbook — its role, install_order, call
    shares, expected_calls_per_game, practice_reps, and counter_responses (the
    pre-snap defensive-counter -> audible mappings).

    Distinct from play-library-mcp's get_play (the football play itself): this
    is how the playbook USES the play.

    Args:
        playbook_id: see list_playbooks().
        play_id:     the play to look up.
    """
    pb = _load_all_playbooks().get(playbook_id)
    if pb is None:
        return {"error": f"no playbook '{playbook_id}'"}
    for sec in (pb.get("formation_sections") or []):
        for entry in (sec.get("plays") or []):
            if entry.get("play_id") == play_id:
                return {"playbook_id": playbook_id,
                        "section_id": sec.get("section_id"), "entry": entry}
    return {"error": f"play '{play_id}' is not in playbook '{playbook_id}'"}


@mcp.tool()
def validate_playbook(playbook_id: str) -> dict[str, Any]:
    """Validate a playbook end-to-end — schema, share-math rollups, audible
    integrity, counter_ref resolution, and disguise-family self-containment.

    Runs tools/validate-playbook/validate.py and returns its full report.

    Args:
        playbook_id: see list_playbooks().
    """
    books = _load_all_playbooks()
    if playbook_id not in books:
        return {"error": f"no playbook '{playbook_id}'", "available": sorted(books)}
    path = _PLAYBOOK_PATHS.get(playbook_id)
    if path is None or not path.exists():
        return {"error": f"could not locate the file for playbook '{playbook_id}'"}
    try:
        proc = subprocess.run(
            [sys.executable, str(VALIDATE_SCRIPT), str(path)],
            capture_output=True, text=True, timeout=60,
        )
    except Exception as e:  # noqa: BLE001
        return {"error": f"validator failed to run: {e}"}
    return {
        "playbook_id": playbook_id,
        "valid": proc.returncode == 0,
        "report": (proc.stdout or "") + (proc.stderr or ""),
    }


@mcp.tool()
def playbook_call_sheet(playbook_id: str) -> dict[str, Any]:
    """Return a call sheet — every play in the playbook with its DERIVED total
    snap share (section target_snap_share_pct x play share_of_section_pct),
    sorted by that share. The coach's-eye view of what gets called most.

    Args:
        playbook_id: see list_playbooks().
    """
    pb = _load_all_playbooks().get(playbook_id)
    if pb is None:
        return {"error": f"no playbook '{playbook_id}'"}
    rows: list[dict[str, Any]] = []
    for sec in (pb.get("formation_sections") or []):
        sec_share = sec.get("target_snap_share_pct")
        for entry in (sec.get("plays") or []):
            pshare = entry.get("share_of_section_pct")
            total = None
            if sec_share is not None and pshare is not None:
                total = round(sec_share * pshare / 100, 2)
            rows.append({
                "play_id": entry.get("play_id"),
                "section_id": sec.get("section_id"),
                "role": entry.get("role"),
                "share_of_section_pct": pshare,
                "total_snap_share_pct": total,
            })
    rows.sort(key=lambda r: (r["total_snap_share_pct"] is None,
                             -(r["total_snap_share_pct"] or 0)))
    return {"playbook_id": playbook_id, "play_count": len(rows), "call_sheet": rows}


@mcp.tool()
def playbook_glossary(playbook_id: str) -> dict[str, Any]:
    """Compile a playbook's glossary — every route and concept its plays use,
    each paired with the description from its data file, plus any terms
    authored in the playbook's front_matter.glossary_additions.

    The glossary is compiled on demand (it is never stored), so it can never
    drift from the plays. Runs tools/compile-glossary/compile_glossary.py.

    Returns:
        {
          "playbook_id": str,
          "term_count":  int,
          "by_category": {"route": N, "run-concept": N, "pass-concept": N, ...},
          "glossary":    [{"term", "definition", "category", "source"}, ...],
        }

    Args:
        playbook_id: see list_playbooks().
    """
    books = _load_all_playbooks()
    if playbook_id not in books:
        return {"error": f"no playbook '{playbook_id}'", "available": sorted(books)}
    path = _PLAYBOOK_PATHS.get(playbook_id)
    if path is None or not path.exists():
        return {"error": f"could not locate the file for playbook '{playbook_id}'"}
    try:
        proc = subprocess.run(
            [sys.executable, str(GLOSSARY_SCRIPT), str(path)],
            capture_output=True, text=True, timeout=60,
        )
    except Exception as e:  # noqa: BLE001
        return {"error": f"glossary compiler failed to run: {e}"}
    if proc.returncode != 0:
        return {"error": f"glossary compiler failed: {(proc.stderr or '').strip()}"}
    try:
        glossary = json.loads(proc.stdout)
    except json.JSONDecodeError as e:
        return {"error": f"could not parse glossary output: {e}"}
    by_category: dict[str, int] = {}
    for entry in glossary:
        by_category[entry["category"]] = by_category.get(entry["category"], 0) + 1
    return {
        "playbook_id": playbook_id,
        "term_count": len(glossary),
        "by_category": by_category,
        "glossary": glossary,
    }


@mcp.tool()
def playbook_tendency_profile(playbook_id: str) -> dict[str, Any]:
    """Compute a playbook's tendency profile — the coach's-eye summary of what
    the playbook does: its run/pass balance, and how its snaps split by play
    type, formation, and personnel grouping.

    Every figure is derived from the call shares already stored in the
    playbook (section target_snap_share_pct x play share_of_section_pct), so
    the profile never drifts. Runs tools/playbook-profile/profile.py.

    Returns:
        {
          "playbook_id":          str,
          "total_snap_share_pct": float,
          "run_pass_split":       {"run": pct, "pass": pct, ...},
          "by_play_type":         {play_type: pct, ...},
          "by_formation":         {formation_id: pct, ...},
          "by_personnel":         {personnel_code: pct, ...},
        }

    Args:
        playbook_id: see list_playbooks().
    """
    books = _load_all_playbooks()
    if playbook_id not in books:
        return {"error": f"no playbook '{playbook_id}'", "available": sorted(books)}
    path = _PLAYBOOK_PATHS.get(playbook_id)
    if path is None or not path.exists():
        return {"error": f"could not locate the file for playbook '{playbook_id}'"}
    try:
        proc = subprocess.run(
            [sys.executable, str(PROFILE_SCRIPT), str(path)],
            capture_output=True, text=True, timeout=60,
        )
    except Exception as e:  # noqa: BLE001
        return {"error": f"profile tool failed to run: {e}"}
    if proc.returncode != 0:
        return {"error": f"profile tool failed: {(proc.stderr or '').strip()}"}
    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError as e:
        return {"error": f"could not parse profile output: {e}"}


@mcp.tool()
def playbook_call_breakdown(playbook_id: str) -> dict[str, Any]:
    """Break a playbook down formation by formation: for each formation
    section, its plays grouped by disguise family, with each play's share of
    that formation's calls.

    This is the "before every formation, list the plays and their call %"
    view. Grouping by disguise family shows how the formation installs — each
    family is a set of plays that share a pre-snap look and early action.

    Every figure is read straight from the playbook's stored call shares, so
    it never drifts. Runs tools/playbook-call-breakdown/breakdown.py.

    Returns:
        {
          "playbook_id": str,
          "sections": [
            {
              "section_id":            str,
              "section_name":          str,
              "target_snap_share_pct": int,
              "formations":            [str, ...],
              "play_count":            int,
              "families": [
                {
                  "family_id":        str | null,   # null = standalone plays
                  "family_name":      str,
                  "family_share_pct": int,          # sum of its plays' shares
                  "plays": [{"play_id", "name", "role",
                             "share_of_section_pct"}, ...],
                }, ...
              ],
            }, ...
          ],
        }

    Args:
        playbook_id: see list_playbooks().
    """
    books = _load_all_playbooks()
    if playbook_id not in books:
        return {"error": f"no playbook '{playbook_id}'", "available": sorted(books)}
    path = _PLAYBOOK_PATHS.get(playbook_id)
    if path is None or not path.exists():
        return {"error": f"could not locate the file for playbook '{playbook_id}'"}
    try:
        proc = subprocess.run(
            [sys.executable, str(BREAKDOWN_SCRIPT), str(path)],
            capture_output=True, text=True, timeout=60,
        )
    except Exception as e:  # noqa: BLE001
        return {"error": f"call-breakdown tool failed to run: {e}"}
    if proc.returncode != 0:
        return {"error": f"call-breakdown tool failed: {(proc.stderr or '').strip()}"}
    try:
        sections = json.loads(proc.stdout)
    except json.JSONDecodeError as e:
        return {"error": f"could not parse call-breakdown output: {e}"}
    return {"playbook_id": playbook_id, "sections": sections}


@mcp.tool()
def playbook_install_schedule(playbook_id: str) -> dict[str, Any]:
    """Return a playbook's install schedule — its plays grouped into install
    phases (Day 1, Day 2, Week 1, Week 2, mid-season), in teaching order.

    Each play is annotated with its formation section and disguise family, so
    the schedule shows the install rule the playbook is built on: the Day-1
    and Week-1 plays are the spine, Week-2 and mid-season adds layer disguise
    depth, and a companion play never installs before its family's base.

    Derived from each play entry's `install_order`. Runs
    tools/playbook-install-schedule/schedule.py.

    Returns:
        {
          "playbook_id": str,
          "phases": [
            {
              "install_order": "install-day-1",
              "label":         "Install — Day 1",
              "play_count":    int,
              "plays": [
                {"play_id", "name", "section_id", "section_name",
                 "family_name", "role", "share_of_section_pct"}, ...
              ],
            }, ...
          ],
        }

    Args:
        playbook_id: see list_playbooks().
    """
    books = _load_all_playbooks()
    if playbook_id not in books:
        return {"error": f"no playbook '{playbook_id}'", "available": sorted(books)}
    path = _PLAYBOOK_PATHS.get(playbook_id)
    if path is None or not path.exists():
        return {"error": f"could not locate the file for playbook '{playbook_id}'"}
    try:
        proc = subprocess.run(
            [sys.executable, str(SCHEDULE_SCRIPT), str(path)],
            capture_output=True, text=True, timeout=60,
        )
    except Exception as e:  # noqa: BLE001
        return {"error": f"install-schedule tool failed to run: {e}"}
    if proc.returncode != 0:
        return {"error": f"install-schedule tool failed: {(proc.stderr or '').strip()}"}
    try:
        phases = json.loads(proc.stdout)
    except json.JSONDecodeError as e:
        return {"error": f"could not parse install-schedule output: {e}"}
    return {"playbook_id": playbook_id, "phases": phases}


@mcp.tool()
def manifest() -> dict[str, Any]:
    """Return this server's purpose, tool list, and worked examples."""
    return {
        "server": "playbook-generation",
        "purpose": (
            "Assembles and completes custom playbooks from the 144-play library. "
            "Owns all collection-level reasoning: play selection, gap-filling, "
            "and (Phase 7) family-aware optimization. "
            "Boundary: single-play analysis stays in play-library-mcp; "
            "this server only acts on plays as a collection."
        ),
        "tools": [
            {"name": "assemble_playbook_simple", "description": "Select N plays by formation/philosophy/game constraints with play-type distribution targeting."},
            {"name": "suggest_complementary_plays", "description": "Given seed plays, recommend what's missing from the playbook (type gaps, ball-carrier gaps, PA gap)."},
            {"name": "list_formations_with_plays", "description": "Formation IDs that have plays in the library (subset of formation-library-mcp)."},
            {"name": "list_philosophies_with_plays", "description": "Philosophy IDs represented in play files (subset of philosophy-mcp)."},
            {"name": "list_playbooks", "description": "Every authored playbook in data/playbooks/ with section + play counts."},
            {"name": "get_playbook", "description": "A playbook's full record — sections, play entries, audibles, counter_responses."},
            {"name": "get_playbook_section", "description": "One formation_section or situational_section of a playbook."},
            {"name": "get_audibles", "description": "A playbook's audible system (global pool or per-formation pools)."},
            {"name": "get_play_in_playbook", "description": "A play's entry in a playbook — role, install, shares, counter_responses."},
            {"name": "validate_playbook", "description": "Full validation: schema, share math, audibles, counter refs, family self-containment."},
            {"name": "playbook_call_sheet", "description": "Every play with its derived total snap share, sorted — the call-sheet view."},
            {"name": "playbook_glossary", "description": "Compile a playbook's glossary — the routes/concepts its plays use, with definitions, plus authored glossary_additions."},
            {"name": "playbook_tendency_profile", "description": "Derive a playbook's run/pass balance and its snap split by play type, formation, and personnel grouping."},
            {"name": "playbook_call_breakdown", "description": "Per formation section, the plays grouped by disguise family with each play's share of that formation's calls."},
            {"name": "playbook_install_schedule", "description": "Plays grouped into install phases (Day 1 / Week 1 / Week 2 / mid-season), annotated with formation + disguise family."},
            {"name": "manifest", "description": "This document."},
        ],
        "examples": [
            "assemble_playbook_simple(formation_constraint='i-formation', play_count=15, philosophy='power-run', game_id='madden-05-ps2')",
            "suggest_complementary_plays(['singleback-trio-inside-zone', 'singleback-trio-mesh'], max_results=3)",
            "validate_playbook('hs-base-2026') -> {valid: true, report: '...'}",
            "playbook_call_sheet('hs-base-2026') -> plays ranked by derived snap share",
            "playbook_call_breakdown('hs-base-2026') -> per-formation plays grouped by disguise family",
            "playbook_install_schedule('hs-base-2026') -> plays grouped into install phases",
            "playbook_glossary('hs-base-2026') -> routes/concepts used, with definitions",
            "playbook_tendency_profile('hs-base-2026') -> run/pass %, play-type / formation / personnel mix",
        ],
    }


if __name__ == "__main__":
    mcp.run()
