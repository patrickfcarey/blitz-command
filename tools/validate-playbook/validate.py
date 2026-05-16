#!/usr/bin/env python3
"""Validate a playbook YAML against the schema and the share-math invariants.

Checks performed:
  1. JSON Schema validity (schemas/playbook.schema.json).
  2. Every play_id in formation_sections references a real play in data/plays/.
  3. Per-section share_of_section_pct sums to ~100.
  4. formation_sections' target_snap_share_pct totals sum to ~100.
  5. Each formation_usage_split sums to ~100.
  6. When formation_usage_split is set, per-formation play-share sums match it.
  7. Plays inside each section are sorted by share_of_section_pct desc.
  8. Each audible pool (the global pool, or each per-formation pool) has
     unique slots numbered contiguously from 1 and play_ids that resolve.
  9. counter_responses: each counter_ref resolves on the referenced play,
     each audible_slot resolves in the relevant pool, hot-route names resolve.
 10. Self-containment: every play-family companion in the playbook also has
     one of its family base plays installed.

Exit code 0 on full pass, 1 on any failure.

Usage:
    python tools/validate-playbook/validate.py data/playbooks/hs-base.yaml
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator


REPO_ROOT = Path(__file__).resolve().parents[2]
SCHEMA_PATH = REPO_ROOT / "schemas" / "playbook.schema.json"
PLAYS_DIR = REPO_ROOT / "data" / "plays"
ROUTES_DIR = REPO_ROOT / "data" / "routes"
FAMILIES_DIR = REPO_ROOT / "data" / "play-families"

SHARE_TOLERANCE = 0.5  # percent


def _load_yaml(path: Path) -> dict:
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def _existing_play_ids() -> set[str]:
    return {p.stem for p in PLAYS_DIR.glob("*.yaml")}


def _check(label: str, ok: bool, detail: str = "") -> bool:
    status = "PASS" if ok else "FAIL"
    line = f"  [{status}] {label}"
    if detail:
        line += f" — {detail}"
    print(line)
    return ok


def validate(playbook_path: Path) -> int:
    abs_path = playbook_path.resolve()
    try:
        display = abs_path.relative_to(REPO_ROOT)
    except ValueError:
        display = abs_path
    print(f"Validating {display}\n")

    schema = json.loads(SCHEMA_PATH.read_text())
    pb = _load_yaml(playbook_path)
    failures = 0

    # 1. Schema
    errs = list(Draft202012Validator(schema).iter_errors(pb))
    if not _check("schema validation", not errs):
        failures += 1
        for e in errs:
            print(f"        - at {list(e.absolute_path)}: {e.message}")

    # 2. Cross-refs
    existing = _existing_play_ids()
    missing = []
    for sec in pb.get("formation_sections", []):
        for p in sec.get("plays", []):
            if p["play_id"] not in existing:
                missing.append((sec["section_id"], p["play_id"]))
    if not _check(f"play_id cross-references ({len(existing)} plays in library)",
                  not missing):
        failures += 1
        for sid, pid in missing:
            print(f"        - {sid}: {pid} not found in data/plays/")

    # 3. Per-section share sums
    print()
    print("  Section share sums:")
    all_ok = True
    fmt_total = 0
    for sec in pb.get("formation_sections", []):
        target = sec.get("target_snap_share_pct", 0)
        fmt_total += target
        play_sum = sum(p.get("share_of_section_pct", 0) for p in sec.get("plays", []))
        ok = abs(play_sum - 100) < SHARE_TOLERANCE
        all_ok = all_ok and ok
        marker = "OK" if ok else "OFF"
        print(f"    {sec['section_id']:<22} target={target:>3}%  "
              f"plays-sum={play_sum:>6.1f}%  [{marker}]")
    if not all_ok:
        failures += 1

    # 4. Total formation target
    if not _check(f"formation_sections target_snap_share_pct sums to ~100 "
                  f"(got {fmt_total})",
                  abs(fmt_total - 100) < SHARE_TOLERANCE):
        failures += 1

    # 5. formation_usage_split sums
    print()
    print("  formation_usage_split sums:")
    all_ok = True
    any_split = False
    for sec in pb.get("formation_sections", []):
        split = sec.get("formation_usage_split")
        if not split:
            continue
        any_split = True
        total = sum(split.values())
        ok = abs(total - 100) < SHARE_TOLERANCE
        all_ok = all_ok and ok
        marker = "OK" if ok else "OFF"
        print(f"    {sec['section_id']:<22} sum={total:>6.1f}%  [{marker}]")
    if not any_split:
        print("    (no multi-formation sections in this playbook)")
    if not all_ok:
        failures += 1

    # 6. Per-formation play-share matches formation_usage_split
    if any_split:
        print()
        print("  Per-formation play-share vs formation_usage_split:")
        all_ok = True
        for sec in pb.get("formation_sections", []):
            split = sec.get("formation_usage_split")
            if not split:
                continue
            share_by_formation = {formation_id: 0.0 for formation_id in split}
            for p in sec.get("plays", []):
                # Attribute by the play file's actual `formation` field. Falling
                # back to play_id prefix matching is ambiguous when one formation
                # id is a prefix of another (i-formation / i-formation-twins-weak).
                formation_id = None
                play_file = PLAYS_DIR / f"{p['play_id']}.yaml"
                if play_file.exists():
                    formation_id = _load_yaml(play_file).get("formation")
                if formation_id not in share_by_formation:
                    formation_id = next(
                        (candidate_formation
                         for candidate_formation in sorted(split, key=len, reverse=True)
                         if p["play_id"].startswith(candidate_formation + "-")
                         or p["play_id"] == candidate_formation),
                        None,
                    )
                if formation_id in share_by_formation:
                    share_by_formation[formation_id] += p.get("share_of_section_pct", 0)
            for formation_id, actual_share in share_by_formation.items():
                target_share = split[formation_id]
                ok = abs(actual_share - target_share) < SHARE_TOLERANCE
                all_ok = all_ok and ok
                marker = "OK" if ok else "OFF"
                print(f"    {sec['section_id']}/{formation_id:<25} "
                      f"target={target_share}%  actual={actual_share:.1f}%  [{marker}]")
        if not all_ok:
            failures += 1

    # 7. Sort order
    print()
    print("  Sort order (call frequency, desc):")
    all_ok = True
    for sec in pb.get("formation_sections", []):
        shares = [p.get("share_of_section_pct", 0) for p in sec.get("plays", [])]
        is_sorted = all(shares[i] >= shares[i + 1] for i in range(len(shares) - 1))
        all_ok = all_ok and is_sorted
        marker = "OK" if is_sorted else "NOT SORTED"
        print(f"    {sec['section_id']:<22}  [{marker}]")
    if not all_ok:
        failures += 1

    # 8. Audibles — mode-aware. 'global' = one playbook-wide pool; per the
    #    'per-formation' mode each formation_section carries its own pool.
    #    Each pool: slots unique and contiguous from 1, play_ids resolve.
    print()
    print("  Audibles:")
    audible_mode = pb.get("audible_mode")
    installed_play_ids = {
        p["play_id"]
        for sec in pb.get("formation_sections", [])
        for p in sec.get("plays", [])
    }

    def _check_audible_pool(label: str, audibles: list | None) -> tuple[dict, bool]:
        """Validate one audible pool. Returns (slot->play_id map, ok)."""
        pool = audibles or []
        slot_map = {a.get("slot"): a.get("play_id") for a in pool}
        if not pool:
            print(f"    [FAIL] {label}: no audibles defined")
            return slot_map, False
        ok = True
        slots_used = sorted(s for s in slot_map if s is not None)
        expected = list(range(1, len(pool) + 1))
        if slots_used != expected:
            print(f"    [FAIL] {label}: slots must be unique and contiguous from 1 "
                  f"(expected {expected}, got {slots_used})")
            ok = False
        else:
            print(f"    [PASS] {label}: {len(pool)} audibles, slots {slots_used}")
        for slot, pid in sorted(slot_map.items(), key=lambda kv: (kv[0] is None, kv[0])):
            cross_ok = pid in existing
            installed_ok = pid in installed_play_ids
            mx = "OK" if cross_ok else "MISSING"
            mi = "OK" if installed_ok else "NOT-IN-PLAYBOOK"
            print(f"      slot {slot}: {pid:<38} library=[{mx}]  playbook=[{mi}]")
            if not cross_ok:
                ok = False
        return slot_map, ok

    global_slot_map: dict = {}
    section_slot_maps: dict = {}

    if audible_mode == "global":
        global_slot_map, ok = _check_audible_pool("global pool", pb.get("audibles"))
        if not ok:
            failures += 1
    elif audible_mode == "per-formation":
        for sec in pb.get("formation_sections", []):
            sm, ok = _check_audible_pool(f"section '{sec['section_id']}'",
                                         sec.get("audibles"))
            section_slot_maps[sec["section_id"]] = sm
            if not ok:
                failures += 1
    else:
        print(f"    [FAIL] unknown audible_mode: {audible_mode!r}")
        failures += 1

    def _slot_map_for(section_id: str) -> dict:
        if audible_mode == "global":
            return global_slot_map
        return section_slot_maps.get(section_id, {})

    # 9. counter_responses: validate counter_ref resolves on the referenced
    #    play, audible_slot resolves in the relevant pool (global or this
    #    play's section, per audible_mode), and hot_routes.new_route resolves
    #    in data/routes/. Track exactly-one-primary per play as a warning.
    print()
    print("  counter_responses:")
    existing_routes = (
        {p.stem for p in ROUTES_DIR.glob("*.yaml")} if ROUTES_DIR.exists() else set()
    )

    counter_failures = 0
    plays_with_counters = 0
    for sec in pb.get("formation_sections", []):
        slot_map = _slot_map_for(sec["section_id"])
        for p in sec.get("plays", []):
            crs = p.get("counter_responses")
            if not crs:
                continue
            plays_with_counters += 1
            play_yaml_path = PLAYS_DIR / f"{p['play_id']}.yaml"
            if play_yaml_path.exists():
                play_yaml = _load_yaml(play_yaml_path)
                defined_counters = {
                    c["counter_id"] for c in (play_yaml.get("defensive_counters") or [])
                }
            else:
                defined_counters = set()

            primary_count = 0
            for cr in crs:
                ref = cr.get("counter_ref")
                pri = cr.get("priority", "primary")
                slot = cr.get("response", {}).get("audible_slot")
                hr_routes = cr.get("response", {}).get("hot_routes", []) or []

                ref_ok = ref in defined_counters
                slot_ok = slot in slot_map
                if pri == "primary":
                    primary_count += 1

                marker_r = "OK" if ref_ok else "UNRESOLVED"
                marker_s = "OK" if slot_ok else "BAD-SLOT"
                print(f"    {p['play_id']:<35} ref={ref:<22} "
                      f"[{marker_r}]  slot={slot} [{marker_s}]  pri={pri}")
                if not ref_ok or not slot_ok:
                    counter_failures += 1

                for hr in hr_routes:
                    nr = hr.get("new_route")
                    route_ok = nr in existing_routes
                    rmarker = "OK" if route_ok else "UNRESOLVED"
                    print(f"        hot_route {hr.get('player')} -> {nr}  [{rmarker}]")
                    if not route_ok:
                        counter_failures += 1

            if primary_count == 0 and crs:
                print(f"    [WARN] {p['play_id']} has counter_responses but no priority:primary")
            elif primary_count > 1:
                print(f"    [WARN] {p['play_id']} has {primary_count} priority:primary entries (expected 1)")

    if plays_with_counters == 0:
        print("    (no plays with counter_responses defined yet)")
    if counter_failures:
        failures += 1

    # 10. Self-containment: every play that is a COMPANION in a play-family
    #     must have at least one of its families' base_play_id present in the
    #     playbook. A play set up by multiple families is satisfied if ANY one
    #     of its setup bases is installed (the multi-layer-setup case).
    print()
    print("  Self-containment (play-family base coverage):")
    families = []
    if FAMILIES_DIR.exists():
        for fp in sorted(FAMILIES_DIR.glob("*.yaml")):
            families.append(_load_yaml(fp))
    if not families:
        print("    (no play-families defined yet)")
    else:
        playbook_play_ids = {
            p["play_id"]
            for sec in pb.get("formation_sections", [])
            for p in sec.get("plays", [])
        }
        # play_id -> list of (family_id, base_play_id) where it is a companion
        companion_of: dict[str, list] = {}
        for fam in families:
            base = fam.get("base_play_id")
            for comp in fam.get("companion_play_ids", []) or []:
                companion_of.setdefault(comp, []).append((fam.get("family_id"), base))
        sc_failures = 0
        n_companions = 0
        for pid in sorted(playbook_play_ids):
            fams = companion_of.get(pid)
            if not fams:
                continue
            n_companions += 1
            bases = [b for (_fid, b) in fams]
            present = [b for b in bases if b in playbook_play_ids]
            if present:
                print(f"    [OK]   {pid:<34} setup present: {', '.join(present)}")
            else:
                fam_ids = ", ".join(fid for (fid, _b) in fams)
                print(f"    [FAIL] {pid:<34} companion of [{fam_ids}] but none "
                      f"of its base plays {bases} are in the playbook")
                sc_failures += 1
        if n_companions == 0:
            print("    (no playbook plays are family companions)")
        if sc_failures:
            failures += 1

    print()
    if failures:
        print(f"FAILED: {failures} check group(s) reported issues.")
        return 1
    print("All checks passed.")
    return 0


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("playbook", type=Path, help="Path to playbook YAML file.")
    args = ap.parse_args()
    if not args.playbook.exists():
        print(f"ERROR: {args.playbook} not found", file=sys.stderr)
        sys.exit(2)
    sys.exit(validate(args.playbook))


if __name__ == "__main__":
    main()
