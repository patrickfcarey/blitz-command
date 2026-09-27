#!/usr/bin/env python3
"""Build template-review.html for hand-validating the 10 route templates.

For each templated concept, find 2 canonical crops of that concept (across
different formations) and display them alongside the template's expected
routes. User reviews and marks each template as confirmed or corrected.
"""
from __future__ import annotations
import html
import json
import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
MANIFEST = REPO / "tools/playbook-vision-pilot/dedup-crops/_canonical_manifest.json"
CROPS_REL = "./dedup-crops"
OUT = REPO / "tools/playbook-vision-pilot/template-review.html"


# The 10 templates with structured expected routes per role.
TEMPLATES = {
    "four_verticals": {
        "summary": "All eligible receivers run streaks; HB checks/releases.",
        "routes": {
            "WR_X": "streak", "WR_Z": "streak",
            "WR_SLOT_L": "seam", "WR_SLOT_R": "seam",
            "TE_L": "seam", "TE_R": "seam",
            "HB": "check_release",
        },
        "search_terms": ["four verticals", "4 verts", "verticals"],
    },
    "mesh": {
        "summary": "Two inner receivers run shallow crosses meeting in the middle. "
                   "Outer WRs run corners or comebacks. HB swing/checkdown.",
        "routes": {
            "TE_L": "drag_l_to_r", "TE_R": "drag_r_to_l",
            "WR_SLOT_L": "drag_l_to_r", "WR_SLOT_R": "drag_r_to_l",
            "WR_X": "corner", "WR_Z": "corner",
            "HB": "swing",
        },
        "search_terms": ["mesh"],
    },
    "smash": {
        "summary": "Outer WR runs hitch (~5 yds), inner receiver (slot or TE) "
                   "runs corner over the hitch (high-low concept). Other side: "
                   "in-breaker or comeback. HB checkdown.",
        "routes": {
            "WR_X": "corner",
            "WR_Z": "hitch",
            "WR_SLOT_L": "corner",
            "WR_SLOT_R": "hitch",
            "TE_R": "hitch",
            "HB": "check_release",
        },
        "search_terms": ["smash"],
    },
    "stick": {
        "summary": "Slot/inner runs a stick (sit/hook at 5-6 yds). Outer WR "
                   "runs flat or fade. Opposite side runs slant or in. HB checkdown.",
        "routes": {
            "WR_SLOT_R": "stick", "WR_SLOT_L": "stick",
            "TE_R": "stick",
            "WR_Z": "flat", "WR_X": "slant",
            "HB": "check_release",
        },
        "search_terms": ["stick"],
    },
    "quick_slants": {
        "summary": "All WRs run 3-step slants. TEs/HB block or checkdown.",
        "routes": {
            "WR_X": "slant", "WR_Z": "slant",
            "WR_SLOT_L": "slant", "WR_SLOT_R": "slant",
            "TE_L": "block", "TE_R": "block",
            "HB": "check_release",
        },
        "search_terms": ["quick slants", "quick slant"],
    },
    "curl_flat": {
        "summary": "Outside WR runs curl (~12 yds). Slot/inner runs flat under "
                   "the curl. Opposite side runs comeback or curl. HB checkdown.",
        "routes": {
            "WR_X": "curl", "WR_Z": "curl",
            "WR_SLOT_R": "flat", "WR_SLOT_L": "flat",
            "TE_R": "flat", "HB": "check_release",
        },
        "search_terms": ["curl flat", "curl flats", "curls"],
    },
    "flood": {
        "summary": "Three routes to one side at different depths (deep + "
                   "intermediate + flat). Backside WR runs crosser or comeback.",
        "routes": {
            "WR_Z": "streak",
            "WR_SLOT_R": "out",
            "HB": "flat",
            "WR_X": "crosser",
        },
        "search_terms": ["flood", "sail"],
    },
    "levels": {
        "summary": "Two receivers run in-breakers at different depths (shallow "
                   "+ deep dig). Other receivers run vertical clearouts.",
        "routes": {
            "WR_X": "shallow_in",
            "WR_SLOT_L": "dig",
            "WR_Z": "streak", "WR_SLOT_R": "streak",
            "TE_R": "block", "HB": "check_release",
        },
        "search_terms": ["levels", "level"],
    },
    "drags": {
        "summary": "One or more inner receivers run drag routes across the "
                   "field (~5 yds). Outer WRs run vertical/corner clearouts.",
        "routes": {
            "WR_SLOT_L": "drag", "WR_SLOT_R": "drag",
            "TE_L": "drag", "TE_R": "drag",
            "WR_X": "streak", "WR_Z": "streak",
            "HB": "swing",
        },
        "search_terms": ["drag", "drags", "shallow drag"],
    },
    "all_streaks": {
        "summary": "Same as four_verticals — every eligible receiver runs a streak.",
        "routes": {
            "WR_X": "streak", "WR_Z": "streak",
            "WR_SLOT_L": "streak", "WR_SLOT_R": "streak",
            "TE_L": "streak", "TE_R": "streak",
            "HB": "check_release",
        },
        "search_terms": ["all go", "all streaks", "go routes"],
    },
}


