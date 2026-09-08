import time
from concurrent.futures import ThreadPoolExecutor

from app.adapters.base import Batch
from app.jobs.queue import claim, enqueue, fail, heartbeat, publish
from app.storage.db import Job, OfferRow, Session, SourceRow
from helpers import offer, publish_offers
from sqlalchemy import func, select


def test_simultaneous_refresh_deduplicated():
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(lambda _: enqueue(["lidl-national"]), range(12)))
    with Session() as s:
        assert s.scalar(select(func.count()).select_from(Job)) == 1
    assert len({r[1][0]["job_id"] for r in results}) == 1


def test_crash_recovery_fences_old_worker():
    enqueue(["lidl-national"])
    first = claim()
    second = claim(now=first.lease_until + 1)
    assert (
        first.id == second.id
        and second.attempts == 2
        and first.lease_token != second.lease_token
    )
    assert heartbeat(first.id, first.lease_token) is False
    import pytest

    with pytest.raises(RuntimeError):
        publish(first.id, first.lease_token, Batch(offers=[offer()]))
    publish(
        second.id, second.lease_token, Batch(offers=[offer()], completeness="complete")
    )
    with Session() as s:
        assert s.scalar(select(func.count()).select_from(OfferRow)) == 1


def new_job():
    with Session.begin() as s:
        source = s.get(SourceRow, "lidl-national")
        source.last_success = None
        source.next_allowed = 0
    enqueue(["lidl-national"])
    return claim()


def test_partial_never_removes_unseen_and_conditions_preserved():
    a, b = offer(loyalty=True), offer("Biscotti")
    publish_offers([a, b])
    j = new_job()
    a.conditions.loyalty_required = None
    publish(
        j.id,
        j.lease_token,
        Batch(offers=[a], completeness="partial", campaign_ids=["fixture-campaign"]),
    )
    with Session() as s:
        assert s.get(OfferRow, b.id).withdrawn is False
        assert s.get(OfferRow, a.id).payload["conditions"]["loyalty_required"] is True


def test_failed_job_does_not_verify_old_data():
    o = offer()
    publish_offers([o])
    with Session() as s:
        before = s.get(OfferRow, o.id).payload["last_verified_at"]
    j = new_job()
    fail(j.id, j.lease_token, "TIMEOUT", "Fonte non raggiungibile")
    with Session() as s:
        assert s.get(OfferRow, o.id).payload["last_verified_at"] == before
        assert s.get(SourceRow, j.source_id).state == "failed"


def test_disappearance_requires_two_complete_spaced_scans():
    a, b = offer(), offer("Biscotti")
    publish_offers([a, b])
    for n in range(2):
        j = new_job()
        if n:
            with Session.begin() as s:
                s.get(OfferRow, b.id).last_missing_at = time.time() - 1801
        publish(
            j.id,
            j.lease_token,
            Batch(
                offers=[a], completeness="complete", campaign_ids=["fixture-campaign"]
            ),
        )
        with Session() as s:
            assert s.get(OfferRow, b.id).withdrawn == (n == 1)


def test_conflict_never_picks_minimum():
    a, b = offer(amount=349), offer(amount=199)
    enqueue(["lidl-national"])
    j = claim()
    publish(j.id, j.lease_token, Batch(offers=[a, b], completeness="complete"))
    with Session() as s:
        assert s.scalar(select(func.count()).select_from(OfferRow)) == 0


def test_cache_cooldown_shared():
    publish_offers([offer()])
    _, entries = enqueue(["lidl-national"])
    assert entries[0]["disposition"] == "cooldown"


def test_multisource_and_facets(client):
    publish_offers([offer(), offer("Biscotti"), offer("Cibo per gatti con pollo")])
    publish_offers([offer("Pollo arrosto", source="eurospin-national")])
    p = [
        ("target_ids", "lidl-national"),
        ("target_ids", "eurospin-national"),
        ("q", "pollo"),
        ("category_ids", "carne"),
    ]
    r = client.get("/api/v1/offers", params=p).json()
    assert (
        r["total"] == 2
        and r["category_counts"]["animali"] == 1
        and r["category_counts"]["carne"] == 2
    )
    assert (
        client.get(
            "/api/v1/offers",
            params={"target_ids": "lidl-national", "loyalty": "not_required"},
        ).json()["total"]
        == 0
    )


