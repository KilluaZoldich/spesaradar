"""Synthetic fixtures for the observed MD schema. Never loaded into the live feed."""

import json

import pytest
from app.adapters.base import StructuralError
from app.adapters.md import MECHANICS, MDAdapter
from app.config import manifests


def page(**changes):
    row = dict(
        idProduct=100,
        idVolantino=900,
        pageNumber=1,
        code="fixture-100",
        name="Petto di pollo",
        brand="",
        category="CARNI",
        section="PROMO",
        um="PZ",
        weight=500,
        weight_um="g",
        price=4.99,
        priceOff=3.49,
        cardMD=False,
        priceStart=False,
        contribute=0,
        prezzoPartenzaSIF=0,
        **{key: False for key in MECHANICS},
    )
    row.update(changes)
    return "<script>var data = " + json.dumps([row]) + ";</script>"


def parse(**changes):
    return (
        MDAdapter()
        .extract(
            page(**changes),
            "https://volantino.mdspa.it/fixture.html",
            "synthetic",
            manifests()["md-151"],
        )
        .offers[0]
    )


def test_pack_price_and_evidence():
    o = parse()
    assert o.price.advertised_amount_cents == 349
    assert o.price.calculated_unit_price == "6.9800"
    assert o.scope["type"] == "store" and "RUBENS" in o.scope["label"]
    assert o.evidence["price_field"] == "priceOff"
    assert o.validity.end_at_exclusive is None


def test_card_uses_real_card_price_not_normal_promotion():
    o = parse(cardMD=True, prezzoPartenzaSIF=2.99)
    assert o.price.advertised_amount_cents == 299
    assert o.conditions.loyalty_required is True
    assert "Buona Spesa Card" in o.conditions.raw_text
    assert o.evidence["price_field"] == "prezzoPartenzaSIF"


def test_kg_is_not_a_pack_price():
    o = parse(um="KG", weight=1000)
    assert o.price.basis == "kg" and o.price.calculated_unit_price is None
    assert o.package.total_quantity is None


def test_drained_weight_does_not_silently_become_comparison_basis():
    o = parse(description="Peso netto 500 g, peso sgocciolato 300 g")
    assert o.package.quantity_basis == "unknown"
    assert o.price.calculated_unit_price is None
    assert o.price.unit_price_basis is None
    assert o.price.calculation is None


@pytest.mark.parametrize(
    "changes",
    [
        {"um": ""},
        {"priceOff": 0},
        {"cardMD": None},
        {"cardMD": True, "prezzoPartenzaSIF": 0},
        {"secondo50": True},
        {"webstoreUrl": "https://webstore.mdspa.it/"},
        {"sellOutStart": "2026-09-18T00:00:00"},
        {"section": "BUONA SPESA CARD"},
    ],
)
def test_uncertain_price_scope_or_condition_is_withheld(changes):
    with pytest.raises(StructuralError):
        parse(**changes)


def test_minimum_spend_preserved():
    assert parse(contribute=25).conditions.minimum_spend_cents == 2500


def test_explicit_dietary_flags_only():
    assert "Senza glutine" not in parse().tags
    assert "Senza glutine" in parse(glutenFree=True).tags


def test_broken_structure_and_changed_store_fail():
    m = manifests()["md-151"]
    with pytest.raises(StructuralError):
        MDAdapter().extract("<html></html>", m.entry_urls[0], "synthetic", m)
    with pytest.raises(StructuralError):
        MDAdapter.resolve(
            '<a id="go_back">Altra sede</a><div data-flyer data-flyer-code="nord"></div>',
            m,
        )
    html = f'<a id="go_back">{m.scope_label}</a><div data-flyer data-flyer-code="nord_atm_nogas"></div>'
    assert (
        MDAdapter.resolve(html, m)
        == "https://service-volantino.mdspa.it/nord_atm_nogas"
    )
