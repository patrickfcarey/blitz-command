#!/usr/bin/env python3
"""Match a repo playbook against a game's team-playbook catalog, formation by
formation.

The earlier "match" collapsed every playbook to family counts (singleback /
i_form / shotgun) — too coarse to tell NFL playbooks apart. This matcher works
at the sub-formation level: it normalises each formation — on both the repo
side and the game-catalog side — to a structural signature

    (family_group, {alignment tags})

so e.g. the repo's `shotgun-2x2` and Madden's `Doubles` both reduce to
(gun, {doubles}). It then scores how well each game playbook *covers* the repo
playbook's formation set, and ranks the game playbooks.

Both sides are tagged from formation NAMES: the game catalog carries no
coordinates, only names, so a name-based crosswalk is the common ground.

Usage:
    python tools/playbook-game-match/match.py [repo_playbook.yaml] [game_id]

Defaults: data/playbooks/hs-base.yaml  vs  madden-25-ps3
"""
from __future__ import annotations

import sys
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PLAYBOOK = REPO_ROOT / "data" / "playbooks" / "hs-base.yaml"
DEFAULT_GAME = "madden-25-ps3"

# --- alignment vocabulary -------------------------------------------------
# Fine-grained (~18 tags). Each formation name is scanned for these keywords;
# every keyword hit adds its tag. "pro" / "normal" and a no-hit name collapse
# to the synonym tag "base" (the plain base set). Direction words (left/right)
# and team nicknames embedded in names simply produce no tag.
ALIGNMENT_KEYWORDS: dict[str, tuple[str, ...]] = {
    "empty":   ("empty", "5wr", "5 wr"),
    "trips":   ("trips", "trip", "trio", "trey", "treys", "v-trip", "y-trip"),
    "quads":   ("quads", "quad"),            # ESPN 2K5 4-WR look
    "stack":   ("stack",),
    "bunch":   ("bunch", "snug", "cluster"),
    "spread":  ("spread", "shoot"),          # run-and-shoot, Madden "Spread"
    "doubles": ("doubles", "double", "2x2", "deuce"),
    "twins":   ("twins", "twin"),
    "wing":    ("wing",),
    "slot":    ("slot",),
    "pair":    ("pair",),
    "tight":   ("tight",),
    "flex":    ("flex",),
    "jumbo":   ("jumbo", "heavy", "goal", "full house", "fullhouse",
                "full-house", "big "),
    "ace":     ("ace",),
    "offset":  ("offset",),
    "weak":    ("weak", " wk", "-wk"),
    "strong":  ("strong",),
    "near":    ("near",),
    "far":     (" far", "-far"),
    "flip":    ("flip",),
}
# Keywords that mean "plain base set" — folded into the single tag "base".
_BASE_KEYWORDS: tuple[str, ...] = ("pro", "normal", "base", "solo", "regular")

# --- family grouping ------------------------------------------------------
# Catalog families are finer than we need for matching; group compatible ones.
FAMILY_GROUP: dict[str, str] = {
    "i_form": "power", "strong": "power", "weak": "power", "near": "power",
    "far": "power", "full_house": "power", "power_i": "power",
    "singleback": "single", "ace": "single", "pro_set": "single",
    "shotgun": "gun", "spread": "gun",
    "pistol": "pistol",
    "wildcat": "wildcat",
    "goal_line": "goal",
}

# Score weights — see _formation_score.
SAME_GROUP_FACTOR = 1.00
CROSS_GROUP_FACTOR = 0.45
FAMILY_FLOOR = 0.35   # credit for a family-group match even with no tag overlap


def _alignment_tags(name: str) -> frozenset[str]:
    """Return the set of structural alignment tags for a formation name."""
    lowered = f" {name.lower()} "
    tags: set[str] = set()
    for tag, keywords in ALIGNMENT_KEYWORDS.items():
        if any(kw in lowered for kw in keywords):
            tags.add(tag)
    if any(kw in lowered for kw in _BASE_KEYWORDS):
        tags.add("base")
    if not tags:                       # nothing recognised -> plain base set
        tags.add("base")
    return frozenset(tags)


def _family_group(family: str | None) -> str:
    """Collapse a catalog family slug to a coarse compatibility group."""
    return FAMILY_GROUP.get((family or "").lower(), "other")


def _formation_score(sig_a: tuple[str, frozenset[str]],
                     sig_b: tuple[str, frozenset[str]]) -> float:
    """Similarity in [0, 1] between two formation signatures."""
    group_a, tags_a = sig_a
    group_b, tags_b = sig_b
    jaccard = len(tags_a & tags_b) / len(tags_a | tags_b) if (tags_a | tags_b) else 0.0
    factor = SAME_GROUP_FACTOR if group_a == group_b else CROSS_GROUP_FACTOR
    return factor * (FAMILY_FLOOR + (1.0 - FAMILY_FLOOR) * jaccard)


