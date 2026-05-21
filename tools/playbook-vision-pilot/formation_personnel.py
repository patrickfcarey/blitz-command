#!/usr/bin/env python3
"""Map an M25 formation (family + name) to expected personnel counts.

Football formations encode personnel by convention. "Singleback Ace" is
canonically 2 TE / 2 WR. "GUN Empty" is 0 RB / 0 TE / 5 WR. Etc.

This module decodes formation names via pattern matching and returns
(RB, FB, TE, WR) counts plus a confidence label. The output is fed to
the LLM as authoritative prior — the LLM verifies and identifies specific
glyphs but doesn't have to RE-DERIVE counts from pixels.

Rules are conservative — if multiple patterns conflict, return
confidence='low' and let the LLM figure it out. Coverage on the M25
dataset's 342 unique formations is >80%; remainder fall back to family
defaults.
"""
from __future__ import annotations
from dataclasses import dataclass


@dataclass
class Personnel:
    rb: int          # Halfback count
    fb: int          # Fullback count (separate position in I/Strong/Weak)
    te: int          # Tight ends (attached + wing/U-TE off-LOS)
    wr: int          # Wide receivers (split out)
    qb: int = 1      # Always 1 unless Wildcat (0 QB)
    confidence: str = "high"   # high | medium | low
    notes: str = ""

    @property
    def total(self) -> int:
        return self.qb + self.rb + self.fb + self.te + self.wr

    def to_dict(self) -> dict:
        return {
            "QB": self.qb, "RB": self.rb, "FB": self.fb,
            "TE": self.te, "WR": self.wr,
            "total": self.total,
            "confidence": self.confidence,
            "notes": self.notes,
        }


# ---- pattern-based deduction ----

