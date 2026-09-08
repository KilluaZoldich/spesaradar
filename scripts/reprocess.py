"""Reparse private captures locally after parser changes; no network, no refreshed timestamps."""

import sys
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
from app.adapters.base import Batch, StructuralError
from app.adapters.eurospin import EurospinAdapter
from app.adapters.lidl import LidlAdapter
from app.jobs.queue import publish
from app.storage.db import CaptureRow, Job, OfferRow, Session, SourceRow
from sqlalchemy import select


def run(source):
    adapter = LidlAdapter() if source == "lidl-national" else EurospinAdapter()
    batch = Batch(completeness="partial")
    seen = set()
    with Session() as s:
        captures = s.scalars(
            select(CaptureRow)
            .where(CaptureRow.source_id == source)
            .order_by(CaptureRow.fetched_at.desc())
        ).all()
        original_success = s.get(SourceRow, source).last_success
    for c in captures:
        if c.url in seen or not c.path or not Path(c.path).is_file():
            continue
        seen.add(c.url)
        if source == "lidl-national" and "/c/" not in c.url:
            continue
        try:
            part = adapter.extract(Path(c.path).read_text(), c.url, c.id)
        except StructuralError:
            batch.failed.append(c.url)
            continue
        for o in part.offers:
            o.last_verified_at = o.last_seen_at = datetime.fromtimestamp(
                c.fetched_at, UTC
            )
        batch.offers.extend(part.offers)
        batch.extracted += part.extracted
        batch.quarantined += part.quarantined
        batch.warnings.extend(part.warnings)
        batch.visited.append(c.url)
        batch.campaign_ids.extend(part.campaign_ids)
    jobid = uuid.uuid4().hex
    token = uuid.uuid4().hex
    with Session.begin() as s:
        for row in s.scalars(select(OfferRow).where(OfferRow.source_id == source)):
            d = dict(row.payload)
            d["quality"] = "quarantined"
            d["limitations"] = ["Riesame dopo correzione del parser"]
            row.payload = d
        s.add(
            Job(
                id=jobid,
                source_id=source,
                state="running",
                stage="reprocess",
                created_at=time.time(),
                started_at=time.time(),
                lease_until=time.time() + 120,
                lease_token=token,
                attempts=1,
            )
        )
    publish(jobid, token, batch, {"reprocessed_without_network": True})
    with Session.begin() as s:
        s.get(SourceRow, source).last_success = original_success
    print(source, len(batch.offers), batch.quarantined, len(batch.failed))


if __name__ == "__main__":
    for source in ["lidl-national", "eurospin-national"]:
        run(source)
