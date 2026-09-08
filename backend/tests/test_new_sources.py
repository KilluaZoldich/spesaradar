"""Synthetic fixtures: regression tests, never proof of live coverage."""

import json
from datetime import date

import pytest
from app.adapters.base import StructuralError
from app.adapters.despar import DesparAdapter
from app.adapters.famila import resolve
from app.config import manifests


def html(card, scope="/it/punto-vendita-interspar/819/carpi/"):
    return f'''<section class="punto_vendita_selezionato"><a href="{scope}">Carpi</a></section>
    <div id="volantino-per-categoria"><div class="validita_volantino">Offerte valide dal 27.08.2026 al 10.09.2026</div>
    <div id="contenitoreBoxOfferte"><div class="anteprima_offerta">{card}</div></div></div>'''


def card(extra="", classes="anteprima_offerta_link", price="2", basis="al pz."):
    return f'''<a class="{classes}" href="https://www.despar.it/it/offerta/123/prodotto/">
    <div class="anteprima_offerta_titolo">Mozzarelle</div><div class="anteprima_offerta_peso">3x100 g</div>
    <div class="anteprima_offerta_prezzo"><strong><span>{price}</span>,19 €</strong>
    <span class="etichetta_prezzo">{basis}</span></div>{extra}</a>'''


def test_despar_package_money_scope():
    b = DesparAdapter().extract(
        html(card()),
        "https://www.despar.it/it/volantino-digitale/819/",
        "fixture",
        manifests()["despar-819"],
    )
    o = b.offers[0]
    assert o.price.advertised_amount_cents == 219
    assert o.package.total_quantity == "300"
    assert o.price.calculated_unit_price is None  # net/drained not verified
    assert o.conditions.loyalty_required is None
    assert o.validity.end_at_exclusive.isoformat() == "2026-09-10T22:00:00+00:00"


@pytest.mark.parametrize(
    "content",
    [
        card('<div class="prezzo_finale">3 pz. 6,38</div>'),
        card(classes="anteprima_offerta_link anteprima_offerta_link_offerte_esclusive"),
        card('<div class="contenitore_offerta_scontata">Sconto extra app</div>'),
        card(price=""),
        card(basis="da"),
    ],
)
def test_despar_no_cheap_conditional_price(content):
    b = DesparAdapter().extract(
        html(content), "https://www.despar.it/", "fixture", manifests()["despar-819"]
    )
    assert not b.offers and b.quarantined == 1


def test_despar_scope_and_broken_layout():
    for data in [html(card(), "/it/punto-vendita/999/"), "<html></html>"]:
        with pytest.raises(StructuralError):
            DesparAdapter().extract(
                data, "https://www.despar.it/", "fixture", manifests()["despar-819"]
            )


def test_famila_only_store_monthly():
    m = manifests()["famila-carpi"]
    monthly = {
        "title": "FAMILA SELEX SETTEMBRE",
        "startDate": "20260903000000",
        "endDate": "20260930000000",
        "linkDigitalFlyer": "https://promo.smt.cloud/digitalflyer/files/00000000-1111-2222-3333-444444444444/FA-00.pdf",
    }

    def fixture(url, flyer):
        return f'''<link rel="canonical" href="{url}"><script id="__NEXT_DATA__">{json.dumps({"props": {"pageProps": {"store": {"flyers": [flyer]}}}})}</script>'''

    assert resolve(fixture(m.entry_urls[0], monthly), m)["end"] == date(2026, 9, 30)
    for url, flyer in [
        ("https://www.famila.it/altro", monthly),
        (m.entry_urls[0], dict(monthly, title="FAMILA SOTTOCOSTO")),
        (
            m.entry_urls[0],
            dict(monthly, linkDigitalFlyer="https://evil.invalid/file.pdf"),
        ),
    ]:
        with pytest.raises(StructuralError):
            resolve(fixture(url, flyer), m)


