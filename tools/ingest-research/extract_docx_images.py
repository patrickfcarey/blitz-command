#!/usr/bin/env python3
"""Extract a .docx file's embedded images in document (reading) order.

The Playbook Gamer per-team playbook .docx files (research_artifacts/, git-
ignored) are, for several games, just an ordered sequence of screenshots with
no text — e.g. each Madden NFL 25 team playbook is ~142 in-game play-screen
images. Reading those images in the order they appear in the document is what
reconstructs the playbook, so this tool resolves the document-order image
sequence — which the `image1.jpg` / `image2.jpg` zip-entry names do NOT
preserve (they sort lexically: image1, image10, image100, image2, ...).

As a module:
    from extract_docx_images import ordered_image_entries, extract_images_in_order

As a CLI:
    python3 tools/ingest-research/extract_docx_images.py <file.docx> <out-dir>

Writes the images to <out-dir> as 0001.<ext>, 0002.<ext>, ... in document order.
"""
from __future__ import annotations

import shutil
import sys
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ElementTreeModule

WORD_NS = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
DRAWING_NS = "{http://schemas.openxmlformats.org/drawingml/2006/main}"
RELATIONSHIP_NS = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"
PACKAGE_REL_NS = "{http://schemas.openxmlformats.org/package/2006/relationships}"


def _relationship_targets(document: zipfile.ZipFile) -> dict[str, str]:
    """Map each relationship id to its target path within the .docx package."""
    targets: dict[str, str] = {}
    root = ElementTreeModule.fromstring(
        document.read("word/_rels/document.xml.rels"))
    for relationship in root.iter(PACKAGE_REL_NS + "Relationship"):
        targets[relationship.get("Id", "")] = relationship.get("Target", "")
    return targets


def ordered_image_entries(docx_path: str | Path) -> list[str]:
    """Return the .docx's image zip-entry names, in document (reading) order.

    Walks the `<a:blip>` image references in `word/document.xml` top to bottom
    and resolves each through the relationships table to its media entry.
    """
    with zipfile.ZipFile(docx_path) as document:
        targets = _relationship_targets(document)
        body = ElementTreeModule.fromstring(document.read("word/document.xml"))
        ordered: list[str] = []
        for blip in body.iter(DRAWING_NS + "blip"):
            embed_id = blip.get(RELATIONSHIP_NS + "embed")
            target = targets.get(embed_id or "")
            if not target:
                continue
            # Relationship targets are relative to word/ — normalise to a
            # full zip-entry name.
            entry = target if target.startswith("word/") else f"word/{target}"
            ordered.append(entry)
        return ordered


def extract_images_in_order(docx_path: str | Path, out_dir: str | Path) -> int:
    """Extract every image to out_dir as NNNN.<ext> in document order.

    Returns the number of images written.
    """
    out_path = Path(out_dir)
    out_path.mkdir(parents=True, exist_ok=True)
    entries = ordered_image_entries(docx_path)
    with zipfile.ZipFile(docx_path) as document:
        for sequence_number, entry in enumerate(entries, start=1):
            suffix = Path(entry).suffix or ".bin"
            destination = out_path / f"{sequence_number:04d}{suffix}"
            with document.open(entry) as source, open(destination, "wb") as sink:
                shutil.copyfileobj(source, sink)
    return len(entries)


def main(argv: list[str]) -> None:
    """CLI: extract <file.docx>'s images to <out-dir> in document order."""
    if len(argv) != 3:
        print("usage: extract_docx_images.py <file.docx> <out-dir>",
              file=sys.stderr)
        sys.exit(1)
    count = extract_images_in_order(argv[1], argv[2])
    print(f"extracted {count} images in document order to {argv[2]}")


if __name__ == "__main__":
    main(sys.argv)
