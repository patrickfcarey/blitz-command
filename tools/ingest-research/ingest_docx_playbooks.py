#!/usr/bin/env python3
"""Ingest per-team .docx playbooks (screenshot sequences) via Claude vision.

Each .docx is a team's offensive playbook captured as an ordered sequence of
in-game screenshots. This script:
  1. Extracts each docx's images in document order (via extract_docx_images).
  2. Sends each image to Claude (haiku) to extract any visible formation name
     and, where available, play count.
  3. Deduplicates and aggregates across all images for a team.
  4. Writes data/games/<game_id>/team-playbooks.yaml in the same schema as
     build_playbook_catalog.py outputs.

Two screenshot formats are handled automatically:

  MADDEN_25_PS3 — "formation list" pages show a left panel with formation names
    + play counts under a family header (e.g. SINGLEBACK).  Play screens show
    "OFFENSE" header with 3 play diagrams.  Only formation-list pages yield data.

  ESPN_2K5_PS2  — formation name appears as a large header on every play-select
    screen.  Play names shown at the bottom are not captured (not needed for the
    formation catalog).

Usage:
    python3 tools/ingest-research/ingest_docx_playbooks.py \\
        --game madden-25-ps3 \\
        --docx-dir "research_artifacts/PS3/Madden NFL 25 (2013)/Playbooks/" \\
        [--workers 8] [--cache-dir /tmp/docx-cache]

    python3 tools/ingest-research/ingest_docx_playbooks.py \\
        --game espn-2k5-ps2 \\
        --docx-dir "research_artifacts/PS2/ESPN NFL 2K5-.../ESPN NFL 2K5/Playbooks/"

Requires ANTHROPIC_API_KEY in the environment.
"""
from __future__ import annotations

import argparse
import base64
import json
import shutil
import sys
import tempfile
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date
from pathlib import Path

import anthropic

sys.path.insert(0, str(Path(__file__).parent))
from extract_docx_images import extract_images_in_order  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[2]
DATA_GAMES = REPO_ROOT / "data" / "games"

# Vision model — haiku is fast and cheap; sufficient for reading game UI text.
VISION_MODEL = "claude-haiku-4-5-20251001"

# Prompt variants keyed by a format tag derived from the game_id.
_PROMPT_MADDEN_25 = """\
This is a screenshot from Madden NFL 25 (PS3).

If this image shows a FORMATION SELECTION LIST — a left panel listing formation \
names with play counts, under a family header like SINGLEBACK, I-FORM, SHOTGUN, \
PISTOL, WILDCAT, or SPECIAL TEAMS — extract the data.

Return ONLY valid JSON, no prose:
{"type":"formation_list","group":"<FAMILY>","formations":[{"name":"<name>","plays":<int>},...]}

If this is any other screen (play diagrams, team logo splash, etc.):
{"type":"other"}
"""

_PROMPT_ESPN_2K5 = """\
This is a screenshot from ESPN NFL 2K5 (PS2).

The formation name appears as a large text label, either at the top-centre of \
the screen or at the bottom bar.  Extract the single formation name visible.

Return ONLY valid JSON, no prose:
{"type":"formation_screen","formation":"<name>"}

If no formation name is legible:
{"type":"other"}
"""


def _format_tag(game_id: str) -> str:
    if "25" in game_id or "madden-13" in game_id:
        return "madden25"
    if "espn" in game_id or "2k5" in game_id:
        return "espn2k5"
    # Default: try madden25 prompt (formation-list style)
    return "madden25"


def _prompt_for_game(game_id: str) -> str:
    tag = _format_tag(game_id)
    return _PROMPT_ESPN_2K5 if tag == "espn2k5" else _PROMPT_MADDEN_25


def _encode_image(path: Path) -> str:
    """Return base64-encoded image content."""
    return base64.standard_b64encode(path.read_bytes()).decode()


