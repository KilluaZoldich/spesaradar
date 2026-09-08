from datetime import timedelta

from app.domain.catalog import (
    Conditions,
    Offer,
    Validity,
    classify,
    identity,
    normalized,
    package_and_price,
    utcnow,
)


def offer(
    title="Petto di pollo",
    source="lidl-national",
    amount=349,
    loyalty=None,
    format="500 g",
    **kwargs,
):
    now = utcnow()
    pack, price = package_and_price(format, amount, "pack", f"{amount} centesimi")
    return Offer(
        id=identity(title, source, format),
        data_origin="synthetic_fixture",
        retailer_id=source.split("-")[0],
        source_id=source,
        campaign_id="fixture-campaign",
        target_ids=[source],
        title=title,
        title_normalized=normalized(title),
        **classify(title),
        package=pack,
        price=price,
        conditions=Conditions(loyalty_required=loyalty),
        validity=Validity(
            start_at=now - timedelta(days=1),
            end_at_exclusive=now + timedelta(days=1),
            evidence_level="explicit_dates",
        ),
        scope={"type": "national", "label": "Fixture sintetica"},
        source_url="https://fixture.invalid/test",
        evidence={"url": "https://fixture.invalid/test", "raw_price": "fixture"},
        parser_version="fixture",
        first_seen_at=now,
        last_seen_at=now,
        last_verified_at=now,
        **kwargs,
    )


def publish_offers(items, complete="complete"):
    from app.adapters.base import Batch
    from app.jobs.queue import claim, enqueue, publish

    source = items[0].source_id
    enqueue([source])
    job = claim()
    publish(
        job.id,
        job.lease_token,
        Batch(
            offers=items,
            completeness=complete,
            extracted=len(items),
            campaign_ids=["fixture-campaign"],
        ),
    )
    return job