def find_canonical_crops(manifest: dict, search_terms: list[str], n: int = 2) -> list[dict]:
    """Find up to N crops whose play_name contains any of the search_terms."""
    hits = []
    seen_formations = set()
    for fname, info in manifest.items():
        pn = (info.get("play_name") or "").lower()
        # Skip team-prefixed and PA-prefixed variants — find vanilla concepts
        if any(pn.startswith(prefix) for prefix in
               ("pa ", "ravens", "cowboys", "bears", "colts", "patriots",
                "panthers", "giants", "saints", "vikings", "broncos",
                "eagles", "packers", "jets", "raiders", "bills", "browns",
                "lions", "chiefs", "chargers", "49ers", "niners", "rams",
                "buccaneers", "titans", "redskins", "ravens ", "chief")):
            continue
        if any(term in pn for term in search_terms):
            # Prefer diverse formations
            if info.get("formation") not in seen_formations:
                hits.append({"filename": fname, **info})
                seen_formations.add(info.get("formation"))
            if len(hits) >= n:
                break
    return hits


CSS = """
body { font-family: -apple-system, system-ui, sans-serif; max-width: 1400px;
       margin: 0 auto; padding: 20px; background: #1a1a1a; color: #e8e8e8; }
h1, h2, h3 { color: #fff; }
.template { background: #252525; border: 1px solid #3a3a3a;
            border-radius: 8px; padding: 20px; margin-bottom: 30px; }
.template-header { display: flex; align-items: center; gap: 12px; }
.template-name { font-size: 22px; font-weight: bold; color: #ffd060; }
.summary { font-style: italic; color: #aaa; margin: 10px 0; }
.routes-table { width: 100%; border-collapse: collapse; margin: 10px 0; }
.routes-table td, .routes-table th { padding: 6px 10px; border-bottom: 1px solid #333; }
.routes-table th { text-align: left; color: #999; }
.routes-table .role { color: #ffd060; font-family: monospace; }
.crops { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; margin-top: 12px; }
.crop img { width: 100%; border: 1px solid #444; border-radius: 4px; display: block; }
.crop .label { color: #888; font-size: 13px; margin-top: 4px; }
.review-controls { background: #2a2a2a; padding: 12px; border-radius: 4px;
                   margin-top: 12px; }
textarea { width: 100%; box-sizing: border-box; background: #1a1a1a;
           color: #e8e8e8; border: 1px solid #444; border-radius: 3px;
           padding: 8px; min-height: 60px; font-family: inherit; }
input[type=radio] { transform: scale(1.2); margin-right: 6px; }
.option-row { display: flex; align-items: center; gap: 12px; margin: 6px 0; }
.save-bar { position: sticky; bottom: 0; background: #1a1a1a; padding: 16px;
            border-top: 2px solid #444; text-align: center; margin-top: 30px; }
button { background: #4a8a4a; color: white; border: 0; padding: 12px 30px;
         font-size: 16px; border-radius: 4px; cursor: pointer; }
"""

