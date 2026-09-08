"""Despar's public, store-selected HTML catalog. No iPaper/CDN or browser required."""

import re
from datetime import UTC, datetime, time
from urllib.parse import urljoin

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
from app.security.fetch import FetchError
from bs4 import BeautifulSoup


def text(node):
    return node.get_text(" ", strip=True) if node else ""


def selected_scope(soup, manifest):
    node = soup.select_one(".punto_vendita_selezionato a[href]")
    if (
        not node
        or urljoin(manifest.entry_urls[0], node["href"]) != manifest.entry_urls[0]
    ):
        raise StructuralError("La sede Despar selezionata non corrisponde al catalogo")


class DesparAdapter:
    parser_version = "1"

    def extract(self, html, url, capture_id, manifest):
        soup = BeautifulSoup(html, "html.parser")
        selected_scope(soup, manifest)
        root = soup.select_one("#volantino-per-categoria")
        if not root:
            raise StructuralError("Catalogo HTML Despar non riconosciuto")
        raw_dates = text(root.select_one(".validita_volantino"))
        dates = re.fullmatch(
            r"Offerte valide dal (\d{2}\.\d{2}\.\d{4}) al (\d{2}\.\d{2}\.\d{4})",
            raw_dates,
        )
        if not dates:
            raise StructuralError("Periodo Despar non verificabile")
        start, end = [datetime.strptime(d, "%d.%m.%Y").date() for d in dates.groups()]
        if end < start or (end - start).days > 45:
            raise StructuralError("Periodo Despar incoerente")
        validity = Validity(
            start_at=datetime.combine(start, time.min, ROME).astimezone(UTC),
            end_at_exclusive=end_exclusive(end),
            raw_text=raw_dates,
            evidence_level="explicit_dates",
        )
        nodes = root.select("#contenitoreBoxOfferte .anteprima_offerta")
        if not nodes or len(nodes) > 24:
            raise StructuralError("Struttura delle schede Despar cambiata")
        campaign = f"{start.isoformat()}_{end.isoformat()}"
        batch = Batch(
            completeness="partial",
            visited=[url],
            extracted=len(nodes),
            campaign_ids=[campaign],
        )
        rules = text(root.select_one(".offerte_regolamento"))
        now = utcnow()
        for index, node in enumerate(nodes):
            try:
                title = text(node.select_one(".anteprima_offerta_titolo"))
                link = node.select_one("a.anteprima_offerta_link[href]")
                product_url = link["href"]
                match = re.fullmatch(
                    r"https://www.despar.it/it/offerta/(\d+)/[a-z0-9-]+/", product_url
                )
                if not title or not match:
                    raise ValueError("Identità non verificabile")
                raw_pack = text(node.select_one(".anteprima_offerta_peso"))
                price_node = node.select_one(".anteprima_offerta_prezzo")
                # Multi-buy, percentage-only and app-extra layouts must have their own
                # complete economic model before admission. Never use their low unit price.
                if (
                    link.get("class") != ["anteprima_offerta_link"]
                    or node.select_one(".prezzo_finale, .contenitore_offerta_scontata")
                    or re.search(r"app|sconto|gratis|punti", text(node), re.I)
                ):
                    raise ValueError("Meccanica condizionata esclusa")
                amounts = price_node.select("strong") if price_node else []
                labels = price_node.select(".etichetta_prezzo") if price_node else []
                if len(amounts) != 1 or len(labels) != 1:
                    raise ValueError("Prezzo non univoco")
                raw_price = text(amounts[0])
                amount = money(re.sub(r"\s+", "", raw_price))
                basis = {"al pz.": "pack", "al kg": "kg", "al litro": "l"}.get(
                    text(labels[0])
                )
                if not amount or not basis:
                    raise ValueError("Base non verificata")
                pack, price = package_and_price(
                    raw_pack, amount, basis, raw_price + " " + text(labels[0])
                )
                # Source gives weight, not a universally verified net/drained basis.
                pack.quantity_basis = "unknown"
                price.calculated_unit_price = None
                price.calculation = None
                if basis == "pack":
                    price.unit_price_basis = None
                batch.offers.append(
                    Offer(
                        id=identity(manifest.source_id, campaign, match[1], raw_pack),
                        source_offer_id=match[1],
                        retailer_id=manifest.retailer_id,
                        source_id=manifest.source_id,
                        target_ids=[manifest.source_id],
                        campaign_id=campaign,
                        title=title,
                        title_normalized=normalized(title),
                        brand=text(node.select_one(".anteprima_offerta_brand")) or None,
                        **classify(title),
                        package=pack,
                        price=price,
                        conditions=Conditions(
                            status="partial",
                            raw_text=rules
                            + " Requisiti ulteriori non integralmente verificati.",
                        ),
                        validity=validity,
                        scope={
                            "type": "store",
                            "label": manifest.scope_label,
                            "applicability": "verified_store_selection",
                        },
                        limitations=[
                            "Copertura parziale: escluse le meccaniche complesse e le pagine non acquisite",
                            "I reparti freschi richiedono la presenza del reparto nel negozio",
                        ],
                        source_url=product_url,
                        evidence={
                            "capture_id": capture_id,
                            "url": url,
                            "selector": f"#contenitoreBoxOfferte .anteprima_offerta[{index}]",
                            "raw_price": raw_price,
                            "raw_conditions": text(node),
                            "scope_url": manifest.entry_urls[0],
                            "validity_selector": "#volantino-per-categoria .validita_volantino",
                        },
                        parser_version=self.parser_version,
                        first_seen_at=now,
                        last_seen_at=now,
                        last_verified_at=now,
                    )
                )
            except (ValueError, TypeError, KeyError, AttributeError):
                batch.quarantined += 1
        return batch


