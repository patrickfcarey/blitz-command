#!/usr/bin/env python3
"""Full M25 extraction over canonical (deduplicated) plays.

Cold-only — the pilot showed priming does not meaningfully reduce cost,
so we skip the primed arm. One API call per unique play.

Inputs:
    tools/playbook-vision-pilot/dedup-crops/*.jpg + _canonical_manifest.json

Outputs:
    /tmp/pilot-work/canonical-extractions/<slug>.json

Resume-safe: skips already-saved extractions. Pre-warms prompt cache with
the first call sequential, then dispatches the rest with 5 parallel workers.

Cost projection: ~7,385 unique plays × ~$0.022 = ~$162.

Run:
    .venv/bin/python tools/playbook-vision-pilot/dispatch_canonical.py [--limit N] [--workers W]
"""
from __future__ import annotations
import argparse
import base64
import json
import os
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import anthropic
from dotenv import load_dotenv

REPO = Path(__file__).resolve().parents[2]
PROMPT_PATH = REPO / "tools/playbook-vision-pilot/subagent-prompt.md"
MANIFEST = REPO / "tools/playbook-vision-pilot/dedup-crops/_canonical_manifest.json"
CROPS_DIR = REPO / "tools/playbook-vision-pilot/dedup-crops"
OUT_DIR = REPO / "data/games/madden-25-ps3/play-geometry"
# Haiku 4.5 + prompt caching = ~$0.008/call, validated as accurate as Sonnet
# on the 12 hand-labeled plays. Python computes target_gap deterministically
# and injects it as a hint in the user message.
MODEL = "claude-haiku-4-5-20251001"
MAX_TOKENS = 2048

sys.path.insert(0, str(REPO / "tools/playbook-vision-pilot"))
from target_gap_python import compute_target_gap_for_crop  # noqa: E402
from play_concepts import classify as classify_play  # noqa: E402


def _load_rules() -> str:
    text = PROMPT_PATH.read_text()
    start = text.index("## SYSTEM PROMPT")
    start = text.index("\n", start) + 1
    end = text.index("## USER MESSAGE template")
    return text[start:end].strip()


def _build_user(info: dict, crop_path: Path, py_hints: dict,
                concept: dict) -> list[dict]:
    img_b64 = base64.standard_b64encode(crop_path.read_bytes()).decode("ascii")
    play_id = crop_path.stem
    # Concept + family + blockers_implicit are Python-classified from the
    # play_name. Pass them as authoritative — the LLM doesn't have to name
    # the concept. For runs with blockers_implicit, the LLM omits route
    # entries for blockers (OL/TE/WR who just block).
    concept_line = ""
    if concept.get("concept") and concept["concept"] != "unknown":
        concept_line = f"py_concept: {concept['concept']} (family={concept['concept_family']})\n"
    blocker_hint = ""
    if concept.get("blockers_implicit"):
        blocker_hint = ("This is a standard run — OL/TE/WR blocking is "
                        "IMPLICIT. Emit `routes` ONLY for the ball-carrier "
                        "(in `ball_carrier`) and any non-blocking receivers "
                        "(rare on runs). For typical run plays the `routes` "
                        "object should be EMPTY {}.\n")

    context = (f"play_id: {play_id}\n"
               f"formation: {info['family']} {info['formation']}\n"
               f"play_name: {info['play_name']}\n"
               f"play_type: {info['play_type']}\n"
               f"py_target_gap: {py_hints.get('target_gap')}\n"
               f"{concept_line}"
               "\n"
               "Filename encodes expected personnel as r#f#t#w# "
               "(RB/FB/TE/WR). Use those counts as ground truth — LABEL "
               "visible glyphs, don't re-derive counts. Skip target_gap "
               "in your output (Python provided). If py_concept was given, "
               "use it as the `concept` field unchanged (don't re-name).\n"
               f"{blocker_hint}"
               "Emit only the JSON object.")
    return [
        {"type": "image",
         "source": {"type": "base64", "media_type": "image/jpeg", "data": img_b64}},
        {"type": "text", "text": context},
    ]


def _call(client: anthropic.Anthropic, rules: str, info: dict,
          crop_path: Path) -> dict:
    t0 = time.time()
    # Python computes target_gap + concept tag deterministically.
    py_hints = compute_target_gap_for_crop(crop_path, info["play_type"])
    concept = classify_play(info["play_name"], info["play_type"])
    resp = client.messages.create(
        model=MODEL,
        max_tokens=MAX_TOKENS,
        system=[{"type": "text", "text": rules,
                 "cache_control": {"type": "ephemeral"}}],
        messages=[{"role": "user",
                   "content": _build_user(info, crop_path, py_hints, concept)}],
    )
    dt = time.time() - t0
    u = resp.usage
    text = "".join(b.text for b in resp.content if b.type == "text")
    return {
        "usage": {
            "input_tokens": u.input_tokens,
            "cache_creation_input_tokens": getattr(u, "cache_creation_input_tokens", 0),
            "cache_read_input_tokens": getattr(u, "cache_read_input_tokens", 0),
            "output_tokens": u.output_tokens,
        },
        "stop_reason": resp.stop_reason,
        "duration_s": round(dt, 2),
        "response_text": text,
        "py_hints": py_hints,
        "py_concept": concept,
    }


