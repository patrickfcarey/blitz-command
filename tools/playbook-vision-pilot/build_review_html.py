#!/usr/bin/env python3
"""Generate a self-contained HTML review tool for hand-labeling 12 stratified plays.

The HTML loads each crop (relative path) alongside the model's bulleted
extraction, with form fields for the user to mark corrections. A "Save
corrections" button bundles all the form state into a downloadable JSON.

Output: tools/playbook-vision-pilot/review.html
"""
from __future__ import annotations
import html
import json
import random
import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SAMPLE_PATH = Path("/tmp/pilot-work/pilot-sample.json")
MANIFEST_PATH = REPO / "tools/playbook-vision-pilot/dispatch-crops/_manifest.json"
EXTRACTIONS_DIR = Path("/tmp/pilot-work/extractions")
CROPS_DIR_REL = "./dispatch-crops"
OUT = REPO / "tools/playbook-vision-pilot/review.html"
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


CSS = """
  body { font-family: -apple-system, system-ui, sans-serif; max-width: 1200px;
         margin: 0 auto; padding: 20px; background: #1a1a1a; color: #e8e8e8; }
  h1, h2 { color: #fff; }
  .play { background: #252525; border: 1px solid #3a3a3a;
          border-radius: 8px; padding: 20px; margin-bottom: 30px; }
  .play h2 { margin-top: 0; border-bottom: 1px solid #3a3a3a; padding-bottom: 8px; }
  .crop-and-data { display: grid; grid-template-columns: 1fr 1fr; gap: 20px;
                   margin-top: 12px; }
  .crop img { width: 100%; border: 1px solid #444; border-radius: 4px;
              display: block; }
  .model-read { background: #1a1a1a; padding: 12px; border-radius: 4px;
                font-size: 14px; }
  .model-read b { color: #ffd060; }
  .model-read code { background: #333; padding: 2px 5px; border-radius: 3px;
                     font-size: 13px; }
  .truth { margin-top: 16px; background: #2a2a2a; padding: 14px;
           border-radius: 4px; }
  .truth h3 { margin: 0 0 12px 0; font-size: 16px; }
  .check-row { display: flex; align-items: center; gap: 8px; margin: 6px 0;
               flex-wrap: wrap; }
  .check-row label { min-width: 220px; }
  .check-row input[type=text] { background: #1a1a1a; color: #e8e8e8;
                                border: 1px solid #444; padding: 4px 8px;
                                border-radius: 3px; width: 180px; }
  .check-row input[type=checkbox] { transform: scale(1.2); }
  textarea { width: 100%; box-sizing: border-box; background: #1a1a1a;
             color: #e8e8e8; border: 1px solid #444; border-radius: 3px;
             padding: 8px; font-family: inherit; min-height: 50px; }
  .meta { color: #999; font-size: 13px; margin: 4px 0; }
  .stratum-tag { display: inline-block; background: #4a3a8a; color: #fff;
                 padding: 2px 8px; border-radius: 3px; font-size: 12px;
                 margin-left: 8px; }
  .save-bar { position: sticky; bottom: 0; background: #1a1a1a;
              padding: 16px; border-top: 2px solid #444;
              text-align: center; margin-top: 30px; }
  button { background: #4a8a4a; color: white; border: 0;
           padding: 12px 30px; font-size: 16px; border-radius: 4px;
           cursor: pointer; }
  button:hover { background: #5aa05a; }
  #copyArea { position: absolute; left: -9999px; }
  details { margin-top: 8px; }
  details summary { cursor: pointer; color: #999; font-size: 13px; }
  details pre { background: #111; padding: 8px; border-radius: 3px;
                font-size: 11px; max-height: 200px; overflow: auto; }
"""

JS = """
function collectAndSave() {
  const plays = [];
  document.querySelectorAll('.play').forEach(playEl => {
    const playId = playEl.dataset.playId;
    const checks = {};
    playEl.querySelectorAll('input[type=checkbox][data-check]').forEach(cb => {
      checks[cb.dataset.check] = cb.checked;
    });
    const corrections = {};
    playEl.querySelectorAll('input[type=text][data-correction]').forEach(t => {
      const v = t.value.trim();
      if (v) corrections[t.dataset.correction] = v;
    });
    const notes = (playEl.querySelector('textarea[data-notes]') || {}).value || '';
    plays.push({ play_id: playId, checks, corrections, notes });
  });
  const payload = {
    saved_at: new Date().toISOString(),
    plays
  };
  const blob = new Blob([JSON.stringify(payload, null, 2)], {type: 'application/json'});
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = 'review_truth.json';
  a.click();
  URL.revokeObjectURL(url);
  alert('Saved as review_truth.json. Send it back to Claude when ready.');
}

// Auto-save to localStorage on any change so user doesn't lose progress
function autosave() {
  const state = {};
  document.querySelectorAll('input, textarea').forEach(el => {
    const key = el.dataset.playId + '|' + (el.dataset.check || el.dataset.correction || (el.dataset.notes ? 'notes' : ''));
    state[key] = el.type === 'checkbox' ? el.checked : el.value;
  });
  localStorage.setItem('m25_review_state', JSON.stringify(state));
}

function loadAutosave() {
  const raw = localStorage.getItem('m25_review_state');
  if (!raw) return;
  try {
    const state = JSON.parse(raw);
    document.querySelectorAll('input, textarea').forEach(el => {
      const key = el.dataset.playId + '|' + (el.dataset.check || el.dataset.correction || (el.dataset.notes ? 'notes' : ''));
      if (key in state) {
        if (el.type === 'checkbox') el.checked = state[key];
        else el.value = state[key];
      }
    });
  } catch(e) {}
}

document.addEventListener('DOMContentLoaded', () => {
  loadAutosave();
  document.querySelectorAll('input, textarea').forEach(el => {
    el.addEventListener('change', autosave);
    el.addEventListener('input', autosave);
  });
});
"""


