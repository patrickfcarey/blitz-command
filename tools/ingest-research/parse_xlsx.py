#!/usr/bin/env python3
"""Parse .xlsx workbooks into plain row data without openpyxl.

The Playbook Gamer research corpus (research_artifacts/, git-ignored) ships
~26 .xlsx workbooks — formation lists, play lists, playbook databases — that
are the most structured, highest-value reference data in the corpus. The repo
.venv has no openpyxl, but an .xlsx is just a zip of XML, so this module reads
it directly.

As a module:
    from parse_xlsx import read_xlsx
    sheets = read_xlsx(path)        # {sheet_name: [[cell, ...], ...]}

As a CLI (prints a digest of every workbook matched by the glob/paths given):
    python3 tools/ingest-research/parse_xlsx.py 'research_artifacts/**/*Formation*.xlsx'
"""
from __future__ import annotations

import glob as glob_module
import sys
import zipfile
from xml.etree import ElementTree as ElementTreeModule

# Every spreadsheetml element lives in this XML namespace.
SPREADSHEET_NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"

# CLI digest limits — enough to reveal a sheet's structure without dumping a
# whole (often 1000-row) database.
DIGEST_ROW_LIMIT = 12
DIGEST_COLUMN_LIMIT = 12
CELL_DIGEST_WIDTH = 16


def _column_index(cell_reference: str) -> int:
    """Return the zero-based column index from a cell ref, e.g. 'AB7' -> 27."""
    column_letters = "".join(ch for ch in cell_reference if ch.isalpha())
    index = 0
    for letter in column_letters:
        index = index * 26 + (ord(letter.upper()) - ord("A") + 1)
    return index - 1


def _read_shared_strings(workbook: zipfile.ZipFile) -> list[str]:
    """Return the workbook's shared-string table (string cells index into it)."""
    if "xl/sharedStrings.xml" not in workbook.namelist():
        return []
    strings: list[str] = []
    root = ElementTreeModule.fromstring(workbook.read("xl/sharedStrings.xml"))
    for string_item in root:
        # A shared string can be split across several <t> runs; join them.
        runs = string_item.iter(SPREADSHEET_NS + "t")
        strings.append("".join(run.text or "" for run in runs))
    return strings


def _read_sheet_names(workbook: zipfile.ZipFile) -> list[str]:
    """Return worksheet display names in workbook order."""
    root = ElementTreeModule.fromstring(workbook.read("xl/workbook.xml"))
    return [sheet.get("name", "") for sheet in root.iter(SPREADSHEET_NS + "sheet")]


def _cell_value(cell: ElementTreeModule.Element, shared_strings: list[str]) -> str:
    """Resolve a single <c> cell element to its text value."""
    cell_type = cell.get("t")
    if cell_type == "inlineStr":
        inline_string = cell.find(SPREADSHEET_NS + "is")
        if inline_string is None:
            return ""
        runs = inline_string.iter(SPREADSHEET_NS + "t")
        return "".join(run.text or "" for run in runs)
    value_element = cell.find(SPREADSHEET_NS + "v")
    if value_element is None or value_element.text is None:
        return ""
    if cell_type == "s":
        return shared_strings[int(value_element.text)]
    return value_element.text


def _read_worksheet(workbook: zipfile.ZipFile, sheet_path: str,
                    shared_strings: list[str]) -> list[list[str]]:
    """Return one worksheet as a list of rows, each a list of cell strings.

    Cells are placed by their column reference, so sparse rows still line up
    column-for-column with their header.
    """
    rows: list[list[str]] = []
    root = ElementTreeModule.fromstring(workbook.read(sheet_path))
    for row_element in root.iter(SPREADSHEET_NS + "row"):
        cells_by_column: dict[int, str] = {}
        for cell in row_element.iter(SPREADSHEET_NS + "c"):
            value = _cell_value(cell, shared_strings)
            if value:
                cells_by_column[_column_index(cell.get("r", "A1"))] = value
        if not cells_by_column:
            rows.append([])
            continue
        row_width = max(cells_by_column) + 1
        rows.append([cells_by_column.get(column, "")
                     for column in range(row_width)])
    return rows


def read_xlsx(path: str) -> dict[str, list[list[str]]]:
    """Return {sheet_name: rows} for an .xlsx workbook."""
    with zipfile.ZipFile(path) as workbook:
        shared_strings = _read_shared_strings(workbook)
        sheet_names = _read_sheet_names(workbook)
        worksheet_paths = sorted(
            (name for name in workbook.namelist()
             if name.startswith("xl/worksheets/sheet") and name.endswith(".xml")),
            key=lambda name: int("".join(ch for ch in name if ch.isdigit()) or 0),
        )
        sheets: dict[str, list[list[str]]] = {}
        for ordinal, sheet_path in enumerate(worksheet_paths):
            name = sheet_names[ordinal] if ordinal < len(sheet_names) else sheet_path
            sheets[name] = _read_worksheet(workbook, sheet_path, shared_strings)
        return sheets


def _print_digest(path: str) -> None:
    """Print a structure digest for one workbook: sheets, sizes, sample rows."""
    print(f"\n{'=' * 78}\n{path}\n{'=' * 78}")
    try:
        sheets = read_xlsx(path)
    except (zipfile.BadZipFile, ElementTreeModule.ParseError, KeyError) as error:
        print(f"  ERROR: {type(error).__name__}: {error}")
        return
    for sheet_name, rows in sheets.items():
        nonempty_rows = [row for row in rows if row]
        print(f"  sheet '{sheet_name}': {len(rows)} rows "
              f"({len(nonempty_rows)} non-empty)")
        for row in nonempty_rows[:DIGEST_ROW_LIMIT]:
            cells = [cell[:CELL_DIGEST_WIDTH] for cell in row[:DIGEST_COLUMN_LIMIT]]
            print("    " + " | ".join(cells))


def main(argv: list[str]) -> None:
    """Print a digest of every workbook matched by the CLI glob(s)/path(s)."""
    patterns = argv[1:] or ["research_artifacts/**/*.xlsx"]
    matched_paths: list[str] = []
    for pattern in patterns:
        matched_paths.extend(sorted(glob_module.glob(pattern, recursive=True)))
    if not matched_paths:
        print(f"no .xlsx files matched: {patterns}")
        return
    for path in matched_paths:
        _print_digest(path)


if __name__ == "__main__":
    main(sys.argv)
