"""Bounded native PDF words inside actual source-drawn product rectangles.

No OCR and no nearest-price matching across cells. Profiles must be audited for
one layout family; callers interpret economic fields and publish only after QA.
"""

import io
import time
from dataclasses import dataclass

import pdfplumber
from app.adapters.base import StructuralError


@dataclass
class Cell:
    page: int
    bbox: tuple[float, float, float, float]
    words: list[dict]
    page_text: str


def read_cells(body: bytes, deadline: float, max_pages: int = 60):
    if len(body) > 30 * 1024 * 1024 or not body.startswith(b"%PDF-"):
        raise StructuralError("PDF testuale non riconosciuto o troppo grande")
    with pdfplumber.open(io.BytesIO(body)) as doc:
        if len(doc.pages) > max_pages:
            raise StructuralError("PDF oltre il limite di pagine")
        for page in doc.pages:
            if time.monotonic() >= deadline:
                raise StructuralError("Tempo massimo di elaborazione PDF raggiunto")
            # Dimension/font/layout guard for the audited Conad CNO print family.
            if abs(page.width - 807.874) > 1 or abs(page.height - 765.354) > 1:
                page.close()
                continue
            if len(page.chars) > 20000:
                raise StructuralError("Pagina PDF oltre il limite di caratteri")
            clean = page.dedupe_chars()
            text = (
                (clean.extract_text() or "")
                + "\n"
                + "".join(c["text"] for c in clean.chars if not c["upright"])
            )
            boxes = set()
            for rect in clean.rects:
                if (
                    180 <= rect["width"] <= 190
                    and 150 <= rect["height"] <= 190
                    and rect.get("non_stroking_color") == (0, 0, 0, 0)
                ):
                    bbox = tuple(rect[k] for k in ("x0", "top", "x1", "bottom"))
                    if bbox in boxes or bbox[0] < 0 or bbox[2] > page.width:
                        continue
                    boxes.add(bbox)
                    words = clean.within_bbox(bbox).extract_words(
                        extra_attrs=["fontname", "size"]
                    )
                    yield Cell(page.page_number, bbox, words, text)
            page.close()