def _existing(slug_name: str) -> bool:
    return (OUT_DIR / f"{Path(slug_name).stem}.json").exists()


def _save(slug_name: str, info: dict, result: dict) -> None:
    out = OUT_DIR / f"{Path(slug_name).stem}.json"
    payload = {"slug": Path(slug_name).stem, "info": info, **result}
    out.write_text(json.dumps(payload, indent=2))


def _run_job(client: anthropic.Anthropic, rules: str, slug_name: str,
             info: dict, progress: dict, lock: threading.Lock) -> None:
    crop = CROPS_DIR / slug_name
    try:
        result = _call(client, rules, info, crop)
        _save(slug_name, info, result)
        ok, err = True, None
    except Exception as exc:  # noqa: BLE001
        ok, err = False, repr(exc)
        result = {"usage": {}, "stop_reason": "error",
                  "duration_s": 0, "response_text": ""}
        (OUT_DIR / f"{Path(slug_name).stem}.json").write_text(
            json.dumps({"slug": Path(slug_name).stem, "info": info,
                        "error": err}, indent=2))

    with lock:
        progress["done"] += 1
        if ok:
            u = result["usage"]
            progress["input_tokens"] += u.get("input_tokens", 0)
            progress["cache_creation"] += u.get("cache_creation_input_tokens", 0)
            progress["cache_read"] += u.get("cache_read_input_tokens", 0)
            progress["output_tokens"] += u.get("output_tokens", 0)
        n_done, n_total = progress["done"], progress["total"]
        status = "OK" if ok else f"ERR {err[:60] if err else ''}"
        if n_done % 25 == 0 or not ok:
            cost = ((progress["input_tokens"] * 3
                    + progress["cache_creation"] * 3.75
                    + progress["cache_read"] * 0.30
                    + progress["output_tokens"] * 15) / 1_000_000)
            print(f"[{n_done:>4}/{n_total}] {status:<3}  "
                  f"running cost ${cost:.2f}  ({slug_name})")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--workers", type=int, default=5)
    args = ap.parse_args()

    load_dotenv(REPO / ".env")
    if not os.environ.get("ANTHROPIC_API_KEY"):
        sys.exit("ANTHROPIC_API_KEY not set (looked in .env and env)")

    rules = _load_rules()
    manifest = json.loads(MANIFEST.read_text())
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    items = list(manifest.items())
    if args.limit:
        items = items[:args.limit]

    to_run = [(slug, info) for slug, info in items if not _existing(slug)]
    skipped = len(items) - len(to_run)
    print(f"rules: {len(rules)} chars (~{len(rules)//4} tokens)")
    print(f"jobs: {len(items)} total, {skipped} already done, {len(to_run)} to run")
    print(f"workers: {args.workers}; model: {MODEL}")
    if not to_run:
        print("nothing to do.")
        return

    client = anthropic.Anthropic()
    progress = {"done": 0, "total": len(to_run),
                "input_tokens": 0, "cache_creation": 0,
                "cache_read": 0, "output_tokens": 0}
    lock = threading.Lock()
    t_start = time.time()

    # Prime the cache sequentially.
    print("priming prompt cache with first job (sequential)...")
    first_slug, first_info = to_run[0]
    _run_job(client, rules, first_slug, first_info, progress, lock)
    rest = to_run[1:]

    if rest:
        with ThreadPoolExecutor(max_workers=args.workers) as ex:
            futs = [ex.submit(_run_job, client, rules, slug, info,
                              progress, lock)
                    for slug, info in rest]
            for _ in as_completed(futs):
                pass

    dt = time.time() - t_start
    p = progress
    # Haiku 4.5 pricing per Mtok: $1 in / $5 out / $1.25 cache_create / $0.10 cache_read.
    cost = (p["input_tokens"] * 1.0 + p["cache_creation"] * 1.25
            + p["cache_read"] * 0.10 + p["output_tokens"] * 5.0) / 1_000_000
    print(f"\n--- summary ---")
    print(f"  jobs done:    {p['done']} / {p['total']}")
    print(f"  wall time:    {dt/60:.1f} min")
    print(f"  input:        {p['input_tokens']:,}")
    print(f"  cache_create: {p['cache_creation']:,}")
    print(f"  cache_read:   {p['cache_read']:,}")
    print(f"  output:       {p['output_tokens']:,}")
    print(f"  cost:         ${cost:.2f}")
    print(f"  outputs:      {OUT_DIR}")


if __name__ == "__main__":
    main()
