from __future__ import annotations

import base64
import hashlib
import json
import time
import uuid
from datetime import UTC, datetime
from typing import Literal

from fastapi import FastAPI, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy import func, select, text
from starlette.middleware.trustedhost import TrustedHostMiddleware

from app.config import MAX_TARGETS, manifests
from app.domain.catalog import CATEGORIES, normalized, temporal, utcnow
from app.jobs.queue import ACTIVE, enqueue
from app.storage.db import Job, OfferRow, Refresh, Session, SourceRow

app = FastAPI(
    title="SpesaRadar",
    version="0.1.0",
    docs_url=None,
    redoc_url=None,
    openapi_url="/api/openapi.json",
)
app.add_middleware(
    TrustedHostMiddleware, allowed_hosts=["127.0.0.1", "localhost", "testserver", "api"]
)


class APIError(Exception):
    def __init__(self, code, message, status=422):
        self.code = code
        self.message = message
        self.status = status


def error(code, message, status, request):
    return JSONResponse(
        {
            "error": {
                "code": code,
                "message": message,
                "correlation_id": getattr(
                    request.state, "correlation_id", uuid.uuid4().hex
                ),
                "details": None,
            }
        },
        status_code=status,
    )


@app.exception_handler(APIError)
async def known_error(request, exc):
    return error(exc.code, exc.message, exc.status, request)


@app.exception_handler(RequestValidationError)
async def validation_error(request, exc):
    return error(
        "INVALID_INPUT", "Controlla selezioni e filtri richiesti.", 422, request
    )


@app.middleware("http")
async def local_protection(request: Request, call_next):
    request.state.correlation_id = uuid.uuid4().hex
    if request.method not in ["GET", "HEAD", "OPTIONS"]:
        if request.headers.get("origin") not in [
            "http://127.0.0.1:8080",
            "http://localhost:8080",
        ] or request.headers.get("sec-fetch-site", "same-origin") not in [
            "same-origin",
            "none",
        ]:
            return error(
                "ORIGIN_REJECTED",
                "Richiesta consentita solo dall’app locale.",
                403,
                request,
            )
        if int(request.headers.get("content-length", "0")) > 4096:
            return error("INVALID_INPUT", "Richiesta troppo grande.", 413, request)
    try:
        response = await call_next(request)
    except Exception:
        return error(
            "INTERNAL", "Operazione non riuscita. Riprova tra poco.", 500, request
        )
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Cache-Control"] = "no-store"
    response.headers["X-Correlation-ID"] = request.state.correlation_id
    return response


UNSUPPORTED = [
    {
        "id": "carrefour",
        "name": "Carrefour",
        "support_status": "permission_required",
        "message": "Riuso dei contenuti soggetto ad autorizzazione; non acquisito.",
    },
    {
        "id": "ins",
        "name": "iN’s",
        "support_status": "unsupported_format",
        "message": "Volantino grafico: prezzi non ancora verificati automaticamente.",
    },
    {
        "id": "dpiu",
        "name": "DPiù",
        "support_status": "candidate",
        "message": "Offerte non ancora verificate per un negozio o un ambito preciso.",
    },
    {
        "id": "todis",
        "name": "Todis",
        "support_status": "candidate",
        "message": "Offerte alimentari per sede non ancora verificate.",
    },
    {
        "id": "aldi",
        "name": "ALDI",
        "support_status": "blocked_access",
        "message": "Accesso automatizzato bloccato dalla fonte.",
    },
    {
        "id": "coop",
        "name": "Coop Alleanza 3.0",
        "support_status": "blocked_access",
        "message": "Carpi 41012: sedi Borgogioioso e via Sigonio verificate. Accesso al servizio prodotti rifiutato; offerte non acquisite.",
        "source_url": "https://www.coopalleanza3-0.it/fare-spesa/elenco-negozi/dettaglio-negozio/3967-ipercoop-il-borgogioioso.html",
    },
    {
        "id": "despar",
        "name": "Despar / Interspar",
        "support_status": "blocked_access",
        "message": "Carpi 41012: Interspar di Tangenziale Bruno Losi verificato. Il lettore è accessibile, ma non tutti i servizi necessari all’estrazione; prezzi non acquisiti.",
        "source_url": "https://www.despar.it/it/punto-vendita-interspar/819/carpi/",
    },
    {
        "id": "penny",
        "name": "PENNY",
        "support_status": "candidate",
        "message": "Estrazione prodotti non ancora verificata.",
    },
]