def _media_type(path: Path) -> str:
    suffix = path.suffix.lower()
    return {"jpg": "image/jpeg", "jpeg": "image/jpeg",
            "png": "image/png", "gif": "image/gif",
            "webp": "image/webp"}.get(suffix.lstrip("."), "image/jpeg")


def _classify_image(client: anthropic.Anthropic,
                    image_path: Path,
                    prompt: str,
                    retries: int = 3) -> dict:
    """Call Claude vision on one image; return parsed JSON dict."""
    for attempt in range(retries):
        try:
            response = client.messages.create(
                model=VISION_MODEL,
                max_tokens=256,
                messages=[{
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": _media_type(image_path),
                                "data": _encode_image(image_path),
                            },
                        },
                        {"type": "text", "text": prompt},
                    ],
                }],
            )
            raw = response.content[0].text.strip()
            # Strip markdown fences if present
            if raw.startswith("```"):
                raw = raw.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
            return json.loads(raw)
        except (json.JSONDecodeError, anthropic.RateLimitError) as exc:
            if attempt < retries - 1:
                time.sleep(2 ** attempt)
            else:
                return {"type": "error", "detail": str(exc)}
        except anthropic.APIError as exc:
            return {"type": "error", "detail": str(exc)}
    return {"type": "error", "detail": "exhausted retries"}


def _process_team_docx(client: anthropic.Anthropic | None,
                       docx_path: Path,
                       game_id: str,
                       cache_dir: Path) -> list[dict]:
    """Extract and classify all images in one team's docx.

    Returns list of dicts, each representing one useful classified image.
    Results are cached by docx stem to survive restarts. ``client`` may be
    None only when this docx is already cached (no API call is made).
    """
    cache_file = cache_dir / f"{docx_path.stem}.json"
    if cache_file.exists():
        with open(cache_file) as f:
            return json.load(f)

    # Extract images to a temp directory
    tmp = tempfile.mkdtemp(prefix="docx_img_")
    try:
        count = extract_images_in_order(docx_path, tmp)
        prompt = _prompt_for_game(game_id)
        results = []
        images = sorted(Path(tmp).glob("*.*"))
        for img in images:
            result = _classify_image(client, img, prompt)
            if result.get("type") not in ("other", "error"):
                results.append(result)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    with open(cache_file, "w") as f:
        json.dump(results, f)
    return results


# ---------------------------------------------------------------------------
# Aggregation
# ---------------------------------------------------------------------------

# Madden formation-menu panel headers → family slug. The panel header is the
# game's own grouping and far more reliable than guessing from a name; OCR
# variants ("I FOR", "I FO" for "I-FORM") are folded in here. Headers absent
# from this map — including the legends-playbook colour headers RED/BROWN/BLUE
# — fall through to "other".
_MADDEN_GROUP_FAMILY: dict[str, str] = {
    "GUN": "shotgun", "SHOTGUN": "shotgun",
    "SINGLEBACK": "singleback",
    "I-FORM": "i_form", "I FORM": "i_form", "I FOR": "i_form", "I FO": "i_form",
    "STRONG": "strong", "STRONG I": "strong",
    "WEAK": "weak", "WEAK I": "weak",
    "PISTOL": "pistol",
    "WILDCAT": "wildcat",
    "NEAR": "near", "FAR": "far", "FULL HOUSE": "full_house",
    "PRO": "pro_set", "SPLIT": "pro_set",
}


def _normalize_madden_group(group: str | None) -> str:
    """Map a Madden formation-menu panel header to a family slug."""
    return _MADDEN_GROUP_FAMILY.get((group or "").strip().upper(), "other")


