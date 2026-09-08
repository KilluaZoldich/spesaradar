"""Coop Alleanza: one audited public stationery voucher, no product API access."""

import hashlib
import re
from datetime import datetime, time
from urllib.parse import urljoin

from app.adapters.base import Batch, StructuralError
from app.domain.catalog import (
    ROME,
    Conditions,
    Offer,
    Package,
    Validity,
    VoucherBenefit,
    end_exclusive,
    identity,
    money,
    normalized,
    utcnow,
)
from bs4 import BeautifulSoup

MONTHS = {
    name: n
    for n, name in enumerate(
        (
            "gennaio febbraio marzo aprile maggio giugno luglio agosto settembre ottobre novembre dicembre"
        ).split(),
        1,
    )
}
SLUG = "spendi-riprendi-scuola.html"
# Full terms manually checked. Any editorial change requires a fresh audit.
AUDITED_TERMS_SHA256 = (
    "ffeb8d0cb98b015800cf5ce72d9a899c0fbcf208bd311fd5aa0129d1a7116fa1"
)


def resolve(html, manifest):
    soup = BeautifulSoup(html, "html.parser")
    canonical = soup.select_one('link[rel="canonical"]')
    if not canonical or canonical.get("href") != manifest.entry_urls[0]:
        raise StructuralError("Pagina sede Coop diversa da quella verificata")
    path = manifest.entry_urls[0].rsplit("/", 1)[-1].removesuffix(".html")
    expected = (
        f"https://www.coopalleanza3-0.it/volantino/promozione/featured/{path}/{SLUG}"
    )
    links = {urljoin(manifest.entry_urls[0], a["href"]) for a in soup.select("a[href]")}
    if expected not in links:
        raise StructuralError("Buono cartoleria non più collegato alla sede")
    return expected


