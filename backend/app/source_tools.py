"""Maintainer-only onboarding. No network and no publication in either command."""

import argparse
import json
import time
from pathlib import Path

from app.adapters.conad import ConadPDFAdapter, resolve
from app.config import ROOT, Manifest
from app.security.fetch import validate_url


def main():
    parser = argparse.ArgumentParser(
        description="Profili fonte: configurazione e replay locale senza crawl"
    )
    sub = parser.add_subparsers(dest="command", required=True)
    scaffold = sub.add_parser(
        "scaffold-conad", help="Crea una fonte disabilitata dal profilo CNO"
    )
    scaffold.add_argument("--store-id", required=True)
    scaffold.add_argument("--url", required=True)
    scaffold.add_argument("--label", required=True)
    scaffold.add_argument("--output", type=Path, required=True)
    replay = sub.add_parser(
        "replay-conad",
        help="Verifica un PDF già acquisito contro i metadati della sede",
    )
    replay.add_argument("--manifest", type=Path, required=True)
    replay.add_argument("--store-html", type=Path, required=True)
    replay.add_argument("--pdf", type=Path, required=True)
    replay.add_argument("--campaign-id", required=True)
    replay.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "scaffold-conad":
        validate_url(args.url, ["www.conad.it"])
        if (
            not args.store_id.isdigit()
            or len(args.store_id) != 6
            or not args.url.endswith("--" + args.store_id)
        ):
            parser.error(
                "URL e identificativo ufficiale della sede devono corrispondere"
            )
        template = json.loads((ROOT / "config/sources/conad-carpi.json").read_text())
        template.update(
            source_id="conad-" + args.store_id,
            store_id=args.store_id,
            scope_label=args.label,
            entry_urls=[args.url],
            enabled=False,
            audit_status="candidate",
        )
        payload = Manifest.model_validate(template).model_dump()
    else:
        manifest = Manifest.model_validate_json(args.manifest.read_text())
        campaigns = resolve(args.store_html.read_text(), manifest)
        campaign = next((c for c in campaigns if c["id"] == args.campaign_id), None)
        if not campaign:
            parser.error("Campagna non collegata alla sede, scaduta o fuori profilo")
        if args.pdf.stat().st_size > 30 * 1024 * 1024:
            parser.error("PDF oltre 30 MB")
        started = time.monotonic()
        batch = ConadPDFAdapter().extract(
            args.pdf.read_bytes(),
            campaign["url"],
            "offline-replay",
            manifest,
            campaign,
            started + 90,
        )
        payload = {
            "mode": "offline_diagnostic_only",
            "published": False,
            "parser_version": manifest.parser_version,
            "duration_seconds": round(time.monotonic() - started, 3),
            "recognized_cells": batch.extracted,
            "accepted": len(batch.offers),
            "quarantined": batch.quarantined,
            "completeness": batch.completeness,
            "warnings": batch.warnings,
            "items": [
                {
                    "title": o.title,
                    "price": o.price.model_dump(),
                    "package": o.package.model_dump(),
                    "conditions": o.conditions.model_dump(),
                    "validity": o.validity.model_dump(mode="json"),
                    "evidence": o.evidence,
                }
                for o in batch.offers
            ],
        }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    # Refuse accidental overwrites, especially of an already admitted manifest.
    with args.output.open("x") as output:
        json.dump(payload, output, indent=2, ensure_ascii=False)
        output.write("\n")
    print(
        json.dumps(
            {"output": str(args.output), "command": args.command, "published": False}
        )
    )


if __name__ == "__main__":
    main()
