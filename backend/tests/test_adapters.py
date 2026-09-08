import html
import json
from pathlib import Path

import pytest
from app.adapters.base import StructuralError
from app.adapters.eurospin import EurospinAdapter
from app.adapters.lidl import LidlAdapter

URL = "https://www.lidl.it/c/carne-e-pesce-kw-36-26/a10101811"


def lidl_document(d):
    return (
        '<a href="/c/carne-e-pesce-kw-36-26/a10101811">Da giovedì 3/09</a><div data-grid-data="'
        + html.escape(json.dumps(d))
        + '"></div>'
    )


def data():
    return json.loads(Path("tests/fixtures/lidl-synthetic.json").read_text())


def test_lidl_fixture():
    b = LidlAdapter().extract(lidl_document(data()), URL, "fixture")
    o = b.offers[0]
    assert (
        o.price.advertised_amount_cents == 349
        and o.package.total_quantity == "500"
        and o.validity.end_at_exclusive.isoformat() == "2026-09-09T22:00:00+00:00"
    )


def test_lidl_future_store_flag_is_not_channel():
    d = data()
    d["store"] = False
    assert LidlAdapter().extract(lidl_document(d), URL, "fixture").offers


def test_lidl_old_product_start_not_current_campaign():
    d = data()
    d["storeStartDate"] = 1782943200
    d.pop("storeEndDate")
    o = LidlAdapter().extract(lidl_document(d), URL, "fixture").offers[0]
    assert o.validity.start_at.isoformat() == "2026-09-02T22:00:00+00:00"
    assert o.validity.end_at_exclusive.isoformat() == "2026-09-09T22:00:00+00:00"


def test_lidl_conditional_price():
    d = data()
    p = d["price"]
    d["price"] = {"currencyCode": "EUR"}
    d["lidlPlus"] = [{"price": p, "lidlPlusText": "Con Lidl Plus"}]
    d["regionsPrices"] = {
        "1": {
            "currentLidlPlusPrice": {
                "price": {**p, "endDateExclusive": "2026-09-09T22:00Z"}
            }
        }
    }
    o = LidlAdapter().extract(lidl_document(d), URL, "fixture").offers[0]
    assert (
        o.conditions.loyalty_required is True and o.price.advertised_amount_cents == 349
    )


def test_lidl_regional_prices_quarantined():
    d = data()
    d["regionsPrices"]["2"] = {"currentPrice": {"price": 2.99}}
    with pytest.raises(StructuralError):
        LidlAdapter().extract(lidl_document(d), URL, "fixture")


def test_eurospin_multipack():
    b = EurospinAdapter().extract(
        Path("tests/fixtures/eurospin-synthetic.html").read_text(),
        "https://www.eurospin.it/promozioni/",
        "fixture",
    )
    assert (
        b.offers[0].price.calculated_unit_price == "3.4900"
        and b.offers[0].conditions.loyalty_required is None
    )


@pytest.mark.parametrize("adapter", [LidlAdapter(), EurospinAdapter()])
def test_layout_break_is_not_success(adapter):
    with pytest.raises(StructuralError):
        adapter.extract(
            "<html>Changed template</html>", "https://www.lidl.it/", "fixture"
        )


def test_eurospin_does_not_invent_year():
    doc = Path("tests/fixtures/eurospin-synthetic.html").read_text().replace("2026", "")
    with pytest.raises(StructuralError):
        EurospinAdapter().extract(doc, "https://www.eurospin.it/promozioni/", "fixture")


def test_brand_only_fulltitle_uses_actual_source_title():
    d = data()
    d["fullTitle"] = "Alpenfest"
    d["brand"] = {"name": "Alpenfest", "showBrand": True}
    d["title"] = "Cavolo rosso"
    o = LidlAdapter().extract(lidl_document(d), URL, "fixture").offers[0]
    assert o.title == "Cavolo rosso" and o.evidence["fields"]["title"] == "title"