def _summarize(extracted: dict) -> str:
    ol = extracted.get("offensive_line", [])
    te = extracted.get("tight_ends", [])
    wr = extracted.get("wide_receivers", [])
    bf = extracted.get("backfield", [])
    bf_positions = ', '.join(p.get('position', '?') for p in bf)
    ol_offset = extracted.get("ol_offset_from_c")
    bc = extracted.get("ball_carrier_or_primary") or {}
    rows = [
        ("play_type", extracted.get("play_type_observed")),
        ("concept", extracted.get("play_concept_observed") or extracted.get("concept")),
        ("OL count (excl C)", f"{len(ol)}"),
        ("ol_offset_from_c", f"<code>{html.escape(str(ol_offset))}</code>"),
        ("TE count", str(len(te))),
        ("WR count", str(len(wr))),
        ("Backfield", f"{len(bf)} ({html.escape(bf_positions)})"),
        ("target_gap", f"<code>{html.escape(str(bc.get('target_gap')))}</code>"),
        ("ball-carrier path", html.escape((bc.get("description") or "")[:140])),
        ("confidence", str(extracted.get("confidence"))),
    ]
    return "\n".join(f"<div><b>{k}:</b> {v}</div>" for k, v in rows)


def main() -> None:
    sample = json.loads(SAMPLE_PATH.read_text())
    manifest = json.loads(MANIFEST_PATH.read_text())
    picked = _pick_stratified(sample, n_per_stratum=3)

    play_blocks = []
    for i, play in enumerate(picked, 1):
        play_id = play["id"]
        info = manifest.get(play_id, {})
        crop_filename = info.get("filename", "MISSING.jpg")
        crop_src = f"{CROPS_DIR_REL}/{crop_filename}"
        ext_path = EXTRACTIONS_DIR / f"{play_id}__cold.json"
        if not ext_path.exists():
            continue
        ext_data = json.loads(ext_path.read_text())
        extracted = _parse_response_json(ext_data.get("response_text", ""))
        if not extracted:
            continue

        summary_html = _summarize(extracted)
        raw_json = html.escape(json.dumps(extracted, indent=2))

        checks = [
            ("play_type", "play_type correct"),
            ("ol_count", "OL count = 4 (excl C)"),
            ("te_count", "TE count correct"),
            ("wr_count", "WR count correct"),
            ("backfield", "Backfield correct"),
            ("ol_offset", "ol_offset_from_c correct"),
            ("target_gap", "target_gap correct (runs)"),
            ("concept", "Play concept reasonable"),
        ]
        check_html = ""
        for key, label in checks:
            check_html += f'''<div class="check-row">
  <input type="checkbox" data-check="{key}" data-play-id="{html.escape(play_id)}" id="{play_id}_{key}">
  <label for="{play_id}_{key}">{html.escape(label)}</label>
  <input type="text" data-correction="{key}_actual" data-play-id="{html.escape(play_id)}" placeholder="if wrong, write correct value">
</div>'''

        block = f'''
<div class="play" data-play-id="{html.escape(play_id)}">
  <h2>Play {i}: {html.escape(play["play_name"])} — {html.escape(play["team"])}
    <span class="stratum-tag">{html.escape(play["stratum"])}</span></h2>
  <div class="meta">Formation: {html.escape(info.get("formation", "?"))}</div>
  <div class="meta">play_id: <code>{html.escape(play_id)}</code></div>
  <div class="meta">Crop: <code>{html.escape(crop_filename)}</code></div>

  <div class="crop-and-data">
    <div class="crop"><img src="{html.escape(crop_src)}" alt="play crop"></div>
    <div class="model-read">{summary_html}
      <details><summary>full raw JSON</summary><pre>{raw_json}</pre></details>
    </div>
  </div>

  <div class="truth">
    <h3>TRUTH (check what's right, fill correction if wrong)</h3>
    {check_html}
    <div style="margin-top: 12px;">
      <label><b>Notes:</b></label>
      <textarea data-notes="1" data-play-id="{html.escape(play_id)}" placeholder="anything else worth flagging — counts that disagree, glyphs the model missed, ambiguous formations"></textarea>
    </div>
  </div>
</div>'''
        play_blocks.append(block)

    full_html = f'''<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<title>M25 vision pilot — hand review</title>
<style>{CSS}</style>
</head>
<body>
<h1>Hand-labeling review — vision pilot ({len(play_blocks)} plays)</h1>
<p>For each play: look at the crop, compare the model's bulleted read on the right.
Check the boxes for things the model got right. Leave a box unchecked AND
fill in the text field next to it when wrong. Use the notes blank for anything
else. Your edits autosave to the browser; click <b>Save</b> at the bottom to
download the truth JSON.</p>

{''.join(play_blocks)}

<div class="save-bar">
  <button onclick="collectAndSave()">Save corrections → review_truth.json</button>
</div>

<script>{JS}</script>
</body>
</html>'''
    OUT.write_text(full_html)
    print(f"wrote {OUT}")
    print(f"  {len(play_blocks)} plays")


if __name__ == "__main__":
    main()
