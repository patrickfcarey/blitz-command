#!/usr/bin/env python3
"""Expand data/playbooks/hs-base.yaml into the full master playbook.

Folds in EVERY play that belongs to a disguise family — taking the playbook
from its hand-authored core to a ~90-play master/reference book. It is meant
to be re-run whenever the families change.

Rules:
  - Every base + companion play of every family in data/play-families/ is
    included, plus any play already in the playbook.
  - Existing play entries keep their hand-authored counter_responses, role,
    install_order, notes. Only their share_of_section_pct is recomputed.
  - New plays get counter_responses generated from their defensive_counters
    via a read_category -> audible-slot heuristic, and a derived role.
  - Section shares are role-weighted, normalised to 100, and re-sorted.
  - audibles, audible_mode, situational_sections, and all top-level fields
    are preserved as-is.

Run from the repo root:
    python3 tools/expand-playbook/expand.py
"""
from __future__ import annotations

from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[2]
PB_PATH = REPO / "data" / "playbooks" / "hs-base.yaml"
FAMILIES_DIR = REPO / "data" / "play-families"
PLAYS_DIR = REPO / "data" / "plays"

# formation_id -> section_id
SECTION_OF = {
    "i-formation": "i-formation",
    "i-formation-twins-weak": "i-formation",
    "singleback-ace": "singleback",
    "singleback-trio": "singleback",
    "shotgun-2x2": "shotgun",
    "shotgun-trips-left": "shotgun",
    "shotgun-trips-right": "shotgun",
    "goal-line": "goal-line",
    "run-and-shoot": "run-and-shoot",
}
SECTION_ORDER = ["i-formation", "singleback", "shotgun", "run-and-shoot", "goal-line"]
SECTION_NAME = {
    "i-formation": "I-Formation",
    "singleback": "Singleback",
    "shotgun": "Shotgun",
    "run-and-shoot": "Run & Shoot",
    "goal-line": "Goal Line",
}
SECTION_TARGET = {
    "i-formation": 33, "singleback": 25, "shotgun": 27,
    "run-and-shoot": 9, "goal-line": 6,
}

# read_category -> audible slot (the 5-audible global pool of hs-base)
AUDIBLE_FOR = {
    "box-count": 3,      # BLUE 80 — loaded box, throw the quick game
    "dl-alignment": 2,   # WIDE 28 — DL movement, hit the perimeter
    "lb-depth": 5,       # WHITE BOOT — LB tells, boot away
    "safety-shell": 1,   # RED 22 — coverage shell, run Power
    "cb-leverage": 1,    # RED 22 — corner leverage, run Power
}
AUDIBLE_CALL = {1: "RED 22", 2: "WIDE 28", 3: "BLUE 80", 4: "KILL POWER", 5: "WHITE BOOT"}
ROLE_WEIGHT = {
    "base": 4, "counter": 2, "complement": 2, "constraint": 2,
    "misdirection": 2, "package": 2, "answer": 1, "opener": 1,
    "tempo": 1, "trick": 1,
}


def _derive_role(pid: str, play: dict, is_base: bool) -> str:
    if is_base:
        return "base"
    if "counter" in pid:
        return "counter"
    if "screen" in pid:
        return "answer"
    pt = play.get("play_type")
    if pt == "screen":
        return "answer"
    return "complement"


def _gen_counter_responses(play: dict) -> list[dict]:
    out = []
    for i, c in enumerate(play.get("defensive_counters") or []):
        slot = AUDIBLE_FOR.get(c.get("read_category"), 1)
        out.append({
            "counter_ref": c["counter_id"],
            "priority": "primary" if i == 0 else "secondary",
            "response": {
                "audible_slot": slot,
                "notes": f"{c.get('qb_key', 'Read the look')} — check to {AUDIBLE_CALL[slot]}.",
            },
        })
    return out


