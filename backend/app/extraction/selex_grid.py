"""Native text cells of the audited Selex 29x32 monthly leaflet, not generic PDF OCR."""

from app.adapters.base import StructuralError


def cells(page):
    if abs(page.width - 822.047) > 1 or abs(page.height - 907.087) > 1:
        raise StructuralError("Dimensioni del profilo Selex cambiate")
    page = page.dedupe_chars(tolerance=1)
    vertical = [
        line
        for line in page.lines
        if abs(line["x1"] - line["x0"]) < 1
        and 100 < line["top"] < 880
        and 150 < line["height"] < 180
        and 25 < line["x0"] < 790
    ]
    groups = []
    for line in sorted(vertical, key=lambda line: line["top"]):
        group = next((g for g in groups if abs(g[0]["top"] - line["top"]) < 3), None)
        if group is None:
            groups.append([line])
        else:
            group.append(line)
    for group in groups:
        if not 2 <= len(group) <= 4:
            continue
        xs = [22.7] + sorted(set(round(line["x0"], 2) for line in group)) + [798.9]
        y0, y1 = (
            min(line["top"] for line in group) - 5,
            max(line["bottom"] for line in group) + 9,
        )
        for left, right in zip(xs, xs[1:]):
            bbox = (left, y0, right, y1)
            cell = page.crop(bbox)

            def content(font, minsize=0):
                return (
                    cell.filter(
                        lambda c: (
                            c["object_type"] == "char"
                            and c["fontname"].endswith(font)
                            and c["size"] > minsize
                        )
                    ).extract_text()
                    or ""
                )

            yield {
                "bbox": bbox,
                "description": content("BarlowCondensed-Medium"),
                "price": content("BarlowCondensed-Bold", 20),
                "unit": content("BarlowCondensed-Regular"),
                "raw": cell.extract_text() or "",
            }