@app.get("/api/v1/health")
def health():
    return {"status": "ok"}


@app.get("/api/v1/ready")
def ready():
    with Session() as s:
        if s.scalar(text("SELECT version_num FROM alembic_version")) != "0001":
            raise APIError("NOT_READY", "Migrazioni da completare.", 503)
    return {"status": "ready"}


@app.get("/api/v1/retailers")
def retailers():
    groups = {}
    for m in manifests().values():
        item = groups.setdefault(
            m.retailer_id,
            {
                "id": m.retailer_id,
                "name": m.name,
                "support_status": m.audit_status if m.enabled else "disabled",
                "capabilities": m.capabilities,
                "message": m.scope_label,
            },
        )
        if m.enabled:
            item["support_status"] = m.audit_status
    return {
        "items": list(groups.values())
        + [r for r in UNSUPPORTED if r["id"] not in groups]
    }


@app.get("/api/v1/targets")
def targets(retailer_id: str | None = None, q: str = Query("", max_length=120)):
    availability = {id: {"current": 0, "future": 0} for id in manifests()}
    now = utcnow()
    with Session() as session:
        for row in session.scalars(
            select(OfferRow).where(OfferRow.withdrawn.is_(False))
        ):
            if (
                row.source_id not in availability
                or row.payload["quality"] == "quarantined"
            ):
                continue
            state, freshness = temporal(row.payload, now)
            if freshness == "hidden" or state == "expired":
                continue
            availability[row.source_id][
                "future" if state == "future" else "current"
            ] += 1
    return {
        "items": [
            {
                "id": m.source_id,
                "retailer_id": m.retailer_id,
                "retailer_name": m.name,
                "availability": availability[m.source_id],
                "type": m.scope_type,
                "label": m.scope_label,
                "enabled": m.enabled,
                "support_status": m.audit_status if m.enabled else "disabled",
            }
            for m in manifests().values()
            if (not retailer_id or m.retailer_id == retailer_id)
            and normalized(q) in normalized(m.name + " " + m.scope_label)
        ],
        "max_selections": MAX_TARGETS,
    }


@app.get("/api/v1/categories")
def categories():
    return {"items": [{"id": id, "label": label} for id, label in CATEGORIES.items()]}


def checked_targets(ids):
    unique = sorted(set(ids))
    config = manifests()
    if not unique:
        raise APIError("SELECT_TARGETS", "Seleziona almeno un negozio o ambito.")
    if len(unique) > MAX_TARGETS:
        raise APIError(
            "TARGET_LIMIT", f"Puoi selezionare al massimo {MAX_TARGETS} ambiti."
        )
    if any(id not in config for id in unique):
        raise APIError("UNSUPPORTED_TARGET", "Una selezione non è più supportata.")
    return unique


def source_states(s, ids):
    states = []
    config = manifests()
    for id in ids:
        row = s.get(SourceRow, id)
        m = config[id]
        job = s.scalar(select(Job).where(Job.source_id == id, Job.state.in_(ACTIVE)))
        states.append(
            {
                "source_id": id,
                "name": m.name,
                "state": row.state if row else "idle",
                "stage": job.stage if job else None,
                "message": row.message if row else None,
                "support_status": m.audit_status if m.enabled else "disabled",
                "last_attempt_at": datetime.fromtimestamp(
                    row.last_attempt, UTC
                ).isoformat()
                if row and row.last_attempt
                else None,
                "last_success_at": datetime.fromtimestamp(
                    row.last_success, UTC
                ).isoformat()
                if row and row.last_success
                else None,
                "completeness": row.completeness if row else "unknown",
                "count": row.metrics.get("published") if row else None,
            }
        )
    return states


@app.get("/api/v1/source-status")
def status():
    with Session() as s:
        return {
            "items": source_states(s, list(manifests())),
            "social_status": "permission_required",
            "social_message": "I canali social non sono acquisiti.",
        }


def public_offer(data, now):
    d = dict(data)
    status, freshness = temporal(d, now)
    d["temporal_status"] = status
    d["freshness"] = freshness
    d["evidence"] = {k: v for k, v in d["evidence"].items() if k != "capture_id"}
    return d