def test_cursor_revision_and_filter_binding(client):
    publish_offers([offer("Pollo uno"), offer("Pollo due")])
    p = {"target_ids": "lidl-national", "limit": 1}
    page = client.get("/api/v1/offers", params=p).json()
    assert page["next_cursor"]
    assert (
        client.get(
            "/api/v1/offers", params={**p, "cursor": page["next_cursor"], "q": "uno"}
        ).json()["error"]["code"]
        == "INVALID_CURSOR"
    )
    with Session.begin() as s:
        s.get(SourceRow, "lidl-national").revision += 1
    assert (
        client.get(
            "/api/v1/offers", params={**p, "cursor": page["next_cursor"]}
        ).json()["error"]["code"]
        == "CATALOG_CHANGED"
    )


def test_api_safety(client):
    assert client.get("/api/v1/ready").status_code == 200
    assert client.get("/api/v1/offers").json()["error"]["code"] == "SELECT_TARGETS"
    assert (
        client.get(
            "/api/v1/offers", params={"target_ids": "http://127.0.0.1"}
        ).status_code
        == 422
    )
    assert (
        client.get(
            "/api/v1/offers", params={"target_ids": "lidl-national", "sort": "price"}
        ).status_code
        == 422
    )
    assert (
        client.post(
            "/api/v1/refreshes",
            headers={"Origin": "https://evil.invalid"},
            json={"target_ids": ["lidl-national"]},
        ).status_code
        == 403
    )
    assert (
        client.get("/api/v1/health", headers={"Host": "evil.invalid"}).status_code
        == 400
    )


def test_reads_never_start_jobs(client):
    client.get("/api/v1/offers", params={"target_ids": "lidl-national"})
    with Session() as s:
        assert s.scalar(select(func.count()).select_from(Job)) == 0


def test_scheduler_enqueue_does_not_extend_user_activity():
    enqueue(["lidl-national"])
    with Session() as s:
        before = s.get(SourceRow, "lidl-national").last_requested
    enqueue(["lidl-national"], now=before + 100, user_activity=False)
    with Session() as s:
        assert s.get(SourceRow, "lidl-national").last_requested == before


def test_cursor_must_be_object(client):
    import base64

    result = client.get(
        "/api/v1/offers",
        params={
            "target_ids": "lidl-national",
            "cursor": base64.urlsafe_b64encode(b"[]").decode(),
        },
    )
    assert (
        result.status_code == 422 and result.json()["error"]["code"] == "INVALID_CURSOR"
    )


def test_old_worker_cannot_fail_reclaimed_job():
    enqueue(["lidl-national"])
    first = claim()
    second = claim(now=first.lease_until + 1)
    fail(first.id, first.lease_token, "TIMEOUT", "Vecchio worker")
    with Session() as s:
        assert s.get(Job, second.id).state == "running"
        assert s.get(Job, second.id).lease_token == second.lease_token


def test_recovery_exhaustion_suspends_source():
    enqueue(["lidl-national"])
    job = claim()
    for _ in range(2):
        job = claim(now=job.lease_until + 1)
    now = job.lease_until + 1
    assert claim(now=now) is None
    with Session() as s:
        assert s.get(Job, job.id).state == "failed"
        assert s.get(SourceRow, job.source_id).next_allowed >= now + 86400


def test_period_facets_and_target_availability(client):
    from datetime import timedelta

    from app.domain.catalog import utcnow

    current = offer("Petto di pollo")
    future = offer("Biscotti")
    future.validity.start_at = utcnow() + timedelta(days=1)
    future.validity.end_at_exclusive = utcnow() + timedelta(days=3)
    publish_offers([current, future])
    r = client.get(
        "/api/v1/offers", params={"target_ids": "lidl-national", "validity": "current"}
    ).json()
    assert r["total"] == 1 and r["period_counts"] == {"current": 1, "future": 1}
    r = client.get(
        "/api/v1/offers",
        params={"target_ids": "lidl-national", "validity": "current", "q": "biscotti"},
    ).json()
    assert r["total"] == 0 and r["period_counts"] == {"current": 0, "future": 1}
    t = client.get("/api/v1/targets").json()["items"]
    assert next(x for x in t if x["id"] == "lidl-national")["availability"] == {
        "current": 1,
        "future": 1,
    }
