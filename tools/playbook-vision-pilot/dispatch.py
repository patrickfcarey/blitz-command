#!/usr/bin/env python3
"""Pilot dispatcher: 50 plays × 2 arms (cold + primed) = 100 API calls.

- Sonnet 4.5 with prompt caching on the system prompt (cleared 2048-token min).
- 5 concurrent workers (per pilot rule: max 5 in flight).
- Resume-safe: skips plays whose extraction JSON already exists on disk.
- Tracks per-call usage, prints running totals.
- Saves each extraction to /tmp/pilot-work/extractions/<play_id>__<arm>.json.

Cost estimate:
- First few calls (cache cold) ~$0.033 each.
- Subsequent calls (cache hit) ~$0.022 each.
- Total ≈ $2.20 for 100 calls.

Run:
    .venv/bin/python tools/playbook-vision-pilot/dispatch.py [--limit N]

(--limit lets you do a small partial run first before committing the full $2.20.)
"""
from __future__ import annotations
import argparse
import base64
import json
import os
import random
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import anthropic
from dotenv import load_dotenv

REPO = Path(__file__).resolve().parents[2]
PROMPT_PATH = REPO / "tools/playbook-vision-pilot/subagent-prompt.md"
MANIFEST = REPO / "tools/playbook-vision-pilot/dispatch-crops/_manifest.json"
CROPS_DIR = REPO / "tools/playbook-vision-pilot/dispatch-crops"
PRIORS = Path("/tmp/pilot-work/priors.json")
OUT_DIR = Path("/tmp/pilot-work/extractions")
MODEL = "claude-sonnet-4-5"
MAX_TOKENS = 2048
SEED = 20260521


def _load_rules() -> str:
    text = PROMPT_PATH.read_text()
    start = text.index("## SYSTEM PROMPT")
    start = text.index("\n", start) + 1
    end = text.index("## USER MESSAGE template")
    return text[start:end].strip()


def _build_user(play: dict, prior: str | None, crop_path: Path) -> list[dict]:
    img_b64 = base64.standard_b64encode(crop_path.read_bytes()).decode("ascii")
    context = (f"play_id: {play['play_id']}\n"
               f"team: {play['team']}\n"
               f"formation: {play['formation']}\n"
               f"play_name: {play['play_name']}\n"
               f"play_type: {play['play_type']}")
    if prior:
        context += f"\n{prior}"
    context += ("\n\nThe image is the wide LOS-zoom JPEG for this play. The "
                "filename encodes formation, play_type, play_slug, team, and "
                "image/panel index for context. Extract per the schema in the "
                "system prompt. Emit only the JSON object.")
    return [
        {"type": "image",
         "source": {"type": "base64", "media_type": "image/jpeg", "data": img_b64}},
        {"type": "text", "text": context},
    ]


def _call(client: anthropic.Anthropic, rules: str, play: dict,
          prior: str | None, crop_path: Path) -> dict:
    t0 = time.time()
    resp = client.messages.create(
        model=MODEL,
        max_tokens=MAX_TOKENS,
        system=[{"type": "text", "text": rules,
                 "cache_control": {"type": "ephemeral"}}],
        messages=[{"role": "user", "content": _build_user(play, prior, crop_path)}],
    )
    dt = time.time() - t0
    u = resp.usage
    text = "".join(b.text for b in resp.content if b.type == "text")
    return {
        "usage": {
            "input_tokens": u.input_tokens,
            "cache_creation_input_tokens":
                getattr(u, "cache_creation_input_tokens", 0),
            "cache_read_input_tokens":
                getattr(u, "cache_read_input_tokens", 0),
            "output_tokens": u.output_tokens,
        },
        "stop_reason": resp.stop_reason,
        "duration_s": round(dt, 2),
        "response_text": text,
    }


def _build_jobs(manifest: dict, priors: dict, rng: random.Random) -> list[dict]:
    jobs = []
    for play_id, info in manifest.items():
        prior_obj = priors.get(play_id)
        prior_text = prior_obj["string"] if prior_obj else None
        arms = ["cold", "primed"]
        rng.shuffle(arms)
        for arm in arms:
            jobs.append({
                "play_id": play_id,
                "arm": arm,
                "info": info,
                "prior_text": prior_text if arm == "primed" else None,
            })
    return jobs


def _existing(play_id: str, arm: str) -> bool:
    return (OUT_DIR / f"{play_id}__{arm}.json").exists()


def _save(job: dict, result: dict) -> None:
    out = OUT_DIR / f"{job['play_id']}__{job['arm']}.json"
    payload = {
        "play_id": job["play_id"],
        "arm": job["arm"],
        "info": job["info"],
        "prior_used": job["prior_text"],
        **result,
    }
    out.write_text(json.dumps(payload, indent=2))


