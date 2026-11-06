# -*- coding: utf-8 -*-
"""Extract text (paragraphs + tables) from a .docx to a UTF-8 txt file."""
import sys
from docx import Document
from docx.table import Table
from docx.text.paragraph import Paragraph
from docx.oxml.ns import qn


def iter_block_items(parent):
    body = parent.element.body
    for child in body.iterchildren():
        if child.tag == qn('w:p'):
            yield Paragraph(child, parent)
        elif child.tag == qn('w:tbl'):
            yield Table(child, parent)


def main(src, dst):
    doc = Document(src)
    out = []
    for block in iter_block_items(doc):
        if isinstance(block, Paragraph):
            text = block.text.strip()
            out.append(text)
        else:
            out.append("[TABLE]")
            for row in block.rows:
                cells = []
                seen = set()
                for cell in row.cells:
                    if id(cell._tc) in seen:
                        continue
                    seen.add(id(cell._tc))
                    cells.append(cell.text.replace("\n", " / ").strip())
                out.append(" | ".join(cells))
            out.append("[/TABLE]")
    text = "\n".join(out)
    with open(dst, "w", encoding="utf-8") as f:
        f.write(text)
    print(f"extracted {len(text)} chars, {len(out)} blocks -> {dst}")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
