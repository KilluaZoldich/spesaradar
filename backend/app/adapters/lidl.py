import json
import re
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from urllib.parse import urljoin

from app.adapters.base import Batch, StructuralError
from app.domain.catalog import (
    ROME,
    Conditions,
    Offer,
    Validity,
    cents,
    classify,
    identity,
    normalized,
    package_and_price,
    utcnow,
)
from bs4 import BeautifulSoup


class LidlAdapter:
    parser_version = "4"

    def extract(self, html, url, capture_id):
        soup = BeautifulSoup(html, "html.parser")
        nodes = soup.select("[data-grid-data]")
        if not nodes:
            raise StructuralError("Struttura prodotti Lidl assente")
        batch = Batch(completeness="complete", visited=[url], extracted=len(nodes))
        now = utcnow()
        for index, node in enumerate(nodes):
            try:
                d = json.loads(node["data-grid-data"], parse_float=Decimal)
                badges = (
                    d.get("stockAvailability", {})
                    .get("badgeInfo", {})
                    .get("badges", [])
                )
                if d.get("online") or not any(
                    "IN_STORE" in b.get("type", "") for b in badges
                ):
                    raise ValueError("Canale fisico non documentato")
                p = d.get("price", {})
                plus = d.get("lidlPlus") or []
                if plus:
                    if len(plus) != 1:
                        raise ValueError("Più meccaniche Lidl Plus")
                    p = plus[0]["price"]
                regional = d.get("regionsPrices", {})
                if len(regional) != 1:
                    raise ValueError("Prezzi regionali non uniformi")
                regional_entry = next(iter(regional.values()))
                regional_price = (
                    (regional_entry.get("currentLidlPlusPrice") or {}).get("price")
                    if plus
                    else regional_entry.get("currentPrice")
                )
                if not regional_price or regional_price.get("price") != p.get("price"):
                    raise ValueError("Prezzo regionale discordante")
                if (
                    p.get("variantsHaveDifferentPrices")
                    or p.get("discount", {}).get("showFrom")
                    or p.get("discount", {}).get("showUpTo")
                ):
                    raise ValueError("Prezzo variabile")
                if (
                    p.get("currencyCode", d.get("price", {}).get("currencyCode"))
                    != "EUR"
                ):
                    raise ValueError("Valuta")
                amount = cents(p["price"])
                raw_pack = p.get("packaging", {}).get("text", "")
                low = normalized(raw_pack)
                basis = (
                    "kg"
                    if low in ["al kg", "1 kg", "kg"] and not p.get("basePrice")
                    else "l"
                    if low == "al litro"
                    else "piece"
                    if low in ["al pezzo", "pezzo", "cadauno", "cad."]
                    else "pack"
                    if raw_pack
                    else "unknown"
                )
                if basis == "unknown":
                    raise ValueError("Base prezzo assente")
                pack, price = package_and_price(
                    raw_pack,
                    amount,
                    basis,
                    str(p["price"]) + " € · " + raw_pack,
                    p.get("basePrice", {}).get("text"),
                )
                title = d["fullTitle"]
                original = d.get("keyfacts", {}).get("wonCategoryPrimary")
                title_field = "fullTitle"
                if normalized(title) == normalized(d.get("brand", {}).get("name", "")):
                    title = d.get("title")
                    title_field = "title"
                    if not title or normalized(title) == normalized(
                        d.get("brand", {}).get("name", "")
                    ):
                        raise ValueError("Nome prodotto assente")
                description = BeautifulSoup(
                    d.get("keyfacts", {}).get("description", ""), "html.parser"
                ).get_text(" ", strip=True)
                if any(
                    x in normalized(description)
                    for x in ["acquist", "3x2", "3×2", "secondo pezzo", "spesa minima"]
                ):
                    raise ValueError("Meccanica economica da verificare")
                start = datetime.fromtimestamp(d["storeStartDate"], UTC)
                end = (
                    datetime.fromtimestamp(d["storeEndDate"] + 1, UTC)
                    if d.get("storeEndDate")
                    else None
                )
                price_end = regional_price.get("endDateExclusive")
                if price_end:
                    price_end = datetime.fromisoformat(price_end.replace("Z", "+00:00"))
                    end = min(end, price_end) if end else price_end
                link = next(
                    (
                        a
                        for a in soup.select("a[href]")
                        if a["href"].split("?")[0]
                        == url.replace("https://www.lidl.it", "")
                    ),
                    None,
                )
                advertised_start = (
                    re.search(r"(\d{1,2})/(\d{1,2})", link.get_text(" ", strip=True))
                    if link
                    else None
                )
                if not advertised_start or not end:
                    raise ValueError("Periodo campagna non correlabile")
                day, month = map(int, advertised_start.groups())
                year = end.astimezone(ROME).year - (month > end.astimezone(ROME).month)
                campaign_start = datetime(year, month, day, tzinfo=ROME).astimezone(UTC)
                if (end - campaign_start).days > 31 or campaign_start >= end:
                    raise ValueError("Campagna incoerente")
                start = max(start, campaign_start)
                if end <= start:
                    raise ValueError("Date incoerenti")
                campaign = url.rsplit("/", 1)[-1]
                source_url = urljoin("https://www.lidl.it", d["canonicalUrl"])
                if not source_url.startswith("https://www.lidl.it/p/"):
                    raise ValueError("Fonte non ammessa")
                condition = (
                    "Solo con Lidl Plus. Verifica nell’app ufficiale eventuale attivazione."
                    if plus
                    else None
                )
                batch.offers.append(
                    Offer(
                        id=identity(
                            "lidl",
                            d["productId"],
                            start.isoformat(),
                            raw_pack,
                            bool(plus),
                        ),
                        source_offer_id=str(d["productId"]),
                        retailer_id="lidl",
                        source_id="lidl-national",
                        campaign_id=campaign,
                        target_ids=["lidl-national"],
                        title=title,
                        title_normalized=normalized(title),
                        brand=d.get("brand", {}).get("name")
                        if d.get("brand", {}).get("showBrand")
                        else None,
                        original_category=original,
                        **classify(title, original, description),
                        package=pack,
                        price=price,
                        conditions=Conditions(
                            status="partial" if plus else "unknown",
                            loyalty_required=True if plus else None,
                            raw_text=condition,
                        ),
                        validity=Validity(
                            start_at=start,
                            end_at_exclusive=end,
                            raw_text=f"Campagna dal {start.astimezone(ROME):%d.%m.%Y}; prezzo valido fino al {(end - timedelta(seconds=1)).astimezone(ROME):%d.%m.%Y}",
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
                        source_url=source_url,
                        evidence={
                            "capture_id": capture_id,
                            "url": url,
                            "selector": f"[data-grid-data]:nth-of-type({index + 1})",
                            "product_id": str(d["productId"]),
                            "fields": {
                                "title": title_field,
                                "price": "lidlPlus[0].price" if plus else "price",
                                "dates": "campaign link + storeStartDate; regionsPrices.*.currentPrice/currentLidlPlusPrice.price.endDateExclusive",
                                "category": "keyfacts.wonCategoryPrimary",
                            },
                            "raw_price": price.raw_text,
                            "description": description,
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
        batch.campaign_ids = list({x.campaign_id for x in batch.offers})
        if batch.quarantined:
            batch.completeness = "partial"
        if not batch.offers:
            raise StructuralError("Nessun prodotto Lidl supera i controlli")
        return batch
