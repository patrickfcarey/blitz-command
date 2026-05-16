#!/usr/bin/env python3
"""Generate a printable PDF call sheet from SVG play diagrams.

Layout: letter portrait, 2 pages, 12 plays per page, 2 sections of 6 plays
each (3 columns × 2 rows per section).

Rule: SVGs must be generated with --field short. Long-field diagrams contain
too much empty downfield space and become unreadable at call-sheet scale.
When both offense AND defense are shown (--vs flag), long-field is acceptable
but short-field is still preferred for readability.

Usage:
    python print_playbook.py play1.svg play2.svg ... [options]
    python print_playbook.py examples/play-diagrams/*.svg -o callsheet.pdf
"""
from __future__ import annotations

import argparse
import re
import sys
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path

from reportlab.lib.pagesizes import letter
from reportlab.pdfgen.canvas import Canvas
from svglib.svglib import svg2rlg
from reportlab.graphics import renderPDF

# Map draw.py screen colors → print-friendly equivalents.
# Dark backgrounds and green fills become white; grid lines become grays
# visible on white paper. Player/route colors are left unchanged.
# Applied in a single regex pass to avoid chaining (e.g. dark→white→dark again).
_PRINT_COLOR_MAP: dict[str, str] = {
    "#1a1a1a": "#ffffff",   # outer dark bg → white
    "#1b5e20": "#ffffff",   # off-editor dark green → white
    "#2e7d32": "#ffffff",   # editor grid green → white
    "#388e3c": "#cccccc",   # fine grid lines (editor) → light gray
    "#2e6b34": "#dddddd",   # fine grid lines (off-editor) → very light gray
    "#cccccc": "#aaaaaa",   # major 5-yd grid lines → medium gray
    "#ffffff": "#555555",   # white hash marks / boundary strokes → dark gray
    "#cfcfcf": "#aaaaaa",   # yard-line ticks → medium gray
    "#666":    "#aaaaaa",   # dim text → medium gray
    "#666666": "#aaaaaa",
    "#888":    "#aaaaaa",   # muted / fake-path → medium gray
    "#888888": "#aaaaaa",
}
# Longest-first + a trailing hex negative-lookahead: a short key ("#666")
# must not match the prefix of a longer hex color ("#666666"), which would
# corrupt it to "#aaaaaa666".
_PRINT_COLOR_RE = re.compile(
    "(?:" + "|".join(re.escape(k) for k in sorted(_PRINT_COLOR_MAP, key=len, reverse=True))
    + ")(?![0-9A-Fa-f])"
)

PAGE_W, PAGE_H = letter  # 612 × 792 pt
MARGIN = 36

CONTENT_W = PAGE_W - 2 * MARGIN   # 540
CONTENT_H = PAGE_H - 2 * MARGIN   # 720

COLS = 3
ROWS_PER_SECTION = 2
PLAYS_PER_SECTION = 6
PLAYS_PER_PAGE = 12

PAGE_TITLE_H = 32
GAP_AFTER_TITLE = 8
SECTION_LABEL_H = 22
GAP_BETWEEN_SECTIONS = 14

GRID_TOTAL_H = CONTENT_H - PAGE_TITLE_H - GAP_AFTER_TITLE - SECTION_LABEL_H * 2 - GAP_BETWEEN_SECTIONS
SECTION_GRID_H = GRID_TOTAL_H / 2  # ~311 pt
CELL_W = CONTENT_W / COLS          # 180 pt
CELL_H = SECTION_GRID_H / ROWS_PER_SECTION  # ~155.5 pt

PLAY_NAME_H = 16
DIAGRAM_PAD = 4
DIAGRAM_W = CELL_W - 2 * DIAGRAM_PAD
DIAGRAM_H = CELL_H - PLAY_NAME_H - DIAGRAM_PAD

COLOR_PAGE_TITLE = (0.10, 0.10, 0.18)
COLOR_SECTION_BG = (0.176, 0.373, 0.176)
COLOR_SECTION_FG = (1.0, 1.0, 1.0)
COLOR_CELL_BORDER = (0.80, 0.80, 0.80)
COLOR_PLAY_NAME = (0.10, 0.10, 0.18)

