#!/usr/bin/env python3
"""Generate hand-review.html — a Tier-1 accuracy-verification tool.

Picks a random sample of the 7,300 canonical extractions and renders
each one with its crop image + the extracted fields + a verdict form.
The user marks each play correct / partial / wrong and (if not correct)
which fields are wrong. Autosaves to localStorage; "Save" downloads
hand_review_results.json for accuracy computation.

Sample size 150 → ±~5% margin at 95% confidence on the overall
accuracy rate. Simple random sample (proportional to formation mix),
which is the statistically correct basis for an OVERALL estimate.
"""
from __future__ import annotations
import html
import json
import random
import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
EXTRACTIONS = REPO / "data/games/madden-25-ps3/play-geometry"
CROPS_REL = "./dedup-crops"
CROPS_DIR = REPO / "tools/playbook-vision-pilot/dedup-crops"
OUT = REPO / "tools/playbook-vision-pilot/hand-review.html"
SAMPLE_SIZE = 150
SEED = 20260522


def _parse(raw: str) -> dict | None:
    m = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", raw, re.DOTALL)
    cand = m.group(1) if m else raw.strip()
    try:
        return json.loads(cand)
    except json.JSONDecodeError:
        return None


CSS = """
body { font-family: -apple-system, system-ui, sans-serif; max-width: 1400px;
       margin: 0 auto; padding: 20px; background: #181818; color: #e8e8e8; }
h1 { color: #fff; }
.progress { position: sticky; top: 0; background: #181818; padding: 10px 0;
            border-bottom: 1px solid #3a3a3a; z-index: 10; font-size: 14px; }
.play { background: #242424; border: 1px solid #383838; border-radius: 8px;
        padding: 18px; margin-bottom: 26px; }
.play.reviewed { border-color: #4a7a4a; }
.play h2 { margin: 0 0 4px 0; font-size: 19px; }
.meta { color: #999; font-size: 13px; }
.cols { display: grid; grid-template-columns: 1.3fr 1fr; gap: 18px;
        margin-top: 12px; }
.crop img { width: 100%; border: 1px solid #444; border-radius: 4px; }
.data { background: #1a1a1a; padding: 12px; border-radius: 4px; font-size: 14px; }
.data b { color: #ffd060; }
.data code { background: #333; padding: 1px 5px; border-radius: 3px; }
.routes { margin: 6px 0; padding-left: 14px; }
.routes div { margin: 2px 0; }
.verdict { margin-top: 14px; background: #2b2b2b; padding: 12px;
           border-radius: 4px; }
.verdict h3 { margin: 0 0 8px 0; font-size: 15px; }
.vrow { display: flex; gap: 18px; align-items: center; margin: 6px 0;
        flex-wrap: wrap; }
.vrow label { cursor: pointer; }
input[type=radio], input[type=checkbox] { transform: scale(1.25);
        margin-right: 5px; }
.wrong-fields { margin-top: 8px; padding-left: 4px; display: none; }
.wrong-fields.show { display: block; }
textarea { width: 100%; box-sizing: border-box; background: #1a1a1a;
           color: #e8e8e8; border: 1px solid #444; border-radius: 3px;
           padding: 7px; min-height: 44px; font-family: inherit; margin-top: 6px; }
.save-bar { position: sticky; bottom: 0; background: #181818;
            border-top: 2px solid #444; padding: 14px; text-align: center;
            margin-top: 20px; }
button { background: #4a8a4a; color: #fff; border: 0; padding: 12px 32px;
         font-size: 16px; border-radius: 4px; cursor: pointer; }
.tag { display: inline-block; padding: 1px 7px; border-radius: 3px;
       font-size: 12px; margin-left: 6px; }
.tag.run { background: #6a4a2a; }
.tag.pass { background: #2a4a6a; }
details summary { cursor: pointer; color: #888; font-size: 12px; margin-top: 6px; }
details pre { background: #111; padding: 8px; font-size: 11px; max-height: 240px;
              overflow: auto; }
"""

