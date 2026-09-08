"""Synthetic words/metadata reproduce layout rules; no retailer artwork is copied."""

import copy
import html
import json
import time
from datetime import UTC, date, datetime
from unittest.mock import MagicMock

import pytest
from app.adapters.base import StructuralError
from app.adapters.conad import ConadPDFAdapter, cell_fields, printed_period, resolve
from app.config import Manifest, manifests
from app.domain.catalog import classify
from app.extraction.pdf import Cell, read_cells


def word(text, font="LibelSuit-Regular", size=12, x0=10, x1=30, top=10, bottom=22):
    return dict(
        text=text,
        fontname="FIXTURE+" + font,
        size=size,
        x0=x0,
        x1=x1,
        top=top,
        bottom=bottom,
    )


def fixture_cell():
    return Cell(
        2,
        (0, 0, 185, 185),
        [
            word("PETTO DI POLLO"),
            word("500 g al kg € 6,98", "DINNextLTPro-Condensed"),
            word("SOLO TITOLARI", "DINNextLTPro-Bold"),
            word("3", "DINNextLTPro-HeavyCondensed", 55, 100, 124, 100, 155),
            word(",49", "DINNextLTPro-HeavyCondensed", 28, 124, 150, 120, 148),
            word("€", "DINNextLTPro-HeavyCondensed", 14),
            word(
                "6,99", "DINNextLTPro-BoldCondensed", 10
            ),  # Previous price must not win.
        ],
        "OFFERTA VALIDA DA GIOVEDÌ 10 A MERCOLEDÌ 23 SETTEMBRE 2026",
    )


def campaign():
    return dict(id="fixture-campaign", start=date(2026, 9, 10), end=date(2026, 9, 23))


def test_split_price_package_and_loyalty():
    title, pack, price, loyalty, _ = cell_fields(fixture_cell())
    assert title == "PETTO DI POLLO" and pack.total_quantity == "500"
    assert (
        price.advertised_amount_cents == 349 and price.calculated_unit_price == "6.9800"
    )
    assert loyalty is True and price.previous_amount_cents is None


def test_no_badge_remains_unknown():
    cell = fixture_cell()
    cell.words = [w for w in cell.words if w["text"] != "SOLO TITOLARI"]
    assert cell_fields(cell)[3] is None


@pytest.mark.parametrize(
    "change",
    [
        "second_price",
        "missing_integer",
        "unit_conflict",
        "drained",
        "mechanic",
        "variable_weight",
    ],
)
def test_ambiguous_economic_fields_withheld(change):
    cell = fixture_cell()
    if change == "second_price":
        cell.words.append(word("2,99", "DINNextLTPro-HeavyCondensed", 24))
    if change == "missing_integer":
        cell.words = [w for w in cell.words if w["text"] != "3"]
    if change == "unit_conflict":
        cell.words[1]["text"] = "500 ml al kg € 6,98"
    if change == "drained":
        cell.words[1]["text"] = "500/300 g al kg € 6,98"
    if change == "mechanic":
        cell.words.append(word("acquisto minimo 2"))
    if change == "variable_weight":
        cell.words[1]["text"] = "al kg € 6,98"
    with pytest.raises(ValueError):
        cell_fields(cell)


def test_multipack_total_and_unit_check():
    cell = fixture_cell()
    cell.words[1]["text"] = "conf. 500 g x 2 pezzi al kg € 3,49"
    assert cell_fields(cell)[1].total_quantity == "1000"
    assert cell_fields(cell)[2].calculated_unit_price == "3.4900"
    cell.words[1]["text"] = "500 g al kg € 1,98"
    with pytest.raises(ValueError):
        cell_fields(cell)


def test_percent_is_not_price():
    cell = fixture_cell()
    cell.words = [w for w in cell.words if w["text"] not in ["3", ",49"]]
    cell.words.extend(
        [
            word("-", "DINNextLTPro-HeavyCondensed", 30),
            word("40", "DINNextLTPro-HeavyCondensed", 42),
            word("%", "DINNextLTPro-HeavyCondensed", 24),
            word("3,49", "DINNextLTPro-HeavyCondensed", 20),
        ]
    )
    assert cell_fields(cell)[2].advertised_amount_cents == 349


def test_printed_dates_required_and_secondary_period_rejected():
    assert printed_period(fixture_cell().page_text, campaign())
    assert not printed_period(
        "Offerta valida da giovedì 10 a mercoledì 16 settembre 2026", campaign()
    )
    assert not printed_period(
        "Offerta valida da giovedì 10 a mercoledì 23 settembre 2025", campaign()
    )
    assert not printed_period("Settembre 2026", campaign())


