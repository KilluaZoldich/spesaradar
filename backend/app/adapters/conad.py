"""Conad CNO: official store campaign metadata + audited native-PDF cell family."""

import json
import re
from datetime import UTC, datetime
from decimal import Decimal

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
from app.extraction.pdf import read_cells
from app.security.fetch import validate_url
from bs4 import BeautifulSoup

MONTHS = [
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


def validate_pdf_url(url, filename):
    parsed = validate_url(url, ["www.conad.it"])
    if not re.fullmatch(
        r"/assets/common/volantini/cno/v[0-9]+/" + re.escape(filename), parsed.path
    ):
        raise StructuralError("URL PDF diverso dalla risorsa dichiarata dalla sede")


def resolve(html, manifest):
    soup = BeautifulSoup(html, "html.parser")
    node = soup.select_one("[data-store-id][data-flyers]")
    if not node or node["data-store-id"] != manifest.store_id:
        raise StructuralError("La sede Conad non corrisponde alla selezione")
    try:
        rows = json.loads(node["data-flyers"])
        if not isinstance(rows, list) or len(rows) > 40:
            raise ValueError()
        now = utcnow()
        result = []
        for row in rows:
            if not row["title"].endswith(
                manifest.campaign_title_suffix
            ) or not re.fullmatch(r"[0-9]{8}PCONADEMILIA\.pdf", row.get("name", "")):
                continue
            validate_pdf_url(row["pdfUrl"], row["name"])
            start = datetime.fromtimestamp(row["validFrom"] / 1000, ROME).date()
            end = datetime.fromtimestamp(row["validTo"] / 1000, ROME).date()
            if end < start or (end - start).days > 31 or end_exclusive(end) <= now:
                continue
            result.append(
                dict(
                    id=row["slug"],
                    filename=row["name"],
                    title=row["title"],
                    url=row["pdfUrl"],
                    start=start,
                    end=end,
                )
            )
        if not result:
            raise StructuralError("Nessuna campagna del formato verificato disponibile")
        return sorted(result, key=lambda x: x["start"])[: manifest.max_documents]
    except (KeyError, TypeError, ValueError) as exc:
        raise StructuralError("Metadati delle campagne Conad non riconosciuti") from exc


def printed_period(text, campaign):
    """A matching footer is essential: subcampaigns can have different dates."""
    text = normalized(text)

    weekdays = r"(?:lunedi|martedi|mercoledi|giovedi|venerdi|sabato|domenica)"
    months = "|".join(MONTHS)
    # A main footer is insufficient if the same page advertises another window.
    ranges = re.finditer(
        rf"\b(?:dal?|dall[’'])\s+(?:{weekdays}\s+)?(\d{{1,2}})(?:\s+({months}))?"
        rf"\s+(?:al?|all[’'])\s+(?:{weekdays}\s+)?(\d{{1,2}})\s+({months})(?:\s+(\d{{4}}))?",
        text,
    )
    for match in ranges:
        start_month = MONTHS.index(match[2] or match[4]) + 1
        end_month = MONTHS.index(match[4]) + 1
        if (int(match[1]), start_month, int(match[3]), end_month) != (
            campaign["start"].day,
            campaign["start"].month,
            campaign["end"].day,
            campaign["end"].month,
        ):
            return False
        if match[5] and int(match[5]) != campaign["end"].year:
            return False

    def day(d):
        return f"{d.day} {MONTHS[d.month - 1]}"

    return bool(
        re.search(
            r"offerta valida da\s+\w+\s+"
            + (
                str(campaign["start"].day)
                + (
                    r"(?: " + MONTHS[campaign["start"].month - 1] + r")?"
                    if campaign["start"].month == campaign["end"].month
                    else " " + MONTHS[campaign["start"].month - 1]
                )
            )
            + r"\s+a\s+\w+\s+"
            + re.escape(day(campaign["end"]))
            + r"\s+"
            + str(campaign["end"].year)
            + r"\b",
            text,
        )
    )


def cell_fields(cell):
    words = cell.words
    title_words = [w for w in words if "LibelSuit-Regular" in w["fontname"]]
    if not title_words or len(title_words) > 35:
        raise ValueError("Titolo non riconosciuto")
    title = " ".join(w["text"] for w in title_words)
    details = " ".join(
        w["text"] for w in words if w["fontname"].endswith("DINNextLTPro-Condensed")
    )
    text = " ".join(w["text"] for w in words)
    if re.search(
        r"\bott[e’\']lla\b|bollin|spesa|minim|contribut|acquist|\b\d\s*[x×]\s*\d\b",
        normalized(text),
    ):
        # The ordinary multipack syntax "60 g x 2 pezzi" remains allowed.
        raise ValueError("Meccanica non supportata")
    heavy = [w for w in words if "HeavyCondensed" in w["fontname"] and w["size"] >= 18]
    full = [w for w in heavy if re.fullmatch(r"\d+,\d{2}", w["text"])]
    decimal = [w for w in heavy if re.fullmatch(r",\d{2}", w["text"])]
    if len(full) == 1 and not decimal:
        price = full[0]["text"]
    elif len(decimal) == 1 and not full:
        frac = decimal[0]
        integers = [
            w
            for w in heavy
            if re.fullmatch(r"\d+", w["text"])
            and abs(w["x1"] - frac["x0"]) < 2
            and w["top"] < frac["top"] < w["bottom"]
        ]
        if len(integers) != 1:
            raise ValueError("Parte intera del prezzo ambigua")
        price = integers[0]["text"] + frac["text"]
    else:
        raise ValueError("Prezzo non univoco nel riquadro")
    if not any(
        w["text"] == "€"
        for w in heavy + [w for w in words if "HeavyCondensed" in w["fontname"]]
    ):
        raise ValueError("Valuta non documentata")
    info = re.split(r"\b(?:al kg|al l|per 100 g)\b", details, maxsplit=1)[0].strip()
    # Explicit package quantity is required. Variable-weight and drained/net pairs
    # are withheld by this profile, never assigned an arbitrary pack price.
    if "/" in info or "sgocc" in normalized(info):
        raise ValueError("Base della quantità ambigua")
    quantities = list(
        re.finditer(
            r"(?<![\d.,])(\d+(?:[.,]\d+)?)\s*(kg|ml|g|l)\b(?:\s*x\s*(\d+)\s*pezzi)?",
            info,
        )
    )
    if len(quantities) != 1:
        raise ValueError("Formato non univoco")
    q = quantities[0]
    raw_pack = (f"{q[3]} x " if q[3] else "") + f"{q[1]} {q[2]}"
    amount = money(price)
    pack, monetary = package_and_price(raw_pack, amount, "pack", price + " €")
    # Where the leaflet calls out a variant example, retain that variant in title.
    description = info[: q.start()].strip()
    title += (" — " + description) if description else ""
    pack.quantity_basis = "unknown"
    unit = re.search(
        r"(al kg|al l|per 100 g)\s+(?:da €\s*\d+,\d{2}\s+a\s+)?€\s*(\d+,\d{2})", details
    )
    if unit and monetary.calculated_unit_price:
        if ("l" if unit[1] == "al l" else "kg") != monetary.unit_price_basis:
            raise ValueError("Unità di confronto incompatibili")
        published = Decimal(unit[2].replace(",", ".")) * (
            10 if unit[1] == "per 100 g" else 1
        )
        # Leaflets round up centesimal unit prices, including per-100g figures.
        tolerance = Decimal(".10") if unit[1] == "per 100 g" else Decimal(".01")
        if abs(published - Decimal(monetary.calculated_unit_price)) > tolerance:
            raise ValueError("Prezzo e quantità incoerenti col prezzo unitario")
        monetary.published_unit_price = str(published)
    loyalty = True if "solotitolari" in normalized(text).replace(" ", "") else None
    return title, pack, monetary, loyalty, text


class ConadPDFAdapter:
    parser_version = "1"

    def extract(self, body, url, capture_id, manifest, campaign, deadline):
        batch = Batch(
            completeness="partial", visited=[url], campaign_ids=[campaign["id"]]
        )
        now = utcnow()
        for cell in read_cells(body, deadline):
            if not printed_period(cell.page_text, campaign):
                continue
            batch.extracted += 1
            try:
                title, pack, price, loyalty, raw = cell_fields(cell)
                if len(title) > 500:
                    raise ValueError("Descrizione troppo lunga")
                classification = classify(title, description=raw)
                if (
                    "REPARTO SURGELATI" in raw
                    and "Surgelato" not in classification["tags"]
                ):
                    classification["tags"].append("Surgelato")
                batch.offers.append(
                    Offer(
                        id=identity(
                            manifest.source_id,
                            campaign["id"],
                            title,
                            pack.raw_text,
                            loyalty,
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
                            status="partial",
                            loyalty_required=loyalty,
                            raw_text=(
                                "Solo titolari Carta Insieme. " if loyalty else ""
                            )
                            + (
                                "Prezzo esposto prima dell’ulteriore vantaggio Club Famiglia; iscrizione richiesta per il vantaggio aggiuntivo. "
                                if "club famiglia" in normalized(cell.page_text)
                                else ""
                            )
                            + "Altre condizioni non integralmente verificate. "
                            + raw,
                        ),
                        validity=Validity(
                            start_at=datetime.combine(
                                campaign["start"], datetime.min.time(), ROME
                            ).astimezone(UTC),
                            end_at_exclusive=end_exclusive(campaign["end"]),
                            evidence_level="explicit_dates",
                            raw_text=f"Dal {campaign['start'].isoformat()} al {campaign['end'].isoformat()} (incluso), confermati nel PDF",
                        ),
                        scope={
                            "type": "store",
                            "label": manifest.scope_label,
                            "applicability": "verified_store_link",
                        },
                        limitations=[
                            "Copertura parziale: riquadri del layout testuale verificato",
                            "Condizioni non integralmente verificate",
                        ],
                        source_url=url,
                        parser_version=self.parser_version,
                        evidence={
                            "capture_id": capture_id,
                            "url": url,
                            "scope_url": manifest.entry_urls[0],
                            "page": cell.page,
                            "bbox": [round(v, 2) for v in cell.bbox],
                            "selector": f"PDF pagina {cell.page}, riquadro {tuple(round(v, 1) for v in cell.bbox)}",
                            "raw_price": price.raw_text,
                            "raw_text": raw,
                            "method": "native_pdf_rectangles",
                        },
                        first_seen_at=now,
                        last_seen_at=now,
                        last_verified_at=now,
                    )
                )
            except ValueError:
                batch.quarantined += 1
        if not batch.offers:
            raise StructuralError("Nessun riquadro PDF supera i controlli del layout")
        batch.warnings = [
            f"{batch.quarantined} riquadri esclusi; copertine, aree senza riquadri e periodi secondari non acquisiti."
        ]
        return batch