def extract(html, url, capture_id, manifest):
    soup = BeautifulSoup(html, "html.parser")
    canonical = soup.select_one('link[rel="canonical"]')
    banner = soup.select_one('[data-component="bannerVolantino"]')
    block = soup.select_one(".content-title.black")
    try:
        if (
            not canonical
            or canonical.get("href") != url
            or banner["data-pdv_id"] != manifest.store_id
        ):
            raise ValueError("Sede/canonica non confermata")
        content = block.select_one(".promotion-content")
        raw = content.get_text(" ", strip=True)
        text = normalized(raw)
        if hashlib.sha256(text.encode()).hexdigest() != AUDITED_TERMS_SHA256:
            raise ValueError("Le condizioni del buono richiedono una nuova verifica")
        period = block.select_one(".h1 .h3").get_text(" ", strip=True)
        title_node = block.select_one(".h1")
        title = " ".join(
            str(t).strip() for t in title_node.find_all(string=True, recursive=False)
        ).strip()
        end = re.search(r"fino al (\d{1,2}) (\w+) (20\d{2}) acquista", text)
        interval = re.fullmatch(r"Dal (\d{1,2}) (\w+) al (\d{1,2}) (\w+)", period)
        mechanics = re.search(
            r"ogni (\d+)€ di spesa nel reparto cartoleria ottieni un buono sconto (\d+)€ da utilizzare entro il (\d{1,2}) (\w+) su una spesa minima di (\d+)€",
            text,
        )
        maximum = re.search(
            r"massimo (\d+) buoni nello stesso scontrino\. sconto massimo (\d+)€", text
        )
        required = (
            "il buono non e cumulabile con buoni di diversa tipologia",
            "ogni buono ottenuto e utilizzabile una sola volta",
            "se non sei socio o socia",
            "attivali prima della spesa",
            "iniziativa valida in tutti gli ipercoop",
        )
        if not all((end, interval, mechanics, maximum)) or not all(
            t in text for t in required
        ):
            raise ValueError("Meccanica/condizioni cambiate")
        year = int(end[3])

        def day(d, m):
            return datetime(year, MONTHS[m], int(d), tzinfo=ROME).date()

        earning_end = day(end[1], end[2])
        earning_start = day(interval[1], interval[2])
        redeem_end = day(mechanics[3], mechanics[4])
        if (
            day(interval[3], interval[4]) != earning_end
            or not earning_start <= earning_end <= redeem_end
            or (redeem_end - earning_start).days > 180
        ):
            raise ValueError("Periodi non concordanti")
        exclusion = next(
            (
                e.get_text(" ", strip=True)
                for e in content.select("h5")
                if "non è utilizzabile" in e.get_text()
            ),
            None,
        )
        if (
            not exclusion
            or "EasyCoop" not in exclusion
            or "latte infanzia tipo 1" not in exclusion
        ):
            raise ValueError("Esclusioni non riconosciute")
        amount, earn_min, use_min = (
            money(mechanics[2] + ",00"),
            money(mechanics[1] + ",00"),
            money(mechanics[5] + ",00"),
        )
        count, cap = int(maximum[1]), money(maximum[2] + ",00")
        if (
            not all((amount, earn_min, use_min, cap))
            or amount * count != cap
            or amount > use_min
        ):
            raise ValueError("Beneficio non coerente")
        if title != f"Spendi {mechanics[1]}€ di cartoleria & riprendi {mechanics[2]}€":
            raise ValueError("Titolo e meccanica discordanti")
        earning = Validity(
            start_at=datetime.combine(earning_start, time.min, ROME),
            end_at_exclusive=end_exclusive(earning_end),
            raw_text=period + f" {year}",
            evidence_level="explicit_dates",
        )
        redemption = Validity(
            end_at_exclusive=end_exclusive(redeem_end),
            raw_text=f"Entro il {mechanics[3]} {mechanics[4]} {year}; inizio utilizzo non specificato",
            evidence_level="explicit_dates",
        )
        instructions = "Buono cartaceo: scansiona il codice a barre in cassa. Per i soci è disponibile anche nell’area coupon; se usi il buono digitale devi attivarlo prima della spesa. Chi rinuncia allo scontrino cartaceo o paga nell’app Salvatempo riceve il buono nell’area coupon. Ogni buono è utilizzabile una sola volta. SpesaRadar non attiva il buono."
        essential = (
            f"Ogni {mechanics[1]} € di cartoleria dà un buono di {mechanics[2]} €. Per utilizzarlo: spesa minima {mechanics[5]} €. Massimo {count} buoni nello stesso scontrino, sconto massimo {maximum[2]} €. "
            + exclusion
        )
        now = utcnow()
        offer = Offer(
            id=identity(manifest.source_id, SLUG, str(year)),
            offer_type="future_voucher",
            source_offer_id=SLUG,
            retailer_id=manifest.retailer_id,
            source_id=manifest.source_id,
            campaign_id=f"cartoleria-{year}",
            target_ids=[manifest.source_id],
            title=title,
            title_normalized=normalized(title),
            category_id="altri",
            category_rule_id="not-a-product",
            classification_level="unclassified",
            classification_version="1",
            package=Package(),
            price=None,
            benefit=VoucherBenefit(
                amount_cents=amount,
                earning_minimum_spend_cents=earn_min,
                redemption_minimum_spend_cents=use_min,
                earning_category="Cartoleria",
                earning_validity=earning,
                redemption_validity=redemption,
                maximum_vouchers_per_receipt=count,
                maximum_discount_cents=cap,
                exclusions=exclusion,
                redemption_instructions=instructions,
                raw_text=essential,
            ),
            conditions=Conditions(
                status="complete",
                loyalty_required=False,
                app_activation_required=False,
                minimum_spend_cents=use_min,
                raw_text=essential,
            ),
            validity=Validity(
                start_at=earning.start_at,
                end_at_exclusive=redemption.end_at_exclusive,
                raw_text=f"Ottenimento: {earning.raw_text}. Utilizzo: {redemption.raw_text}.",
                evidence_level="explicit_dates",
            ),
            scope={
                "type": "store",
                "label": manifest.scope_label,
                "applicability": "official_store_link",
            },
            quality="limited",
            limitations=[
                "Solo questo buono pubblico; catalogo prodotti Coop non acquisito.",
                "Iniziativa nei negozi in cui sono presenti i prodotti; disponibilità a scaffale non garantita.",
                "La fonte non specifica una data iniziale di utilizzo del buono.",
            ],
            source_url=url,
            evidence={
                "capture_id": capture_id,
                "url": url,
                "selector": ".content-title.black .promotion-content",
                "raw_benefit": essential,
            },
            parser_version=manifest.parser_version,
            first_seen_at=now,
            last_seen_at=now,
            last_verified_at=now,
        )
        return Batch(
            offers=[offer],
            completeness="partial",
            extracted=1,
            visited=[url],
            campaign_ids=[offer.campaign_id],
        )
    except (ValueError, TypeError, AttributeError, KeyError) as exc:
        raise StructuralError("Buono Coop fuori dal profilo verificato") from exc


def collect_coop(manifest, fetcher, stage):
    entry = manifest.entry_urls[0]
    html, _, canonical = fetcher.fetch(entry)
    if canonical != entry:
        raise StructuralError("Redirect della sede Coop non verificato")
    url = resolve(html, manifest)
    stage("fetch")
    html, cid, canonical = fetcher.fetch(url)
    if canonical != url:
        raise StructuralError("Redirect del buono Coop non verificato")
    stage("parse")
    batch = extract(html, url, cid, manifest)
    batch.visited.insert(0, entry)
    return batch
