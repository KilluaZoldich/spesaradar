import os
from pathlib import Path

from sqlalchemy import (
    JSON,
    Float,
    Index,
    String,
    Text,
    create_engine,
    event,
    text,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker

DB_PATH = Path(os.environ.get("SPESARADAR_DB", ".private/spesaradar.db")).resolve()
DB_PATH.parent.mkdir(parents=True, exist_ok=True)
engine = create_engine(
    "sqlite:///" + str(DB_PATH), connect_args={"timeout": 15}, pool_pre_ping=True
)


@event.listens_for(engine, "connect")
def pragmas(conn, _):
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=15000")
    conn.execute("PRAGMA foreign_keys=ON")


Session = sessionmaker(engine, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


class OfferRow(Base):
    __tablename__ = "offers"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    source_id: Mapped[str] = mapped_column(String, index=True)
    campaign_id: Mapped[str] = mapped_column(String, index=True)
    payload: Mapped[dict] = mapped_column(JSON)
    withdrawn: Mapped[bool] = mapped_column(default=False)
    missing_count: Mapped[int] = mapped_column(default=0)
    last_missing_at: Mapped[float | None] = mapped_column(Float, nullable=True)


class SourceRow(Base):
    __tablename__ = "sources"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    revision: Mapped[int] = mapped_column(default=0)
    last_requested: Mapped[float | None] = mapped_column(Float, nullable=True)
    last_attempt: Mapped[float | None] = mapped_column(Float, nullable=True)
    last_success: Mapped[float | None] = mapped_column(Float, nullable=True)
    next_allowed: Mapped[float] = mapped_column(default=0)
    failures: Mapped[int] = mapped_column(default=0)
    state: Mapped[str] = mapped_column(default="idle")
    message: Mapped[str | None] = mapped_column(Text, nullable=True)
    completeness: Mapped[str] = mapped_column(default="unknown")
    metrics: Mapped[dict] = mapped_column(JSON, default=dict)


class Job(Base):
    __tablename__ = "jobs"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    source_id: Mapped[str] = mapped_column(String, index=True)
    state: Mapped[str] = mapped_column(String, default="queued")
    stage: Mapped[str] = mapped_column(String, default="queued")
    created_at: Mapped[float] = mapped_column(Float)
    started_at: Mapped[float | None] = mapped_column(Float, nullable=True)
    finished_at: Mapped[float | None] = mapped_column(Float, nullable=True)
    lease_until: Mapped[float | None] = mapped_column(Float, nullable=True)
    heartbeat_at: Mapped[float | None] = mapped_column(Float, nullable=True)
    lease_token: Mapped[str | None] = mapped_column(String, nullable=True)
    attempts: Mapped[int] = mapped_column(default=0)
    message: Mapped[str | None] = mapped_column(Text, nullable=True)
    counters: Mapped[dict] = mapped_column(JSON, default=dict)


Index(
    "one_active_job_per_source",
    Job.source_id,
    unique=True,
    sqlite_where=text("state IN ('queued','running')"),
)


class Refresh(Base):
    __tablename__ = "refreshes"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    created_at: Mapped[float] = mapped_column(Float)
    targets: Mapped[list] = mapped_column(JSON)


class CaptureRow(Base):
    __tablename__ = "captures"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    url: Mapped[str] = mapped_column(Text)
    source_id: Mapped[str] = mapped_column(String, index=True)
    fetched_at: Mapped[float] = mapped_column(Float)
    sha256: Mapped[str] = mapped_column(String)
    path: Mapped[str | None] = mapped_column(Text, nullable=True)
    etag: Mapped[str | None] = mapped_column(Text, nullable=True)
    modified: Mapped[str | None] = mapped_column(Text, nullable=True)
