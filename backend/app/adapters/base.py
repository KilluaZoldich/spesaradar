from dataclasses import dataclass, field
from typing import Literal, Protocol

from app.domain.catalog import Offer


@dataclass
class Batch:
    offers: list[Offer] = field(default_factory=list)
    completeness: Literal["complete", "partial", "unknown"] = "unknown"
    warnings: list[str] = field(default_factory=list)
    visited: list[str] = field(default_factory=list)
    failed: list[str] = field(default_factory=list)
    extracted: int = 0
    quarantined: int = 0
    campaign_ids: list[str] = field(default_factory=list)


class StructuralError(ValueError):
    pass


class Adapter(Protocol):
    parser_version: str

    def extract(self, html: str, url: str, capture_id: str) -> Batch: ...
