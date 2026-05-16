#!/usr/bin/env python3
"""Generate a detailed teaching PDF: 2 fully-explained plays per page.

Layout: letter portrait. Each page has 2 play slots stacked vertically.
Within each slot: title bar + diagram (top half) + notes (bottom half, 2 columns).

Notes are pulled from existing fields in the play YAML — no schema additions.
For every play, we surface:
  - Header line (formation, type, philosophy, concept)
  - Aliases (if any)
  - Per-player assignments (role + scheme/target + notes)
  - Reads — run_reads list for runs, primary/secondary/checkdown for passes
  - Strengths / Weaknesses (two columns within notes)
  - Best vs / Worst vs / Common uses
  - Play-level notes (free text)

Usage:
    python print_playbook_detailed.py \
        data/plays/i-formation-power-o.yaml \
        data/plays/i-formation-counter-trey.yaml \
        --game madden-05-ps2 \
        --diagram-dir examples/play-diagrams \
        -o detailed.pdf
"""
from __future__ import annotations

import argparse
import re
import sys
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

import yaml
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import inch
from reportlab.pdfgen.canvas import Canvas
from reportlab.platypus import Frame, KeepInFrame, Paragraph, Spacer
from svglib.svglib import svg2rlg
from reportlab.graphics import renderPDF


# ─── Page geometry ────────────────────────────────────────────────────────────

PAGE_W, PAGE_H = letter
MARGIN = 36
CONTENT_W = PAGE_W - 2 * MARGIN
CONTENT_H = PAGE_H - 2 * MARGIN

PAGE_TITLE_H = 24
GAP_AFTER_TITLE = 6
GAP_BETWEEN_SLOTS = 8

SLOT_H = (CONTENT_H - PAGE_TITLE_H - GAP_AFTER_TITLE - GAP_BETWEEN_SLOTS) / 2

# Within a slot
SLOT_HEADER_H = 26
DIAGRAM_H = 150
NOTES_H = SLOT_H - SLOT_HEADER_H - DIAGRAM_H
NOTES_COL_GAP = 10
NOTES_COL_W = (CONTENT_W - NOTES_COL_GAP) / 2


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


def _field_bounds(svg_path: Path) -> tuple[float, float, float, float] | None:
    """Return (x, y, w, h) of the editor field — the largest STROKED rect.

    Palette-agnostic: in the legacy dark SVGs the editor field is a green rect
    with a white stroke; in the current light SVGs it is a white rect with a
    dark stroke. Either way it is the largest rect carrying a stroke (panels
    and backgrounds are drawn fill-only), so 'largest stroked rect' finds it
    without depending on a specific fill color."""
    try:
        tree = ET.parse(svg_path)
    except ET.ParseError:
        return None
    root = tree.getroot()
    best: tuple[float, float, float, float, float] | None = None  # (area,x,y,w,h)

    def scan(elem: ET.Element, tx: float, ty: float) -> None:
        nonlocal best
        t = elem.get("transform", "")
        m = re.match(r"translate\(\s*([0-9.+-]+)\s*(?:,\s*([0-9.+-]+))?\s*\)", t)
        if m:
            tx += float(m.group(1))
            ty += float(m.group(2)) if m.group(2) else 0.0
        tag = elem.tag.split("}")[-1] if "}" in elem.tag else elem.tag
        stroke = elem.get("stroke")
        if tag == "rect" and stroke and stroke.lower() != "none":
            try:
                w = float(elem.get("width", 0))
                h = float(elem.get("height", 0))
                x = float(elem.get("x", 0)) + tx
                y = float(elem.get("y", 0)) + ty
            except ValueError:
                w = h = 0.0
                x = y = 0.0
            area = w * h
            if area > 0 and (best is None or area > best[0]):
                best = (area, x, y, w, h)
        for child in elem:
            scan(child, tx, ty)

    scan(root, 0.0, 0.0)
    if best is None:
        return None
    return (best[1], best[2], best[3], best[4])


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


def _draw_slot_header(c: Canvas, x: float, y_top: float, play: dict) -> None:
    name = play.get("name", play.get("play_id", "Untitled"))
    pid = play.get("play_id", "")
    c.saveState()
    c.setFillColor(C_SLOT_HEADER_BG)
    c.rect(x, y_top - SLOT_HEADER_H, CONTENT_W, SLOT_HEADER_H, fill=1, stroke=0)
    c.setFillColor(C_SLOT_HEADER_FG)
    c.setFont("Helvetica-Bold", 13)
    c.drawString(x + 10, y_top - SLOT_HEADER_H + 8, str(name))
    if pid:
        c.setFont("Helvetica-Oblique", 8)
        c.drawRightString(x + CONTENT_W - 10, y_top - SLOT_HEADER_H + 9, str(pid))
    c.restoreState()


