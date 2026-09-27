#!/usr/bin/env python3
"""Aggregate the cold-vs-primed extractions and decide whether priming wins.

For each play, we have two extractions (cold + primed). Compute per-pair
deltas on the dependent variables (output tokens, total cost, completeness),
run a paired t-test on log(output_tokens), compute Cohen's d with 95% CI,
and stratify by sample stratum (run_clean, run_generic, pass_named, pass_generic).

Decision rule (adapted from the pilot README):
  >= 15% reduction in primed output_tokens AND no completeness regression
       -> build the hybrid (priming pipeline) for production.
  Otherwise -> drop the hybrid; go straight to cold extraction.

Outputs:
  /tmp/pilot-work/pilot-results/report.md   (human-readable summary)
  /tmp/pilot-work/pilot-results/pairs.json  (machine-readable per-pair data)
"""
from __future__ import annotations
import json
import math
import re
import statistics
from pathlib import Path

EXTRACTIONS = Path("/tmp/pilot-work/extractions")
OUT_DIR = Path("/tmp/pilot-work/pilot-results")
SAMPLE = Path("/tmp/pilot-work/pilot-sample.json")

# Sonnet 4.5 pricing per Mtok.
P_IN = 3.0
P_OUT = 15.0
P_CACHE_WRITE = 3.75
P_CACHE_READ = 0.30


def _cost(usage: dict) -> float:
    return ((usage.get("input_tokens", 0) * P_IN
             + usage.get("cache_creation_input_tokens", 0) * P_CACHE_WRITE
             + usage.get("cache_read_input_tokens", 0) * P_CACHE_READ
             + usage.get("output_tokens", 0) * P_OUT) / 1_000_000)


def _parse_json_from_response(raw: str) -> dict | None:
    """Strip ```json ... ``` fences if present and parse."""
    m = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", raw, re.DOTALL)
    candidate = m.group(1) if m else raw.strip()
    try:
        return json.loads(candidate)
    except json.JSONDecodeError:
        return None


def _player_count(extracted: dict) -> int:
    """Total players the model identified across all role-arrays."""
    n = 1 if extracted.get("center") else 0
    n += len(extracted.get("offensive_line", []))
    n += len(extracted.get("tight_ends", []))
    n += len(extracted.get("wide_receivers", []))
    n += len(extracted.get("backfield", []))
    return n


def _load_pairs() -> list[dict]:
    sample = {p["id"]: p for p in json.loads(SAMPLE.read_text())}
    by_play: dict[str, dict] = {}
    for f in EXTRACTIONS.glob("*.json"):
        d = json.loads(f.read_text())
        pid = d["play_id"]
        arm = d["arm"]
        by_play.setdefault(pid, {})[arm] = d
    pairs = []
    for pid, arms in by_play.items():
        if "cold" not in arms or "primed" not in arms:
            continue
        cold = arms["cold"]
        primed = arms["primed"]
        cold_x = _parse_json_from_response(cold.get("response_text", ""))
        primed_x = _parse_json_from_response(primed.get("response_text", ""))
        pairs.append({
            "play_id": pid,
            "stratum": sample.get(pid, {}).get("stratum"),
            "play_name": sample.get(pid, {}).get("play_name"),
            "team": sample.get(pid, {}).get("team"),
            "cold": {
                "usage": cold["usage"],
                "cost": _cost(cold["usage"]),
                "duration_s": cold.get("duration_s"),
                "players": _player_count(cold_x) if cold_x else 0,
                "json_parsed": cold_x is not None,
                "play_type_observed": cold_x.get("play_type_observed") if cold_x else None,
                "confidence": cold_x.get("confidence") if cold_x else None,
            },
            "primed": {
                "usage": primed["usage"],
                "cost": _cost(primed["usage"]),
                "duration_s": primed.get("duration_s"),
                "players": _player_count(primed_x) if primed_x else 0,
                "json_parsed": primed_x is not None,
                "play_type_observed": primed_x.get("play_type_observed") if primed_x else None,
                "confidence": primed_x.get("confidence") if primed_x else None,
                "prior_used": primed.get("prior_used"),
            },
        })
    return pairs