def _aggregate_madden25(results: list[dict]) -> list[dict]:
    """Collapse formation-list results into a deduplicated formation list.

    Each entry is {"name", "personnel", "family", "play_count"}, preserving
    first-seen order. ``family`` comes from the formation's menu panel header
    (SINGLEBACK / I-FORM / GUN / ...), and ``play_count`` from the play count
    the menu prints beside each formation.

    Deduplication is case-insensitive: vision OCR routinely reads the same
    formation with inconsistent casing (e.g. "Bunch Wk" vs "Bunch WK"); the
    first-seen spelling — and its family / play_count — is kept as canonical.
    """
    seen: set[str] = set()  # case-folded formation names already emitted
    ordered: list[dict] = []
    for r in results:
        if r.get("type") != "formation_list":
            continue
        family = _normalize_madden_group(r.get("group"))
        for f in r.get("formations", []):
            name = f.get("name", "").strip()
            key = name.lower()
            if name and key not in seen:
                seen.add(key)
                plays = f.get("plays")
                ordered.append({
                    "name": name,
                    "personnel": None,
                    "family": family,
                    "play_count": plays if isinstance(plays, int) else None,
                })
    return ordered


def _aggregate_espn2k5(results: list[dict]) -> list[dict]:
    """Collect unique formation names from ESPN 2K5 play screens.

    ESPN play screens carry no panel header or play count, so ``family`` is
    derived from the formation name and ``play_count`` is None — keeping the
    entry shape identical to the Madden path.

    Deduplication is case-insensitive for the same OCR-casing reason as
    _aggregate_madden25; the first-seen spelling is kept as canonical.
    """
    seen: set[str] = set()  # case-folded formation names already emitted
    ordered: list[dict] = []
    for r in results:
        if r.get("type") != "formation_screen":
            continue
        name = r.get("formation", "").strip()
        key = name.lower()
        if name and key not in seen:
            seen.add(key)
            ordered.append({
                "name": name,
                "personnel": None,
                "family": _family(name),
                "play_count": None,
            })
    return ordered


def _aggregate(game_id: str, results: list[dict]) -> list[dict]:
    tag = _format_tag(game_id)
    if tag == "espn2k5":
        return _aggregate_espn2k5(results)
    return _aggregate_madden25(results)


# ---------------------------------------------------------------------------
# Family detection (reuse from build_playbook_catalog)
# ---------------------------------------------------------------------------

import re