def _draw_diagram(c: Canvas, svg_path: Path | None, x: float, y_bottom: float, w: float, h: float) -> None:
    c.saveState()
    c.setStrokeColor(C_BORDER)
    c.setLineWidth(0.5)
    c.rect(x, y_bottom, w, h, fill=0, stroke=1)
    c.restoreState()

    if svg_path is None or not svg_path.exists():
        c.saveState()
        c.setFillColor(C_MUTED)
        c.setFont("Helvetica-Oblique", 9)
        msg = "diagram not found" if svg_path else "no diagram provided"
        if svg_path:
            msg = f"missing: {svg_path.name}"
        c.drawCentredString(x + w / 2, y_bottom + h / 2, msg)
        c.restoreState()
        return

    try:
        drawing = _load_svg_print(svg_path)
        if drawing is None:
            raise ValueError("svg2rlg returned None")
        bounds = _field_bounds(svg_path)
        if bounds:
            fx, fy, fw, fh = bounds
        else:
            fx, fy, fw, fh = 0.0, 0.0, drawing.width, drawing.height
        pad = 3
        avail_w = w - 2 * pad
        avail_h = h - 2 * pad
        scale = min(avail_w / fw, avail_h / fh)
        field_pdf_w = fw * scale
        field_pdf_h = fh * scale
        clip_x = x + (w - field_pdf_w) / 2
        clip_y = y_bottom + (h - field_pdf_h) / 2
        field_pdf_bottom = (drawing.height - fy - fh) * scale
        field_pdf_left = fx * scale
        draw_x = clip_x - field_pdf_left
        draw_y = clip_y - field_pdf_bottom
        c.saveState()
        cp = c.beginPath()
        cp.rect(clip_x, clip_y, field_pdf_w, field_pdf_h)
        c.clipPath(cp, stroke=0, fill=0)
        c.translate(draw_x, draw_y)
        c.scale(scale, scale)
        renderPDF.draw(drawing, c, 0, 0)
        c.restoreState()
    except Exception as exc:
        c.saveState()
        c.setFillColor(colors.red)
        c.setFont("Helvetica", 7)
        c.drawCentredString(x + w / 2, y_bottom + h / 2, f"[diagram error: {exc}]")
        c.restoreState()


def _draw_notes_columns(c: Canvas, play: dict, x: float, y_bottom: float) -> None:
    styles = _styles()
    left_flow = _left_column_flowables(play, styles)
    right_flow = _right_column_flowables(play, styles)

    left_frame = Frame(
        x, y_bottom, NOTES_COL_W, NOTES_H,
        leftPadding=2, rightPadding=2, topPadding=2, bottomPadding=2,
        showBoundary=0,
    )
    right_frame = Frame(
        x + NOTES_COL_W + NOTES_COL_GAP, y_bottom, NOTES_COL_W, NOTES_H,
        leftPadding=2, rightPadding=2, topPadding=2, bottomPadding=2,
        showBoundary=0,
    )
    # KeepInFrame shrinks content to fit; "truncate" mode drops overflow instead.
    left_frame.addFromList([KeepInFrame(NOTES_COL_W, NOTES_H, left_flow, mode="shrink")], c)
    right_frame.addFromList([KeepInFrame(NOTES_COL_W, NOTES_H, right_flow, mode="shrink")], c)


def _draw_play_slot(c: Canvas, play: dict, svg_path: Path | None, y_top: float) -> None:
    x = MARGIN
    _draw_slot_header(c, x, y_top, play)
    diagram_y_top = y_top - SLOT_HEADER_H
    diagram_y_bottom = diagram_y_top - DIAGRAM_H
    _draw_diagram(c, svg_path, x, diagram_y_bottom, CONTENT_W, DIAGRAM_H)
    notes_y_bottom = diagram_y_bottom - NOTES_H
    _draw_notes_columns(c, play, x, notes_y_bottom)


# ─── Play / SVG resolution ────────────────────────────────────────────────────

def _load_play(path: Path) -> dict:
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


# ─── Main ─────────────────────────────────────────────────────────────────────

def main() -> None:
    ap = argparse.ArgumentParser(
        description="Detailed teaching PDF — 2 fully-explained plays per page.",
    )
    ap.add_argument("plays", nargs="+", metavar="PLAY",
                    help="Path to play YAML file(s).")
    ap.add_argument("--game", default="madden-05-ps2",
                    help="Game tag for diagram lookup (default: madden-05-ps2).")
    ap.add_argument("--diagram-dir", default="examples/play-diagrams", type=Path,
                    help="Directory containing SVG diagrams.")
    ap.add_argument("--title", default="Playbook Notes",
                    help="Title printed at the top of each page.")
    ap.add_argument("-o", "--output", default="playbook-detailed.pdf", type=Path,
                    help="Output PDF path.")
    args = ap.parse_args()

    play_paths = [Path(p) for p in args.plays]
    missing = [p for p in play_paths if not p.exists()]
    if missing:
        for p in missing:
            print(f"ERROR: play YAML not found: {p}", file=sys.stderr)
        sys.exit(1)

    plays_with_svgs: list[tuple[dict, Path | None]] = []
    for p in play_paths:
        play = _load_play(p)
        pid = play.get("play_id") or p.stem
        svg = _resolve_svg(pid, args.game, args.diagram_dir)
        plays_with_svgs.append((play, svg))

    c = Canvas(str(args.output), pagesize=letter)

    PER_PAGE = 2
    for page_idx in range(0, len(plays_with_svgs), PER_PAGE):
        chunk = plays_with_svgs[page_idx:page_idx + PER_PAGE]
        _draw_page_title(c, args.title)
        y_cursor = PAGE_H - MARGIN - PAGE_TITLE_H - GAP_AFTER_TITLE
        for play, svg in chunk:
            _draw_play_slot(c, play, svg, y_cursor)
            y_cursor -= SLOT_H + GAP_BETWEEN_SLOTS
        c.showPage()

    c.save()
    print(f"Wrote {args.output} ({len(plays_with_svgs)} plays, "
          f"{(len(plays_with_svgs) + PER_PAGE - 1) // PER_PAGE} pages)")


if __name__ == "__main__":
    main()
