#!/usr/bin/env python3
"""Smoke test: 1 play from each major formation family.

Picks one canonical play from each formation family in the manifest,
dispatches them through the v5 + Lever B + Lever C pipeline, and reports
output token count + concept + routes. Catches issues that might bite
during the full $19 launch.

Run after dedup_crop.py has produced an up-to-date manifest.
"""
from __future__ import annotations
import base64
import json
import os
import re
import sys
import time
from pathlib import Path

import anthropic
from dotenv import load_dotenv

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "tools/playbook-vision-pilot"))
from target_gap_python import compute_target_gap_for_crop  # noqa: E402
from play_concepts import classify as classify_play  # noqa: E402

MANIFEST = REPO / "tools/playbook-vision-pilot/dedup-crops/_canonical_manifest.json"
CROPS = REPO / "tools/playbook-vision-pilot/dedup-crops"
PROMPT = REPO / "tools/playbook-vision-pilot/subagent-prompt.md"
MODEL = "claude-haiku-4-5-20251001"


def _load_rules() -> str:
    text = PROMPT.read_text()
    start = text.index("## SYSTEM PROMPT")
    start = text.index("\n", start) + 1
    end = text.index("## USER MESSAGE template")
    return text[start:end].strip()


def main() -> None:
    load_dotenv(REPO / ".env")
    if not os.environ.get("ANTHROPIC_API_KEY"):
        sys.exit("ANTHROPIC_API_KEY missing")

    manifest = json.loads(MANIFEST.read_text())
    rules = _load_rules()

    # Group by family; pick the first play of each
    by_family: dict[str, str] = {}
    for fname, info in manifest.items():
        f = info["family"]
        if f not in by_family:
            by_family[f] = fname

    print(f"Testing {len(by_family)} families:")
    client = anthropic.Anthropic()
    total_cost = 0
    failures = []
    for family, fname in sorted(by_family.items()):
        info = manifest[fname]
        crop = CROPS / fname
        if not crop.exists():
            print(f"  ❌ {family:<18} MISSING CROP: {fname}")
            failures.append((family, "missing_crop"))
            continue
        py = compute_target_gap_for_crop(crop, info["play_type"])
        concept = classify_play(info["play_name"], info["play_type"])
        play_id = crop.stem
        cl = f"py_concept: {concept['concept']} (family={concept['concept_family']})\n" if concept["concept"] != "unknown" else ""
        bh = ("This is a standard run — OL/TE/WR blocking is IMPLICIT. "
              "Emit `routes` ONLY for non-blocking receivers. For typical "
              "runs the routes object should be EMPTY {}.\n"
              if concept.get("blockers_implicit") else "")
        img_b64 = base64.standard_b64encode(crop.read_bytes()).decode()
        context = (f"play_id: {play_id}\n"
                   f"formation: {info['family']} {info['formation']}\n"
                   f"play_name: {info['play_name']}\n"
                   f"play_type: {info['play_type']}\n"
                   f"py_target_gap: {py.get('target_gap')}\n"
                   f"{cl}\n"
                   "Filename encodes personnel as r#f#t#w#. If py_concept "
                   "matches a template, emit \"routes\":\"std\". "
                   "Skip target_gap. Emit only the JSON object.\n"
                   f"{bh}")
        try:
            t0 = time.time()
            resp = client.messages.create(
                model=MODEL, max_tokens=2048,
                system=[{"type": "text", "text": rules,
                         "cache_control": {"type": "ephemeral"}}],
                messages=[{"role": "user", "content": [
                    {"type": "image",
                     "source": {"type": "base64", "media_type": "image/jpeg",
                                "data": img_b64}},
                    {"type": "text", "text": context}]}],
            )
            dt = time.time() - t0
            u = resp.usage
            out_text = "".join(b.text for b in resp.content if b.type == "text")
            m = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", out_text, re.DOTALL)
            try:
                obj = json.loads(m.group(1) if m else out_text.strip())
                parsed = True
            except Exception:
                obj = None
                parsed = False
            # Cost
            cost = ((u.input_tokens * 1
                     + getattr(u, "cache_creation_input_tokens", 0) * 1.25
                     + getattr(u, "cache_read_input_tokens", 0) * 0.10
                     + u.output_tokens * 5) / 1_000_000)
            total_cost += cost
            status = "✓" if parsed else "✗ JSON-parse-fail"
            concept_out = obj.get("concept", "?") if obj else "?"
            print(f"  {status} {family:<18} {info['formation'][:18]:<18} "
                  f"out_tok={u.output_tokens:<4} concept={concept_out:<22} "
                  f"play={info['play_name'][:30]}")
            if not parsed:
                failures.append((family, "parse_failed"))
        except Exception as exc:
            print(f"  ❌ {family:<18} EXCEPTION: {exc}")
            failures.append((family, f"exception: {exc}"))

    print(f"\nTotal cost: ${total_cost:.4f}")
    if failures:
        print(f"FAILURES ({len(failures)}):")
        for fam, reason in failures:
            print(f"  {fam}: {reason}")
    else:
        print("All families passed.")


if __name__ == "__main__":
    main()
