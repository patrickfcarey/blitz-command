#!/usr/bin/env python3
"""Map a play name to a concept tag (and optional route template).

Football play names follow strong conventions: "HB Dive" is always an
inside dive; "Mesh" is the crossing-routes concept; "Power O" is a power
gap scheme; "PA " prefix means play-action. We can encode 80%+ of M25
play names into structured concept tags from Python, sparing the LLM the
job of naming the concept.

Output format:
    {
      "concept": "power_run" | "outside_zone" | "mesh" | ... | "unknown",
      "concept_family": "run" | "pass" | "screen" | "pa_pass" | "rpo" | "trick",
      "blockers_implicit": bool,   # True for vanilla runs → tell LLM to skip blocker routes
      "matched_pattern": "<the regex hint for debugging>",
    }
"""
from __future__ import annotations
import re


# Patterns ordered by specificity — longer/more specific first.
# Each entry: (regex, concept_tag, family, blockers_implicit, notes)
PLAY_PATTERNS = [
    # ---- Screens (high specificity) ----
    (r"\bhb (slip )?screen\b", "hb_screen", "screen", False),
    (r"\bbubble screen\b|\bwr bubble\b|\bbubble\b", "bubble_screen", "screen", False),
    (r"\bwr screen\b|\bfl screen\b|\bse screen\b|\bx screen\b|\bz screen\b",
     "wr_screen", "screen", False),
    (r"\bte screen\b|\by screen\b", "te_screen", "screen", False),
    (r"\bjail screen\b", "jail_screen", "screen", False),

    # ---- Run plays (specific) ----
    (r"\bqb sneak\b", "qb_sneak", "run", True),
    (r"\bqb (draw|run|keep)\b", "qb_run", "run", True),
    (r"\bfb dive\b", "fb_dive", "run", True),
    (r"\bfb plunge\b", "fb_dive", "run", True),
    (r"\bhb dive\b|\bdive\b", "inside_run", "run", True),
    (r"\bhb toss\b|\btoss\b", "outside_run_toss", "run", True),
    (r"\bhb stretch\b|\bstretch\b", "outside_zone", "run", True),
    (r"\binside zone\b|\bhb (zone|izn|iz)\b", "inside_zone", "run", True),
    (r"\boutside zone\b|\bhb (oz|ozn)\b", "outside_zone", "run", True),
    (r"\bpower ?o\b", "power_o", "run", True),
    (r"\bpower\b", "power_run", "run", True),
    (r"\bcounter\b", "counter_run", "run", True),
    (r"\btrap\b", "trap_run", "run", True),
    (r"\bblast\b", "iso_blast", "run", True),
    (r"\biso\b", "iso", "run", True),
    (r"\bgap\b", "gap_run", "run", True),
    (r"\bdraw\b", "draw", "run", True),
    (r"\bwham\b", "wham", "run", True),
    (r"\bduo\b", "duo", "run", True),
    (r"\bsweep\b", "sweep", "run", True),
    (r"\boff[ -]?tackle\b", "off_tackle", "run", True),
    (r"\bjet sweep\b|\bjet\b", "jet_sweep", "run", True),
    (r"\bend around\b|\breverse\b", "reverse", "run", True),
    (r"\bslam\b", "iso_slam", "run", True),
    (r"\bmisdirection\b", "misdirection_run", "run", True),
    (r"\bcutback\b", "cutback_run", "run", True),
    (r"\bslash\b", "slash_run", "run", True),
    (r"\bplunge\b", "plunge_run", "run", True),
    (r"\bbase\b", "base_run", "run", True),
    (r"\bcrack\b", "crack_run", "run", True),
    (r"\bpitch\b", "pitch_run", "run", True),
    (r"\bdouble option\b", "double_option", "rpo", False),
    (r"\bhb option\b|\bte option\b", "option_pass", "pass", False),
    # Catch any "HB <word>" not yet matched as run (after the specific
    # patterns above). HB is the halfback, so HB-something is a run.
    (r"^hb \w+", "generic_hb_run", "run", True),
    (r"\bhb \w+", "generic_hb_run", "run", True),

    # ---- Read options / RPO ----
    (r"\bread option\b|\bzone read\b", "zone_read", "rpo", False),
    (r"\bspeed option\b", "speed_option", "rpo", False),
    (r"\bpower read\b", "power_read", "rpo", False),
    (r"\bshovel\b", "shovel_option", "rpo", False),
    (r"\brpo\b", "rpo_generic", "rpo", False),

    # ---- Pass plays — named concepts ----
    (r"\bmesh\b", "mesh", "pass", False),
    (r"\blevels?\b", "levels", "pass", False),
    (r"\bsmash\b", "smash", "pass", False),
    (r"\bstick\b", "stick", "pass", False),
    (r"\bsail\b", "sail", "pass", False),
    (r"\bdagger\b", "dagger", "pass", False),
    (r"\bdrive\b", "drive_concept", "pass", False),
    (r"\bflood\b", "flood", "pass", False),
    (r"\bspacing\b", "spacing", "pass", False),
    (r"\bsnag\b", "snag", "pass", False),
    (r"\bfour ?verticals?\b|\b4 ?verts?\b", "four_verticals", "pass", False),
    (r"\bhi[- ]?lo\b|\bhilo\b", "hi_lo", "pass", False),
    (r"\bcurl flats?\b", "curl_flat", "pass", False),
    (r"\bquick slants?\b", "quick_slants", "pass", False),
    (r"\bquick out\b", "quick_outs", "pass", False),
    (r"\bquick (in|cross|hitch)\b", "quick_pass", "pass", False),
    (r"\bdouble slants?\b", "double_slants", "pass", False),
    (r"\bcorner strike\b", "corner_strike", "pass", False),
    (r"\bdeep outs?\b", "deep_outs", "pass", False),
    (r"\bdeep cross\b", "deep_cross", "pass", False),
    (r"\bdeep in\b", "deep_in", "pass", False),
    (r"\bdeep post\b", "deep_post", "pass", False),
    (r"\bv[- ]?corner\b", "v_corner", "pass", False),
    (r"\by[- ]?(cross|sail|stick|corner|trail|spot|drive|shallow)\b",
     "y_concept", "pass", False),
    (r"\bx[- ]?(drag|cross|streak|shallow|post|out)\b",
     "x_concept", "pass", False),
    (r"\bz[- ]?(spot|cross|streak|corner|drive|trail|out|drag|sail)\b",
     "z_concept", "pass", False),
    (r"\bslot (drag|cross|streak|corner|out|in|wheel)\b",
     "slot_concept", "pass", False),
    (r"\bwheel\b", "wheel_concept", "pass", False),
    (r"\bpost(?![- ]corner)\b", "post_concept", "pass", False),
    (r"\bpost[- ]?corner\b", "post_corner", "pass", False),
    (r"\bspot\b", "spot_concept", "pass", False),
    (r"\bcross(es)?\b", "cross_concept", "pass", False),
    (r"\bcomebacks?\b", "comebacks", "pass", False),
    (r"\bcurls?\b", "curls", "pass", False),
    (r"\bouts?\b", "outs", "pass", False),
    (r"\bins?\b", "ins", "pass", False),
    (r"\bhitch(es)?\b", "hitches", "pass", False),
    (r"\bstreaks?\b", "streaks", "pass", False),
    (r"\bslants?\b", "slants", "pass", False),
    (r"\bfade\b", "fade", "pass", False),
    (r"\bdrags?\b", "drags", "pass", False),
    (r"\bunders?\b", "under_route", "pass", False),
    (r"\bclowns?\b", "clown_route", "pass", False),
    (r"\bflys?\b", "fly_route", "pass", False),
    (r"\bgo (route|routes)?\b|^go$", "go_route", "pass", False),
    (r"\bflares?\b", "flare_route", "pass", False),
    (r"\bfakes?\b", "play_fake", "pa_pass", False),
    (r"\bcrossers?\b", "crossers", "pass", False),
    (r"\bclearout\b", "clearout", "pass", False),
    (r"\bbananas?\b", "banana_route", "pass", False),
    (r"\bspider\b", "spider_concept", "pass", False),
    (r"\bpin (deep|out|in)\b", "pin_route", "pass", False),
    (r"\bverticals?\b", "verticals", "pass", False),
    (r"\bdig\b|\bdigs\b", "dig_route", "pass", False),
    (r"\bflanker (dig|cross|trail|drive|drag|out|in|corner|comeback)\b",
     "flanker_concept", "pass", False),
    (r"\bbench\b", "bench_concept", "pass", False),
    (r"\bflats?\b", "flats_concept", "pass", False),
    (r"\bswing\b", "swing_route", "pass", False),
    (r"\bhinge\b", "hinge_route", "pass", False),
    (r"\bsit\b", "sit_route", "pass", False),
    (r"\bshallow (cross|drag)\b", "shallow_cross", "pass", False),
    (r"\bshallow\b", "shallow", "pass", False),
    (r"\btrail\b", "trail_concept", "pass", False),
    (r"\bsticks?\b", "stick", "pass", False),
    (r"\bbend\b", "bend_route", "pass", False),
    (r"\bsneak\b(?! out)", "sneak_route", "pass", False),

    # ---- Play-action specific (boot, waggle, slide, read) ----
    (r"\bboot\b|\bbootleg\b", "boot_pass", "pa_pass", False),
    (r"\bwaggle\b", "waggle_pass", "pa_pass", False),
    (r"\bslide\b", "slide_pass", "pa_pass", False),
    (r"\bread\b(?!.*option)", "read_pass", "pa_pass", False),
    (r"\brollout\b|\broll\b", "rollout_pass", "pa_pass", False),

    # ---- Additional run patterns (from unknowns audit) ----
    (r"\bqb wrap\b", "qb_run", "run", True),
    (r"\bfb (belly|inside|base)\b", "fb_run", "run", True),
    (r"\bbelly\b", "belly_run", "run", True),
    (r"\bzone (wk|str|weak|strong)\b", "zone_run", "run", True),
    (r"\bh zone (wk|str)\b", "zone_run", "run", True),
    (r"\b(atl|mtn|den|sea|phi|chi|car) zone\b", "zone_run", "run", True),
    (r"\binverted veer\b", "inverted_veer", "rpo", False),
    (r"\bveer\b", "veer_option", "rpo", False),

    # ---- Pass concepts: receiver-prefix shortcuts (X/Y/Z/TE/WR/Slot/FL) ----
    # Cover "WR Corners", "X Drag", "TE Angle", "Slot Seam" etc. — these
    # carry the route concept after the receiver tag.
    (r"\b(wr|te|x|y|z|fl|se|slot|h) (corner|drag|hook|option|under|seam|follow|"
     r"attack|inside|angle|shake|fork|scissors|cross|trail|streak|spot|fade|"
     r"in|out|wheel|seams|hooks|corners|outs|ins|posts|streaks)\b",
     "receiver_concept", "pass", False),
    (r"\b(wr|te) screens?\b", "wr_screen", "screen", False),

    # ---- Pass concept names from audit ----
    (r"\bdeep attack\b|\bdeep corners?\b|\bdeep middle\b", "deep_pass", "pass", False),
    (r"\btexas\b", "texas_concept", "pass", False),
    (r"\bsluggos?\b|\bsluggo seam\b", "sluggo", "pass", False),
    (r"\bwhip\b", "whip_route", "pass", False),
    (r"\bchina\b", "china_concept", "pass", False),
    (r"\bscat\b", "scat_route", "pass", False),
    (r"\bshakes?\b", "shake_route", "pass", False),
    (r"\binside switch\b|\bswitch\b", "switch_concept", "pass", False),
    (r"\ball ?go\b", "all_streaks", "pass", False),
    (r"\bomaha\b", "omaha_concept", "pass", False),
    (r"\bhank\b", "hank_concept", "pass", False),
    (r"\bhooks?\b", "hooks", "pass", False),
    (r"\b(strong|weak) flow\b", "flow_pass", "pass", False),
    (r"\bseams?\b", "seam_route", "pass", False),
    (r"\bmiddle\b", "middle_concept", "pass", False),
    (r"\bfork\b", "fork_concept", "pass", False),
    (r"\bchoice\b", "choice_route", "pass", False),
    (r"\bscissors\b", "scissors_concept", "pass", False),
    (r"\boption\b", "option_route", "pass", False),
    # Numbered concept (e.g. "60 Go", "61 X Choice", "689 Hook") — route tree
    # numbering. Treat as a generic pass concept.
    (r"^\d{2,3}\b", "numbered_concept", "pass", False),

    # ---- Long-tail pass concepts from second audit ----
    (r"\bcorners?$", "corner_concept", "pass", False),
    (r"^posts?\b", "post_concept", "pass", False),
    (r"\bangle\b", "angle_route", "pass", False),
    (r"\bcircle\b", "circle_route", "pass", False),
    (r"\bpivot\b", "pivot_route", "pass", False),
    (r"\bstop ?n? ?go\b|\bstop and go\b", "stop_and_go", "pass", False),
    (r"\bflea flicker\b", "trick_play", "trick", False),
    (r"\bdouble (drags?|unders?|china|sluggo|posts?|cross|seams?|hitches?)\b",
     "double_concept", "pass", False),
    (r"\bdbl (under|drag|cross|china|sluggo|post|seam|hitch)s?\b",
     "double_concept", "pass", False),
    (r"\bleak\b", "leak_route", "pass", False),
    (r"\bthunder\b", "thunder_concept", "pass", False),
    (r"\bf (angle|drag|cross|seam|trail|streak|out|in)\b",
     "fullback_concept", "pass", False),
    (r"\bfb (screen|hb)\b", "fb_screen", "screen", False),
    (r"\bseattle\b|\bphilly\b|\bgreen bay\b|\bdallas\b|\bbal\b", "city_concept", "pass", False),
    (r"\bace posts?\b", "post_concept", "pass", False),
    (r"\bsmash 7\b|\bsmash (out|in|drag)\b", "smash_variant", "pass", False),
    # Catch-all: any standalone short play_type-marked pass — let LLM name it
    # (still useful family classification for cost purposes).

    # ---- Play action (prefix overrides concept family to pa_pass) ----
    # Handled below via pa_prefix transform.
]