def _paired_t(diffs: list[float]) -> tuple[float, float, float, float]:
    """Returns (mean_diff, std_diff, t_stat, cohens_d)."""
    n = len(diffs)
    mean = statistics.fmean(diffs)
    std = statistics.stdev(diffs) if n > 1 else 0.0
    t = (mean / (std / math.sqrt(n))) if std > 0 else 0.0
    d = (mean / std) if std > 0 else 0.0
    return mean, std, t, d


def _d_ci95(d: float, n: int) -> tuple[float, float]:
    """Approximate 95% CI on Cohen's d for paired design."""
    if n < 2:
        return (d, d)
    se = math.sqrt((1 / n) + (d ** 2) / (2 * n))
    return (d - 1.96 * se, d + 1.96 * se)


def _pct(a: float, b: float) -> float:
    return ((a - b) / b * 100) if b else 0.0


def main() -> None:
    pairs = _load_pairs()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "pairs.json").write_text(json.dumps(pairs, indent=2))

    if not pairs:
        print("no complete cold+primed pairs found")
        return

    # Diffs for paired stats: primed - cold on log(output_tokens). Negative = primed cheaper.
    diffs_log_out = [
        math.log(max(p["primed"]["usage"]["output_tokens"], 1))
        - math.log(max(p["cold"]["usage"]["output_tokens"], 1))
        for p in pairs
    ]
    diffs_cost = [p["primed"]["cost"] - p["cold"]["cost"] for p in pairs]
    diffs_completeness = [p["primed"]["players"] - p["cold"]["players"]
                          for p in pairs]

    n = len(pairs)
    primed_only = [p for p in pairs if p["primed"].get("prior_used")]
    no_prior = [p for p in pairs if not p["primed"].get("prior_used")]

    md_lines = []
    md_lines.append("# Vision pilot results — cold vs primed extraction\n")
    md_lines.append(f"**Pairs analyzed:** {n} ({len(primed_only)} with a real prior, "
                    f"{len(no_prior)} primed = cold because no prior decoded)\n")
    md_lines.append(f"**Model:** claude-sonnet-4-5\n")

    # --- Overall stats ---
    md_lines.append("## Headline numbers\n")
    md_lines.append("| Metric | Cold | Primed | Δ (primed − cold) | Δ % |")
    md_lines.append("|---|---:|---:|---:|---:|")
    for key, label in [("output_tokens", "Avg output_tokens"),
                       ("input_tokens", "Avg input_tokens (post-cache)")]:
        cold_avg = statistics.fmean(p["cold"]["usage"][key] for p in pairs)
        primed_avg = statistics.fmean(p["primed"]["usage"][key] for p in pairs)
        md_lines.append(f"| {label} | {cold_avg:.0f} | {primed_avg:.0f} | "
                        f"{primed_avg - cold_avg:+.0f} | {_pct(primed_avg, cold_avg):+.1f}% |")
    cold_cost = statistics.fmean(p["cold"]["cost"] for p in pairs)
    primed_cost = statistics.fmean(p["primed"]["cost"] for p in pairs)
    md_lines.append(f"| Avg cost/call | ${cold_cost:.4f} | ${primed_cost:.4f} | "
                    f"${primed_cost - cold_cost:+.4f} | {_pct(primed_cost, cold_cost):+.1f}% |")
    cold_players = statistics.fmean(p["cold"]["players"] for p in pairs)
    primed_players = statistics.fmean(p["primed"]["players"] for p in pairs)
    md_lines.append(f"| Avg player count | {cold_players:.1f} | {primed_players:.1f} | "
                    f"{primed_players - cold_players:+.1f} | {_pct(primed_players, cold_players):+.1f}% |\n")

    # --- Paired stats on log(output_tokens) ---
    mean_log, std_log, t_log, d_log = _paired_t(diffs_log_out)
    ci_lo, ci_hi = _d_ci95(d_log, n)
    pct_change = (math.exp(mean_log) - 1) * 100
    md_lines.append("## Paired statistics — log(output_tokens), primed vs cold\n")
    md_lines.append(f"- **n** = {n}")
    md_lines.append(f"- mean Δlog(output) = {mean_log:+.4f} → "
                    f"**{pct_change:+.1f}% change in output_tokens, geometric mean**")
    md_lines.append(f"- t-statistic = {t_log:.2f}  (df = {n-1})")
    md_lines.append(f"- Cohen's d = {d_log:+.3f}  (95% CI [{ci_lo:+.3f}, {ci_hi:+.3f}])\n")

    # --- Stratified ---
    md_lines.append("## By stratum\n")
    md_lines.append("| Stratum | n | Cold out_tok | Primed out_tok | Δ % | Players cold | Players primed |")
    md_lines.append("|---|---:|---:|---:|---:|---:|---:|")
    by_stratum: dict[str, list[dict]] = {}
    for p in pairs:
        by_stratum.setdefault(p["stratum"] or "?", []).append(p)
    for stratum, items in sorted(by_stratum.items()):
        if not items: continue
        c_out = statistics.fmean(p["cold"]["usage"]["output_tokens"] for p in items)
        p_out = statistics.fmean(p["primed"]["usage"]["output_tokens"] for p in items)
        c_pl = statistics.fmean(p["cold"]["players"] for p in items)
        p_pl = statistics.fmean(p["primed"]["players"] for p in items)
        md_lines.append(f"| {stratum} | {len(items)} | {c_out:.0f} | {p_out:.0f} | "
                        f"{_pct(p_out, c_out):+.1f}% | {c_pl:.1f} | {p_pl:.1f} |")
    md_lines.append("")

    # --- Completeness ---
    md_lines.append("## Completeness check\n")
    md_lines.append(f"- All pairs JSON-parsed? "
                    f"{sum(p['cold']['json_parsed'] and p['primed']['json_parsed'] for p in pairs)} / {n}")
    play_type_match = sum(p["cold"]["play_type_observed"] == p["primed"]["play_type_observed"]
                          for p in pairs)
    md_lines.append(f"- Cold and primed agree on play_type? {play_type_match} / {n}")
    cold_only_more = sum(1 for p in pairs if p["cold"]["players"] > p["primed"]["players"])
    primed_only_more = sum(1 for p in pairs if p["primed"]["players"] > p["cold"]["players"])
    md_lines.append(f"- Cold found more players in {cold_only_more} plays; "
                    f"primed found more in {primed_only_more} plays\n")

    # --- Decision ---
    md_lines.append("## Decision\n")
    decision_pct = pct_change  # negative means reduction
    regressed_completeness = primed_players < cold_players - 0.5  # >0.5 player loss
    md_lines.append(f"- Output-token change: **{decision_pct:+.1f}%** (target: ≤ −15% to favor hybrid)")
    md_lines.append(f"- Completeness regression? {'YES' if regressed_completeness else 'no'}")
    if decision_pct <= -15 and not regressed_completeness:
        md_lines.append("\n**→ Build the hybrid pipeline.** Priming statistically reduces extraction cost without losing players.")
    else:
        md_lines.append("\n**→ Drop the hybrid.** Priming does not show the required cost reduction in this design. "
                        "Either go straight to cold extraction at scale, or invest in a tighter extraction prompt.")

    # --- Spot-check 5 random pairs ---
    md_lines.append("\n## Spot-check (5 pairs)\n")
    import random
    rng = random.Random(20260521)
    samples = rng.sample(pairs, k=min(5, n))
    for p in samples:
        md_lines.append(f"### {p['play_name']} ({p['team']}) — {p['stratum']}")
        md_lines.append(f"- play_id: `{p['play_id']}`")
        md_lines.append(f"- cold: out_tok={p['cold']['usage']['output_tokens']} "
                        f"players={p['cold']['players']} type={p['cold']['play_type_observed']}")
        md_lines.append(f"- primed: out_tok={p['primed']['usage']['output_tokens']} "
                        f"players={p['primed']['players']} type={p['primed']['play_type_observed']} "
                        f"prior={p['primed']['prior_used']}")
        md_lines.append("")

    (OUT_DIR / "report.md").write_text("\n".join(md_lines))
    print(f"wrote {OUT_DIR / 'report.md'}")
    print(f"wrote {OUT_DIR / 'pairs.json'}")
    print()
    print("\n".join(md_lines[:30]))


if __name__ == "__main__":
    main()
