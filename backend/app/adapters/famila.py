"""Famila Carpi: monthly Selex native PDF linked in the store's Next.js data."""

import io
import json
import re
import time as clock
from datetime import UTC, datetime, time
from decimal import Decimal
from urllib.parse import urlsplit

import pdfplumber
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
from app.extraction.selex_grid import cells
from bs4 import BeautifulSoup


def resolve(html, manifest):
    try:
        soup = BeautifulSoup(html, "html.parser")
        store = json.loads(soup.select_one("#__NEXT_DATA__").text)["props"][
            "pageProps"
        ]["store"]
        # Resolve only from the exact maintainer-approved store page, never a global
        # regional flyer and never the separate online-shopping destination.
        canonical = soup.select_one('link[rel="canonical"]')
        if not canonical or canonical["href"].rstrip("/") != manifest.entry_urls[
            0
        ].rstrip("/"):
            raise ValueError("Sede diversa")
        found = []
        for flyer in store["flyers"]:
            if not re.fullmatch(r"FAMILA SELEX [A-ZÀ]+", flyer["title"]):
                continue
            url = flyer["linkDigitalFlyer"]
            if not re.fullmatch(
                r"https://promo\.smt\.cloud/digitalflyer/files/[a-f0-9-]{36}/FA-00\.pdf",
                url,
            ):
                raise ValueError("Risorsa PDF fuori profilo")
            start, end = [
                datetime.strptime(flyer[k], "%Y%m%d%H%M%S").date()
                for k in ["startDate", "endDate"]
            ]
            if end < start or (end - start).days > 31:
                raise ValueError("Periodo incoerente")
            found.append(
                {
                    "id": urlsplit(url).path.split("/")[-2],
                    "url": url,
                    "start": start,
                    "end": end,
                    "title": flyer["title"],
                }
            )
        if len(found) != 1:
            raise ValueError("Campagna mensile non univoca")
        return found[0]
    except (ValueError, KeyError, TypeError, AttributeError) as exc:
        raise StructuralError(
            "Collegamento al mensile Famila non verificabile"
        ) from exc


class FamilaAdapter:
    parser_version = "1"

    def extract(self, body, url, capture_id, manifest, campaign, deadline=None):
        batch = Batch(
            completeness="partial", visited=[url], campaign_ids=[campaign["id"]]
        )
        now = utcnow()
        with pdfplumber.open(io.BytesIO(body)) as doc:
            if not 2 <= len(doc.pages) <= 24:
                raise StructuralError("Numero pagine Selex fuori profilo")
            for pi, page in enumerate(doc.pages):
                if deadline and clock.monotonic() > deadline:
                    raise StructuralError("Deadline PDF raggiunta")
                for cell in cells(page):
                    batch.extracted += 1
                    try:
                        # Require native price, explicit package AND published unit price.
                        # Their arithmetic agreement catches adjacent article association.
                        lines = cell["description"].splitlines()
                        raw_pack = lines[-1]
                        title = " ".join(lines[:-1])
                        if not title or re.search(
                            r"carta|coupon|sconto|gratis|punti|solo con",
                            cell["raw"],
                            re.I,
                        ):
                            raise ValueError("Condizione economica")
                        amount = money(re.sub(r"\s+", "", cell["price"]))
                        unit = re.fullmatch(
                            r"al (kg|l) € (\d+,\d{2})", cell["unit"].strip()
                        )
                        if not amount or not unit:
                            raise ValueError("Prezzo unitario assente")
                        pack, price = package_and_price(
                            raw_pack,
                            amount,
                            "pack",
                            cell["price"],
                            unit[2] + " €/" + unit[1],
                        )
                        if (
                            not price.calculated_unit_price
                            or ("kg" if pack.quantity_unit in ["g", "kg"] else "l")
                            != unit[1]
                        ):
                            raise ValueError("Formato ambiguo")
                        if abs(
                            Decimal(price.calculated_unit_price)
                            - Decimal(price.published_unit_price)
                        ) > Decimal(".011"):
                            raise ValueError("Prezzo/quantità non coerenti")
                        pack.quantity_basis = "unknown"
                        classification = classify(title)
                        # Tags are literal in source description, never inferred from category.
                        for pattern, tag in [
                            (r"\bsurgelat[oaie]\b", "Surgelato"),
                            (r"\bbiologic[oaie]\b", "Biologico"),
                            (r"\bsenza glutine\b", "Senza glutine"),
                            (r"\bsenza lattosio\b", "Senza lattosio"),
                        ]:
                            if (
                                re.search(pattern, normalized(title))
                                and tag not in classification["tags"]
                            ):
                                classification["tags"].append(tag)
                        batch.offers.append(
                            Offer(
                                id=identity(
                                    manifest.source_id, campaign["id"], title, raw_pack
                                ),
                                retailer_id=manifest.retailer_id,
                                source_id=manifest.source_id,
                                target_ids=[manifest.source_id],
                                campaign_id=campaign["id"],
                                title=title,
                                title_normalized=normalized(title),
                                **classification,
                                package=pack,
                                price=price,
                                conditions=Conditions(
                                    status="unknown",
                                    raw_text="Requisiti fedeltà e altre condizioni non integralmente verificati.",
                                ),
                                validity=Validity(
                                    start_at=datetime.combine(
                                        campaign["start"], time.min, ROME
                                    ).astimezone(UTC),
                                    end_at_exclusive=end_exclusive(campaign["end"]),
                                    evidence_level="explicit_dates",
                                    raw_text=f"{campaign['title']}: {campaign['start']} — {campaign['end']} (pagina ufficiale della sede)",
                                ),
                                scope={
                                    "type": "store",
                                    "label": manifest.scope_label,
                                    "applicability": "verified_store_link",
                                },
                                limitations=[
                                    "Solo il mensile Selex; volantini sottocosto e sponsor esclusi",
                                    "Condizioni non integralmente verificate",
                                ],
                                source_url=url,
                                evidence={
                                    "capture_id": capture_id,
                                    "url": url,
                                    "page": pi + 1,
                                    "bbox": cell["bbox"],
                                    "selector": f"PDF pagina {pi + 1}, cella {tuple(round(v, 1) for v in cell['bbox'])}",
                                    "raw_price": cell["price"],
                                    "raw_text": cell["raw"],
                                    "scope_url": manifest.entry_urls[0],
                                    "validity_selector": "__NEXT_DATA__.props.pageProps.store.flyers",
                                },
                                parser_version=self.parser_version,
                                first_seen_at=now,
                                last_seen_at=now,
                                last_verified_at=now,
                            )
                        )
                    except (ValueError, IndexError, TypeError):
                        batch.quarantined += 1
        if not batch.offers:
            raise StructuralError("Nessuna cella del mensile Famila verificata")
        batch.warnings = [
            f"{batch.extracted} celle riconosciute, {batch.quarantined} escluse. Solo mensile Selex."
        ]
        return batch


def collect_famila(m, fetcher, stage):
    html, _, final = fetcher.fetch(m.entry_urls[0])
    if final.rstrip("/") != m.entry_urls[0].rstrip("/"):
        raise StructuralError("Sede Famila cambiata")
    campaign = resolve(html, m)
    body, cid, url = fetcher.fetch_bytes(campaign["url"], max_bytes=30 * 1024 * 1024)
    if url != campaign["url"]:
        raise StructuralError("PDF Famila reindirizzato")
    stage("parse")
    batch = FamilaAdapter().extract(
        body, url, cid, m, campaign, deadline=fetcher.start + m.deadline_seconds
    )
    batch.visited.insert(0, m.entry_urls[0])
    return batch
