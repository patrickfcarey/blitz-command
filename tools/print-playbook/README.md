# print-playbook

Generates a printable PDF call sheet from SVG play diagrams.

**Layout:** letter portrait (8.5 × 11 in), 2 pages, 12 plays per page, 2 sections of 6 plays each (3 columns × 2 rows per section).

## Usage

```bash
python tools/print-playbook/print_playbook.py examples/play-diagrams/*.svg
```

```bash
python tools/print-playbook/print_playbook.py \
    examples/play-diagrams/i-formation-power-o--madden-05-ps2.svg \
    examples/play-diagrams/i-formation-counter-trey--madden-05-ps2.svg \
    ... \
    --title "Week 3 Game Plan" \
    --labels "Base Run" "Play Action" "Screens" "Two-Minute Passing" \
    -o week3.pdf
```

## Options

| Flag | Default | Description |
|------|---------|-------------|
| `SVG ...` | (required) | SVG play diagram files, up to 24 (2 pages × 12) |
| `--title TEXT` | `Game Plan` | Title printed at the top of each page |
| `--labels L1 L2 L3 L4` | `Run Plays / Pass Plays` × 2 | Section header labels, one per section (4 total across 2 pages) |
| `-o FILE` | `callsheet.pdf` | Output PDF path |

## Play names

Play names are derived from the SVG filename: the game-tag suffix (`--madden-05-ps2`) is stripped and the remaining kebab-case stem is converted to Title Case.

## Setup

```bash
pip install reportlab>=4.0 svglib>=1.5
# or:
pip install -r requirements.txt
```

No system dependencies — pure Python.
