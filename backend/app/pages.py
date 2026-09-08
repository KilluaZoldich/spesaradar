"""Publish a bounded, public catalog; never publish SQLite, captures or credentials."""

from __future__ import annotations

import argparse
import hashlib
import json
import time
import uuid
from pathlib import Path
from urllib.parse import urlsplit

from sqlalchemy import select

from app.api import categories, retailers, source_states, targets
from app.config import manifests
from app.domain.catalog import Offer, temporal, utcnow
from app.jobs.queue import claim, enqueue
from app.jobs.worker import run_job
from app.storage.db import Job, OfferRow, Session, SourceRow

# One audited native capture, including its original verification instant.
# Changing these facts requires a new source audit, never a timestamp edit.
REVIEWED_COOP_SHA256 = (
    "17dfb3efbf192edb906e38bddb92c989add556e9332b208fea327587f7dae7bd"
)

MAX_BYTES = 10 * 1024 * 1024
SOURCE_FIELDS = (
    "revision",
    "last_attempt",
    "last_success",
    "next_allowed",
    "failures",
    "state",
    "message",
    "completeness",
)


def safe_offer(data):
    offer = Offer.model_validate(data)
    m = manifests().get(offer.source_id)
    u = urlsplit(offer.source_url)
    if (
        not m
        or offer.data_origin != "official_live"
        or offer.quality == "quarantined"
        or u.scheme != "https"
        or u.hostname not in m.allowed_domains
        or u.username
        or u.password
        or u.port not in (None, 443)
        or offer.retailer_id != m.retailer_id
        or offer.target_ids != [m.source_id]
        or offer.last_verified_at > utcnow()
    ):
        raise ValueError("Record non ammesso nel catalogo pubblico")
    d = offer.model_dump(mode="json")
    d["evidence"] = {
        "url": offer.source_url,
        "selector": str(offer.evidence.get("selector", ""))[:500],
        "raw_price": offer.price.raw_text if offer.price else None,
    }
    return d


def export_snapshot(path):
    now = utcnow()
    with Session() as s:
        records = []
        for row in s.scalars(select(OfferRow).order_by(OfferRow.id)):
            status, freshness = temporal(row.payload, now)
            if (
                row.payload["quality"] == "quarantined"
                or freshness == "hidden"
                or status == "expired"
            ):
                continue
            data = safe_offer(row.payload)
            records.append(
                {
                    "offer": data,
                    "withdrawn": row.withdrawn,
                    "missing_count": row.missing_count,
                    "last_missing_at": row.last_missing_at,
                }
            )
        sources = source_states(s, list(manifests()))
        source_records = {
            row.id: {k: getattr(row, k) for k in SOURCE_FIELDS}
            for row in s.scalars(select(SourceRow))
            if row.id in manifests()
        }
    payload = {
        "schema_version": 1,
        "generated_at": now.isoformat(),
        "retailers": retailers(),
        "targets": targets(q=""),
        "categories": categories(),
        "sources": sources,
        "source_records": source_records,
        "records": records,
    }
    content = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    if len(content.encode()) > MAX_BYTES:
        raise ValueError("Catalogo oltre il budget di pubblicazione")
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(content)
    temporary.replace(path)
    print(
        json.dumps(
            {"published_records": len(records), "sources": sources}, ensure_ascii=False
        )
    )
    return payload


def restore_snapshot(path):
    path = Path(path)
    if path.stat().st_size > MAX_BYTES:
        raise ValueError("Snapshot troppo grande")
    snapshot = json.loads(path.read_text())
    if snapshot.get("schema_version") != 1 or len(snapshot.get("records", [])) > 10000:
        raise ValueError("Snapshot non compatibile")
    records = [(r, safe_offer(r["offer"])) for r in snapshot["records"]]
    with Session.begin() as s:
        for id, values in snapshot.get("source_records", {}).items():
            if id not in manifests():
                continue
            row = SourceRow(id=id)
            for field in SOURCE_FIELDS:
                value = values.get(field)
                if field in ("revision", "failures"):
                    if not isinstance(value, int) or not 0 <= value <= 10**9:
                        raise ValueError("Contatore non valido")
                elif field in ("last_attempt", "last_success", "next_allowed"):
                    if value is not None and (
                        not isinstance(value, (int, float))
                        or not 0 <= value <= time.time() + 7 * 86400
                    ):
                        raise ValueError("Istante non valido")
                elif value is not None and (
                    not isinstance(value, str) or len(value) > 2000
                ):
                    raise ValueError("Stato non valido")
                setattr(row, field, value)
            s.merge(row)
        for record, data in records:
            s.merge(
                OfferRow(
                    id=data["id"],
                    source_id=data["source_id"],
                    campaign_id=data["campaign_id"],
                    payload=data,
                    withdrawn=bool(record["withdrawn"]),
                    missing_count=int(record["missing_count"]),
                    last_missing_at=record["last_missing_at"],
                )
            )