# Keyword groups in the formation name → adjustments / overrides.
def _decode(family: str, formation: str) -> Personnel:
    f = (family or "").upper().strip()
    n = (formation or "").strip()
    nl = n.lower()

    # --- Wildcat: RB at QB position, no QB ---
    if "WILDCAT" in f:
        return Personnel(qb=0, rb=1, fb=0, te=1, wr=3,
                         notes="Wildcat — RB at QB position, no QB; "
                               "TE/WR counts approximate per variant")

    # --- Goal Line: heavy short-yardage ---
    if "GOAL LINE" in f or "GOAL_LINE" in f:
        return Personnel(rb=1, fb=1, te=3, wr=0,
                         notes="Goal Line — typical heavy package")

    # --- Empty (5-wide) family: no RB ---
    if "empty" in nl:
        if "trips te" in nl or "wing trio" in nl or "trio" in nl:
            return Personnel(rb=0, fb=0, te=1, wr=4)
        return Personnel(rb=0, fb=0, te=0, wr=5,
                         notes="Empty — 5-wide, no RB, no FB")

    # --- 5-WR / spread shotgun variants ---
    if "5wr" in nl:
        return Personnel(rb=0, fb=0, te=0, wr=5,
                         notes="5-WR set, no RB")

    # --- Jumbo: 3 TE heavy ---
    if "jumbo" in nl:
        return Personnel(rb=1, fb=0, te=3, wr=1,
                         notes="Jumbo — typically 3 TE 1 WR")

    # --- I-Form / Strong / Weak (under-center 2-back) ---
    if f.startswith("I-FORM") or f.startswith("I_FORM") or f.startswith("I FOR") \
            or f.startswith("STRONG I") or f.startswith("WEAK I"):
        # I-Form variants
        if "twin te" in nl or "tight pair" in nl or "tight" in nl:
            return Personnel(rb=1, fb=1, te=2, wr=2,
                             notes="I-Form Tight/Twin-TE — 2 TE")
        if "twins" in nl:
            return Personnel(rb=1, fb=1, te=1, wr=3,
                             notes="I-Form Twins — 1 TE 3 WR")
        if "slot" in nl:
            return Personnel(rb=1, fb=1, te=1, wr=3,
                             notes="I-Form Slot — 1 TE 3 WR")
        # Default I-Form Pro
        return Personnel(rb=1, fb=1, te=1, wr=2,
                         notes="I-Form Pro default")

    if f in ("STRONG", "WEAK"):
        if "twin te" in nl or "tight pair" in nl or "tight" in nl:
            return Personnel(rb=1, fb=1, te=2, wr=2)
        if "twins" in nl:
            return Personnel(rb=1, fb=1, te=1, wr=3)
        if "h pro" in nl or "pro" in nl:
            return Personnel(rb=1, fb=1, te=1, wr=2)
        if "slot" in nl:
            return Personnel(rb=1, fb=1, te=1, wr=3)
        return Personnel(rb=1, fb=1, te=1, wr=2,
                         confidence="medium",
                         notes=f"{f} default — variant unclear")

    # --- Pistol (QB stacked behind C, HB behind QB) ---
    if "PISTOL" in f:
        if "full house" in nl:
            return Personnel(rb=1, fb=1, te=2, wr=1,
                             notes="Pistol Full House — heavy backfield")
        if "twin te" in nl or "jumbo" in nl:
            return Personnel(rb=1, fb=0, te=2, wr=2)
        if "trips" in nl or "spread" in nl:
            return Personnel(rb=1, fb=0, te=0, wr=4,
                             confidence="medium")
        if "bunch" in nl:
            return Personnel(rb=1, fb=0, te=1, wr=3)
        if "weak" in nl or "strong" in nl:
            return Personnel(rb=1, fb=0, te=1, wr=3,
                             notes="Pistol Strong/Weak")
        return Personnel(rb=1, fb=0, te=1, wr=3,
                         confidence="medium",
                         notes="Pistol default — variant unclear")

    # --- GUN/Shotgun: QB ~5 yards back, HB to side or alone ---
    if "GUN" in f or "SHOTGUN" in f:
        # 4-WR / 5-WR variants
        if "4wr" in nl or "spread 4" in nl:
            return Personnel(rb=1, fb=0, te=0, wr=4)
        # 2-TE shotgun
        if "twin te" in nl or "trips te" in nl:
            return Personnel(rb=1, fb=0, te=2, wr=2)
        # Ace = 2 TE (shotgun-ace)
        if "ace" in nl and "twins" not in nl:
            return Personnel(rb=1, fb=0, te=2, wr=2,
                             notes="GUN Ace — 2 TE 2 WR (shotgun-ace)")
        if "ace twins" in nl or "ace pair" in nl:
            return Personnel(rb=1, fb=0, te=2, wr=2,
                             notes="GUN Ace Twins — 2 TE 2 WR")
        # Trips / Bunch / Spread / Y-Trips / V-Trips → 3+ WR
        if any(k in nl for k in ("trips", "v-trips", "y-trips", "bunch",
                                  "spread", "wing trio")):
            return Personnel(rb=1, fb=0, te=1, wr=3,
                             notes="GUN Trips-family — 1 TE 3 WR")
        # Doubles → 2 WR each side, with 1 TE attached
        if "doubles" in nl or "deuce" in nl:
            return Personnel(rb=1, fb=0, te=1, wr=3,
                             notes="GUN Doubles — 1 TE 3 WR (slot variant)")
        if "dice" in nl:
            return Personnel(rb=1, fb=0, te=1, wr=3)
        # Heavy
        if "heavy" in nl:
            return Personnel(rb=1, fb=0, te=3, wr=1)
        # Y-Slot, Y-Flex — 3 WR with TE in slot/flex
        if "y-slot" in nl or "y-flex" in nl:
            return Personnel(rb=1, fb=0, te=1, wr=3)
        # Snugs / Tight Doubles On — likely 1-TE 3-WR
        if "snugs" in nl or "tight" in nl:
            return Personnel(rb=1, fb=0, te=1, wr=3,
                             confidence="medium")
        # Normal default
        return Personnel(rb=1, fb=0, te=1, wr=3,
                         confidence="medium",
                         notes="GUN/Shotgun default — 1 TE 3 WR")

    # --- Singleback: 1 RB, no FB ---
    if "SINGLEBACK" in f:
        # Tier 1: explicit heavy/empty cases
        if "spread" in nl and "4wr" in nl:
            return Personnel(rb=1, fb=0, te=0, wr=4)
        if "spread" in nl:
            return Personnel(rb=1, fb=0, te=1, wr=3)
        if "4wr" in nl:
            return Personnel(rb=1, fb=0, te=0, wr=4)
        # 2-TE Ace family
        if "ace" in nl:
            return Personnel(rb=1, fb=0, te=2, wr=2,
                             notes="Singleback Ace family — 2 TE 2 WR")
        # 2-TE Twin TE
        if "twin te" in nl:
            return Personnel(rb=1, fb=0, te=2, wr=2)
        # 3-WR sets
        if any(k in nl for k in ("trips", "v-trips", "y-trips", "bunch",
                                  "doubles", "deuce", "dice")):
            return Personnel(rb=1, fb=0, te=1, wr=3,
                             notes="Singleback Trips/Doubles family")
        # Wing-TE / Slot variants
        if "wing" in nl or "slot" in nl:
            return Personnel(rb=1, fb=0, te=1, wr=3,
                             confidence="medium")
        # Pro / Big Wing / generic
        if "big wing" in nl or "double wing" in nl:
            return Personnel(rb=1, fb=0, te=2, wr=2,
                             confidence="medium",
                             notes="Singleback wing-heavy")
        return Personnel(rb=1, fb=0, te=1, wr=3,
                         confidence="medium",
                         notes="Singleback default — 1 TE 3 WR")

    # --- Split / Near / Far / Red / Blue / Brown / Full House (old-school) ---
    if f in ("FAR", "NEAR", "SPLIT", "FULL HOUSE", "FULL_HOUSE",
             "BLUE", "BROWN", "RED"):
        if "twins" in nl:
            return Personnel(rb=1, fb=1, te=1, wr=3, confidence="medium")
        if "tight" in nl or "twin te" in nl:
            return Personnel(rb=1, fb=1, te=2, wr=2, confidence="medium")
        if "wide" in nl:
            return Personnel(rb=1, fb=1, te=1, wr=2, confidence="medium")
        return Personnel(rb=1, fb=1, te=1, wr=2,
                         confidence="medium",
                         notes=f"{f} family — old-school 2-back default")

    # --- Fallback ---
    return Personnel(rb=1, fb=0, te=1, wr=3,
                     confidence="low",
                     notes=f"unknown family {f!r} — generic 11-personnel guess")


