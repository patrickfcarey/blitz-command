#!/usr/bin/env python3
"""Derive concept priors from play names for the vision pilot.

Reads /tmp/pilot-work/pilot-sample.json and emits /tmp/pilot-work/priors.json
keyed by play id. For each play, attempts to extract:

    concept    — e.g. "power", "iso", "stretch", "mesh", "smash"
    gap        — "A" | "B" | "C" | "D" (run plays only)
    direction  — "left" | "right" | "strong" | "weak" | None
    notes      — short free-text hints (e.g. "lead blocker: FB")

If nothing decodes from the name, prior is None. The primed-arm subagent
gets this string prepended to its prompt; the cold-arm sees nothing.

Usage:
    python3 name_to_prior.py
"""
from __future__ import annotations

import json
import re
from pathlib import Path

SAMPLE = Path("/tmp/pilot-work/pilot-sample.json")
OUT = Path("/tmp/pilot-work/priors.json")

RUN_CONCEPTS = [
    "iso", "power", "blast", "sweep", "toss", "counter", "stretch",
    "trap", "dive", "draw", "lead", "gap", "duo", "wham", "pin and pull",
    "inside zone", "outside zone", "off tackle", "jet sweep", "reverse",
    "speed option", "power read", "shovel option",
]
PASS_CONCEPTS = [
    "mesh", "levels", "smash", "stick", "sail", "dagger", "drive", "flood",
    "four verticals", "hi-lo", "hi lo", "hilo", "double slants",
    "drag", "cross", "hb wheel", "y stick", "y sail", "spacing", "snag",
]
DIRECTION_MAP = {
    "lt": "left", "left": "left",
    "rt": "right", "right": "right",
    "str": "strong", "strong": "strong",
    "wk": "weak", "weak": "weak",
}
GAP_RE = re.compile(r"\b([abcd])[- ]?gap\b", re.I)


def _concept(name: str, play_type: str) -> str | None:
    needle = name.lower()
    pool = RUN_CONCEPTS if play_type == "run" else PASS_CONCEPTS
    for c in sorted(pool, key=len, reverse=True):
        if c in needle:
            return c.replace(" ", "_")
    return None


def _direction(name: str) -> str | None:
    tokens = re.findall(r"[A-Za-z]+", name.lower())
    for t in tokens:
        if t in DIRECTION_MAP:
            return DIRECTION_MAP[t]
    return None


def _gap(name: str) -> str | None:
    m = GAP_RE.search(name)
    return m.group(1).upper() if m else None


def _build_prior(play: dict) -> dict | None:
    name = play["play_name"]
    ptype = play.get("play_type")
    concept = _concept(name, ptype)
    direction = _direction(name)
    gap = _gap(name)
    if not (concept or direction or gap):
        return None
    prior = {"concept": concept, "direction": direction, "gap": gap,
             "play_type": ptype}
    bits = [f"{k}={v}" for k, v in prior.items() if v]
    prior["string"] = ("Concept prior (from name): " + ", ".join(bits)
                       + ". Emit deltas if the diagram disagrees.")
    return prior


def main() -> None:
    plays = json.loads(SAMPLE.read_text())
    priors = {}
    hits = 0
    for play in plays:
        prior = _build_prior(play)
        priors[play["id"]] = prior
        if prior:
            hits += 1
    OUT.write_text(json.dumps(priors, indent=2))
    print(f"wrote {OUT}: {hits}/{len(plays)} plays decoded a prior")


if __name__ == "__main__":
    main()