# Markers of the legacy DARK-theme SVG palette (pre-rewrite draw.py). The
# current draw.py emits light, print-ready SVGs — those must NOT be color-
# remapped (remapping would, e.g., turn the white field gray).
_LEGACY_DARK_MARKERS = ("#1a1a1a", "#1b5e20", "#2e7d32")


def _load_svg_print(svg_path: Path):
    """Load an SVG for print. Legacy dark-theme SVGs get their screen colors
    remapped to print-friendly values; current light SVGs are already
    print-ready and are loaded as-is. Writes a temp file because svg2rlg
    requires a path, not a string.
    """
    with open(svg_path, encoding="utf-8") as f:
        content = f.read()

    # Single-pass substitution — only for legacy dark SVGs.
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
    and backgrounds are fill-only), so 'largest stroked rect' finds it without
    depending on a specific fill color.
    """
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
                w = h = x = y = 0.0
            area = w * h
            if area > 0 and (best is None or area > best[0]):
                best = (area, x, y, w, h)
        for child in elem:
            scan(child, tx, ty)

    scan(root, 0.0, 0.0)
    if best is None:
        return None
    return (best[1], best[2], best[3], best[4])


def _play_name_from_path(path: Path) -> str:
    stem = path.stem
    stem = re.sub(r"--[a-z0-9]+-[0-9]+-[a-z0-9]+$", "", stem)
    return " ".join(w.capitalize() for w in stem.split("-"))


def _draw_page_title(c: Canvas, title: str, y_top: float) -> None:
    c.saveState()
    c.setFillColorRGB(*COLOR_PAGE_TITLE)
    c.setFont("Helvetica-Bold", 18)
    c.drawCentredString(PAGE_W / 2, y_top - 22, title)
    c.restoreState()


def _draw_section(
    c: Canvas,
    label: str,
    plays: list[Path],
    x_left: float,
    y_top: float,
) -> None:
    # Section label bar
    c.saveState()
    c.setFillColorRGB(*COLOR_SECTION_BG)
    c.rect(x_left, y_top - SECTION_LABEL_H, CONTENT_W, SECTION_LABEL_H, fill=1, stroke=0)
    c.setFillColorRGB(*COLOR_SECTION_FG)
    c.setFont("Helvetica-Bold", 11)
    c.drawCentredString(x_left + CONTENT_W / 2, y_top - SECTION_LABEL_H + 5, label.upper())
    c.restoreState()

    grid_top = y_top - SECTION_LABEL_H

    for idx, svg_path in enumerate(plays[:PLAYS_PER_SECTION]):
        col = idx % COLS
        row = idx // COLS
        cell_x = x_left + col * CELL_W
        cell_y = grid_top - (row + 1) * CELL_H

        # Cell border
        c.saveState()
        c.setStrokeColorRGB(*COLOR_CELL_BORDER)
        c.setLineWidth(0.5)
        c.rect(cell_x, cell_y, CELL_W, CELL_H, fill=0, stroke=1)

        # Play name
        c.setFillColorRGB(*COLOR_PLAY_NAME)
        c.setFont("Helvetica", 7)
        c.drawCentredString(cell_x + CELL_W / 2, cell_y + 4, _play_name_from_path(svg_path))
        c.restoreState()

        # SVG diagram — render full SVG, clip via PDF to field area only
        diagram_x = cell_x + DIAGRAM_PAD
        diagram_y = cell_y + PLAY_NAME_H
        try:
            drawing = _load_svg_print(svg_path)
            if drawing is None:
                raise ValueError("svg2rlg returned None")

            bounds = _field_bounds(svg_path)
            if bounds:
                fx, fy, fw, fh = bounds
            else:
                # Fall back: treat full SVG as the field
                fx, fy, fw, fh = 0.0, 0.0, drawing.width, drawing.height

            # Scale so the field fits inside the diagram area
            scale = min(DIAGRAM_W / fw, DIAGRAM_H / fh)
            field_pdf_w = fw * scale
            field_pdf_h = fh * scale

            # Center the field within the diagram area
            clip_x = diagram_x + (DIAGRAM_W - field_pdf_w) / 2
            clip_y = diagram_y + (DIAGRAM_H - field_pdf_h) / 2

            # reportlab/svglib flips SVG y: SVG y=0 → PDF y=drawing.height.
            # The field's bottom in PDF space (pre-translate):
            #   field_pdf_bottom = (drawing.height - fy - fh) * scale
            # To position field at clip_y, offset the drawing by:
            #   draw_y = clip_y - field_pdf_bottom
            field_pdf_bottom = (drawing.height - fy - fh) * scale
            field_pdf_left = fx * scale
            draw_x = clip_x - field_pdf_left
            draw_y = clip_y - field_pdf_bottom

            c.saveState()
            # PDF-level clip: only render the field rectangle
            cp = c.beginPath()
            cp.rect(clip_x, clip_y, field_pdf_w, field_pdf_h)
            c.clipPath(cp, stroke=0, fill=0)
            # Position and scale the full drawing
            c.translate(draw_x, draw_y)
            c.scale(scale, scale)
            renderPDF.draw(drawing, c, 0, 0)
            c.restoreState()

        except Exception as exc:
            c.saveState()
            c.setFillColorRGB(0.6, 0.1, 0.1)
            c.setFont("Helvetica", 6)
            c.drawCentredString(cell_x + CELL_W / 2, cell_y + CELL_H / 2, f"[error: {exc}]")
            c.restoreState()


def _draw_page(
    c: Canvas,
    page_title: str,
    section_labels: tuple[str, str],
    plays: list[Path],
) -> None:
    y_cursor = PAGE_H - MARGIN
    _draw_page_title(c, page_title, y_cursor)
    y_cursor -= PAGE_TITLE_H + GAP_AFTER_TITLE

    for sec_idx in range(2):
        sec_plays = plays[sec_idx * PLAYS_PER_SECTION: (sec_idx + 1) * PLAYS_PER_SECTION]
        _draw_section(c, section_labels[sec_idx], sec_plays, MARGIN, y_cursor)
        y_cursor -= SECTION_LABEL_H + SECTION_GRID_H
        if sec_idx == 0:
            y_cursor -= GAP_BETWEEN_SECTIONS


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate a printable PDF call sheet from SVG play diagrams."
    )
    parser.add_argument(
        "svgs",
        nargs="+",
        metavar="SVG",
        help="SVG play diagram files (up to 24 for 2 pages of 12). "
             "Use --field short when generating SVGs with draw.py.",
    )
    parser.add_argument(
        "--labels",
        nargs="*",
        metavar="LABEL",
        default=[],
        help="Section labels, one per section (up to 4). "
             "Defaults: 'Run Plays', 'Pass Plays', 'Run Plays', 'Pass Plays'.",
    )
    parser.add_argument(
        "--title",
        default="Game Plan",
        help="Title printed at the top of each page (default: 'Game Plan').",
    )
    parser.add_argument(
        "-o", "--output",
        default="callsheet.pdf",
        metavar="FILE",
        help="Output PDF path (default: callsheet.pdf).",
    )
    args = parser.parse_args()

    svg_paths = [Path(p) for p in args.svgs]
    missing = [p for p in svg_paths if not p.exists()]
    if missing:
        for p in missing:
            print(f"ERROR: file not found: {p}", file=sys.stderr)
        sys.exit(1)

    default_labels = ["Run Plays", "Pass Plays", "Run Plays", "Pass Plays"]
    section_labels = [
        args.labels[i] if i < len(args.labels) else default_labels[i]
        for i in range(4)
    ]

    out_path = Path(args.output)
    c = Canvas(str(out_path), pagesize=letter)

    for page_idx in range(2):
        page_plays = svg_paths[page_idx * PLAYS_PER_PAGE: (page_idx + 1) * PLAYS_PER_PAGE]
        if not page_plays and page_idx > 0:
            break
        _draw_page(c, args.title, (section_labels[page_idx * 2], section_labels[page_idx * 2 + 1]), page_plays)
        c.showPage()

    c.save()
    print(f"Wrote {out_path}")


if __name__ == "__main__":
    main()