def _fix_to_100(shares: list[int]) -> list[int]:
    diff = 100 - sum(shares)
    order = sorted(range(len(shares)), key=lambda i: -shares[i])
    j = 0
    while diff != 0 and order:
        idx = order[j % len(order)]
        if diff > 0:
            shares[idx] += 1
            diff -= 1
        elif shares[idx] > 1:
            shares[idx] -= 1
            diff += 1
        j += 1
    return shares


def main() -> None:
    pb = yaml.safe_load(PB_PATH.read_text())

    existing = {e["play_id"]: e
                for sec in pb["formation_sections"]
                for e in sec["plays"]}

    family_bases: set[str] = set()
    family_members: set[str] = set()
    for fp in sorted(FAMILIES_DIR.glob("*.yaml")):
        fam = yaml.safe_load(fp.read_text())
        family_bases.add(fam["base_play_id"])
        family_members.add(fam["base_play_id"])
        family_members.update(fam.get("companion_play_ids") or [])

    include = set(existing) | family_members

    # group plays into sections
    buckets: dict[str, list[tuple[dict, dict]]] = {s: [] for s in SECTION_ORDER}
    skipped = []
    for pid in sorted(include):
        pf = PLAYS_DIR / f"{pid}.yaml"
        if not pf.exists():
            skipped.append(pid)
            continue
        play = yaml.safe_load(pf.read_text())
        sec = SECTION_OF.get(play.get("formation"))
        if sec is None:
            skipped.append(pid)
            continue
        if pid in existing:
            entry = dict(existing[pid])
        else:
            entry = {
                "play_id": pid,
                "role": _derive_role(pid, play, pid in family_bases),
                "install_order": "install-week-2",
                "counter_responses": _gen_counter_responses(play),
            }
        buckets[sec].append((entry, play))

    formation_sections = []
    total_plays = 0
    for sec_id in SECTION_ORDER:
        entries = buckets[sec_id]
        if not entries:
            continue
        weights = [ROLE_WEIGHT.get(e.get("role"), 1) for e, _ in entries]
        tot = sum(weights) or 1
        shares = _fix_to_100([max(1, round(w / tot * 100)) for w in weights])
        for (entry, _), s in zip(entries, shares):
            entry["share_of_section_pct"] = s
        entries.sort(key=lambda ep: -ep[0]["share_of_section_pct"])
        by_fmt: dict[str, int] = {}
        for entry, play in entries:
            by_fmt[play["formation"]] = by_fmt.get(play["formation"], 0) + entry["share_of_section_pct"]
        sec_obj = {
            "section_id": sec_id,
            "name": SECTION_NAME[sec_id],
            "formations": sorted(by_fmt),
            "target_snap_share_pct": SECTION_TARGET[sec_id],
        }
        if len(by_fmt) > 1:
            sec_obj["formation_usage_split"] = dict(sorted(by_fmt.items()))
        sec_obj["plays"] = [e for e, _ in entries]
        formation_sections.append(sec_obj)
        total_plays += len(entries)

    pb["formation_sections"] = formation_sections
    pb["notes"] = (
        "MASTER / REFERENCE playbook — every play from every disguise family is "
        "folded in (regenerate with tools/expand-playbook/expand.py). This is a "
        "library, not a game-day install; cut it down per opponent. Section "
        "shares are role-weighted approximations.\n"
    )

    header = ("# GENERATED by tools/expand-playbook/expand.py — do not hand-edit.\n"
              "# Master playbook: every disguise-family play folded in.\n")
    PB_PATH.write_text(header + yaml.dump(pb, sort_keys=False,
                                          default_flow_style=False,
                                          allow_unicode=True, width=100))
    print(f"Wrote {PB_PATH.relative_to(REPO)} — {total_plays} plays across "
          f"{len(formation_sections)} sections.")
    if skipped:
        print(f"Skipped (no file / unmapped formation): {skipped}")


if __name__ == "__main__":
    main()
