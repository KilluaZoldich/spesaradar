import os
import tempfile
from pathlib import Path

os.environ["SPESARADAR_DB"] = str(
    Path(tempfile.mkdtemp(prefix="spesaradar-tests-")) / "test.db"
)
import pytest
from alembic import command
from alembic.config import Config
from app.storage.db import Base, engine


@pytest.fixture(autouse=True)
def database():
    Base.metadata.drop_all(engine)
    with engine.begin() as c:
        c.exec_driver_sql("DROP TABLE IF EXISTS alembic_version")
    command.upgrade(Config("alembic.ini"), "head")
    yield


@pytest.fixture
def client():
    from app.api import app
    from fastapi.testclient import TestClient

    with TestClient(
        app,
        base_url="http://127.0.0.1:8080",
        headers={"Origin": "http://127.0.0.1:8080"},
    ) as client:
        yield client
