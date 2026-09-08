"""Shared collector entry point for workers and isolated onboarding/replay tools."""

from urllib.parse import urljoin

from app.adapters.base import Batch, StructuralError
from app.adapters.conad import ConadPDFAdapter, resolve, validate_pdf_url
from app.adapters.eurospin import EurospinAdapter
from app.adapters.lidl import LidlAdapter
from app.adapters.md import MDAdapter
from app.security.fetch import FetchError
from bs4 import BeautifulSoup


def collect_pdf(m, fetcher, stage):
    entry = m.entry_urls[0]
    html, _, _ = fetcher.fetch(entry)
    campaigns = resolve(html, m)
    batch = Batch(completeness="partial", visited=[entry])
    for campaign in campaigns:
        try:
            stage("fetch")
            body, cid, url = fetcher.fetch_bytes(
                campaign["url"], max_bytes=30 * 1024 * 1024
            )
            validate_pdf_url(url, campaign["filename"])
            stage("parse")
            part = ConadPDFAdapter().extract(
                body, url, cid, m, campaign, deadline=fetcher.start + m.deadline_seconds
            )
            batch.offers.extend(part.offers)
            batch.extracted += part.extracted
            batch.quarantined += part.quarantined
            batch.warnings.extend(part.warnings)
            batch.visited.extend(part.visited)
            batch.campaign_ids.extend(part.campaign_ids)
        except FetchError as exc:
            if exc.code in [
                "BLOCKED_ACCESS",
                "ROBOTS_BLOCKED",
                "RATE_LIMITED",
                "DESTINATION_BLOCKED",
            ]:
                raise
            batch.failed.append(campaign["url"])
        except StructuralError:
            batch.failed.append(campaign["url"])
    if not batch.offers:
        raise StructuralError("Nessuna campagna PDF supera i controlli")
    return batch


def collect(m, fetcher, stage):
    family = m.connector or m.retailer_id
    if family == "conad_pdf":
        return collect_pdf(m, fetcher, stage)
    adapters = {"lidl": LidlAdapter, "eurospin": EurospinAdapter, "md": MDAdapter}
    if family not in adapters:
        raise StructuralError("Nessun connettore verificato per questa insegna")
    adapter = adapters[family]()
    entry = m.entry_urls[0]
    html, cid, url = fetcher.fetch(entry)
    if isinstance(adapter, MDAdapter):
        catalog_url = adapter.resolve(html, m)
        html, cid, url = fetcher.fetch(catalog_url)
        stage("parse")
        batch = adapter.extract(html, url, cid, m)
        batch.visited.insert(0, entry)
        return batch
    if family != "lidl":
        stage("parse")
        return adapter.extract(html, url, cid)
    soup = BeautifulSoup(html, "html.parser")
    links = list(
        dict.fromkeys(
            urljoin(entry, a["href"])
            for a in soup.select("a[href]")
            if "/c/" in a["href"] and "-kw-" in a["href"] and "/a" in a["href"]
        )
    )
    if not links:
        raise StructuralError("Navigazione campagne Lidl non riconosciuta")
    batch = Batch(completeness="complete", visited=[entry])
    for link in links:
        try:
            stage("fetch")
            html, cid, url = fetcher.fetch(link)
            stage("parse")
            part = adapter.extract(html, url, cid)
            batch.offers.extend(part.offers)
            batch.extracted += part.extracted
            batch.quarantined += part.quarantined
            batch.warnings.extend(part.warnings)
            batch.visited.extend(part.visited)
            batch.campaign_ids.extend(part.campaign_ids)
            if part.completeness != "complete":
                batch.completeness = "partial"
        except FetchError as exc:
            if exc.code in [
                "BLOCKED_ACCESS",
                "ROBOTS_BLOCKED",
                "RATE_LIMITED",
                "DESTINATION_BLOCKED",
            ]:
                raise
            batch.failed.append(link)
            batch.completeness = "partial"
            if exc.code == "BUDGET":
                break
        except StructuralError:
            batch.failed.append(link)
            batch.completeness = "partial"
    if not batch.offers:
        raise StructuralError("Nessuna campagna Lidl verificabile")
    return batch
