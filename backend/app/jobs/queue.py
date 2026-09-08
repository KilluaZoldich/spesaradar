import random
import time
import uuid

from app.config import manifests
from app.storage.db import Job, OfferRow, Refresh, Session, SourceRow
from sqlalchemy import select, text

ACTIVE = ["queued", "running"]
TERMINAL = ["succeeded", "partial", "failed", "blocked", "cancelled"]


def enqueue(target_ids, now=None, *, user_activity=True):
    now = now or time.time()
    entries = []
    config = manifests()
    with Session() as s:
        s.execute(text("BEGIN IMMEDIATE"))
        for target in target_ids:
            m = config[target]
            source = s.get(SourceRow, target)
            if source is None:
                source = SourceRow(id=target)
                s.add(source)
                s.flush()
            if user_activity:
                source.last_requested = now
            job = s.scalar(
                select(Job).where(Job.source_id == target, Job.state.in_(ACTIVE))
            )
            disposition = "job_active" if job else "cache"
            if not m.enabled:
                disposition = "disabled"
            elif not job and source.next_allowed > now:
                disposition = "cooldown"
            elif not job and (
                not source.last_success
                or now - source.last_success >= m.refresh_seconds
            ):
                job = Job(id=uuid.uuid4().hex, source_id=target, created_at=now)
                s.add(job)
                disposition = "job_new"
                source.last_attempt = now
                source.next_allowed = now + m.cooldown_seconds
                source.state = "queued"
            entries.append(
                {
                    "target_id": target,
                    "source_id": target,
                    "disposition": disposition,
                    "job_id": job.id if job else None,
                    "next_allowed_at": source.next_allowed,
                }
            )
        ref = Refresh(id=uuid.uuid4().hex, created_at=now, targets=entries)
        s.add(ref)
        s.commit()
        return ref.id, entries


def claim(now=None):
    now = now or time.time()
    config = manifests()
    with Session() as s:
        s.execute(text("BEGIN IMMEDIATE"))
        for job in s.scalars(
            select(Job).where(Job.state == "running", Job.lease_until < now)
        ):
            job.state = "queued" if job.attempts < 3 else "failed"
            job.stage = job.state
            job.message = "Raccolta interrotta, recupero dopo riavvio"
            job.lease_token = None
            if job.state == "failed":
                source = s.get(SourceRow, job.source_id)
                source.state = "failed"
                source.message = job.message
                source.failures += 1
                source.next_allowed = max(source.next_allowed, now + 86400)
        s.flush()
        jobs = s.scalars(
            select(Job).where(Job.state == "queued").order_by(Job.created_at)
        ).all()
        for job in jobs:
            if job.source_id not in config or not config[job.source_id].enabled:
                job.state = "cancelled"
                job.stage = "cancelled"
                job.finished_at = now
                continue
            job.state = "running"
            job.stage = "fetch"
            job.attempts += 1
            job.started_at = now
            job.lease_until = now + 120
            job.heartbeat_at = now
            job.lease_token = uuid.uuid4().hex
            source = s.get(SourceRow, job.source_id)
            source.state = "running"
            source.last_attempt = now
            s.commit()
            return job
        s.commit()


def heartbeat(job_id, token, stage=None):
    with Session.begin() as s:
        s.execute(text("BEGIN IMMEDIATE"))
        job = s.get(Job, job_id)
        if not job or job.state != "running" or job.lease_token != token:
            return False
        job.heartbeat_at = time.time()
        job.lease_until = time.time() + 120
        if stage:
            job.stage = stage
        return True