def collect_despar(manifest, fetcher, stage):
    # A fresh Fetcher per scope gives an isolated cookie jar. The form is the same
    # public store preference action used by visitors, without account/login.
    html, _, _ = fetcher.fetch(manifest.entry_urls[0])
    soup = BeautifulSoup(html, "html.parser")
    form = soup.select_one("#formPuntoVenditaPreferito")
    if not form or form.get("method", "").lower() != "post":
        raise StructuralError("Selezione pubblica Despar assente")
    endpoint = urljoin(manifest.entry_urls[0], form["action"])
    if endpoint != manifest.selection_endpoint:
        raise StructuralError("Modulo Despar diverso dalla sede verificata")
    fields = {n["name"]: n.get("value", "") for n in form.select("input[name]")}
    if set(fields) - {"_method", "imposta_punto_vendita_preferito", "__ncforminfo"}:
        raise StructuralError("Il modulo richiede nuovi dati")
    fetcher.request(endpoint, method="POST", fields=fields)
    # Follow only the catalog route observed in the store-selected official site.
    url = f"https://www.despar.it/it/volantino-digitale/{manifest.store_id}/"
    batch = Batch(completeness="partial", visited=[manifest.entry_urls[0]])
    seen = set()
    for page in range(manifest.max_catalog_pages):
        try:
            stage("fetch")
            html, cid, final = fetcher.fetch(url)
            stage("parse")
            part = DesparAdapter().extract(html, final, cid, manifest)
            if batch.campaign_ids and batch.campaign_ids != part.campaign_ids:
                raise StructuralError("Campagna cambiata durante la raccolta")
            if any(o.id in seen for o in part.offers):
                raise StructuralError("Paginazione senza avanzamento")
            seen.update(o.id for o in part.offers)
            batch.offers.extend(part.offers)
            batch.extracted += part.extracted
            batch.quarantined += part.quarantined
            batch.visited.extend(part.visited)
            batch.campaign_ids = part.campaign_ids
            soup = BeautifulSoup(html, "html.parser")
            next_page = soup.select_one('#volantino-per-categoria a[rel="next"]')
            if not next_page:
                break
            url = urljoin(final, next_page["href"])
            if url != f"https://www.despar.it/it/volantino-digitale/page:{page + 2}":
                raise StructuralError("Paginazione Despar cambiata")
        except FetchError as exc:
            if exc.code in [
                "BLOCKED_ACCESS",
                "ROBOTS_BLOCKED",
                "RATE_LIMITED",
                "DESTINATION_BLOCKED",
            ]:
                raise
            batch.failed.append(url)
            break
        except StructuralError:
            if not batch.offers:
                raise
            batch.failed.append(url)
            break
    if not batch.offers:
        raise StructuralError("Nessun prodotto Despar supera i controlli")
    batch.warnings = [
        f"{len(batch.visited) - 1} pagine acquisite; {batch.quarantined} meccaniche escluse. Copertura parziale."
    ]
    return batch
