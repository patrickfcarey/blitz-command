#!/usr/bin/env python3
"""Smoke-test Haiku 3.5 + Python pre-detection on the 12 hand-labeled plays.

Goal: validate that with the v4 prompt MINUS target_gap (which Python now
handles) + Python pre-detection hints injected into the user message,
Haiku 3.5 can produce extractions of comparable quality to Sonnet 4.5
at ~4x lower cost.

For each play:
- Compute target_gap in Python (deterministic).
- Send the rest to Haiku 3.5 with a hint string:
    "Pre-detected (deterministic Python): C-square at (x,y),
     target_gap=<value>. The model only needs to fill in player counts,
     concept, routes."
- Compare to user's ground truth for the categories we have truth for.

Outputs:
- /tmp/pilot-work/haiku-extractions/<play_id>.json
- printed accuracy summary
"""
from __future__ import annotations
import base64
import json
import os
import re
import sys
from pathlib import Path

import anthropic
from dotenv import load_dotenv

REPO = Path(__file__).resolve().parents[2]
PROMPT_PATH = REPO / "tools/playbook-vision-pilot/subagent-prompt.md"
MANIFEST = REPO / "tools/playbook-vision-pilot/dispatch-crops/_manifest.json"
CROPS_DIR = REPO / "tools/playbook-vision-pilot/dispatch-crops"
TRUTH_PATH = Path("/mnt/c/Users/root/Downloads/review_truth.json")
OUT_DIR = Path("/tmp/pilot-work/haiku-extractions")
MODEL = "claude-haiku-4-5-20251001"   # latest Haiku — let's see if it caches now
# fallback: "claude-3-5-haiku-20241022" (older, definitely supports caching)
MAX_TOKENS = 2048

sys.path.insert(0, str(REPO / "tools/playbook-vision-pilot"))
from target_gap_python import compute_target_gap_for_crop  # noqa: E402


def _load_rules() -> str:
    text = PROMPT_PATH.read_text()
    start = text.index("## SYSTEM PROMPT")
    start = text.index("\n", start) + 1
    end = text.index("## USER MESSAGE template")
    return text[start:end].strip()


def _build_user(info: dict, crop_path: Path, py_hints: dict) -> list[dict]:
    img_b64 = base64.standard_b64encode(crop_path.read_bytes()).decode("ascii")
    context = (f"play_id: {info.get('play_id', crop_path.stem)}\n"
               f"team: {info['team']}\n"
               f"formation: {info['formation']}\n"
               f"play_name: {info['play_name']}\n"
               f"play_type: {info['play_type']}\n"
               "\n"
               "## Pre-detected geometry (deterministic, from Python)\n"
               f"- C-square center: {py_hints.get('c_xy')}\n"
               f"- target_gap (run only, computed in Python): {py_hints.get('target_gap')}\n"
               "\n"
               "You do NOT need to compute target_gap — Python already did it "
               "deterministically and accurately. Skip it in your output. "
               "Focus on player counts, route classification, and concept naming.\n"
               "\nExtract per the schema. Emit only the JSON object.")
    return [
        {"type": "image",
         "source": {"type": "base64", "media_type": "image/jpeg", "data": img_b64}},
        {"type": "text", "text": context},
    ]


def main() -> None:
    load_dotenv(REPO / ".env")
    if not os.environ.get("ANTHROPIC_API_KEY"):
        sys.exit("ANTHROPIC_API_KEY not set")

    rules = _load_rules()
    manifest = json.loads(MANIFEST.read_text())
    truth = json.loads(TRUTH_PATH.read_text())
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    client = anthropic.Anthropic()

    print(f"Model: {MODEL}")
    print(f"Rules: {len(rules)} chars (~{len(rules) // 4} tokens)")

    totals = {"in": 0, "create": 0, "read": 0, "out": 0, "n": 0}

    for tp in truth["plays"]:
        pid = tp["play_id"]
        info = manifest.get(pid)
        if not info:
            continue
        crop = CROPS_DIR / info["filename"]
        py_hints = compute_target_gap_for_crop(crop, info["play_type"])
        # Add play_id to info for the prompt
        info_with_id = {**info, "play_id": pid}
        resp = client.messages.create(
            model=MODEL,
            max_tokens=MAX_TOKENS,
            system=[{"type": "text", "text": rules,
                     "cache_control": {"type": "ephemeral"}}],
            messages=[{"role": "user",
                       "content": _build_user(info_with_id, crop, py_hints)}],
        )
        u = resp.usage
        out_text = "".join(b.text for b in resp.content if b.type == "text")
        totals["in"] += u.input_tokens
        totals["create"] += getattr(u, "cache_creation_input_tokens", 0)
        totals["read"] += getattr(u, "cache_read_input_tokens", 0)
        totals["out"] += u.output_tokens
        totals["n"] += 1
        # Save
        (OUT_DIR / f"{pid}.json").write_text(json.dumps({
            "play_id": pid,
            "info": info,
            "py_hints": py_hints,
            "usage": {"input_tokens": u.input_tokens,
                      "cache_creation_input_tokens":
                          getattr(u, "cache_creation_input_tokens", 0),
                      "cache_read_input_tokens":
                          getattr(u, "cache_read_input_tokens", 0),
                      "output_tokens": u.output_tokens},
            "response_text": out_text,
        }, indent=2))
        # Quick result summary
        m = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", out_text, re.DOTALL)
        try:
            obj = json.loads(m.group(1) if m else out_text.strip())
            ol = len(obj.get("offensive_line", []))
            te = len(obj.get("tight_ends", []))
            wr = len(obj.get("wide_receivers", []))
            bf = len(obj.get("backfield", []))
            pt = obj.get("play_type_observed")
        except Exception:
            ol = te = wr = bf = pt = "?"
        cache_hit = " (cache hit)" if getattr(u, "cache_read_input_tokens", 0) > 0 else ""
        print(f"  {pid:<48} ol={ol} te={te} wr={wr} bf={bf} type={pt}{cache_hit}")

    # Cost (Haiku 4.5 pricing: $1/M in, $5/M out, $1.25/M cache_create, $0.10/M cache_read)
    # Haiku 3.5 pricing: $0.80/M in, $4/M out, $1/M cache_create, $0.08/M cache_read
    P_IN, P_OUT, P_CC, P_CR = 1.0, 5.0, 1.25, 0.10
    cost = (totals["in"] * P_IN + totals["create"] * P_CC
            + totals["read"] * P_CR + totals["out"] * P_OUT) / 1_000_000
    print(f"\n=== {totals['n']} calls ===")
    print(f"  input:        {totals['in']}")
    print(f"  cache_create: {totals['create']}")
    print(f"  cache_read:   {totals['read']}")
    print(f"  output:       {totals['out']}")
    print(f"  cost:         ${cost:.4f}  (avg ${cost/totals['n']:.4f}/call)")


if __name__ == "__main__":
    main()
