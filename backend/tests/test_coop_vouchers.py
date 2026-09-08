"""Synthetic coupon text tests mechanics, never supplies the public catalog."""

import hashlib
from datetime import UTC, datetime
from unittest.mock import Mock

import pytest
from app.adapters import coop
from app.adapters.base import StructuralError
from app.config import manifests
from app.domain.catalog import Offer, normalized
from app.jobs.queue import claim, enqueue, publish
from app.pages import safe_offer
from app.storage.db import OfferRow, Session
from bs4 import BeautifulSoup
from pydantic import ValidationError

M = manifests()["coop-carpi-buoni"]
URL = "https://www.coopalleanza3-0.it/volantino/promozione/featured/3967-ipercoop-il-borgogioioso/spendi-riprendi-scuola.html"
STORE = f'<link rel="canonical" href="{M.entry_urls[0]}"><a href="{URL}">Buono</a>'
HTML = f'''<!-- synthetic fixture -->
<link rel="canonical" href="{URL}"><section data-component="bannerVolantino" data-pdv_id="9012"></section>
<div class="content-title black"><div class="h1">Spendi 30€ di cartoleria &amp; riprendi 10€<div class="h3">Dal 16 luglio al 20 settembre</div></div>
<div class="promotion-content"><p>Fino al 20 settembre 2026 acquista: ogni 30€ di spesa nel reparto cartoleria ottieni un buono sconto 10€ da utilizzare entro il 7 ottobre su una spesa minima di 30€.</p>
<p>Massimo 3 buoni nello stesso scontrino. Sconto massimo 30€.</p>
<h5>Il buono non è cumulabile con buoni di diversa tipologia. Il buono non è utilizzabile per latte infanzia tipo 1 e EasyCoop.</h5>
<p>Anche se non sei socio o socia. I buoni digitali: attivali prima della spesa. Ogni buono ottenuto è utilizzabile una sola volta. Iniziativa valida in tutti gli Ipercoop.</p></div></div>'''


def admit_fixture(monkeypatch, html=HTML):
    raw = (
        BeautifulSoup(html, "html.parser")
        .select_one(".promotion-content")
        .get_text(" ", strip=True)
    )
    monkeypatch.setattr(
        coop,
        "AUDITED_TERMS_SHA256",
        hashlib.sha256(normalized(raw).encode()).hexdigest(),
    )
    monkeypatch.setattr(coop, "utcnow", lambda: datetime(2026, 9, 8, 10, tzinfo=UTC))
    return coop.extract(html, URL, "synthetic-capture", M)


def test_separate_benefit_periods_and_no_product_price(monkeypatch):
    o = admit_fixture(monkeypatch).offers[0]
    assert o.price is None and o.offer_type == "future_voucher"
    assert o.benefit.amount_cents == 1000
    assert o.benefit.earning_minimum_spend_cents == 3000
    assert o.benefit.redemption_minimum_spend_cents == 3000
    assert (
        o.benefit.earning_validity.end_at_exclusive.isoformat()
        == "2026-09-20T22:00:00+00:00"
    )
    assert o.validity.end_at_exclusive.isoformat() == "2026-10-07T22:00:00+00:00"
    assert o.benefit.redemption_validity.start_at is None
    assert o.conditions.loyalty_required is False
    assert safe_offer(o.model_dump(mode="json"))["evidence"]["raw_price"] is None
    bad = o.model_dump()
    bad["offer_type"] = "product_offer"
    with pytest.raises(ValidationError):
        Offer.model_validate(bad)


@pytest.mark.parametrize(
    "before,after",
    [
        ('data-pdv_id="9012"', 'data-pdv_id="9530"'),
        ("Dal 16 luglio al 20 settembre", "Dal 16 luglio al 21 settembre"),
        ("Fino al 20 settembre 2026", "Fino al 20 settembre"),
        ("Sconto massimo 30€", "Sconto massimo 40€"),
        ("spesa minima di 30€", "spesa minima non specificata"),
        ("non è utilizzabile", "è utilizzabile"),
    ],
)
def test_changed_economics_rejected(monkeypatch, before, after):
    with pytest.raises(StructuralError):
        admit_fixture(monkeypatch, HTML.replace(before, after))


def test_added_unrecognized_restriction_requires_new_audit(monkeypatch):
    admit_fixture(monkeypatch)
    changed = HTML.replace("</h5>", " Solo con carta e almeno 90€ di spesa.</h5>")
    with pytest.raises(StructuralError):
        coop.extract(changed, URL, "synthetic", M)


def test_collector_verifies_store_links_and_redirect(monkeypatch):
    admit_fixture(monkeypatch)
    fetcher = Mock()
    fetcher.fetch.side_effect = [(STORE, "a", M.entry_urls[0]), (HTML, "b", URL)]
    assert len(coop.collect_coop(M, fetcher, Mock()).offers) == 1
    assert coop.resolve(STORE, M) == URL
    with pytest.raises(StructuralError):
        coop.resolve(STORE.replace(URL, "https://example.invalid/"), M)
    fetcher.fetch.side_effect = [(STORE, "a", "https://example.invalid/")]
    with pytest.raises(StructuralError):
        coop.collect_coop(M, fetcher, Mock())


def test_publication_products_and_coupons_separated(client, monkeypatch):
    batch = admit_fixture(monkeypatch)
    import app.api as api

    monkeypatch.setattr(api, "utcnow", lambda: datetime(2026, 9, 8, 10, tzinfo=UTC))
    enqueue([M.source_id])
    job = claim()
    publish(job.id, job.lease_token, batch)
    p = {"target_ids": M.source_id}
    assert client.get("/api/v1/offers", params=p).json()["total"] == 0
    assert (
        client.get(
            "/api/v1/offers", params={**p, "sort": "price", "price_basis": "pack"}
        ).json()["total"]
        == 0
    )
    r = client.get("/api/v1/coupons", params=p).json()
    assert len(r["items"]) == 1 and r["items"][0]["price"] is None
    target = next(
        t
        for t in client.get("/api/v1/targets").json()["items"]
        if t["id"] == M.source_id
    )
    assert target["availability"] == {"current": 0, "future": 0, "coupons": 1}
    assert client.get("/api/v1/coupons").status_code == 422
    # A published voucher cannot survive freshness or commercial expiry in the feed.
    monkeypatch.setattr(api, "utcnow", lambda: datetime(2026, 10, 8, 10, tzinfo=UTC))
    assert client.get("/api/v1/coupons", params=p).json()["items"] == []


def test_conflicting_benefits_never_choose_larger(monkeypatch):
    batch = admit_fixture(monkeypatch)
    other = batch.offers[0].model_copy(deep=True)
    other.benefit.amount_cents = 2000
    batch.offers.append(other)
    enqueue([M.source_id])
    job = claim()
    publish(job.id, job.lease_token, batch)
    with Session() as s:
        assert s.query(OfferRow).count() == 0