@app.get("/api/v1/offers")
def offers(
    target_ids: list[str] = Query(default=[]),
    q: str = Query("", max_length=120),
    category_ids: list[str] = Query(default=[]),
    retailer_ids: list[str] = Query(default=[]),
    validity: Literal["current", "future", "all"] = "current",
    loyalty: Literal["all", "required", "not_required", "unknown"] = "all",
    minimum_quantity: Literal["all", "required", "not_required", "unknown"] = "all",
    sort: Literal["relevance", "recent", "expiry", "price"] = "recent",
    price_basis: Literal["pack", "kg", "l", "piece"] | None = None,
    cursor: str | None = Query(None, max_length=2048),
    limit: int = Query(24, ge=1, le=100),
):
    ids = checked_targets(target_ids)
    if any(x not in CATEGORIES for x in category_ids):
        raise APIError("INVALID_CATEGORY", "Categoria non riconosciuta.")
    if sort == "price" and price_basis is None:
        raise APIError(
            "PRICE_BASIS_REQUIRED",
            "Scegli una base di prezzo per confrontare gli articoli.",
        )
    allowed_retailers = {manifests()[x].retailer_id for x in ids}
    if any(x not in allowed_retailers for x in retailer_ids):
        raise APIError("INVALID_RETAILER", "Insegna non compresa nelle selezioni.")
    now = utcnow()
    tokens = normalized(q).split()
    counts = {k: 0 for k in CATEGORIES}
    period_counts = {"current": 0, "future": 0}
    fingerprint = hashlib.sha256(
        json.dumps(
            [
                ids,
                normalized(q),
                sorted(category_ids),
                sorted(retailer_ids),
                validity,
                loyalty,
                minimum_quantity,
                sort,
                price_basis,
                limit,
            ]
        ).encode()
    ).hexdigest()
    with Session() as s:
        s.execute(text("BEGIN"))  # explicit snapshot across revision, facets and page
        revisions = [
            (id, s.get(SourceRow, id).revision if s.get(SourceRow, id) else 0)
            for id in ids
        ]
        # Minute revision also expires cursors across temporal/freshness transitions.
        revision = hashlib.sha256(
            json.dumps([revisions, int(now.timestamp() // 60)]).encode()
        ).hexdigest()[:24]
        offset = 0
        if cursor:
            try:
                cur = json.loads(base64.urlsafe_b64decode(cursor))
            except Exception:
                raise APIError("INVALID_CURSOR", "Pagina non valida.")
            if not isinstance(cur, dict):
                raise APIError("INVALID_CURSOR", "Pagina non valida.")
            if cur.get("filters") != fingerprint:
                raise APIError("INVALID_CURSOR", "I filtri della pagina sono cambiati.")
            if cur.get("revision") != revision:
                raise APIError(
                    "CATALOG_CHANGED",
                    "Le offerte sono cambiate. Ricarico la prima pagina.",
                    409,
                )
            offset = cur.get("offset")
            if not isinstance(offset, int) or offset < 0:
                raise APIError("INVALID_CURSOR", "Pagina non valida.")
        selected = []
        for row in s.scalars(
            select(OfferRow).where(
                OfferRow.source_id.in_(ids), OfferRow.withdrawn.is_(False)
            )
        ):
            d = public_offer(row.payload, now)
            if (
                d["quality"] == "quarantined"
                or d["freshness"] == "hidden"
                or d["temporal_status"] == "expired"
            ):
                continue
            if retailer_ids and d["retailer_id"] not in retailer_ids:
                continue
            searchable = normalized(d["title"] + " " + (d["brand"] or "")).split()
            if tokens and not all(
                any(
                    word == token or len(token) >= 3 and word.startswith(token)
                    for word in searchable
                )
                for token in tokens
            ):
                continue
            required = d["conditions"]["loyalty_required"]
            minimum = d["conditions"]["minimum_pack_count"]
            if (
                loyalty != "all"
                and required
                is not {"required": True, "not_required": False, "unknown": None}[
                    loyalty
                ]
            ):
                continue
            if minimum_quantity == "required" and (minimum is None or minimum < 2):
                continue
            if minimum_quantity == "not_required" and minimum != 1:
                continue
            if minimum_quantity == "unknown" and minimum is not None:
                continue
            if sort == "price":
                if d["price"]["basis"] != price_basis or minimum and minimum > 1:
                    continue
            if not category_ids or d["category_id"] in category_ids:
                period_counts[
                    "future" if d["temporal_status"] == "future" else "current"
                ] += 1
            if validity == "current" and d["temporal_status"] == "future":
                continue
            if validity == "future" and d["temporal_status"] != "future":
                continue
            counts[d["category_id"]] += 1
            if category_ids and d["category_id"] not in category_ids:
                continue
            selected.append(d)
        if sort == "price":
            selected.sort(
                key=lambda x: (x["price"]["advertised_amount_cents"], x["id"])
            )
        elif sort == "expiry":
            selected.sort(
                key=lambda x: (x["validity"]["end_at_exclusive"] or "9999", x["id"])
            )
        elif sort == "relevance" and tokens:
            selected.sort(
                key=lambda x: (
                    0 if normalized(q) == x["title_normalized"] else 1,
                    0 if x["title_normalized"].startswith(normalized(q)) else 1,
                    x["id"],
                )
            )
        else:
            selected.sort(key=lambda x: (x["first_seen_at"], x["id"]), reverse=True)
        page = selected[offset : offset + limit]
        next_cursor = None
        if offset + limit < len(selected):
            next_cursor = base64.urlsafe_b64encode(
                json.dumps(
                    {
                        "offset": offset + limit,
                        "filters": fingerprint,
                        "revision": revision,
                    }
                ).encode()
            ).decode()
        return {
            "items": page,
            "next_cursor": next_cursor,
            "total": len(selected),
            "category_counts": counts,
            "period_counts": period_counts,
            "catalog_revision": revision,
            "server_time": now.isoformat(),
            "source_states": source_states(s, ids),
            "limitations": [
                "Consulta l’ambito di ciascuna offerta: sede o catalogo nazionale.",
                "Le offerte pubblicate non garantiscono disponibilità a scaffale.",
            ]
            + (
                [
                    "Il confronto include solo prezzi con la base scelta; quantità minime escluse."
                ]
                if sort == "price"
                else []
            ),
        }


@app.get("/api/v1/offers/{offer_id}")
def offer_detail(offer_id: str):
    with Session() as s:
        row = s.get(OfferRow, offer_id)
        if not row or row.payload["quality"] == "quarantined":
            raise APIError("NOT_FOUND", "Offerta non trovata.", 404)
        result = public_offer(row.payload, utcnow())
        result["withdrawn"] = row.withdrawn
        return result


@app.get("/api/v1/coupons")
def coupons(target_ids: list[str] = Query(default=[])):
    checked_targets(target_ids)
    return {
        "items": [],
        "coverage": "unsupported",
        "message": "Buoni generici e vantaggi non ancora acquisiti dalle fonti supportate. I prezzi Lidl Plus verificati sono nella vista prodotti.",
        "server_time": utcnow().isoformat(),
    }


class RefreshInput(BaseModel):
    target_ids: list[str] = Field(min_length=1, max_length=20)


@app.post("/api/v1/refreshes", status_code=202)
def refresh(payload: RefreshInput):
    ids = checked_targets(payload.target_ids)
    with Session() as s:
        count = s.scalar(
            select(func.count())
            .select_from(Refresh)
            .where(Refresh.created_at > time.time() - 60)
        )
        queued = s.scalar(
            select(func.count()).select_from(Job).where(Job.state.in_(ACTIVE))
        )
        if count >= 30 or queued >= 20:
            raise APIError("RATE_LIMIT", "Troppe richieste. Attendi un minuto.", 429)
    id, entries = enqueue(ids)
    return {"id": id, "targets": entries, "server_time": utcnow().isoformat()}


@app.get("/api/v1/refreshes/{refresh_id}")
def refresh_status(refresh_id: str):
    with Session() as s:
        ref = s.get(Refresh, refresh_id)
        if not ref:
            raise APIError("NOT_FOUND", "Aggiornamento non trovato.", 404)
        results = []
        for entry in ref.targets:
            job = s.get(Job, entry["job_id"]) if entry["job_id"] else None
            results.append(
                {
                    **entry,
                    "state": job.state if job else "cached",
                    "stage": job.stage if job else None,
                    "message": job.message if job else None,
                    "counters": job.counters if job else {},
                }
            )
        return {
            "id": ref.id,
            "terminal": all(x["state"] not in ACTIVE for x in results),
            "targets": results,
            "source_states": source_states(s, [x["target_id"] for x in ref.targets]),
            "server_time": utcnow().isoformat(),
        }
