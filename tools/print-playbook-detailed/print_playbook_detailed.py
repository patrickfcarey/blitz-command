#!/usr/bin/env python3
"""Generate a detailed teaching PDF — a whole playbook, or an ad-hoc set of plays.

Play pages come in two layouts, chosen with --layout: 'side-by-side' (two
plays per page as tall columns) and 'one-per-page' (one play with a large
diagram). Each play slot has a title bar, the play diagram, and notes.

Notes are pulled from existing fields in the play YAML — no schema additions.
For every play, we surface:
  - Header line (formation, type, philosophy, concept)
  - Aliases (if any)
  - Per-player assignments (role + scheme/target + notes)
  - Reads — run_reads list for runs, primary/secondary/checkdown for passes
  - Strengths / Weaknesses (two columns within notes)
  - Best vs / Worst vs / Common uses
  - Play-level notes (free text)

In --playbook mode the PDF additionally carries the playbook's front matter
(identity / philosophy, how-to-read, cadence, install notes), a compiled
glossary, and the appendix — assembled as: identity -> how-to-read ->
glossary -> plays -> appendix.

Usage:
    # A whole playbook — front matter, glossary, every play, appendix:
    python print_playbook_detailed.py --playbook data/playbooks/hs-base.yaml -o book.pdf

    # An ad-hoc set of plays (no front matter):
    python print_playbook_detailed.py \
        data/plays/i-formation-power-o.yaml \
        data/plays/i-formation-counter-trey.yaml \
        --game madden-05-ps2 --diagram-dir examples/play-diagrams -o detailed.pdf
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, NamedTuple

import yaml
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import inch
from reportlab.pdfgen.canvas import Canvas
from reportlab.platypus import Frame, KeepInFrame, Paragraph, Spacer
from svglib.svglib import svg2rlg
from reportlab.graphics import renderPDF

# The glossary compiler is a shared tool module — add its directory to the
# import path so the printed playbook's Glossary pages use the very same
# logic the playbook-generation MCP exposes as the `playbook_glossary` tool.
REPO_ROOT = Path(__file__).resolve().parents[2]
PLAYS_DIR = REPO_ROOT / "data" / "plays"
DRAW_SCRIPT = REPO_ROOT / "tools" / "draw-play" / "draw.py"
sys.path.insert(0, str(REPO_ROOT / "tools" / "compile-glossary"))
import compile_glossary  # noqa: E402


# ─── Page geometry ────────────────────────────────────────────────────────────

PAGE_W, PAGE_H = letter
MARGIN = 36
CONTENT_W = PAGE_W - 2 * MARGIN

PAGE_TITLE_H = 24
GAP_AFTER_TITLE = 6

# The content area below the page title.
CONTENT_TOP = PAGE_H - MARGIN - PAGE_TITLE_H - GAP_AFTER_TITLE
CONTENT_HEIGHT = CONTENT_TOP - MARGIN

SLOT_HEADER_H = 26      # the play-name bar at the top of a play slot
NOTES_COL_GAP = 12      # gap between the two note columns (one-per-page layout)
COLUMN_GAP = 16         # gap between the two plays in side-by-side layout

# Diagram-box height per layout, tuned so downfield pass routes stay readable.
ONE_PER_PAGE_DIAGRAM_H = 470
SIDE_BY_SIDE_DIAGRAM_H = 400


class _Slot(NamedTuple):
    """The rectangle and per-slot sizing for one play on a page."""
    x: float
    y_top: float
    width: float
    height: float
    diagram_h: float
    notes_columns: int


# ─── Colors ───────────────────────────────────────────────────────────────────

C_PAGE_TITLE = colors.HexColor("#1a1a2e")
C_SLOT_HEADER_BG = colors.HexColor("#2c4d2c")
C_SLOT_HEADER_FG = colors.white
C_TAG_TEXT = colors.HexColor("#444444")
C_SECTION_HEAD = colors.HexColor("#1a4e1a")
C_BODY_TEXT = colors.HexColor("#222222")
C_MUTED = colors.HexColor("#666666")
C_BORDER = colors.HexColor("#cccccc")


# ─── SVG color remap (same approach as print-playbook) ────────────────────────

_PRINT_COLOR_MAP: dict[str, str] = {
    "#1a1a1a": "#ffffff",
    "#1b5e20": "#ffffff",
    "#2e7d32": "#ffffff",
    "#388e3c": "#cccccc",
    "#2e6b34": "#dddddd",
    "#cccccc": "#aaaaaa",
    "#ffffff": "#555555",
    "#cfcfcf": "#aaaaaa",
    "#666":    "#aaaaaa",
    "#666666": "#aaaaaa",
    "#888":    "#aaaaaa",
    "#888888": "#aaaaaa",
}
# Trailing negative lookahead: a short key like "#666" must NOT match the
# prefix of a longer hex color like "#666666" (which would corrupt it to
# "#aaaaaa666"). Longest-first ordering + the lookahead make substitution safe.
_PRINT_COLOR_RE = re.compile(
    "(?:" + "|".join(re.escape(k) for k in sorted(_PRINT_COLOR_MAP, key=len, reverse=True))
    + ")(?![0-9A-Fa-f])"
)
# Markers of the legacy DARK-theme SVG palette (pre-rewrite draw.py). The
# current draw.py emits light, print-ready SVGs — those must NOT be color-
# remapped (remapping would, e.g., turn the white field gray).
_LEGACY_DARK_MARKERS = ("#1a1a1a", "#1b5e20", "#2e7d32")


def _load_svg_print(svg_path: Path):
    """Load an SVG for print. Legacy dark SVGs get their colors remapped to
    print-friendly values; current light SVGs are already print-ready and
    are loaded as-is."""
    with open(svg_path, encoding="utf-8") as f:
        content = f.read()
    if any(marker in content for marker in _LEGACY_DARK_MARKERS):
        content = _PRINT_COLOR_RE.sub(lambda m: _PRINT_COLOR_MAP[m.group(0)], content)
    with tempfile.NamedTemporaryFile(suffix=".svg", mode="w", encoding="utf-8", delete=False) as tf:
        tf.write(content)
        tmp_path = tf.name
    try:
        drawing = svg2rlg(tmp_path)
    finally:
        Path(tmp_path).unlink(missing_ok=True)
    return drawing


# ─── Paragraph styles ─────────────────────────────────────────────────────────

def _styles() -> dict[str, ParagraphStyle]:
    base = ParagraphStyle(
        "base", fontName="Helvetica", fontSize=7.5, leading=9.5,
        textColor=C_BODY_TEXT, spaceAfter=2,
    )
    return {
        "section": ParagraphStyle(
            "section", parent=base, fontName="Helvetica-Bold", fontSize=7.5,
            leading=9.5, textColor=C_SECTION_HEAD, spaceBefore=3, spaceAfter=1,
        ),
        "body": base,
        "bullet": ParagraphStyle(
            "bullet", parent=base, leftIndent=8, bulletIndent=0, firstLineIndent=0,
        ),
        "muted": ParagraphStyle(
            "muted", parent=base, fontSize=7, textColor=C_MUTED,
        ),
    }


# ─── Notes assembly ───────────────────────────────────────────────────────────

def _esc(s: Any) -> str:
    if s is None:
        return ""
    return (
        str(s)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def _header_line(play: dict) -> str:
    parts = []
    if play.get("formation"):
        parts.append(f"<b>Formation:</b> {_esc(play['formation'])}")
    if play.get("play_type"):
        parts.append(f"<b>Type:</b> {_esc(play['play_type'])}")
    phil = play.get("philosophy") or play.get("philosophy_ref")
    if phil:
        parts.append(f"<b>Philosophy:</b> {_esc(phil)}")
    concept = play.get("run_concept_ref") or play.get("pass_concept_ref")
    if concept:
        parts.append(f"<b>Concept:</b> {_esc(concept)}")
    if play.get("ball_carrier"):
        parts.append(f"<b>Ball:</b> {_esc(play['ball_carrier'])}")
    return "  &nbsp;|&nbsp;  ".join(parts)


def _build_assignments(play: dict, styles) -> list:
    out = []
    if not play.get("assignments"):
        return out
    out.append(Paragraph("Assignments", styles["section"]))
    for a in play["assignments"]:
        player = _esc(a.get("player", "?"))
        role = _esc(a.get("role", ""))
        scheme = a.get("blocking_scheme") or ""
        target = a.get("target") or ""
        note = a.get("notes") or ""
        mid_parts = [p for p in [scheme, target] if p]
        mid = f" — {_esc(' / '.join(mid_parts))}" if mid_parts else ""
        primary = f"<b>{player}</b> ({role}){mid}"
        if note:
            primary += f". {_esc(note)}"
        out.append(Paragraph(primary, styles["bullet"]))
    return out


def _build_reads(play: dict, styles) -> list:
    out = []
    if play.get("run_reads"):
        out.append(Paragraph("Reads / Progression", styles["section"]))
        for r in play["run_reads"]:
            pri = _esc(r.get("priority", "?"))
            key = _esc(r.get("read_key", ""))
            to = _esc(r.get("run_to", ""))
            note = _esc(r.get("notes", ""))
            line = f"<b>{pri}.</b> Read <i>{key}</i> — {to}"
            if note:
                line += f" <font color='#666666'>{note}</font>"
            out.append(Paragraph(line, styles["bullet"]))
        return out

    pass_bits = []
    if play.get("primary_read"):
        pass_bits.append(f"<b>1.</b> {_esc(play['primary_read'])}")
    if play.get("secondary_read"):
        pass_bits.append(f"<b>2.</b> {_esc(play['secondary_read'])}")
    if play.get("checkdown"):
        pass_bits.append(f"<b>CD.</b> {_esc(play['checkdown'])}")
    if pass_bits:
        out.append(Paragraph("Progression", styles["section"]))
        out.append(Paragraph("  ".join(pass_bits), styles["body"]))
    return out


def _bullet_list(items, styles) -> list:
    out = []
    for item in items:
        out.append(Paragraph(f"• {_esc(item)}", styles["bullet"]))
    return out


def _build_list_section(title: str, items, styles) -> list:
    if not items:
        return []
    out = [Paragraph(title, styles["section"])]
    out.extend(_bullet_list(items, styles))
    return out


def _build_freeform_notes(play: dict, styles) -> list:
    out = []
    note = play.get("notes")
    if note:
        out.append(Paragraph("Notes", styles["section"]))
        text = _esc(str(note).strip()).replace("\n\n", "<br/><br/>").replace("\n", " ")
        out.append(Paragraph(text, styles["body"]))
    return out


def _left_column_flowables(play: dict, styles) -> list:
    flowables: list = []
    # Header line + aliases at very top
    flowables.append(Paragraph(_header_line(play), styles["body"]))
    if play.get("aliases"):
        alias_text = "<b>aka:</b> " + ", ".join(_esc(a) for a in play["aliases"])
        flowables.append(Paragraph(alias_text, styles["muted"]))
    flowables.append(Spacer(1, 2))
    flowables.extend(_build_assignments(play, styles))
    return flowables


def _right_column_flowables(play: dict, styles) -> list:
    # Coaching keys only — reads/progression + the play's own coaching notes.
    # Strengths/weaknesses/best-vs/worst-vs/common-uses are intentionally NOT
    # shown: they overstuff the half-page notes area and force KeepInFrame to
    # shrink everything to an unreadable size. Keep the teaching page focused.
    flowables: list = []
    flowables.extend(_build_reads(play, styles))
    flowables.extend(_build_freeform_notes(play, styles))
    return flowables


# ─── Drawing primitives ───────────────────────────────────────────────────────

def _draw_page_title(c: Canvas, title: str) -> None:
    c.saveState()
    c.setFillColor(C_PAGE_TITLE)
    c.setFont("Helvetica-Bold", 16)
    c.drawCentredString(PAGE_W / 2, PAGE_H - MARGIN - 16, title)
    c.restoreState()


def _draw_slot_header(c: Canvas, x: float, y_top: float, width: float,
                      play: dict) -> None:
    name = play.get("name", play.get("play_id", "Untitled"))
    pid = play.get("play_id", "")
    name_size = 13 if width >= 380 else 11  # the narrow side-by-side column
    c.saveState()
    c.setFillColor(C_SLOT_HEADER_BG)
    c.rect(x, y_top - SLOT_HEADER_H, width, SLOT_HEADER_H, fill=1, stroke=0)
    c.setFillColor(C_SLOT_HEADER_FG)
    c.setFont("Helvetica-Bold", name_size)
    c.drawString(x + 8, y_top - SLOT_HEADER_H + 8, str(name))
    if pid:
        c.setFont("Helvetica-Oblique", 7)
        c.drawRightString(x + width - 8, y_top - SLOT_HEADER_H + 9, str(pid))
    c.restoreState()


def _draw_diagram(c: Canvas, svg_path: Path | None, x: float, y_bottom: float,
                  w: float, h: float) -> None:
    """Draw a play's SVG diagram into the (x, y_bottom, w, h) box — the WHOLE
    diagram, scaled to fit and centered. The full SVG canvas is used (not just
    the editor-grid rectangle), so downfield routes are never clipped off."""
    c.saveState()
    c.setStrokeColor(C_BORDER)
    c.setLineWidth(0.5)
    c.rect(x, y_bottom, w, h, fill=0, stroke=1)
    c.restoreState()

    if svg_path is None or not svg_path.exists():
        c.saveState()
        c.setFillColor(C_MUTED)
        c.setFont("Helvetica-Oblique", 9)
        msg = f"missing: {svg_path.name}" if svg_path else "no diagram provided"
        c.drawCentredString(x + w / 2, y_bottom + h / 2, msg)
        c.restoreState()
        return

    try:
        drawing = _load_svg_print(svg_path)
        if drawing is None:
            raise ValueError("svg2rlg returned None")
        pad = 4
        scale = min((w - 2 * pad) / drawing.width,
                    (h - 2 * pad) / drawing.height)
        drawn_w = drawing.width * scale
        drawn_h = drawing.height * scale
        origin_x = x + (w - drawn_w) / 2
        origin_y = y_bottom + (h - drawn_h) / 2
        c.saveState()
        c.translate(origin_x, origin_y)
        c.scale(scale, scale)
        renderPDF.draw(drawing, c, 0, 0)
        c.restoreState()
    except Exception as exc:
        c.saveState()
        c.setFillColor(colors.red)
        c.setFont("Helvetica", 7)
        c.drawCentredString(x + w / 2, y_bottom + h / 2, f"[diagram error: {exc}]")
        c.restoreState()


def _draw_notes(c: Canvas, play: dict, x: float, y_bottom: float,
                width: float, height: float, columns: int) -> None:
    """Draw the play's coaching notes into the given box, in 1 or 2 columns.
    KeepInFrame shrinks the content to fit the box."""
    styles = _styles()
    left_flow = _left_column_flowables(play, styles)
    right_flow = _right_column_flowables(play, styles)
    pad = dict(leftPadding=2, rightPadding=2, topPadding=2, bottomPadding=2,
               showBoundary=0)
    if columns == 1:
        flow = left_flow + right_flow
        frame = Frame(x, y_bottom, width, height, **pad)
        frame.addFromList([KeepInFrame(width, height, flow, mode="shrink")], c)
        return
    col_w = (width - NOTES_COL_GAP) / 2
    left = Frame(x, y_bottom, col_w, height, **pad)
    right = Frame(x + col_w + NOTES_COL_GAP, y_bottom, col_w, height, **pad)
    left.addFromList([KeepInFrame(col_w, height, left_flow, mode="shrink")], c)
    right.addFromList([KeepInFrame(col_w, height, right_flow, mode="shrink")], c)


def _draw_play_in_rect(c: Canvas, play: dict, svg_path: Path | None,
                       slot: _Slot) -> None:
    """Draw one fully-explained play into the given slot rectangle."""
    _draw_slot_header(c, slot.x, slot.y_top, slot.width, play)
    diagram_top = slot.y_top - SLOT_HEADER_H
    diagram_bottom = diagram_top - slot.diagram_h
    _draw_diagram(c, svg_path, slot.x, diagram_bottom, slot.width, slot.diagram_h)
    notes_height = slot.height - SLOT_HEADER_H - slot.diagram_h
    notes_bottom = diagram_bottom - notes_height
    _draw_notes(c, play, slot.x, notes_bottom, slot.width, notes_height,
                slot.notes_columns)


def _play_slots(layout: str) -> list[_Slot]:
    """Return the play-slot rectangle(s) for one page in the given layout."""
    if layout == "one-per-page":
        return [_Slot(MARGIN, CONTENT_TOP, CONTENT_W, CONTENT_HEIGHT,
                      ONE_PER_PAGE_DIAGRAM_H, 2)]
    # side-by-side: two equal-width columns, each the full content height
    column_w = (CONTENT_W - COLUMN_GAP) / 2
    return [
        _Slot(MARGIN, CONTENT_TOP, column_w, CONTENT_HEIGHT,
              SIDE_BY_SIDE_DIAGRAM_H, 1),
        _Slot(MARGIN + column_w + COLUMN_GAP, CONTENT_TOP, column_w,
              CONTENT_HEIGHT, SIDE_BY_SIDE_DIAGRAM_H, 1),
    ]


# ─── Play / SVG resolution ────────────────────────────────────────────────────

def _load_yaml(path: Path) -> dict:
    """Parse a YAML file (a play or a playbook) into a dict."""
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def _resolve_svg(play_id: str, game: str, diagram_dir: Path) -> Path | None:
    candidates = [
        diagram_dir / f"{play_id}--{game}.svg",
        diagram_dir / f"{play_id}.svg",
    ]
    for c in candidates:
        if c.exists():
            return c
    return candidates[0]  # return non-existent path for "missing" message


def _ensure_svg(play_id: str, game: str, diagram_dir: Path,
                render_dir: Path) -> tuple[Path | None, str]:
    """Return (svg_path, status) for a play's diagram.

    Uses a pre-rendered SVG from diagram_dir when one exists; otherwise
    renders the play on demand with the draw tool into render_dir, so the PDF
    always has a diagram for every play. status is 'found', 'rendered', or
    'failed' — on 'failed' the path is None and the page shows a placeholder.
    """
    pre_rendered = _resolve_svg(play_id, game, diagram_dir)
    if pre_rendered and pre_rendered.exists():
        return pre_rendered, "found"
    cached = render_dir / f"{play_id}--{game}.svg"
    if cached.exists():
        return cached, "rendered"
    try:
        proc = subprocess.run(
            [sys.executable, str(DRAW_SCRIPT),
             "--play", play_id, "--game", game, "-o", str(cached)],
            capture_output=True, text=True, timeout=90,
        )
    except Exception:  # noqa: BLE001 - a render failure must not abort the PDF
        return None, "failed"
    if proc.returncode == 0 and cached.exists():
        return cached, "rendered"
    return None, "failed"


# ─── Front-matter / glossary / appendix rendering ─────────────────────────────

# Glossary category id -> the heading shown for that group on the glossary pages.
GLOSSARY_CATEGORY_LABELS = {
    "formation": "Formations",
    "route": "Routes",
    "run-concept": "Run Concepts",
    "pass-concept": "Pass Concepts",
    "blocking": "Blocking",
    "coverage": "Coverage & Recognition",
    "motion": "Motion",
    "audible": "Audibles",
    "situational": "Situational",
    "other": "Other Terms",
}


def _doc_styles() -> dict[str, ParagraphStyle]:
    """Paragraph styles for the full-page front-matter, glossary, and appendix
    sections — larger and more readable than the half-page play-note styles."""
    base = ParagraphStyle(
        "doc-base", fontName="Helvetica", fontSize=10, leading=14,
        textColor=C_BODY_TEXT, spaceAfter=6,
    )
    return {
        "body": base,
        "lead": ParagraphStyle(
            "doc-lead", parent=base, fontSize=11, leading=15,
            textColor=C_MUTED, spaceAfter=10,
        ),
        "h1": ParagraphStyle(
            "doc-h1", parent=base, fontName="Helvetica-Bold", fontSize=15,
            leading=19, textColor=C_PAGE_TITLE, spaceBefore=4, spaceAfter=8,
        ),
        "h2": ParagraphStyle(
            "doc-h2", parent=base, fontName="Helvetica-Bold", fontSize=11,
            leading=14, textColor=C_SECTION_HEAD, spaceBefore=12, spaceAfter=4,
        ),
        "bullet": ParagraphStyle(
            "doc-bullet", parent=base, leftIndent=14, spaceAfter=3,
        ),
        "term": ParagraphStyle(
            "doc-term", parent=base, leftIndent=14, firstLineIndent=-14,
            spaceAfter=5,
        ),
    }


def _text_to_paragraphs(text: Any, style: ParagraphStyle) -> list:
    """One Paragraph per non-empty block of `text`. Front-matter prose is
    stored as folded YAML scalars, so paragraph breaks arrive as newlines."""
    paragraphs = []
    for block in str(text or "").split("\n"):
        block = block.strip()
        if block:
            paragraphs.append(Paragraph(_esc(block), style))
    return paragraphs


def _identity_flowables(front_matter: dict, styles: dict) -> list:
    """Flowables for the identity / philosophy opening page(s)."""
    identity = front_matter.get("identity") or {}
    flowables: list = []
    if identity.get("title"):
        flowables.append(Paragraph(_esc(identity["title"]), styles["h1"]))
    if identity.get("summary"):
        flowables.extend(_text_to_paragraphs(identity["summary"], styles["lead"]))
    if identity.get("philosophy"):
        flowables.append(Paragraph("Philosophy", styles["h2"]))
        flowables.extend(_text_to_paragraphs(identity["philosophy"], styles["body"]))
    if identity.get("keys_to_success"):
        flowables.append(Paragraph("Keys to Success", styles["h2"]))
        for key in identity["keys_to_success"]:
            flowables.append(Paragraph(f"•  {_esc(key)}", styles["bullet"]))
    return flowables


def _how_to_read_flowables(front_matter: dict, styles: dict) -> list:
    """Flowables for the how-to-read / cadence / install page."""
    flowables: list = []
    for heading, text in [
        ("How to Read This Playbook", front_matter.get("how_to_read")),
        ("Cadence", front_matter.get("cadence")),
        ("Install", front_matter.get("install_notes")),
    ]:
        if text:
            flowables.append(Paragraph(heading, styles["h2"]))
            flowables.extend(_text_to_paragraphs(text, styles["body"]))
    return flowables


def _glossary_flowables(glossary: list, styles: dict) -> list:
    """Flowables for the glossary pages, grouped by category."""
    entries_by_category: dict[str, list] = {}
    for entry in glossary:
        entries_by_category.setdefault(entry["category"], []).append(entry)
    flowables: list = []
    for category in sorted(entries_by_category,
                           key=lambda cat: GLOSSARY_CATEGORY_LABELS.get(cat, cat)):
        label = GLOSSARY_CATEGORY_LABELS.get(category, category.replace("-", " ").title())
        flowables.append(Paragraph(label, styles["h2"]))
        for entry in sorted(entries_by_category[category],
                            key=lambda e: e["term"].lower()):
            definition = _esc(entry.get("definition", "")).replace("\n", " ")
            flowables.append(
                Paragraph(f"<b>{_esc(entry['term'])}</b> — {definition}", styles["term"])
            )
    return flowables


def _appendix_flowables(front_matter: dict, styles: dict) -> list:
    """Flowables for the appendix sections."""
    flowables: list = []
    for section in front_matter.get("appendix") or []:
        if section.get("title"):
            flowables.append(Paragraph(_esc(section["title"]), styles["h2"]))
        flowables.extend(_text_to_paragraphs(section.get("body", ""), styles["body"]))
    return flowables


def _flow_text_pages(c: Canvas, page_title: str, flowables: list) -> int:
    """Draw `flowables` across as many letter pages as needed, each carrying
    `page_title`. Returns the number of pages drawn."""
    if not flowables:
        return 0
    remaining = list(flowables)
    body_height = PAGE_H - 2 * MARGIN - PAGE_TITLE_H - GAP_AFTER_TITLE
    pages = 0
    while remaining:
        _draw_page_title(c, page_title)
        frame = Frame(
            MARGIN, MARGIN, CONTENT_W, body_height,
            leftPadding=6, rightPadding=6, topPadding=6, bottomPadding=6,
            showBoundary=0,
        )
        count_before = len(remaining)
        frame.addFromList(remaining, c)
        c.showPage()
        pages += 1
        if len(remaining) == count_before:
            # A single flowable could not fit an empty frame. Paragraphs and
            # headings split or are tiny, so this is a guard against a
            # pathological input, not an expected path — drop it and move on.
            remaining.pop(0)
    return pages


def _draw_play_pages(c: Canvas, plays_with_svgs: list, title: str,
                     layout: str) -> int:
    """Draw the play pages in `layout` ('one-per-page' or 'side-by-side').
    Returns the number of pages drawn."""
    slots = _play_slots(layout)
    plays_per_page = len(slots)
    pages = 0
    for start in range(0, len(plays_with_svgs), plays_per_page):
        chunk = plays_with_svgs[start:start + plays_per_page]
        _draw_page_title(c, title)
        for (play, svg), slot in zip(chunk, slots):
            _draw_play_in_rect(c, play, svg, slot)
        c.showPage()
        pages += 1
    return pages


# ─── Main ─────────────────────────────────────────────────────────────────────

def _render_playbook(playbook_path: Path, args: argparse.Namespace) -> None:
    """Render a full playbook PDF: front matter, glossary, plays, appendix.

    Play diagrams not pre-rendered in --diagram-dir are rendered on demand
    with the draw tool, so the PDF always carries a diagram for every play.
    """
    playbook = _load_yaml(playbook_path)
    front_matter = playbook.get("front_matter") or {}
    title = args.title or playbook.get("name") or "Playbook"
    styles = _doc_styles()

    c = Canvas(str(args.output), pagesize=letter)

    _flow_text_pages(c, title, _identity_flowables(front_matter, styles))
    _flow_text_pages(c, "How to Read This Playbook",
                     _how_to_read_flowables(front_matter, styles))

    glossary = compile_glossary.compile_glossary(playbook_path)
    _flow_text_pages(c, "Glossary", _glossary_flowables(glossary, styles))

    play_entries = [
        entry
        for section in playbook.get("formation_sections", [])
        for entry in section.get("plays", [])
    ]
    plays_with_svgs: list = []
    missing_play_ids: list[str] = []
    failed_diagram_ids: list[str] = []
    diagram_counts = {"found": 0, "rendered": 0, "failed": 0}
    with tempfile.TemporaryDirectory(prefix="playbook-diagrams-") as render_dir_name:
        render_dir = Path(render_dir_name)
        for entry in play_entries:
            play_id = entry["play_id"]
            play_path = PLAYS_DIR / f"{play_id}.yaml"
            if not play_path.exists():
                missing_play_ids.append(play_id)
                continue
            play = _load_yaml(play_path)
            resolved_id = play.get("play_id") or play_id
            svg, status = _ensure_svg(resolved_id, args.game,
                                      args.diagram_dir, render_dir)
            diagram_counts[status] += 1
            if status == "failed":
                failed_diagram_ids.append(resolved_id)
            plays_with_svgs.append((play, svg))
        # The on-demand renders live in the temp dir — it must outlive the
        # play pages being drawn, so draw them inside the `with` block.
        _draw_play_pages(c, plays_with_svgs, title, args.layout)

    _flow_text_pages(c, "Appendix", _appendix_flowables(front_matter, styles))

    c.save()
    print(f"Wrote {args.output} — playbook '{playbook.get('playbook_id')}': "
          f"{len(plays_with_svgs)} plays, {len(glossary)} glossary terms")
    print(f"  diagrams: {diagram_counts['found']} pre-rendered, "
          f"{diagram_counts['rendered']} rendered on demand, "
          f"{diagram_counts['failed']} failed")
    if failed_diagram_ids:
        print(f"  diagram render failed for: {failed_diagram_ids}", file=sys.stderr)
    if missing_play_ids:
        print(f"  play file(s) missing: {missing_play_ids}", file=sys.stderr)


def _render_play_list(play_paths: list[Path], args: argparse.Namespace) -> None:
    """Render an ad-hoc set of plays — play pages only, no front matter.

    Diagrams missing from --diagram-dir are rendered on demand."""
    missing = [path for path in play_paths if not path.exists()]
    if missing:
        for path in missing:
            print(f"ERROR: play YAML not found: {path}", file=sys.stderr)
        sys.exit(1)
    plays_with_svgs: list = []
    diagram_counts = {"found": 0, "rendered": 0, "failed": 0}
    c = Canvas(str(args.output), pagesize=letter)
    with tempfile.TemporaryDirectory(prefix="playbook-diagrams-") as render_dir_name:
        render_dir = Path(render_dir_name)
        for path in play_paths:
            play = _load_yaml(path)
            svg, status = _ensure_svg(play.get("play_id") or path.stem,
                                      args.game, args.diagram_dir, render_dir)
            diagram_counts[status] += 1
            plays_with_svgs.append((play, svg))
        pages = _draw_play_pages(c, plays_with_svgs,
                                 args.title or "Playbook Notes", args.layout)
    c.save()
    print(f"Wrote {args.output} ({len(plays_with_svgs)} plays, {pages} pages; "
          f"{diagram_counts['rendered']} diagram(s) rendered on demand)")


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Detailed teaching PDF — a whole playbook, or an ad-hoc set of plays.",
    )
    ap.add_argument("plays", nargs="*", metavar="PLAY",
                    help="Play YAML file(s). Used when --playbook is not given.")
    ap.add_argument("--playbook", type=Path, default=None,
                    help="Playbook YAML. Renders front matter + glossary + every "
                         "play in the playbook + appendix.")
    ap.add_argument("--game", default="madden-05-ps2",
                    help="Game tag for diagram lookup (default: madden-05-ps2).")
    ap.add_argument("--diagram-dir", default="examples/play-diagrams", type=Path,
                    help="Directory containing SVG diagrams.")
    ap.add_argument("--layout", choices=["side-by-side", "one-per-page"],
                    default="side-by-side",
                    help="Play-page layout: 'side-by-side' (two plays per page "
                         "as tall columns; default) or 'one-per-page' (one play "
                         "with a large diagram).")
    ap.add_argument("--title", default=None,
                    help="Page title. Defaults to the playbook name (playbook "
                         "mode) or 'Playbook Notes' (play-list mode).")
    ap.add_argument("-o", "--output", default="playbook-detailed.pdf", type=Path,
                    help="Output PDF path.")
    args = ap.parse_args()

    if args.playbook:
        if not args.playbook.exists():
            print(f"ERROR: playbook YAML not found: {args.playbook}", file=sys.stderr)
            sys.exit(1)
        _render_playbook(args.playbook, args)
    elif args.plays:
        _render_play_list([Path(p) for p in args.plays], args)
    else:
        print("ERROR: pass either --playbook PATH or one or more play files",
              file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