def test_famila_pdf_arithmetic_quarantine_and_tags(monkeypatch):
    from unittest.mock import MagicMock

    from app.adapters.famila import FamilaAdapter

    good = {
        "description": "SELEX PISELLI SURGELATI\n2 x 500 g",
        "price": "3,49\n€",
        "unit": "al kg € 3,49",
        "bbox": (20, 100, 200, 300),
        "raw": "SELEX PISELLI SURGELATI 2 x 500 g 3,49 €",
    }
    rows = [
        good,
        dict(good, unit="al kg € 6,98"),
        dict(good, unit="al l € 3,49"),
        dict(good, raw="solo con carta"),
        dict(good, price="3,49 2,49 €"),
    ]
    doc = MagicMock()
    doc.__enter__.return_value.pages = [object(), object()]
    monkeypatch.setattr("app.adapters.famila.pdfplumber.open", lambda _: doc)
    monkeypatch.setattr("app.adapters.famila.cells", lambda _: iter(rows))
    campaign = {
        "id": "synthetic",
        "title": "Fixture mensile",
        "start": date(2026, 9, 3),
        "end": date(2026, 9, 30),
    }
    b = FamilaAdapter().extract(
        b"fixture",
        "https://promo.smt.cloud/fixture",
        "fixture",
        manifests()["famila-carpi"],
        campaign,
    )
    assert len(b.offers) == 2 and b.quarantined == 8
    assert b.offers[0].price.advertised_amount_cents == 349
    assert b.offers[0].package.total_quantity == "1000"
    assert "Surgelato" in b.offers[0].tags
    assert b.offers[0].conditions.loyalty_required is None


class FakeDesparFetcher:
    def __init__(self, pages=2, changed=False):
        self.pages = pages
        self.changed = changed
        self.calls = []
        self.selected = False

    def request(self, url, **kwargs):
        assert url == manifests()["despar-819"].selection_endpoint
        assert kwargs["method"] == "POST"
        assert set(kwargs["fields"]) == {"_method"}
        self.selected = True
        self.calls.append(("POST", url))

    def fetch(self, url):
        self.calls.append(("GET", url))
        m = manifests()["despar-819"]
        if url == m.entry_urls[0]:
            return (
                f'<form method="post" id="formPuntoVenditaPreferito" action="{m.selection_endpoint}"><input name="_method" value="POST"></form>',
                "fixture",
                url,
            )
        assert self.selected  # same scope session before any products
        number = int(url.split("page:")[-1]) if "page:" in url else 1
        data = html(card().replace("/123/", "/" + str(number) + "/"))
        if self.changed and number == 2:
            data = data.replace("27.08.2026", "28.08.2026")
        if number < self.pages:
            data = data.replace(
                "</div></div>",
                f'</div><a rel="next" href="/it/volantino-digitale/page:{number + 1}">Next</a></div>',
            )
        return data, "fixture", url


def test_despar_public_form_and_bounded_pagination():
    from app.adapters.despar import collect_despar

    m = manifests()["despar-819"]
    f = FakeDesparFetcher()
    b = collect_despar(m, f, lambda _: None)
    assert len(b.offers) == 2 and not b.failed
    assert len(f.calls) == 4  # store, form, two pages
    f = FakeDesparFetcher(pages=77)
    b = collect_despar(m, f, lambda _: None)
    assert len(b.offers) == 20 and b.completeness == "partial"
    assert len(f.calls) == 22


def test_despar_campaign_change_keeps_valid_first_page():
    from app.adapters.despar import collect_despar

    b = collect_despar(
        manifests()["despar-819"], FakeDesparFetcher(changed=True), lambda _: None
    )
    assert len(b.offers) == 1 and len(b.failed) == 1 and b.completeness == "partial"


def test_famila_collect_rejects_redirects(monkeypatch):
    from unittest.mock import MagicMock

    from app.adapters.famila import collect_famila

    m = manifests()["famila-carpi"]
    f = MagicMock()
    f.fetch.return_value = ("fixture", "cid", "https://www.famila.it/another-store")
    with pytest.raises(StructuralError):
        collect_famila(m, f, lambda _: None)
    f.fetch_bytes.assert_not_called()
    f.fetch.return_value = ("fixture", "cid", m.entry_urls[0])
    f.start = 100
    monkeypatch.setattr(
        "app.adapters.famila.resolve",
        lambda *a: {"url": "https://promo.smt.cloud/approved.pdf"},
    )
    f.fetch_bytes.return_value = (b"pdf", "cid", "https://promo.smt.cloud/other.pdf")
    with pytest.raises(StructuralError):
        collect_famila(m, f, lambda _: None)
    f.fetch_bytes.return_value = (b"pdf", "cid", "https://promo.smt.cloud/approved.pdf")
    from app.adapters.base import Batch

    extract = MagicMock(return_value=Batch())
    monkeypatch.setattr("app.adapters.famila.FamilaAdapter.extract", extract)
    collect_famila(m, f, lambda _: None)
    assert extract.call_args.kwargs["deadline"] == 280
