#!/usr/bin/env python3
"""Stratified sample of 50 Madden 25 plays for the hybrid-vs-cold vision pilot.

Reads the per-team play_screen cache (`.docx-cache-m25-plays/<Team>__chunkNN.json`)
and emits ``/tmp/pilot-work/pilot-sample.json`` — a list of records:

    {"id":         "indianapolis_colts__hb_toss__0001",
     "team":       "Indianapolis Colts",
     "docx_stem":  "Indianapolis_Colts",
     "image":      5,
     "panel":      0,
     "play_name":  "HB Toss",
     "play_type":  "run",
     "stratum":    "run_clean" | "run_generic" | "pass_named" | "pass_generic"}

Stratification keeps power balanced across the four cells we care about:
clean-name runs (where the parser should give the strongest prior), generic
runs (where it shouldn't), named passes (well-known concepts like Mesh /
Levels), and generic passes.
"""
from __future__ import annotations

import json
import random
import re
from collections import defaultdict
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
CACHE_DIR = REPO_ROOT / ".docx-cache-m25-plays"
OUT = Path("/tmp/pilot-work/pilot-sample.json")

# Tunable: total pilot sample. With paired within-subject design, ~50 pairs
# (~25-13 per cell) gives ~80% power to detect a ~15% reduction in tool_calls.
PILOT_N = 50
PER_STRATUM = {"run_clean": 12, "run_generic": 12,
               "pass_named": 13, "pass_generic": 13}
SEED = 20260520

# Plays whose name encodes direction/gap/strong-weak — the parser will have
# something to work with. Add liberally; we just need a strong "decodable" prior.
RUN_CLEAN_PATTERNS = [
    r"\b(iso|power|blast|sweep|toss|counter|off ?tackle|stretch|trap|dive)\b.*\b(lt|rt|wk|str|strong|weak|left|right)\b",
    r"\b(power|counter|toss|stretch|sweep|blast)\b\s+[a-z]\b",  # "Power O Lt"
    r"\bgap\b",                                                   # "HB Gap"
    r"\bzone\b\s+(lt|rt|wk|str)\b",                              # "Inside Zone Lt"
]
PASS_NAMED_PATTERNS = [
    # Well-known pass-concept names already in data/concepts/pass-concepts/.
    r"\b(mesh|levels|smash|stick|sail|dagger|drive|flood|four ?verticals|"
    r"hi[- ]?lo|double slants|drag|cross|hb wheel|y stick|y sail)\b",
    r"\bpa (boot|read|wheel|deep|cross)\b",
    r"\bhitches?\b",
    r"\bcurls?\b\s+(flat|streak|out)\b",
]


def _matches(patterns: list[str], play_name: str) -> bool:
    needle = play_name.lower()
    return any(re.search(p, needle) for p in patterns)


def _stratum(play: dict) -> str:
    name = play.get("name", "")
    ptype = play.get("type")
    if ptype == "run":
        return "run_clean" if _matches(RUN_CLEAN_PATTERNS, name) else "run_generic"
    if ptype == "pass":
        return "pass_named" if _matches(PASS_NAMED_PATTERNS, name) else "pass_generic"
    return "skip"  # null/unknown play-types stay out of the pilot


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")


def _walk_cache() -> list[dict]:
    """Flatten every per-team play_screen cache into individual play records."""
    plays = []
    for chunk_file in sorted(CACHE_DIR.glob("*__chunk*.json")):
        team_part = chunk_file.stem.split("__")[0]
        docx_stem = team_part.replace(" ", "_")
        entries = json.loads(chunk_file.read_text())
        for entry in entries:
            if entry.get("kind") != "play_screen":
                continue
            for panel_idx, play in enumerate(entry.get("plays", [])):
                name = (play.get("name") or "").strip()
                if not name:
                    continue
                plays.append({
                    "team": team_part,
                    "docx_stem": docx_stem,
                    "image": entry["img"],
                    "panel": panel_idx,
                    "play_name": name,
                    "play_type": play.get("type"),
                    "stratum": _stratum(play),
                })
    return plays


def main() -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    rng = random.Random(SEED)
    all_plays = _walk_cache()
    by_stratum: dict[str, list[dict]] = defaultdict(list)
    for play in all_plays:
        by_stratum[play["stratum"]].append(play)

    print("population per stratum:")
    for stratum, items in sorted(by_stratum.items()):
        print(f"  {stratum:<14} n={len(items)}")

    sample: list[dict] = []
    teams_seen: set[str] = set()
    for stratum, target in PER_STRATUM.items():
        pool = by_stratum.get(stratum, [])
        rng.shuffle(pool)
        # Diversify across teams: prefer plays from teams not yet represented.
        cell = []
        for play in pool:
            if len(cell) >= target:
                break
            if play["team"] in teams_seen and len(teams_seen) < target:
                continue
            cell.append(play)
            teams_seen.add(play["team"])
        # Backfill if filtering left us short.
        for play in pool:
            if len(cell) >= target:
                break
            if play in cell:
                continue
            cell.append(play)
        sample.extend(cell)

    for play in sample:
        play["id"] = (f"{_slug(play['team'])}__{_slug(play['play_name'])}"
                      f"__{play['image']:04d}_{play['panel']}")

    OUT.write_text(json.dumps(sample, indent=2))
    print(f"\nwrote {OUT}: {len(sample)} plays across "
          f"{len({p['team'] for p in sample})} teams")


if __name__ == "__main__":
    main()