def _run_job(client: anthropic.Anthropic, rules: str, job: dict,
             progress: dict, lock: threading.Lock) -> dict:
    info = job["info"]
    crop = CROPS_DIR / info["filename"]
    play = {
        "play_id": job["play_id"],
        "team": info["team"],
        "formation": info["formation"],
        "play_name": info["play_name"],
        "play_type": info["play_type"],
    }
    try:
        result = _call(client, rules, play, job["prior_text"], crop)
        _save(job, result)
        ok = True
        err = None
    except Exception as exc:  # noqa: BLE001
        result = {"usage": {}, "stop_reason": "error",
                  "duration_s": 0, "response_text": ""}
        ok = False
        err = repr(exc)
        # Still save so we can see what failed.
        payload = {"play_id": job["play_id"], "arm": job["arm"],
                   "info": job["info"], "error": err}
        out = OUT_DIR / f"{job['play_id']}__{job['arm']}.json"
        out.write_text(json.dumps(payload, indent=2))

    with lock:
        progress["done"] += 1
        if ok:
            u = result["usage"]
            progress["input_tokens"] += u.get("input_tokens", 0)
            progress["cache_creation"] += u.get("cache_creation_input_tokens", 0)
            progress["cache_read"] += u.get("cache_read_input_tokens", 0)
            progress["output_tokens"] += u.get("output_tokens", 0)
        n_done = progress["done"]
        n_total = progress["total"]
        status = "OK" if ok else f"ERR {err[:60] if err else ''}"
        cache_hit = ""
        if ok and result["usage"].get("cache_read_input_tokens", 0) > 0:
            cache_hit = " (cache hit)"
        print(f"[{n_done:>3}/{n_total}] {job['arm']:<6} {job['play_id']}  "
              f"{result.get('duration_s', 0)}s  {status}{cache_hit}")
    return result


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=None,
                    help="Only run the first N jobs (for partial test).")
    ap.add_argument("--workers", type=int, default=5,
                    help="Max concurrent API calls (default 5).")
    args = ap.parse_args()

    load_dotenv(REPO / ".env")
    if not os.environ.get("ANTHROPIC_API_KEY"):
        sys.exit("ANTHROPIC_API_KEY not set (looked in .env and env)")

    rules = _load_rules()
    manifest = json.loads(MANIFEST.read_text())
    priors_raw = json.loads(PRIORS.read_text())
    priors = {k: v for k, v in priors_raw.items() if v is not None}

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    rng = random.Random(SEED)
    jobs = _build_jobs(manifest, priors, rng)
    if args.limit:
        jobs = jobs[:args.limit]

    # Skip already-done.
    to_run = [j for j in jobs if not _existing(j["play_id"], j["arm"])]
    skipped = len(jobs) - len(to_run)
    print(f"rules: {len(rules)} chars (~{len(rules) // 4} tokens)")
    print(f"jobs: {len(jobs)} total, {skipped} already done, {len(to_run)} to run")
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

    # Pre-warm the prompt cache with the FIRST job sequentially. If we launch
    # all 5 workers simultaneously, they all submit before any has finished,
    # so each one creates its own cache entry (no shared hits). Doing the
    # first call alone populates the cache; subsequent parallel workers all
    # hit it.
    first_job, rest = to_run[0], to_run[1:]
    print("priming prompt cache with first job (sequential)...")
    _run_job(client, rules, first_job, progress, lock)

    if rest:
        with ThreadPoolExecutor(max_workers=args.workers) as ex:
            futs = [ex.submit(_run_job, client, rules, job, progress, lock)
                    for job in rest]
            for _ in as_completed(futs):
                pass

    dt = time.time() - t_start
    p = progress
    # Sonnet 4.5 pricing (per Mtok): input=$3, output=$15,
    # cache_creation=$3.75, cache_read=$0.30.
    cost = (p["input_tokens"] * 3 + p["cache_creation"] * 3.75
            + p["cache_read"] * 0.30 + p["output_tokens"] * 15) / 1_000_000
    print(f"\n--- summary ---")
    print(f"  jobs done:           {p['done']} / {p['total']}")
    print(f"  wall time:           {dt:.1f}s")
    print(f"  input_tokens:        {p['input_tokens']}")
    print(f"  cache_creation:      {p['cache_creation']}")
    print(f"  cache_read:          {p['cache_read']}")
    print(f"  output_tokens:       {p['output_tokens']}")
    print(f"  estimated cost:      ${cost:.3f}")
    print(f"  outputs in:          {OUT_DIR}")


if __name__ == "__main__":
    main()
