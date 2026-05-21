#!/usr/bin/env python3
"""Generate a markdown review file for hand-labeling 12 stratified plays.

Picks 3 plays from each stratum (run_clean, run_generic, pass_named, pass_generic)
from the 50-play pilot. For each, embeds:

- The crop image (relative path so it renders in markdown viewers).
- The model's cold-arm extraction as readable JSON.
- A TRUTH section with checkboxes and a notes blank.

Output:
    tools/playbook-vision-pilot/review.md
"""
from __future__ import annotations
import json
import random
import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SAMPLE_PATH = Path("/tmp/pilot-work/pilot-sample.json")
MANIFEST_PATH = REPO / "tools/playbook-vision-pilot/dispatch-crops/_manifest.json"
EXTRACTIONS_DIR = Path("/tmp/pilot-work/extractions")
CROPS_DIR_REL = "./dispatch-crops"   # relative from review.md
OUT = REPO / "tools/playbook-vision-pilot/review.md"
SEED = 20260521


def _parse_response_json(raw: str) -> dict | None:
    m = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", raw, re.DOTALL)
    candidate = m.group(1) if m else raw.strip()
    try:
        return json.loads(candidate)
    except json.JSONDecodeError:
        return None


def _pick_stratified(sample: list[dict], n_per_stratum: int = 3) -> list[dict]:
    by_stratum: dict[str, list[dict]] = {}
    for p in sample:
        by_stratum.setdefault(p["stratum"], []).append(p)
    rng = random.Random(SEED)
    picked = []
    for stratum in sorted(by_stratum.keys()):
        items = by_stratum[stratum][:]
        rng.shuffle(items)
        picked.extend(items[:n_per_stratum])
    return picked


def _summarize_extraction(extracted: dict) -> str:
    """Short bullet summary of the model's read."""
    ol = extracted.get("offensive_line", [])
    te = extracted.get("tight_ends", [])
    wr = extracted.get("wide_receivers", [])
    bf = extracted.get("backfield", [])
    ol_offset = extracted.get("ol_offset_from_c")
    bc = extracted.get("ball_carrier_or_primary") or {}
    play_type = extracted.get("play_type_observed")
    concept = extracted.get("play_concept_observed") or extracted.get("concept")
    target_gap = bc.get("target_gap")
    bc_desc = bc.get("description", "")[:120]
    confidence = extracted.get("confidence")
    lines = [
        f"- **play_type observed:** {play_type}",
        f"- **concept observed:** {concept}",
        f"- **OL count:** {len(ol)} (expected 4 here — C is separate)"
        f" — ol_offset_from_c: `{ol_offset}`",
        f"- **TE count:** {len(te)}",
        f"- **WR count:** {len(wr)}",
        f"- **Backfield count:** {len(bf)}  "
        f"({', '.join(p.get('position', '?') for p in bf)})",
        f"- **target_gap:** `{target_gap}`",
        f"- **ball-carrier path:** {bc_desc}",
        f"- **confidence:** {confidence}",
    ]
    return "\n".join(lines)


def main() -> None:
    sample = json.loads(SAMPLE_PATH.read_text())
    manifest = json.loads(MANIFEST_PATH.read_text())
    picked = _pick_stratified(sample, n_per_stratum=3)

    lines = []
    lines.append("# Hand-labeling review — vision pilot")
    lines.append("")
    lines.append(f"**{len(picked)} plays** (3 per stratum). For each, "
                 "look at the crop, compare against the model's read, and "
                 "fill in the TRUTH section.")
    lines.append("")
    lines.append("**How to mark corrections:**")
    lines.append("- Check the box if the model got that aspect right.")
    lines.append("- Leave unchecked and write a brief note if wrong.")
    lines.append("- Use the **Notes** blank for anything else.")
    lines.append("")
    lines.append("---")
    lines.append("")

    for i, play in enumerate(picked, 1):
        play_id = play["id"]
        info = manifest.get(play_id, {})
        crop = f"{CROPS_DIR_REL}/{info.get('filename', 'MISSING.jpg')}"
        ext_path = EXTRACTIONS_DIR / f"{play_id}__cold.json"
        if not ext_path.exists():
            print(f"  skip — missing {ext_path}")
            continue
        ext = json.loads(ext_path.read_text())
        extracted = _parse_response_json(ext.get("response_text", ""))
        if not extracted:
            print(f"  skip — couldn't parse {ext_path}")
            continue

        lines.append(f"## Play {i}: {play['play_name']} — {play['team']}")
        lines.append(f"*Stratum: {play['stratum']}*")
        lines.append("")
        lines.append(f"**Formation:** {info.get('formation', '?')}")
        lines.append(f"**play_id:** `{play_id}`")
        lines.append(f"**Crop:** `{info.get('filename', '?')}`")
        lines.append("")
        lines.append(f"![]({crop})")
        lines.append("")
        lines.append("### Model's read")
        lines.append("")
        lines.append(_summarize_extraction(extracted))
        lines.append("")
        lines.append("### TRUTH (edit below)")
        lines.append("")
        lines.append("Check each box if the model got it right; leave "
                     "unchecked + note if wrong:")
        lines.append("")
        lines.append("- [ ] play_type correct")
        lines.append("- [ ] OL count = 4 (excluding C)")
        lines.append("- [ ] TE count correct  ← expected count if wrong: __")
        lines.append("- [ ] WR count correct  ← expected count if wrong: __")
        lines.append("- [ ] Backfield correct  ← expected positions if wrong: __")
        lines.append("- [ ] ol_offset_from_c correct (at vs below)")
        lines.append("- [ ] target_gap correct (for runs)  "
                     "← correct gap if wrong: __")
        lines.append("- [ ] Play concept reasonable")
        lines.append("")
        lines.append("**Notes:**")
        lines.append("")
        lines.append("```")
        lines.append("(write here)")
        lines.append("```")
        lines.append("")
        lines.append("---")
        lines.append("")

    OUT.write_text("\n".join(lines))
    print(f"wrote {OUT}")
    print(f"  {len(picked)} plays embedded")


if __name__ == "__main__":
    main()
