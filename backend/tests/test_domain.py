from datetime import UTC, date, datetime, timedelta

import pytest
from app.domain.catalog import (
    classify,
    end_exclusive,
    money,
    package_and_price,
    temporal,
)
from helpers import offer


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("€ 1,99", 199),
        ("1,99 €", 199),
        ("1,99\u00a0€", 199),
        ("1.299,00 €", 129900),
        (None, None),
    ],
)
def test_money(raw, expected):
    assert money(raw) == expected


@pytest.mark.parametrize("raw", ["-1,99 €", "8,9", "GBP 3,99", "1,99 3,99", ""])
def test_ambiguous_money(raw):
    with pytest.raises(ValueError):
        money(raw)


@pytest.mark.parametrize(
    "pack,expected",
    [("500 g", "6.9800"), ("2 × 500 g", "3.4900"), ("2x 500 g confezione", "3.4900")],
)
def test_unit_calculation(pack, expected):
    assert (
        package_and_price(pack, 349, "pack", "3,49 €")[1].calculated_unit_price
        == expected
    )


def test_variable_weight():
    pack, price = package_and_price("al kg", 799, "kg", "7,99 €/kg")
    assert (
        pack.total_quantity is None
        and price.basis == "kg"
        and price.calculated_unit_price is None
    )


def test_drained_or_appliance_not_guessed():
    for raw in ["6 x 400 g/sgocc. 1,44 kg", "serbatoio da 300 ml", "300-500 g"]:
        pack, price = package_and_price(raw, 399, "pack", "3,99 €")
        assert pack.total_quantity is None and price.calculated_unit_price is None


@pytest.mark.parametrize(
    "title,cat",
    [
        ("Petto di pollo", "carne"),
        ("Alimento per gatti con pollo", "animali"),
        ("Uovo di cioccolato", "dolci"),
        ("Uova fresche", "latticini_uova"),
        ("Latte detergente", "cura_persona"),
        ("Latte intero", "latticini_uova"),
        ("Burger vegetale", "piatti_pronti"),
        ("Gelato al cioccolato", "dolci"),
        ("Biscotti", "dolci"),
        ("Patatine in sacchetto", "snack_salati"),
        ("Oggetto ambiguo", "altri"),
        ("Salamini affumicati", "salumi"),
        ("Mini toast con prosciutto", "piatti_pronti"),
    ],
)
def test_classification(title, cat):
    assert classify(title)["category_id"] == cat


def test_tags_evidence():
    assert "Surgelato" not in classify("Gelato al cioccolato")["tags"]
    assert (
        "Surgelato"
        in classify("Gelato al cioccolato", description="Prodotto surgelato")["tags"]
    )
    assert "Senza glutine" not in classify("Riso")["tags"]


@pytest.mark.parametrize(
    "day,expected",
    [
        ("2026-03-29", "2026-03-29T22:00:00+00:00"),
        ("2026-10-25", "2026-10-25T23:00:00+00:00"),
        ("2026-12-31", "2026-12-31T23:00:00+00:00"),
    ],
)
def test_local_end(day, expected):
    assert end_exclusive(date.fromisoformat(day)).isoformat() == expected


def test_expiry_stale_independent():
    o = offer().model_dump(mode="json")
    now = datetime.now(UTC)
    o["validity"]["end_at_exclusive"] = (now - timedelta(seconds=1)).isoformat()
    assert temporal(o, now) == ("expired", "fresh")
    o["validity"]["end_at_exclusive"] = None
    o["last_verified_at"] = (now - timedelta(hours=49)).isoformat()
    assert temporal(o, now)[1] == "hidden"


def test_identity_format():
    assert offer(format="400 g").id != offer(format="500 g").id


def test_unknown_loyalty():
    assert offer().conditions.loyalty_required is None


@pytest.mark.parametrize(
    "title,original,expected",
    [
        ("Aceto di vino bianco", None, "dispensa"),
        ("Focaccia ripiena con mortadella e mozzarella", None, "pane_forno"),
        ("Pancetta arrotolata", "Carne e pollame", "salumi"),
        ("Stick di salame", "Carne e pollame", "salumi"),
        ("Latte di cocco BIO", None, "dispensa"),
        ("Pagnotta ai cereali", None, "pane_forno"),
        ("Pretzel con sale marino", None, "snack_salati"),
        ("Contorno di patate, carote, zucchine e olive", None, "piatti_pronti"),
    ],
)
def test_live_classification_regressions(title, original, expected):
    assert classify(title, original)["category_id"] == expected


@pytest.mark.parametrize(
    "title,original,expected",
    [
        ("W5 Pasta lavamani", None, "cura_persona"),
        ("Crauti al vino bianco", None, "dispensa"),
        ("Würstel classico", "Carne e pollame", "salumi"),
        ("Trancino ai 5 cereali", None, "altri"),
    ],
)
def test_nonfood_and_ingredient_ambiguities(title, original, expected):
    assert classify(title, original)["category_id"] == expected