_FAMILY_PATTERNS: list[tuple[str, str]] = [
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


def _family(name: str) -> str:
    lowered = name.lower()
    for pattern, fam in _FAMILY_PATTERNS:
        if re.match(pattern, lowered):
            return fam
    return "other"


def _team_id(name: str) -> str:
    slug = name.lower()
    slug = re.sub(r"[^a-z0-9]+", "_", slug)
    return slug.strip("_")


def _build_team_entry(docx_path: Path, formations: list[dict]) -> dict:
    team_name = docx_path.stem  # e.g. "Arizona Cardinals"
    fam_counts: dict[str, int] = defaultdict(int)
    for f in formations:
        # Each formation already carries its family (panel header for Madden,
        # name-derived for ESPN); roll those up rather than re-deriving.
        fam_counts[f.get("family") or _family(f["name"])] += 1
    return {
        "team_id": _team_id(team_name),
        "name": team_name,
        "playbook_style": None,
        "formation_count": len(formations),
        "formations": formations,
        "personnel_breakdown": None,
        "formation_families": dict(sorted(fam_counts.items())),
    }


# ---------------------------------------------------------------------------
# YAML writer (mirrors build_playbook_catalog)
# ---------------------------------------------------------------------------

def _yaml_str(value: str) -> str:
    if not value:
        return '""'
    if any(ch in value for ch in (': ', '#', '[', ']', '{', '}', ',', '&', '*', '!', "'", '"', '\n')):
        return '"' + value.replace('\\', '\\\\').replace('"', '\\"') + '"'
    return value


def _write_yaml(catalog: dict, path: Path) -> None:
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
        lines.append("    formation_families:")
        for fam, count in (team["formation_families"] or {}).items():
            lines.append(f"      {fam}: {count}")
        lines.append("    personnel_breakdown: null")
        lines.append("    formations:")
        for f in team["formations"]:
            lines.append(f"      - name: {_yaml_str(f['name'])}")
            family = f.get("family")
            lines.append(f"        family: {family if family else 'null'}")
            play_count = f.get("play_count")
            lines.append(f"        play_count: "
                         f"{play_count if isinstance(play_count, int) else 'null'}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main(argv: list[str]) -> None:
    parser = argparse.ArgumentParser(
        description="Build team-playbooks.yaml from per-team docx screenshot sequences.")
    parser.add_argument("--game", required=True,
                        help="Game ID, e.g. 'madden-25-ps3' or 'espn-2k5-ps2'")
    parser.add_argument("--docx-dir", required=True,
                        help="Directory containing one .docx per team")
    parser.add_argument("--workers", type=int, default=6,
                        help="Parallel worker threads (default 6)")
    parser.add_argument("--cache-dir", default=None,
                        help="Dir to cache per-team JSON results (default: auto temp)")
    args = parser.parse_args(argv[1:])

    game_dir = DATA_GAMES / args.game
    if not game_dir.exists():
        print(f"ERROR: game directory not found: {game_dir}", file=sys.stderr)
        sys.exit(1)

    docx_dir = Path(args.docx_dir)
    docx_files = sorted(docx_dir.glob("*.docx"))
    if not docx_files:
        print(f"ERROR: no .docx files found in {docx_dir}", file=sys.stderr)
        sys.exit(1)

    cache_dir = Path(args.cache_dir) if args.cache_dir else Path(tempfile.mkdtemp(prefix="docx_cache_"))
    cache_dir.mkdir(parents=True, exist_ok=True)
    print(f"Cache dir: {cache_dir}")
    print(f"Processing {len(docx_files)} teams for {args.game} ...")

    # The Anthropic client is only needed for cache misses. A re-run that just
    # re-aggregates already-cached classifications (e.g. after a dedup fix)
    # then needs no API key at all — skip client construction in that case.
    uncached = [d for d in docx_files
                if not (cache_dir / f"{d.stem}.json").exists()]
    if uncached:
        client = anthropic.Anthropic()
        print(f"{len(uncached)} team(s) need vision classification (cache miss).")
    else:
        client = None
        print("All teams cached — re-aggregating with no API calls.")

    def process_one(docx_path: Path) -> tuple[str, list[dict]]:
        results = _process_team_docx(client, docx_path, args.game, cache_dir)
        formations = _aggregate(args.game, results)
        return docx_path.stem, formations

    teams: list[dict] = []
    failed: list[str] = []

    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {pool.submit(process_one, d): d for d in docx_files}
        for i, future in enumerate(as_completed(futures), 1):
            docx_path = futures[future]
            try:
                team_name, formations = future.result()
                if formations:
                    entry = _build_team_entry(docx_path, formations)
                    teams.append(entry)
                    print(f"  [{i}/{len(docx_files)}] {team_name}: "
                          f"{len(formations)} formations")
                else:
                    failed.append(team_name)
                    print(f"  [{i}/{len(docx_files)}] {docx_path.stem}: NO FORMATIONS FOUND")
            except Exception as exc:
                failed.append(docx_path.stem)
                print(f"  [{i}/{len(docx_files)}] {docx_path.stem}: ERROR — {exc}")

    teams.sort(key=lambda t: t["name"])

    if failed:
        print(f"\nWARNING: {len(failed)} teams yielded no formations: {failed}")

    catalog = {
        "game_id": args.game,
        "source": "Playbook Gamer",
        "verification_status": "unverified",
        "generated_date": str(date.today()),
        "notes": (f"Derived from per-team .docx screenshot sequences in {docx_dir.name}. "
                  "Vision extraction via Claude (haiku). Per layering rules: "
                  "game-truth data; not in-game-verified."),
        "teams": teams,
    }
    out_path = game_dir / "team-playbooks.yaml"
    _write_yaml(catalog, out_path)

    formation_total = sum(t["formation_count"] for t in teams)
    print(f"\nWrote {out_path}")
    print(f"  {len(teams)} teams, {formation_total} formation entries total")


if __name__ == "__main__":
    main(sys.argv)
