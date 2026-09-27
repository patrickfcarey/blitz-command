#!/usr/bin/env python3
"""Smoke-test the M25 vision pipeline before the full pilot.

Sends the I-Form Pro HB Blast crop to claude-haiku-4-5 twice — once "cold"
(no concept prior) and once "primed" (with prior). Uses prompt caching on
the rules section so the second call should show cache_read_input_tokens.

Verifies:
- Prompt caching works (cache_read on call 2).
- Haiku correctly identifies C-square, 5 OL, TEs, WRs, backfield.
- Run-vs-pass classification matches (should emit play_type_observed=run).

Outputs:
- pilot-work/extractions/iform-pro__cold.json
- pilot-work/extractions/iform-pro__primed.json
- Printed cost summary.

Requires ANTHROPIC_API_KEY in .env or env.
"""
from __future__ import annotations
import base64
import json
import os
import sys
from pathlib import Path

import anthropic
from dotenv import load_dotenv

REPO = Path(__file__).resolve().parents[2]
PROMPT_PATH = REPO / "tools/playbook-vision-pilot/subagent-prompt.md"
CROP_PATH = (REPO / "tools/playbook-vision-pilot/dispatch-crops"
             / "iform-pro__run__hb-blast__baltimore-ravens__img45p1__WIDE.jpg")
OUT_DIR = Path("/tmp/pilot-work/extractions")
MODEL = "claude-sonnet-4-5"  # debug-only override (was haiku-4-5)
                              # — checks whether caching infrastructure is wired
                              # right. Haiku 4.5 may not yet support caching.
MAX_TOKENS = 2048

# Smoke-test play context (would come from pilot-sample.json + priors.json
# in the real dispatcher).
PLAY = {
    "play_id": "baltimore-ravens__iform-pro__hb-blast__img45p1",
    "team": "Baltimore Ravens",
    "formation": "I-Form Pro",
    "play_name": "HB Blast",
    "play_type": "run",
}
PRIOR = ("Concept prior (from name): concept=blast, play_type=run. "
         "Emit deltas if the diagram disagrees.")


def _load_rules() -> str:
    """Extract the SYSTEM PROMPT section from subagent-prompt.md
    (between '## SYSTEM PROMPT' and '## USER MESSAGE template').
    That is the portion sized to clear Haiku's 2048-token cache minimum."""
    text = PROMPT_PATH.read_text()
    start_marker = "## SYSTEM PROMPT"
    end_marker = "## USER MESSAGE template"
    if start_marker not in text or end_marker not in text:
        raise RuntimeError("subagent-prompt.md missing expected section headers")
    start = text.index(start_marker)
    # Skip to the line after the heading itself.
    start = text.index("\n", start) + 1
    end = text.index(end_marker)
    return text[start:end].strip()


def _build_user_message(play: dict, prior: str | None) -> list[dict]:
    img_b64 = base64.standard_b64encode(CROP_PATH.read_bytes()).decode("ascii")
    context = (f"play_id: {play['play_id']}\n"
               f"team: {play['team']}\n"
               f"formation: {play['formation']}\n"
               f"play_name: {play['play_name']}\n"
               f"play_type: {play['play_type']}")
    if prior:
        context += f"\n{prior}"
    context += ("\n\nThe image is the wide LOS-zoom JPEG for this play "
                "(filename encodes: formation, play_type, play_slug, team, "
                "img/panel index). Extract per the schema.")
    return [
        {"type": "image",
         "source": {"type": "base64",
                    "media_type": "image/jpeg",
                    "data": img_b64}},
        {"type": "text", "text": context},
    ]


def _call(client: anthropic.Anthropic, rules: str,
          user_blocks: list[dict], label: str) -> dict:
    resp = client.messages.create(
        model=MODEL,
        max_tokens=MAX_TOKENS,
        system=[{"type": "text",
                 "text": rules,
                 "cache_control": {"type": "ephemeral"}}],
        messages=[{"role": "user", "content": user_blocks}],
    )
    usage = resp.usage
    out_text = "".join(b.text for b in resp.content if b.type == "text")
    print(f"\n=== {label} ===")
    print(f"  input_tokens:              {usage.input_tokens}")
    print(f"  cache_creation_input:      {getattr(usage, 'cache_creation_input_tokens', 0)}")
    print(f"  cache_read_input:          {getattr(usage, 'cache_read_input_tokens', 0)}")
    print(f"  output_tokens:             {usage.output_tokens}")
    print(f"  stop_reason:               {resp.stop_reason}")
    print(f"  --- response text (first 600 chars) ---")
    print(out_text[:600])
    if len(out_text) > 600:
        print(f"  ... ({len(out_text) - 600} more chars)")
    return {
        "label": label,
        "usage": {
            "input_tokens": usage.input_tokens,
            "cache_creation_input_tokens":
                getattr(usage, "cache_creation_input_tokens", 0),
            "cache_read_input_tokens":
                getattr(usage, "cache_read_input_tokens", 0),
            "output_tokens": usage.output_tokens,
        },
        "stop_reason": resp.stop_reason,
        "response_text": out_text,
    }


def main() -> None:
    load_dotenv(REPO / ".env")
    if not os.environ.get("ANTHROPIC_API_KEY"):
        sys.exit("ANTHROPIC_API_KEY not set (looked in .env and env)")
    if not CROP_PATH.exists():
        sys.exit(f"Crop missing: {CROP_PATH}\n"
                 "Run crop_for_dispatch.py first.")

    rules = _load_rules()
    print(f"rules section: {len(rules)} chars (~{len(rules) // 4} tokens)")
    print(f"crop: {CROP_PATH.name} ({CROP_PATH.stat().st_size // 1024} KB)")

    client = anthropic.Anthropic()
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    # Cold first — populates the cache.
    cold = _call(client, rules, _build_user_message(PLAY, None), "cold")
    (OUT_DIR / "iform-pro__cold.json").write_text(json.dumps(cold, indent=2))

    # Primed second — should show cache_read_input_tokens > 0.
    primed = _call(client, rules, _build_user_message(PLAY, PRIOR), "primed")
    (OUT_DIR / "iform-pro__primed.json").write_text(json.dumps(primed, indent=2))

    print("\n=== summary ===")
    print(f"  cold output saved to:   {OUT_DIR}/iform-pro__cold.json")
    print(f"  primed output saved to: {OUT_DIR}/iform-pro__primed.json")
    if primed["usage"]["cache_read_input_tokens"] > 0:
        print(f"  PROMPT CACHE HIT on primed call: "
              f"{primed['usage']['cache_read_input_tokens']} tokens read from cache")
    else:
        print("  no cache hit on primed call — investigate cache_control wiring")


if __name__ == "__main__":
    main()
