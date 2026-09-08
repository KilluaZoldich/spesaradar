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