# PA prefix transforms (applied after pattern matching):
PA_PREFIX_RE = re.compile(r"^(pa|pa\b|play action|play-action)\s+", re.IGNORECASE)
BOOT_RE = re.compile(r"\b(boot|boot[- ]?legs?|bootleg|waggle|roll(out)?)\b", re.IGNORECASE)


def classify(play_name: str, play_type: str | None = None) -> dict:
    """Classify a play name into a concept tag + family.

    `play_type` is the cache's run/pass hint; we use it as a fallback when
    the name doesn't match any pattern.
    """
    if not play_name:
        return {"concept": "unknown", "concept_family": play_type or "unknown",
                "blockers_implicit": False, "matched_pattern": None}
    name = play_name.strip()
    nl = name.lower()

    # Strip leading team prefix (e.g. "Ravens Mesh" → "Mesh")
    nl_stripped = re.sub(r"^(ravens?|bears?|bills?|browns?|colts?|cowboys|"
                         r"chiefs?|chargers|49ers|niners?|panthers?|patriots?|"
                         r"giants?|jets?|jaguars?|lions?|raiders?|saints?|"
                         r"seahawks?|steelers?|texans?|vikings?|broncos|"
                         r"dolphins|eagles|falcons|packers|titans?|"
                         r"buccaneers?|bucs?|cardinals?|bengals?|redskins?|"
                         r"raven|chief|panther|bengal|cowboy|giant|patriot|"
                         r"lion|steeler|saint|jet|texan|viking|seahawk|"
                         r"jaguar|charger|falcon|eagle|packer|brown|hawk|"
                         r"bear|bill|bal|nyg|nyj|pit|sd|sea|sf|ten|was|"
                         r"phi|chi|car|cin|den|det|gb|hou|ind|jax|kc|"
                         r"mia|min|ne|no|oak|tb|stl|atl|ari)\s+",
                         "", nl, flags=re.IGNORECASE)

    # Detect PA prefix
    is_pa = bool(PA_PREFIX_RE.match(nl_stripped))
    if is_pa:
        # Remove the "PA " prefix and classify the post-PA token.
        nl_inner = PA_PREFIX_RE.sub("", nl_stripped, count=1)
    else:
        nl_inner = nl_stripped

    is_boot = bool(BOOT_RE.search(nl_stripped))

    for pattern, concept, family, blockers_implicit in PLAY_PATTERNS:
        if re.search(pattern, nl_inner, re.IGNORECASE):
            # PA modifies family: pa_pass instead of pass; blockers stay implicit-False.
            if is_pa and family == "run":
                family = "pa_pass"
                blockers_implicit = False
            elif is_pa and family == "pass":
                family = "pa_pass"
            if is_boot and family in ("pass", "pa_pass"):
                family = "pa_pass"  # boot/waggle/rollout are pa_pass even without "PA"
            return {
                "concept": concept,
                "concept_family": family,
                "blockers_implicit": blockers_implicit,
                "matched_pattern": pattern,
                "is_pa": is_pa,
                "is_boot_or_roll": is_boot,
            }

    # Fallback: use play_type to decide family
    fam = play_type or "unknown"
    return {
        "concept": "unknown",
        "concept_family": fam,
        "blockers_implicit": False,
        "matched_pattern": None,
        "is_pa": is_pa,
        "is_boot_or_roll": is_boot,
    }


if __name__ == "__main__":
    import json
    import sys
    if len(sys.argv) >= 2:
        result = classify(" ".join(sys.argv[1:]))
        print(json.dumps(result, indent=2))
    else:
        # Coverage check across the canonical manifest
        manifest = json.load(open(
            "tools/playbook-vision-pilot/dedup-crops/_canonical_manifest.json"))
        from collections import Counter
        coverage = Counter()
        unknowns = []
        for info in manifest.values():
            result = classify(info.get("play_name", ""), info.get("play_type"))
            if result["concept"] == "unknown":
                coverage["unknown"] += 1
                unknowns.append(info.get("play_name", ""))
            else:
                coverage[result["concept_family"]] += 1
        total = sum(coverage.values())
        print(f"Coverage across {total} unique plays:")
        for fam, n in coverage.most_common():
            print(f"  {fam:<10}: {n} ({100*n/total:.0f}%)")
        print()
        # Show 20 unknowns for inspection
        if unknowns:
            print(f"\nSample unknowns ({len(unknowns)} total):")
            from collections import Counter as C
            unknown_counts = C(unknowns)
            for name, n in unknown_counts.most_common(20):
                print(f"  {n:>3}× {name}")
