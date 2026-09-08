import os
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, model_validator

ROOT = Path(__file__).resolve().parents[2]


class Manifest(BaseModel):
    source_id: str
    retailer_id: str
    name: str
    source_type: Literal["html", "text_pdf"]
    parser_version: str
    allowed_domains: list[str]
    entry_urls: list[str]
    audit_status: Literal[
        "candidate",
        "verified_supported",
        "partial",
        "blocked_access",
        "permission_required",
        "unsupported_format",
        "disabled",
    ]
    enabled: bool
    scope_type: Literal["national", "regional", "store", "online"]
    scope_label: str
    capabilities: list[str]
    max_requests: int = Field(ge=1, le=60)
    min_interval_seconds: float = Field(ge=3)
    deadline_seconds: int = Field(ge=1, le=180)
    refresh_seconds: int = Field(ge=43200)
    cooldown_seconds: int = Field(ge=1800)
    suspend_on: list[int]
    timeout_seconds: int = Field(le=30)
    connector: (
        Literal[
            "lidl", "eurospin", "md", "conad_pdf", "despar_html", "famila_selex_pdf"
        ]
        | None
    ) = None
    selection_endpoint: str | None = None
    max_catalog_pages: int = Field(default=20, ge=1, le=40)
    store_id: str | None = None
    campaign_title_suffix: str | None = None
    max_documents: int = Field(default=2, ge=1, le=3)
    accept_encoding: Literal["gzip, deflate", "identity"] = "gzip, deflate"

    @model_validator(mode="after")
    def admitted(self):
        if self.enabled and self.audit_status not in ["partial", "verified_supported"]:
            raise ValueError("Una fonte deve superare l’audit prima dell’abilitazione")
        if self.connector == "conad_pdf" and (
            not self.store_id or not self.campaign_title_suffix
        ):
            raise ValueError("Profilo Conad privo di sede o ambito campagna")
        if self.connector == "despar_html" and (
            not self.store_id or not self.selection_endpoint
        ):
            raise ValueError("Profilo Despar privo di sede o modulo verificato")
        return self


def manifests():
    disabled = os.getenv("DISABLED_SOURCES", "").split(",")
    output = {}
    for p in (ROOT / "config/sources").glob("*.json"):
        m = Manifest.model_validate_json(p.read_text())
        if m.source_id in disabled:
            m.enabled = False
        output[m.source_id] = m
    return output


MAX_TARGETS = int(os.getenv("MAX_TARGETS", "5"))
