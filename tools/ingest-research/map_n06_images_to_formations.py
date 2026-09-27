"""Walk the NCAA 06 Offensive Plays.docx and map each image (by document order)
to the most-recent Heading-1 formation name.

Emits /tmp/n06-work/image_to_formation.json:
    {"1": "Ace 4WR Trips", "2": "Ace 4WR Trips", ...}

The image indices match the 0001.png ... ordering used by extract_docx_images.py.
"""
import json
from pathlib import Path

from docx import Document
from docx.oxml.ns import qn

DOC = Path(
    "research_artifacts/PS2/NCAA Football 06-20260517T193750Z-3-001/"
    "NCAA Football 06/Playbooks/Offensive Plays.docx"
)

PIC_TAGS = {qn("w:drawing"), qn("w:pict")}


def _walk_body_elements(doc):
    """Yield (kind, element) for each block element in body order."""
    for child in doc.element.body.iterchildren():
        if child.tag == qn("w:p"):
            yield "p", child
        elif child.tag == qn("w:tbl"):
            for row in child.findall(qn("w:tr")):
                for cell in row.findall(qn("w:tc")):
                    for p in cell.findall(qn("w:p")):
                        yield "p", p


def _paragraph_text(p_elem) -> str:
    return "".join(t.text or "" for t in p_elem.iter(qn("w:t")))


def _paragraph_style(p_elem) -> str:
    style_el = p_elem.find(f"{qn('w:pPr')}/{qn('w:pStyle')}")
    if style_el is None:
        return ""
    return style_el.get(qn("w:val")) or ""


def _paragraph_image_count(p_elem) -> int:
    return sum(1 for tag in PIC_TAGS for _ in p_elem.iter(tag))


def main() -> None:
    doc = Document(DOC)
    image_to_formation: dict[int, str] = {}
    current_formation: str | None = None
    image_index = 0

    for kind, elem in _walk_body_elements(doc):
        style = _paragraph_style(elem)
        text = _paragraph_text(elem).strip()
        if style in {"Heading1", "Heading 1"} and text:
            current_formation = text
        n_images = _paragraph_image_count(elem)
        for _ in range(n_images):
            image_index += 1
            if current_formation is not None:
                image_to_formation[image_index] = current_formation

    out = Path("/tmp/n06-work/image_to_formation.json")
    out.write_text(json.dumps(image_to_formation, indent=2))
    formations = sorted(set(image_to_formation.values()))
    print(f"mapped {image_index} images across {len(formations)} formations")
    print(f"first formations: {formations[:10]}")
    print(f"last formations:  {formations[-10:]}")


if __name__ == "__main__":
    main()