JS = """
function toggleWrong(slug) {
  const play = document.querySelector('.play[data-slug="'+slug+'"]');
  const v = play.querySelector('input[name="verdict_'+slug+'"]:checked');
  const wf = play.querySelector('.wrong-fields');
  wf.classList.toggle('show', v && v.value !== 'correct');
  play.classList.toggle('reviewed', !!v);
  updateProgress();
}
function updateProgress() {
  const total = document.querySelectorAll('.play').length;
  let done = 0;
  document.querySelectorAll('.play').forEach(p => {
    if (p.querySelector('input[type=radio]:checked')) done++;
  });
  document.getElementById('prog').textContent =
    done + ' / ' + total + ' reviewed';
}
function save() {
  const plays = [];
  document.querySelectorAll('.play').forEach(p => {
    const slug = p.dataset.slug;
    const v = p.querySelector('input[name="verdict_'+slug+'"]:checked');
    const wrong = [];
    p.querySelectorAll('input[type=checkbox][data-field]:checked').forEach(
      cb => wrong.push(cb.dataset.field));
    const notes = (p.querySelector('textarea')||{}).value || '';
    plays.push({ slug: slug,
                 verdict: v ? v.value : 'unreviewed',
                 wrong_fields: wrong,
                 notes: notes });
  });
  const payload = { saved_at: new Date().toISOString(),
                    sample_size: plays.length, plays: plays };
  const blob = new Blob([JSON.stringify(payload, null, 2)],
                        {type:'application/json'});
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = 'hand_review_results.json';
  a.click();
  alert('Saved hand_review_results.json — send it back to Claude.');
}
function autosave() {
  const st = {};
  document.querySelectorAll('input, textarea').forEach(el => {
    const slug = el.closest('.play').dataset.slug;
    const key = slug + '|' + (el.name || el.dataset.field || 'notes');
    st[key] = el.type === 'checkbox' || el.type === 'radio'
      ? (el.checked ? (el.value||'1') : '') : el.value;
  });
  localStorage.setItem('m25_hand_review', JSON.stringify(st));
}
function load() {
  const raw = localStorage.getItem('m25_hand_review');
  if (!raw) return;
  const st = JSON.parse(raw);
  document.querySelectorAll('input, textarea').forEach(el => {
    const slug = el.closest('.play').dataset.slug;
    const key = slug + '|' + (el.name || el.dataset.field || 'notes');
    if (!(key in st) || st[key] === '') return;
    if (el.type === 'radio' || el.type === 'checkbox') {
      if ((el.value||'1') === st[key]) el.checked = true;
    } else { el.value = st[key]; }
  });
  document.querySelectorAll('.play').forEach(p => toggleWrong(p.dataset.slug));
}
document.addEventListener('DOMContentLoaded', () => {
  load();
  document.querySelectorAll('input, textarea').forEach(el => {
    el.addEventListener('change', autosave);
    el.addEventListener('input', autosave);
  });
  updateProgress();
});
"""


def _routes_html(routes) -> str:
    if routes == "std":
        return '<code>std</code> (matched the concept route-template)'
    if isinstance(routes, dict):
        if not routes:
            return '<code>{}</code> (empty — run blockers implicit)'
        return ('<div class="routes">'
                + "".join(f"<div><b>{html.escape(k)}</b>: {html.escape(str(v))}</div>"
                          for k, v in routes.items())
                + '</div>')
    return f'<code>{html.escape(str(routes))}</code>'


