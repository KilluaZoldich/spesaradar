"""MD's public embedded product JSON, resolved through a verified store page.

Only explicit PZ/KG selling units are admitted. Graphic-only prices, webstore
products and complex mechanics are withheld, never inferred from neighbouring art.
"""

import json
import re
from decimal import Decimal

from app.adapters.base import Batch, StructuralError
from app.domain.catalog import (
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

MECHANICS = (
    "x32",
    "secondo50",
    "menoSpendi",
    "scontiInFesta",
    "acquistominimo",
    "pezzi2euro1",
    "piu1",
    "piu_1_1",
    "piu_2_1",
    "piu_3_1",
    "per_3_2",
    "piu_3_2",
)


class MDAdapter:
    parser_version = "1"

    @staticmethod
    def resolve(html, manifest):
        soup = BeautifulSoup(html, "html.parser")
        scope = soup.select_one("#go_back")
        node = soup.select_one("[data-flyer][data-flyer-code]")
        if not scope or normalized(scope.get_text(" ", strip=True)) != normalized(
            manifest.scope_label
        ):
            raise StructuralError(
                "La sede MD non corrisponde alla selezione verificata"
            )
        code = node.get("data-flyer-code", "") if node else ""
        if not re.fullmatch(r"[a-z0-9_]{1,80}", code):
            raise StructuralError("Collegamento al catalogo MD assente")
        return "https://service-volantino.mdspa.it/" + code

    def extract(self, html, url, capture_id, manifest):
        match = re.search(r"\bvar data =\s*", html)
        if not match:
            raise StructuralError("Struttura dati prodotti MD assente")
        try:
            rows, _ = json.JSONDecoder(parse_float=Decimal).raw_decode(
                html[match.end() :]
            )
        except (ValueError, TypeError) as exc:
            raise StructuralError("Dati MD non validi") from exc
        if not isinstance(rows, list) or not rows or len(rows) > 2000:
            raise StructuralError("Catalogo MD vuoto o non riconosciuto")
        batch = Batch(completeness="partial", visited=[url], extracted=len(rows))
        now = utcnow()
        for index, row in enumerate(rows):
            try:
                if row.get("webstoreUrl") or row.get("category") == "MDWS":
                    raise ValueError("Canale webstore separato")
                if any(row.get(key) is not False for key in MECHANICS):
                    raise ValueError("Meccanica economica da verificare")
                if row.get("sellOutStart") or row.get("sellOutEnd"):
                    raise ValueError("Periodo specifico non ancora verificato")
                if row.get("um") not in ["PZ", "KG"]:
                    raise ValueError("Base prezzo non documentata")
                if not isinstance(row.get("cardMD"), bool):
                    raise ValueError("Requisito carta sconosciuto")
                if "CARD" in row.get("section", "") and not row["cardMD"]:
                    raise ValueError("Requisito carta incoerente")
                # The actual card price fills #discountPercSIF_Card_MD, despite its name.
                field = "prezzoPartenzaSIF" if row["cardMD"] else "priceOff"
                amount = cents(row[field])
                if row["cardMD"] and amount > cents(row["priceOff"]):
                    raise ValueError("Prezzo carta incoerente")
                if not isinstance(row.get("priceStart"), bool):
                    raise ValueError("Prezzo da verificare")
                title = BeautifulSoup(row["name"], "html.parser").get_text(
                    " ", strip=True
                )
                raw_pack = ""
                if row.get("weight", 0) > 0 and row.get("weight_um", "").lower() in [
                    "g",
                    "kg",
                    "ml",
                    "l",
                ]:
                    raw_pack = f"{row['weight']} {row['weight_um'].lower()}"
                basis = (
                    "from"
                    if row["priceStart"]
                    else "kg"
                    if row["um"] == "KG"
                    else "pack"
                )
                # An offered kg is not a package of the arbitrary reference weight.
                if basis == "kg":
                    raw_pack = "Vendita al kg"
                raw_price = f"{Decimal(amount) / 100:.2f} €" + (
                    "/kg" if basis == "kg" else ""
                )
                pack, price = package_and_price(raw_pack, amount, basis, raw_price)
                pack.quantity_basis = (
                    "unknown"  # MD does not label net versus drained weight here.
                )
                description = normalized(row.get("description", ""))
                if "sgocc" in description:
                    price.calculated_unit_price = None
                    price.unit_price_basis = None
                    price.calculation = None
                spend = (
                    cents(row["contribute"]) if row.get("contribute", 0) > 0 else None
                )
                condition = "Solo con Buona Spesa Card." if row["cardMD"] else ""
                if spend:
                    condition += f" Spesa minima {Decimal(spend) / 100:.2f} €."
                condition += " Altre condizioni non integralmente verificate."
                classification = classify(title, original=row.get("category"))
                for key, label in [
                    ("glutenFree", "Senza glutine"),
                    ("lactFree", "Senza lattosio"),
                    ("bio", "Biologico"),
                    ("surgelato", "Surgelato"),
                ]:
                    if row.get(key) is True and label not in classification["tags"]:
                        classification["tags"].append(label)
                campaign = str(row["idVolantino"])
                batch.campaign_ids.append(campaign)
                batch.offers.append(
                    Offer(
                        id=identity(
                            manifest.source_id,
                            campaign,
                            row["code"],
                            title,
                            raw_pack,
                            row["cardMD"],
                        ),
                        source_offer_id=str(row["idProduct"]),
                        retailer_id="md",
                        source_id=manifest.source_id,
                        target_ids=[manifest.source_id],
                        campaign_id=campaign,
                        title=title,
                        title_normalized=normalized(title),
                        brand=row.get("brand") or None,
                        **classification,
                        package=pack,
                        price=price,
                        conditions=Conditions(
                            status="partial",
                            loyalty_required=row["cardMD"],
                            minimum_spend_cents=spend,
                            raw_text=condition.strip(),
                        ),
                        validity=Validity(
                            raw_text="Catalogo promozionale attualmente collegato alla sede. Date non confermate per questo articolo."
                        ),
                        scope={
                            "type": "store",
                            "label": manifest.scope_label,
                            "applicability": "verified_store_link",
                        },
                        limitations=[
                            "Date dell’articolo non confermate",
                            "Copertura parziale del volantino",
                            "Condizioni non integralmente verificate",
                        ],
                        source_url=url,
                        evidence={
                            "capture_id": capture_id,
                            "url": url,
                            "selector": f"var data[{index}], idProduct={row['idProduct']}, pagina {row['pageNumber']}",
                            "raw_price": raw_price,
                            "price_field": field,
                            "scope_url": manifest.entry_urls[0],
                            "fields": {
                                "title": "name",
                                "price": field,
                                "basis": "um",
                                "package": "weight + weight_um",
                                "loyalty": "cardMD",
                            },
                        },
                        parser_version=self.parser_version,
                        first_seen_at=now,
                        last_seen_at=now,
                        last_verified_at=now,
                    )
                )
            except (ValueError, KeyError, TypeError):
                batch.quarantined += 1
        batch.campaign_ids = sorted(set(batch.campaign_ids))
        if not batch.offers:
            raise StructuralError("Nessun articolo MD supera i controlli")
        batch.warnings = [
            f"{batch.quarantined} voci escluse: ambito, unità, periodo o condizioni non verificabili."
        ]
        return batch