def publish(job_id, token, batch, metrics=None):
    now = time.time()
    with Session() as s:
        s.execute(text("BEGIN IMMEDIATE"))
        job = s.get(Job, job_id)
        if (
            not job
            or job.state != "running"
            or job.lease_token != token
            or job.lease_until < now
        ):
            raise RuntimeError("Lease non valido")
        source = s.get(SourceRow, job.source_id)
        existing = {
            o.id: o
            for o in s.scalars(
                select(OfferRow).where(OfferRow.source_id == job.source_id)
            )
        }
        incoming = {}
        conflicts = set()
        for offer in batch.offers:
            data = offer.model_dump(mode="json")
            if offer.id in incoming and incoming[offer.id]["price"] != data["price"]:
                conflicts.add(offer.id)
                continue
            incoming[offer.id] = data
        for id in conflicts:
            incoming.pop(id, None)
        if conflicts:
            batch.completeness = "partial"
            batch.quarantined += len(conflicts)
            batch.warnings.append("Prezzi discordanti nello stesso lotto")
        # A catastrophic count collapse in a known campaign is never a complete disappearance signal.
        previous_count = sum(
            1
            for o in existing.values()
            if o.campaign_id in batch.campaign_ids and not o.withdrawn
        )
        if previous_count > 20 and len(incoming) < previous_count * 0.25:
            batch.completeness = "partial"
            batch.warnings.append("Riduzione anomala della campagna")
        for id, data in incoming.items():
            previous = existing.get(id)
            if previous:
                data["first_seen_at"] = previous.payload["first_seen_at"]
                for field, value in previous.payload["conditions"].items():
                    if data["conditions"].get(field) is None and value is not None:
                        data["conditions"][field] = value
                previous.payload = data
                previous.withdrawn = False
                previous.missing_count = 0
                previous.last_missing_at = None
            else:
                s.add(
                    OfferRow(
                        id=id,
                        source_id=job.source_id,
                        campaign_id=data["campaign_id"],
                        payload=data,
                    )
                )
        if batch.completeness == "complete":
            for id, row in existing.items():
                if (
                    id not in incoming
                    and row.campaign_id in batch.campaign_ids
                    and (not row.last_missing_at or now - row.last_missing_at >= 1800)
                ):
                    row.missing_count += 1
                    row.last_missing_at = now
                    if row.missing_count >= 2:
                        row.withdrawn = True
        state = "succeeded" if batch.completeness == "complete" else "partial"
        source.revision += 1
        source.last_success = now
        source.state = state
        source.failures = 0
        source.completeness = batch.completeness
        source.message = (
            "Aggiornamento parziale: alcuni articoli non sono verificabili"
            if state == "partial"
            else None
        )
        source.metrics = {
            "extracted": batch.extracted,
            "published": len(incoming),
            "limited": sum(x["quality"] == "limited" for x in incoming.values()),
            "quarantined": batch.quarantined,
            "duplicate_count": len(batch.offers) - len(incoming),
            "resources": len(batch.visited),
            "failed_resources": len(batch.failed),
            **(metrics or {}),
        }
        job.state = state
        job.stage = "published"
        job.finished_at = now
        job.counters = source.metrics
        job.message = source.message
        job.lease_until = None
        s.commit()


def fail(job_id, token, code, message, retry_after=0):
    with Session.begin() as s:
        s.execute(text("BEGIN IMMEDIATE"))
        job = s.get(Job, job_id)
        if not job or job.lease_token != token or job.state != "running":
            return
        blocked = code in ["BLOCKED_ACCESS", "ROBOTS_BLOCKED", "DESTINATION_BLOCKED"]
        job.state = "blocked" if blocked else "failed"
        job.stage = job.state
        job.message = message
        job.finished_at = time.time()
        job.lease_until = None
        source = s.get(SourceRow, job.source_id)
        source.state = job.state
        source.message = message
        source.failures += 1
        source.next_allowed = max(
            source.next_allowed,
            time.time()
            + max(retry_after, 86400 if blocked or source.failures >= 3 else 1800),
        )
        source.metrics = {**source.metrics, "last_error_code": code}


def schedule():
    now = time.time()
    with Session() as s:
        active = [
            r.id
            for r in s.scalars(
                select(SourceRow).where(
                    SourceRow.last_requested > now - 7 * 86400,
                    SourceRow.next_allowed <= now,
                )
            )
            if not r.last_success
            or now - r.last_success >= 43200 + random.randint(0, 600)
        ]
    for id in active:
        if id in manifests() and manifests()[id].enabled:
            # Preserve actual browser activity; scheduled jobs must not keep scopes active forever.
            enqueue([id], user_activity=False)
