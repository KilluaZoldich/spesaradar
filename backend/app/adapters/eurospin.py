import re
from datetime import date, datetime, time

from app.adapters.base import Batch, StructuralError
from app.domain.catalog import (
    ROME,
    Conditions,
    Offer,
    Validity,
    classify,
    end_exclusive,
    identity,
    money,
    normalized,
    package_and_price,
    utcnow,
)
from bs4 import BeautifulSoup

MONTHS = {
    x: i + 1
    for i, x in enumerate(
        [
            "gennaio",
            "febbraio",
            "marzo",
            "aprile",
            "maggio",
            "giugno",
            "luglio",
            "agosto",
            "settembre",
            "ottobre",
            "novembre",
            "dicembre",
        ]
    )
}


class EurospinAdapter:
    parser_version = "3"

    def extract(self, html, url, capture_id):
        soup = BeautifulSoup(html, "html.parser")
        nodes = soup.select(".sn_promo_grid_item")
        heading = next(
            (
                x.get_text(" ", strip=True)
                for x in soup.select("h2")
                if "Offerte valide" in x.text
            ),
            "",
        )
        period = re.search(
            r"dal\s+(\d+)\s+(\w+)\s+(\d{4})?\s*al\s+(\d+)\s+(\w+)\s+(\d{4})",
            heading,
            re.IGNORECASE,
        )
        if not nodes or not period:
            raise StructuralError("Struttura o anno campagna Eurospin assente")
        sm = MONTHS[period[2].lower()]
        em = MONTHS[period[5].lower()]
        ey = int(period[6])
        sy = int(period[3] or ey - (sm > em))
        start_day = date(sy, sm, int(period[1]))
        end_day = date(ey, em, int(period[4]))
        campaign = f"{start_day}_{end_day}"
        batch = Batch(
            completeness="complete",
            visited=[url],
            extracted=len(nodes),
            campaign_ids=[campaign],
        )
        now = utcnow()
        for index, node in enumerate(nodes):

            def txt(selector):
                el = node.select_one(selector)
                return " ".join(el.get_text(" ", strip=True).split()) if el else ""

            try:
                title = txt(".i_title")
                brand = txt(".i_brand") or None
                raw_price = txt('[itemprop="price"]')
                amount = money(raw_price)
                if not amount:
                    raise ValueError("Prezzo assente")
                period_card = txt(".date_current_promo")
                if period_card != f"{start_day:%d.%m} - {end_day:%d.%m}":
                    raise ValueError("Periodo articolo diverso dal periodo verificato")
                raw_info = txt(".i_price_info")
                parts = re.split(r"\s+-\s+", raw_info, maxsplit=1)
                raw_pack = parts[0].strip()
                price_text = txt(".i_price")
                description = txt(".i_descrizione")
                if any(
                    w in normalized(description + " " + price_text)
                    for w in [
                        "carta",
                        "coupon",
                        "acquist",
                        "spesa minima",
                        "3x2",
                        "3×2",
                        "app eurospin",
                    ]
                ):
                    raise ValueError("Condizione economica da verificare")
                # No unit computation from non-food specifications or drained/net mixtures.
                basis = (
                    "kg"
                    if raw_pack.lower() == "al kg"
                    else "l"
                    if raw_pack.lower() == "al litro"
                    else "pack"
                )
                pack, price = package_and_price(
                    raw_pack,
                    amount,
                    basis,
                    raw_price,
                    parts[1] if len(parts) > 1 and "sgocc" not in raw_pack else None,
                )
                image = node.select_one(".i_image")
                official_id = None
                if image and (m := re.search(r"/smt/(\d+)\.", image.get("src", ""))):
                    official_id = m[1]
                batch.offers.append(
                    Offer(
                        id=identity(
                            "eurospin", official_id or title, raw_pack, campaign
                        ),
                        source_offer_id=official_id,
                        retailer_id="eurospin",
                        source_id="eurospin-national",
                        campaign_id=campaign,
                        target_ids=["eurospin-national"],
                        title=title,
                        title_normalized=normalized(title),
                        brand=brand,
                        **classify(title, description=description),
                        package=pack,
                        price=price,
                        conditions=Conditions(
                            status="unknown", raw_text=description or None
                        ),
                        validity=Validity(
                            start_at=datetime.combine(start_day, time.min, ROME),
                            end_at_exclusive=end_exclusive(end_day),
                            raw_text=heading,
                            evidence_level="explicit_dates",
                        ),
                        scope={
                            "type": "national",
                            "label": "Offerte nazionali — adesione del negozio non verificata",
                            "applicability": "unverified_store",
                        },
                        limitations=[
                            "Adesione del negozio non verificata",
                            "Condizioni non integralmente verificate",
                        ],
                        source_url=url,
                        evidence={
                            "capture_id": capture_id,
                            "url": url,
                            "selector": f".sn_promo_grid_item:nth-child({index + 1})",
                            "fields": {
                                "title": ".i_title",
                                "price": "[itemprop=price]",
                                "package": ".i_price_info",
                                "dates": ".date_current_promo + h2 periodo pagina",
                            },
                            "raw_price": price_text,
                            "raw_package": raw_info,
                        },
                        parser_version=self.parser_version,
                        first_seen_at=now,
                        last_seen_at=now,
                        last_verified_at=now,
                    )
                )
            except (ValueError, KeyError, TypeError) as exc:
                batch.quarantined += 1
                batch.warnings.append(f"Articolo {index + 1}: {exc}")
        if batch.quarantined:
            batch.completeness = "partial"
        if not batch.offers:
            raise StructuralError("Nessun prodotto Eurospin supera i controlli")
        return batch