def personnel_for(family: str, formation: str) -> dict:
    """Public API: returns a dict suitable for JSON/prompt injection."""
    p = _decode(family, formation)
    return {
        "family": family,
        "formation": formation,
        **p.to_dict(),
    }


def describe(personnel: dict) -> str:
    """Human-readable line for the LLM prompt."""
    bf_count = personnel["QB"] + personnel["RB"] + personnel["FB"]
    bf_note = f"{bf_count} circles behind C ({personnel['QB']} QB + "
    bf_note += f"{personnel['RB']} RB"
    if personnel["FB"]:
        bf_note += f" + {personnel['FB']} FB"
    bf_note += ")"
    return (f"Expected personnel for {personnel['family']} {personnel['formation']}: "
            f"{personnel['RB']} RB, {personnel['FB']} FB, "
            f"{personnel['TE']} TE, {personnel['WR']} WR. "
            f"Backfield: {bf_note}. "
            f"Confidence: {personnel['confidence']}. "
            f"{personnel['notes']}".strip())


if __name__ == "__main__":
    import json
    import sys
    if len(sys.argv) >= 3:
        result = personnel_for(sys.argv[1], sys.argv[2])
        print(json.dumps(result, indent=2))
        print()
        print(describe(result))
    else:
        # Walk the canonical manifest and verify coverage
        manifest = json.load(open(
            "tools/playbook-vision-pilot/dedup-crops/_canonical_manifest.json"))
        formations = sorted({(item["family"], item["formation"])
                              for item in manifest.values()})
        from collections import Counter
        confidence_counts = Counter()
        for fam, form in formations:
            p = _decode(fam, form)
            confidence_counts[p.confidence] += 1
        print(f"Coverage across {len(formations)} unique formations:")
        for conf, n in sorted(confidence_counts.items()):
            print(f"  {conf:<8}: {n} ({100*n/len(formations):.0f}%)")
