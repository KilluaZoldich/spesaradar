"""Offline catalog benchmark: 5,000 declared synthetic rows in a temporary DB."""

import json
import os
import platform
import statistics
import sys
import tempfile
import time
from pathlib import Path

root = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(root / "backend"), str(root / "backend/tests")]
with tempfile.TemporaryDirectory(prefix="spesaradar-benchmark-") as folder:
    os.environ["SPESARADAR_DB"] = str(Path(folder) / "benchmark.db")
    from alembic import command
    from alembic.config import Config
    from app.api import app
    from app.storage.db import OfferRow, Session, SourceRow, engine
    from fastapi.testclient import TestClient
    from helpers import offer

    command.upgrade(Config(str(root / "alembic.ini")), "head")
    with Session.begin() as s:
        s.add(SourceRow(id="lidl-national", last_success=time.time()))
        s.add_all(
            [
                OfferRow(
                    id=(o := offer(f"Petto di pollo fixture {i}")).id,
                    source_id=o.source_id,
                    campaign_id=o.campaign_id,
                    payload=o.model_dump(mode="json"),
                )
                for i in range(5000)
            ]
        )
    durations = []
    with TestClient(app, base_url="http://127.0.0.1:8080") as client:
        for i in range(110):
            started = time.perf_counter()
            response = client.get(
                "/api/v1/offers", params={"target_ids": "lidl-national", "limit": 24}
            )
            elapsed = (time.perf_counter() - started) * 1000
            assert response.status_code == 200 and response.json()["total"] == 5000
            if i >= 10:
                durations.append(elapsed)
    result = {
        "date": time.strftime("%Y-%m-%d"),
        "platform": platform.platform(),
        "python": platform.python_version(),
        "dataset": "5000 synthetic_fixture rows, one source; isolated temporary SQLite WAL",
        "concurrency": 1,
        "warmup_requests": 10,
        "measured_requests": 100,
        "page_size": 24,
        "transport": "FastAPI TestClient in process, includes JSON response serialization",
        "median_ms": round(statistics.median(durations), 2),
        "p95_ms": round(sorted(durations)[94], 2),
        "max_ms": round(max(durations), 2),
    }
    (root / "docs/benchmark.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))
    engine.dispose()
