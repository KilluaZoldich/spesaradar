import json
import signal
import threading
import time
from urllib.parse import urljoin

from app.adapters.base import Batch, StructuralError
from app.adapters.eurospin import EurospinAdapter
from app.adapters.lidl import LidlAdapter
from app.config import manifests
from app.jobs.queue import claim, fail, heartbeat, publish, schedule
from app.security.fetch import Fetcher, FetchError, retention
from app.storage.db import DB_PATH
from bs4 import BeautifulSoup

stop = threading.Event()


def collect(m, fetcher, stage):
    adapter = LidlAdapter() if m.retailer_id == "lidl" else EurospinAdapter()
    entry = m.entry_urls[0]
    html, cid, url = fetcher.fetch(entry)
    if m.retailer_id != "lidl":
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


def run_job(job):
    m = manifests()[job.source_id]
    fetcher = Fetcher(m)
    done = threading.Event()
    started = time.monotonic()

    def beat():
        while not done.wait(30):
            (DB_PATH.parent / "worker.heartbeat").touch()
            if not heartbeat(job.id, job.lease_token):
                break

    thread = threading.Thread(target=beat, daemon=True)
    thread.start()

    def stage(value):
        if not manifests()[job.source_id].enabled:
            raise FetchError("DISABLED", "Fonte disabilitata")
        if not heartbeat(job.id, job.lease_token, value):
            raise FetchError("LEASE_LOST", "Raccolta ripresa da altro worker")

    try:
        batch = collect(m, fetcher, stage)
        stage("validate")
        publish(
            job.id,
            job.lease_token,
            batch,
            {
                "requests": fetcher.count,
                "cache_hits": fetcher.cache_hits,
                "duration_seconds": round(time.monotonic() - started, 2),
                "browser": 0,
                "ocr": 0,
            },
        )
        outcome = batch.completeness
    except FetchError as exc:
        fail(job.id, job.lease_token, exc.code, str(exc), exc.retry_after)
        outcome = exc.code
    except Exception as exc:
        fail(
            job.id,
            job.lease_token,
            "PARSE_ERROR" if isinstance(exc, StructuralError) else "INTERNAL",
            "La fonte non è temporaneamente aggiornabile",
        )
        outcome = type(exc).__name__
    finally:
        done.set()
        thread.join(timeout=1)
        fetcher.close()
        retention()
    print(
        json.dumps(
            {
                "run_id": job.id,
                "job_id": job.id,
                "source_id": job.source_id,
                "scope": job.source_id,
                "stage": "finished",
                "outcome": outcome,
                "duration_seconds": round(time.monotonic() - started, 2),
                "requests": fetcher.count,
            }
        ),
        flush=True,
    )


def main():
    signal.signal(signal.SIGTERM, lambda *_: stop.set())
    signal.signal(signal.SIGINT, lambda *_: stop.set())
    last_schedule = 0
    while not stop.is_set():
        (DB_PATH.parent / "worker.heartbeat").touch()
        if time.monotonic() - last_schedule > 60:
            schedule()
            retention()
            last_schedule = time.monotonic()
        job = claim()
        if job:
            run_job(job)
        else:
            stop.wait(2)


if __name__ == "__main__":
    main()