# --- repo-playbook side ---------------------------------------------------

def _repo_family(formation_id: str) -> str:
    """Family slug for a repo formation id (prefix-based)."""
    fid = formation_id.lower()
    if fid.startswith("i-formation") or fid.startswith("i_formation"):
        return "i_form"
    if fid.startswith("singleback") or fid.startswith("double-slot"):
        return "singleback"  # double-slot: under-centre 10-personnel single-back
    if fid.startswith("shotgun"):
        return "shotgun"
    if fid.startswith("goal-line"):
        return "goal_line"
    if fid.startswith("pistol"):
        return "pistol"
    return "other"


def load_repo_formations(playbook_path: Path) -> list[dict]:
    """Return [{id, name, family, group, tags}] for a repo playbook's formations."""
    pb = yaml.safe_load(playbook_path.read_text())
    formation_ids: list[str] = []
    for section in pb.get("formation_sections", []):
        for fid in section.get("formations", []):
            if fid not in formation_ids:
                formation_ids.append(fid)
    out = []
    for fid in formation_ids:
        family = _repo_family(fid)
        # Tag from the id; goal-line gets an explicit jumbo nudge.
        name = fid.replace("-", " ")
        tags = set(_alignment_tags(name))
        if family == "goal_line":
            tags.add("jumbo")
        out.append({
            "id": fid,
            "name": name,
            "family": family,
            "group": _family_group(family),
            "tags": frozenset(tags),
        })
    return out


# --- game-catalog side ----------------------------------------------------

def load_game_playbooks(game_id: str) -> list[dict]:
    """Return the game's team playbooks with per-formation signatures attached."""
    catalog_path = REPO_ROOT / "data" / "games" / game_id / "team-playbooks.yaml"
    catalog = yaml.safe_load(catalog_path.read_text())
    playbooks = []
    for team in catalog["teams"]:
        formations = []
        for f in team["formations"]:
            family = f.get("family")
            formations.append({
                "name": f["name"],
                "family": family,
                "group": _family_group(family),
                "tags": _alignment_tags(f["name"]),
                "play_count": f.get("play_count"),
            })
        playbooks.append({"name": team["name"], "formations": formations})
    return playbooks


# --- matching -------------------------------------------------------------

def best_match(repo_formation: dict, game_formations: list[dict]) -> tuple[dict, float]:
    """Find the game formation that best covers one repo formation."""
    repo_sig = (repo_formation["group"], repo_formation["tags"])
    best, best_score = None, -1.0
    for gf in game_formations:
        score = _formation_score(repo_sig, (gf["group"], gf["tags"]))
        if score > best_score:
            best, best_score = gf, score
    return best, best_score


def score_playbook(repo_formations: list[dict], game_playbook: dict) -> dict:
    """Coverage of the repo playbook by one game playbook (mean best-match)."""
    pairs = []
    for rf in repo_formations:
        gf, score = best_match(rf, game_playbook["formations"])
        pairs.append({"repo": rf, "game": gf, "score": score})
    coverage = sum(p["score"] for p in pairs) / len(pairs) if pairs else 0.0
    return {"name": game_playbook["name"], "coverage": coverage, "pairs": pairs}


def main(argv: list[str]) -> None:
    playbook_path = Path(argv[1]) if len(argv) > 1 else DEFAULT_PLAYBOOK
    game_id = argv[2] if len(argv) > 2 else DEFAULT_GAME

    repo_formations = load_repo_formations(playbook_path)
    game_playbooks = load_game_playbooks(game_id)

    print(f"Repo playbook : {playbook_path.name}  ({len(repo_formations)} formations)")
    print(f"Game catalog  : {game_id}  ({len(game_playbooks)} playbooks)\n")
    print("Repo formations and their structural signatures:")
    for rf in repo_formations:
        print(f"  {rf['id']:24} group={rf['group']:8} tags={sorted(rf['tags'])}")
    print()

    ranked = sorted((score_playbook(repo_formations, gp) for gp in game_playbooks),
                    key=lambda r: -r["coverage"])

    print(f"{'#':<4}{'coverage':<11}{'game playbook':<26}")
    print("-" * 41)
    for i, r in enumerate(ranked[:12], 1):
        print(f"{i:<4}{r['coverage']:<11.3f}{r['name']:<26}")

    top = ranked[0]
    print(f"\nBest match: {top['name']} — formation-by-formation crosswalk:")
    for p in top["pairs"]:
        gf = p["game"]
        pc = f"{gf['play_count']} plays" if gf and gf.get("play_count") else "?"
        print(f"  {p['repo']['id']:24} -> {gf['name'] if gf else '(none)':22} "
              f"[{pc}]  score={p['score']:.2f}")


if __name__ == "__main__":
    main(sys.argv)