def metadata(store="000350"):
    row = dict(
        title="TEST CONAD EMILIA",
        name="20262619PCONADEMILIA.pdf",
        slug="fixture-campaign",
        pdfUrl="https://www.conad.it/assets/common/volantini/cno/v20262/20262619PCONADEMILIA.pdf",
        validFrom=1788991200000,
        validTo=1790114400000,
    )
    return f'<div data-store-id="{store}" data-flyers="{html.escape(json.dumps([row]))}"></div>'


def test_resolver_store_isolation(monkeypatch):
    monkeypatch.setattr(
        "app.adapters.conad.utcnow", lambda: datetime(2026, 9, 8, tzinfo=UTC)
    )
    m = manifests()["conad-000350"]
    assert resolve(metadata(), m)[0]["id"] == "fixture-campaign"
    with pytest.raises(StructuralError):
        resolve(metadata("000386"), m)
    with pytest.raises(StructuralError):
        resolve("<html>changed layout</html>", m)


def test_extract_has_bbox_and_does_not_publish_secondary_period(monkeypatch):
    cell = fixture_cell()
    wrong = copy.deepcopy(cell)
    wrong.page_text = "altro periodo"
    bad = copy.deepcopy(cell)
    bad.words[1]["text"] = "peso sconosciuto"
    monkeypatch.setattr(
        "app.adapters.conad.read_cells", lambda *a: iter([cell, wrong, bad])
    )
    b = ConadPDFAdapter().extract(
        b"%PDF-fixture",
        "https://www.conad.it/fixture.pdf",
        "capture",
        manifests()["conad-000350"],
        campaign(),
        time.monotonic() + 10,
    )
    assert b.completeness == "partial" and b.extracted == 2 and b.quarantined == 1
    assert b.offers[0].evidence["bbox"] == [0, 0, 185, 185]
    assert b.offers[0].category_id == "carne"


def test_native_rectangle_excludes_neighbor_words(monkeypatch):
    page = MagicMock()
    page.width = 807.874
    page.height = 765.354
    page.page_number = 1
    page.chars = []
    page.dedupe_chars.return_value = page
    page.extract_text.return_value = "dates"
    page.rects = [
        dict(
            width=185,
            height=185,
            x0=0,
            top=0,
            x1=185,
            bottom=185,
            non_stroking_color=(0, 0, 0, 0),
        )
    ]
    words = [word("inside", x0=10, x1=30), word("neighbor", x0=190, x1=210)]

    def crop(box):
        c = MagicMock()
        c.extract_words.return_value = [
            w for w in words if w["x0"] >= box[0] and w["x1"] <= box[2]
        ]
        return c

    page.within_bbox.side_effect = crop
    document = MagicMock()
    document.__enter__.return_value.pages = [page]
    monkeypatch.setattr("app.extraction.pdf.pdfplumber.open", lambda _: document)
    cells = list(read_cells(b"%PDF-fixture", time.monotonic() + 5))
    assert [w["text"] for w in cells[0].words] == ["inside"]
    page.close.assert_called_once()
    with pytest.raises(StructuralError):
        list(read_cells(b"not PDF", time.monotonic() + 5))


def test_unverified_manifest_cannot_be_enabled():
    m = manifests()["conad-000350"].model_dump()
    m["audit_status"] = "candidate"
    with pytest.raises(ValueError):
        Manifest.model_validate(m)


@pytest.mark.parametrize(
    "title,category",
    [
        ("Omogeneizzati alla carne Mellin", "infanzia"),
        ("Affettati Aequilibrium AIA petto di pollo al forno", "salumi"),
        ("Pizza salame", "piatti_pronti"),
        ("Kebab 100% vegetale", "piatti_pronti"),
    ],
)
def test_catalog_context_categories(title, category):
    assert classify(title)["category_id"] == category


def test_retailers_group_multiple_stores(client):
    names = [x["id"] for x in client.get("/api/v1/retailers").json()["items"]]
    assert names.count("conad") == 1 and "coop" in names and "despar" in names
    stores = client.get("/api/v1/targets?q=41012").json()["items"]
    assert len([x for x in stores if x["retailer_id"] == "conad"]) == 3
    assert all(x["type"] == "store" for x in stores)


def test_mixed_period_page_is_withheld():
    text = (
        fixture_cell().page_text
        + " Dal 10 al 16 settembre. Dal 17 al 23 settembre. Dal 24 al 30 settembre 2026."
    )
    assert not printed_period(text, campaign())


def test_pdf_url_must_match_named_campaign(monkeypatch):
    monkeypatch.setattr(
        "app.adapters.conad.utcnow", lambda: datetime(2026, 9, 8, tzinfo=UTC)
    )
    value = metadata().replace(
        "/assets/common/volantini/cno/v20262/20262619PCONADEMILIA.pdf", "/unrelated.pdf"
    )
    with pytest.raises(StructuralError):
        resolve(value, manifests()["conad-000350"])
