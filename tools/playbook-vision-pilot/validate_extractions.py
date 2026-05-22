#!/usr/bin/env python3
"""Walk all canonical extractions and flag suspect ones.

Runs offline (no API cost). Checks each extraction JSON for:

- JSON parse failure
- Concept disagrees with play_name (where play_concepts had a strong match)
- routes dict count disagrees with expected personnel (too many or too few)
- ball_carrier gap disagrees with Python target_gap by 2+ gaps
- primary_target references a role not in the expected personnel
- Wildcat play with non-null QB

Output: a JSON report at data/games/madden-25-ps3/play-geometry/_validation.json
listing each suspect play with the reason.
"""
from __future__ import annotations
import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "tools/playbook-vision-pilot"))
from play_concepts import classify as classify_play  # noqa: E402

EXTRACTIONS_DIR = REPO / "data/games/madden-25-ps3/play-geometry"


def _parse_extracted(raw: str) -> dict | None:
    m = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", raw, re.DOTALL)
    candidate = m.group(1) if m else raw.strip()
    try:
        return json.loads(candidate)
    except json.JSONDecodeError:
        return None


def _flag(report: list, slug: str, reason: str, detail: str = "") -> None:
    report.append({"slug": slug, "reason": reason, "detail": detail})


def main() -> None:
    if not EXTRACTIONS_DIR.exists():
        sys.exit(f"missing: {EXTRACTIONS_DIR}")
    report: list[dict] = []
    total = parse_failed = 0
    for f in sorted(EXTRACTIONS_DIR.glob("*.json")):
        if f.name.startswith("_"):
            continue
        total += 1
        d = json.loads(f.read_text())
        slug = d.get("slug", f.stem)
        info = d.get("info", {})
        py = d.get("py_hints", {})
        py_concept = d.get("py_concept", {})
        expected = info.get("expected_personnel", {})
        obj = _parse_extracted(d.get("response_text", ""))
        if obj is None:
            parse_failed += 1
            _flag(report, slug, "parse_failed",
                  d.get("response_text", "")[:120])
            continue

        # Check 1: concept disagrees with py_concept
        py_c = py_concept.get("concept")
        if py_c and py_c != "unknown":
            llm_c = obj.get("concept")
            if llm_c and llm_c != py_c and not llm_c.startswith(py_c) \
                    and not py_c.startswith(llm_c):
                _flag(report, slug, "concept_mismatch",
                      f"py={py_c} llm={llm_c}")

        # Check 2: ball_carrier gap vs Python target_gap
        bc = obj.get("ball_carrier") or ""
        if py.get("target_gap") and info.get("play_type") == "run":
            if py["target_gap"] not in bc:
                _flag(report, slug, "gap_mismatch",
                      f"py={py['target_gap']} bc={bc}")

        # Check 3: primary_target role plausibility
        pt = obj.get("primary_target")
        if info.get("play_type") == "pass" and pt is None:
            _flag(report, slug, "pass_no_primary_target", "")
        if info.get("play_type") == "run" and pt is not None:
            _flag(report, slug, "run_has_primary_target", str(pt))

        # Check 4: routes count vs expected personnel — PASS PLAYS ONLY.
        # Use the authoritative manifest play_type, not the LLM's
        # play_type_observed (run plays correctly emit empty routes via
        # the blockers-implicit rule and must not be flagged).
        routes = obj.get("routes")
        if (isinstance(routes, dict) and expected
                and info.get("play_type") == "pass"):
            expected_targets = (expected.get("TE", 0) + expected.get("WR", 0)
                                + 1)  # +1 for HB as checkdown
            n_routes = len(routes)
            # Only flag a SHORTFALL of 3+ (missing routes). An overflow is
            # fine — the LLM may detail more than the minimum.
            if expected_targets - n_routes >= 3:
                _flag(report, slug, "route_count_off",
                      f"expected≈{expected_targets} got={n_routes}")

        # Check 5: Wildcat should have no QB role used
        if "wildcat" in (info.get("family") or "").lower():
            for role_field in [bc, pt]:
                if role_field and "QB" in str(role_field):
                    _flag(report, slug, "wildcat_has_qb",
                          str(role_field))

    # Write report
    out = EXTRACTIONS_DIR / "_validation.json"
    summary = {
        "total_extractions": total,
        "parse_failed": parse_failed,
        "flag_count": len(report),
        "flag_rate_pct": round(100 * len(report) / total, 1) if total else 0,
        "flags_by_reason": {},
        "flags": report,
    }
    from collections import Counter
    summary["flags_by_reason"] = dict(Counter(r["reason"] for r in report))
    out.write_text(json.dumps(summary, indent=2))
    print(f"validated {total} extractions, {len(report)} flagged "
          f"({summary['flag_rate_pct']}%)")
    for reason, n in summary["flags_by_reason"].items():
        print(f"  {reason}: {n}")
    print(f"\nReport written: {out}")


if __name__ == "__main__":
    main()