def main() -> None:
    files = sorted(f for f in EXTRACTIONS.glob("*.json")
                   if not f.name.startswith("_"))
    rng = random.Random(SEED)
    sample = rng.sample(files, min(SAMPLE_SIZE, len(files)))

    blocks = []
    for i, f in enumerate(sample, 1):
        d = json.loads(f.read_text())
        info = d.get("info", {})
        slug = d.get("slug", f.stem)
        obj = _parse(d.get("response_text", ""))
        if obj is None:
            continue
        crop_file = f"{slug}.jpg"
        crop_src = f"{CROPS_REL}/{crop_file}"
        play_type = info.get("play_type", "?")
        py_concept = d.get("py_concept", {}).get("concept", "?")
        py_gap = d.get("py_hints", {}).get("target_gap")

        # Per-play fields
        bc = obj.get("ball_carrier")
        pt = obj.get("primary_target")
        concept = obj.get("concept")
        concepts = obj.get("concepts", [])
        data_rows = [
            f"<div><b>concept (LLM):</b> {html.escape(str(concept))}"
            f" &nbsp;|&nbsp; <b>py_concept:</b> {html.escape(str(py_concept))}</div>",
        ]
        if concepts and concepts != [concept]:
            data_rows.append(f"<div><b>concepts[]:</b> {html.escape(str(concepts))}</div>")
        data_rows.append(f"<div><b>routes:</b> {_routes_html(obj.get('routes'))}</div>")
        if play_type == "run":
            data_rows.append(f"<div><b>ball_carrier:</b> <code>{html.escape(str(bc))}</code>"
                             f" &nbsp;(Python gap: <code>{html.escape(str(py_gap))}</code>)</div>")
        else:
            data_rows.append(f"<div><b>primary_target:</b> <code>{html.escape(str(pt))}</code></div>")
        notes_field = obj.get("notes", "")
        if notes_field:
            data_rows.append(f"<div><b>notes:</b> {html.escape(str(notes_field))}</div>")

        # Which fields the user can mark wrong, by play type
        wrong_checks = ['<label><input type="checkbox" data-field="concept">concept</label>',
                        '<label><input type="checkbox" data-field="routes">routes</label>']
        if play_type == "run":
            wrong_checks.append('<label><input type="checkbox" data-field="ball_carrier">ball_carrier/gap</label>')
        else:
            wrong_checks.append('<label><input type="checkbox" data-field="primary_target">primary_target</label>')
        wrong_checks.append('<label><input type="checkbox" data-field="players">player count/roles</label>')

        raw_json = html.escape(json.dumps(obj, indent=2))
        block = f'''
<div class="play" data-slug="{html.escape(slug)}">
  <h2>{i}. {html.escape(info.get("play_name","?"))}
    <span class="tag {play_type}">{play_type}</span></h2>
  <div class="meta">{html.escape(info.get("family","?"))} {html.escape(info.get("formation","?"))}
    &nbsp;·&nbsp; canonical from {html.escape(info.get("canonical_team","?"))}
    &nbsp;·&nbsp; applies to {info.get("owner_count","?")} playbooks</div>
  <div class="cols">
    <div class="crop"><img src="{html.escape(crop_src)}" loading="lazy"></div>
    <div>
      <div class="data">{"".join(data_rows)}
        <details><summary>raw extraction JSON</summary><pre>{raw_json}</pre></details>
      </div>
      <div class="verdict">
        <h3>Is this extraction correct?</h3>
        <div class="vrow">
          <label><input type="radio" name="verdict_{slug}" value="correct"
            onchange="toggleWrong('{slug}')">Correct</label>
          <label><input type="radio" name="verdict_{slug}" value="partial"
            onchange="toggleWrong('{slug}')">Minor issues</label>
          <label><input type="radio" name="verdict_{slug}" value="wrong"
            onchange="toggleWrong('{slug}')">Wrong</label>
        </div>
        <div class="wrong-fields">
          <div style="font-size:13px;color:#999;">What's wrong?</div>
          <div class="vrow">{"".join(wrong_checks)}</div>
          <textarea placeholder="notes (optional)"></textarea>
        </div>
      </div>
    </div>
  </div>
</div>'''
        blocks.append(block)

    full = f'''<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>M25 Extraction — Hand Review</title>
<style>{CSS}</style></head><body>
<h1>M25 Extraction — Hand Review ({len(blocks)}-play sample)</h1>
<div class="progress"><span id="prog">0 / {len(blocks)} reviewed</span>
  &nbsp;—&nbsp; mark each play, then Save at the bottom. Autosaves as you go.</div>
<p style="font-size:14px;color:#999;">For each play: compare the crop against
the extracted data. Mark <b>Correct</b>, <b>Minor issues</b>, or <b>Wrong</b>.
If not correct, check which field(s) are off. The crop has a cyan LOS line and
a yellow box on the C-square as reference overlays — those are not part of the
play.</p>
{"".join(blocks)}
<div class="save-bar"><button onclick="save()">Save → hand_review_results.json</button></div>
<script>{JS}</script>
</body></html>'''
    OUT.write_text(full)
    print(f"wrote {OUT}")
    print(f"  {len(blocks)} plays in the sample (seed={SEED})")
    # Composition
    from collections import Counter
    types = Counter(json.loads(f.read_text()).get("info", {}).get("play_type")
                    for f in sample)
    print(f"  composition: {dict(types)}")


if __name__ == "__main__":
    main()