def restore_reviewed_records(path):
    """Admit already verified facts as old cache; never reset remote source health.

    Maintainer-only file from a successful local run. This does not fetch, renew
    timestamps, unwithdraw records, or override a newer successful source scan.
    """
    path = Path(path)
    if path.stat().st_size > MAX_BYTES:
        raise ValueError("Cache verificata troppo grande")
    snapshot = json.loads(path.read_text())
    if snapshot.get("schema_version") != 1 or len(snapshot.get("records", [])) != 1:
        raise ValueError("Cache verificata non compatibile")
    # Validate the entire input before any write, and discard private evidence.
    offers = [
        safe_offer(record["offer"])
        for record in snapshot["records"]
        if not record.get("withdrawn")
    ]
    for data in offers:
        digest = hashlib.sha256(
            json.dumps(
                data, sort_keys=True, ensure_ascii=False, separators=(",", ":")
            ).encode()
        ).hexdigest()
        if digest != REVIEWED_COOP_SHA256:
            raise ValueError(
                "Cache diversa dal buono Coop verificato: richiesto nuovo audit"
            )
    now = utcnow()
    admitted = 0
    with Session.begin() as s:
        for data in offers:
            state, freshness = temporal(data, now)
            if (
                state == "expired"
                or freshness == "hidden"
                or s.get(OfferRow, data["id"])
            ):
                continue
            source = s.get(SourceRow, data["source_id"])
            verified = Offer.model_validate(data).last_verified_at.timestamp()
            if (
                source is None
                or source.last_success is not None
                and source.last_success > verified
            ):
                continue
            s.add(
                OfferRow(
                    id=data["id"],
                    source_id=data["source_id"],
                    campaign_id=data["campaign_id"],
                    payload=data,
                )
            )
            source.revision += 1
            admitted += 1
    print(
        json.dumps(
            {
                "reviewed_cache_admitted": admitted,
                "verification_timestamps_renewed": False,
            }
        )
    )


def collect_once(initial_probe=False):
    ids = [id for id, m in manifests().items() if m.enabled]
    _, entries = enqueue(ids)
    if initial_probe:
        # One deployment smoke test may use fresh bootstrap data. Respect source cooldown
        # and access suspensions; leave last_success/offer timestamps untouched on failure.
        with Session.begin() as s:
            for entry in entries:
                source = s.get(SourceRow, entry["source_id"])
                if (
                    entry["disposition"] == "cache"
                    and source.next_allowed <= time.time()
                ):
                    now = time.time()
                    s.add(Job(id=uuid.uuid4().hex, source_id=source.id, created_at=now))
                    source.last_attempt = now
                    source.next_allowed = now + manifests()[source.id].cooldown_seconds
                    source.state = "queued"
    for _ in ids:
        job = claim()
        if job is None:
            break
        run_job(job)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--restore", type=Path)
    parser.add_argument("--export", type=Path, required=True)
    parser.add_argument("--collect", action="store_true")
    parser.add_argument("--reviewed-cache", type=Path)
    parser.add_argument("--initial-probe", action="store_true")
    args = parser.parse_args()
    if args.restore:
        restore_snapshot(args.restore)
    if args.reviewed_cache:
        restore_reviewed_records(args.reviewed_cache)
    if args.collect:
        collect_once(args.initial_probe)
    export_snapshot(args.export)


if __name__ == "__main__":
    main()
