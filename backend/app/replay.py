"""Offline replay for admitted parser families; never fetches or publishes."""

import argparse
import json
import time
from pathlib import Path

from app.adapters.despar import DesparAdapter
from app.adapters.famila import FamilaAdapter, resolve
from app.config import Manifest


def main():
    p = argparse.ArgumentParser(
        description="Verifica un parser su capture locali, senza rete o pubblicazione"
    )
    p.add_argument("--manifest", type=Path, required=True)
    p.add_argument("--capture", type=Path, required=True)
    p.add_argument("--store-html", type=Path)
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args()
    m = Manifest.model_validate_json(args.manifest.read_text())
    if args.capture.stat().st_size > 30 * 1024 * 1024:
        p.error("Capture oltre 30 MB")
    started = time.monotonic()
    if m.connector == "despar_html":
        b = DesparAdapter().extract(
            args.capture.read_text(), m.entry_urls[0], "offline-replay", m
        )
    elif m.connector == "famila_selex_pdf":
        if not args.store_html or args.store_html.stat().st_size > 10 * 1024 * 1024:
            p.error("Pagina sede necessaria, massimo 10 MB")
        campaign = resolve(args.store_html.read_text(), m)
        b = FamilaAdapter().extract(
            args.capture.read_bytes(),
            campaign["url"],
            "offline-replay",
            m,
            campaign,
            started + 90,
        )
    else:
        p.error(
            "Profilo non supportato dal replay; per Conad usare app.source_tools replay-conad"
        )
    result = {
        "mode": "offline_diagnostic_only",
        "published": False,
        "parser_version": m.parser_version,
        "seconds": round(time.monotonic() - started, 3),
        "recognized": b.extracted,
        "accepted": len(b.offers),
        "quarantined": b.quarantined,
        "completeness": b.completeness,
        "warnings": b.warnings,
        "items": [
            {
                "title": o.title,
                "price": o.price.model_dump(),
                "package": o.package.model_dump(),
                "category": o.category_id,
                "conditions": o.conditions.model_dump(),
                "validity": o.validity.model_dump(mode="json"),
                "evidence": o.evidence,
            }
            for o in b.offers
        ],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x") as file:
        json.dump(result, file, ensure_ascii=False, indent=2)
    print(json.dumps({k: v for k, v in result.items() if k != "items"}))


if __name__ == "__main__":
    main()