JS = """
function saveReview() {
  const out = {saved_at: new Date().toISOString(), templates: {}};
  document.querySelectorAll('.template').forEach(t => {
    const name = t.dataset.template;
    const status = t.querySelector('input[name="status_'+name+'"]:checked');
    const corrections = t.querySelector('textarea[data-corrections]').value;
    out.templates[name] = {
      verdict: status ? status.value : 'unreviewed',
      corrections: corrections
    };
  });
  const blob = new Blob([JSON.stringify(out, null, 2)], {type: 'application/json'});
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = 'template_review.json';
  a.click();
  alert('Saved. Send template_review.json back to Claude.');
}
function autosave() {
  const state = {};
  document.querySelectorAll('input, textarea').forEach(el => {
    state[el.name || el.dataset.corrections + '|' + el.closest('.template').dataset.template] =
      el.type === 'radio' ? (el.checked ? el.value : null) : el.value;
  });
  localStorage.setItem('m25_template_review', JSON.stringify(state));
}
function loadAutosave() {
  const raw = localStorage.getItem('m25_template_review');
  if (!raw) return;
  const state = JSON.parse(raw);
  document.querySelectorAll('input, textarea').forEach(el => {
    const key = el.name || el.dataset.corrections + '|' + el.closest('.template').dataset.template;
    if (key in state && state[key] !== null) {
      if (el.type === 'radio') {
        if (el.value === state[key]) el.checked = true;
      } else {
        el.value = state[key];
      }
    }
  });
}
document.addEventListener('DOMContentLoaded', () => {
  loadAutosave();
  document.querySelectorAll('input, textarea').forEach(el => {
    el.addEventListener('change', autosave);
    el.addEventListener('input', autosave);
  });
});
"""


def main() -> None:
    manifest = json.loads(MANIFEST.read_text())
    blocks = []
    for name, template in TEMPLATES.items():
        crops = find_canonical_crops(manifest, template["search_terms"], n=2)
        crops_html = ""
        for crop in crops:
            src = f"{CROPS_REL}/{crop['filename']}"
            label = f"{crop.get('family','?')} {crop.get('formation','?')} — {crop.get('play_name','?')}"
            crops_html += f'''<div class="crop"><img src="{html.escape(src)}"><div class="label">{html.escape(label)}</div></div>'''
        if not crops_html:
            crops_html = "<div>No canonical crops found for this concept.</div>"
        routes_rows = ""
        for role, route in template["routes"].items():
            routes_rows += f'<tr><td class="role">{role}</td><td>{html.escape(route)}</td></tr>'

        block = f'''
<div class="template" data-template="{name}">
  <div class="template-header">
    <span class="template-name">{name}</span>
  </div>
  <div class="summary">{html.escape(template["summary"])}</div>

  <h3>Expected routes per role</h3>
  <table class="routes-table">
    <thead><tr><th>Role</th><th>Route</th></tr></thead>
    <tbody>{routes_rows}</tbody>
  </table>

  <h3>Sample crops (compare against the routes above)</h3>
  <div class="crops">{crops_html}</div>

  <div class="review-controls">
    <h3>Your verdict</h3>
    <div class="option-row">
      <input type="radio" name="status_{name}" id="ok_{name}" value="confirmed">
      <label for="ok_{name}">Template is correct as-is</label>
    </div>
    <div class="option-row">
      <input type="radio" name="status_{name}" id="fix_{name}" value="needs_fix">
      <label for="fix_{name}">Template needs corrections (describe below)</label>
    </div>
    <div class="option-row">
      <input type="radio" name="status_{name}" id="drop_{name}" value="drop">
      <label for="drop_{name}">Drop this template entirely (too variable)</label>
    </div>
    <label><b>Corrections / notes:</b></label>
    <textarea data-corrections="1" placeholder="e.g. 'WR_X should be post, not corner' or 'this concept varies too much by formation to template'"></textarea>
  </div>
</div>'''
        blocks.append(block)

    full = f'''<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><title>Route Template Review</title>
<style>{CSS}</style></head>
<body>
<h1>Route Template Review ({len(TEMPLATES)} templates)</h1>
<p>For each template: look at the sample crops, verify the expected routes
match what's in the diagram. Mark <b>confirmed</b> if good, <b>needs_fix</b>
with notes if a route is wrong, or <b>drop</b> if the concept is too
variable to template.</p>
{''.join(blocks)}
<div class="save-bar">
  <button onclick="saveReview()">Save → template_review.json</button>
</div>
<script>{JS}</script>
</body>
</html>'''
    OUT.write_text(full)
    print(f"wrote {OUT}")
    print(f"  {len(TEMPLATES)} templates with sample crops")


if __name__ == "__main__":
    main()
