"""Synthetic test records never enter the deployed catalog."""

import json

import pytest
from app.pages import export_snapshot, restore_snapshot, safe_offer
from app.storage.db import OfferRow, Session, SourceRow
from helpers import offer


def published_fixture():
    # Explicitly simulate the official-origin gate, without fetching a live source.
    o = offer()
    o.data_origin = "official_live"
    o.source_url = "https://www.lidl.it/p/test-fixture"
    o.evidence = {
        "capture_id": "PRIVATE-CAPTURE",
        "path": "/private/test.html",
        "selector": "synthetic",
    }
    return o


def test_reject_synthetic_and_foreign_sources():
    with pytest.raises(ValueError):
        safe_offer(offer().model_dump(mode="json"))
    o = published_fixture()
    o.source_url = "https://example.invalid/test"
    with pytest.raises(ValueError):
        safe_offer(o.model_dump(mode="json"))


def test_export_restore_preserves_verification_and_reconciliation(tmp_path):
    o = published_fixture()
    with Session.begin() as s:
        s.add(
            SourceRow(
                id=o.source_id,
                state="partial",
                revision=4,
                last_success=o.last_verified_at.timestamp(),
            )
        )
        s.add(
            OfferRow(
                id=o.id,
                source_id=o.source_id,
                campaign_id=o.campaign_id,
                payload=o.model_dump(mode="json"),
                missing_count=1,
                last_missing_at=123,
            )
        )
    path = tmp_path / "catalog.json"
    snapshot = export_snapshot(path)
    assert "PRIVATE-CAPTURE" not in path.read_text()
    assert "/private/test.html" not in path.read_text()
    assert (
        snapshot["records"][0]["offer"]["last_verified_at"]
        == o.model_dump(mode="json")["last_verified_at"]
    )
    with Session.begin() as s:
        s.query(OfferRow).delete()
        s.query(SourceRow).delete()
    restore_snapshot(path)
    with Session() as s:
        assert s.get(OfferRow, o.id).missing_count == 1
        assert s.get(SourceRow, o.source_id).revision == 4
        assert (
            s.get(OfferRow, o.id).payload["last_verified_at"]
            == snapshot["records"][0]["offer"]["last_verified_at"]
        )


def test_restore_is_atomic_on_invalid_record(tmp_path):
    o = published_fixture()
    path = tmp_path / "bad.json"
    path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "records": [
                    {
                        "offer": o.model_dump(mode="json"),
                        "withdrawn": False,
                        "missing_count": 0,
                        "last_missing_at": None,
                    },
                    {"offer": offer().model_dump(mode="json")},
                ],
            }
        )
    )
    with pytest.raises(ValueError):
        restore_snapshot(path)
    with Session() as s:
        assert s.query(OfferRow).count() == 0


def reviewed_coupon(monkeypatch):
    from datetime import timedelta
    from pathlib import Path

    from app.domain.catalog import Offer

    path = Path(__file__).resolve().parents[2] / "site/reviewed-cache.json"
    o = Offer.model_validate(json.loads(path.read_text())["records"][0]["offer"])
    monkeypatch.setattr(
        "app.pages.utcnow", lambda: o.last_verified_at + timedelta(minutes=10)
    )
    return o


def test_reviewed_cache_preserves_remote_block_and_original_time(tmp_path, monkeypatch):
    from app.pages import restore_reviewed_records

    o = reviewed_coupon(monkeypatch)
    verified = o.last_verified_at.timestamp()
    path = tmp_path / "reviewed.json"
    path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "records": [{"offer": o.model_dump(mode="json"), "withdrawn": False}],
            }
        )
    )
    with Session.begin() as s:
        s.add(
            SourceRow(
                id=o.source_id,
                state="blocked",
                revision=5,
                last_attempt=verified + 1,
                last_success=None,
                next_allowed=verified + 86400,
                failures=1,
                message="Blocked",
            )
        )
    restore_reviewed_records(path)
    restore_reviewed_records(path)
    with Session() as s:
        row = s.get(SourceRow, o.source_id)
        assert (
            row.state,
            row.failures,
            row.last_attempt,
            row.last_success,
            row.next_allowed,
            row.revision,
        ) == ("blocked", 1, verified + 1, None, verified + 86400, 6)
        assert (
            s.get(OfferRow, o.id).payload["last_verified_at"]
            == o.model_dump(mode="json")["last_verified_at"]
        )
        assert s.query(OfferRow).count() == 1


def test_reviewed_cache_cannot_override_newer_success_or_revive_old_data(
    tmp_path, monkeypatch
):
    from datetime import timedelta

    from app.pages import restore_reviewed_records

    o = reviewed_coupon(monkeypatch)
    path = tmp_path / "reviewed.json"

    def write():
        path.write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "records": [
                        {"offer": o.model_dump(mode="json"), "withdrawn": False}
                    ],
                }
            )
        )

    write()
    with Session.begin() as s:
        s.add(
            SourceRow(id=o.source_id, last_success=o.last_verified_at.timestamp() + 1)
        )
    restore_reviewed_records(path)
    with Session() as s:
        assert s.query(OfferRow).count() == 0
    monkeypatch.setattr(
        "app.pages.utcnow", lambda: o.last_verified_at + timedelta(hours=49)
    )
    with Session.begin() as s:
        s.get(SourceRow, o.source_id).last_success = None
    restore_reviewed_records(path)
    with Session() as s:
        assert s.query(OfferRow).count() == 0


@pytest.mark.parametrize("change", ["source", "identity", "economics", "timestamp"])
def test_reviewed_cache_rejects_unreviewed_facts(tmp_path, monkeypatch, change):
    from datetime import timedelta

    from app.pages import restore_reviewed_records

    o = reviewed_coupon(monkeypatch)
    if change == "source":
        o.source_id = "lidl-national"
    elif change == "identity":
        o.id = "another-voucher"
    elif change == "economics":
        o.benefit.amount_cents = 2000
    else:
        o.last_verified_at += timedelta(minutes=1)
    path = tmp_path / "changed.json"
    path.write_text(
        json.dumps(
            {"schema_version": 1, "records": [{"offer": o.model_dump(mode="json")}]}
        )
    )
    with pytest.raises(ValueError):
        restore_reviewed_records(path)
    with Session() as s:
        assert s.query(OfferRow).count() == 0
