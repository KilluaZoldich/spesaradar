"""Private evidence comparison; no network. Generates a review sample, not an accuracy claim."""

import json
import sys
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
from app.storage.db import CaptureRow, OfferRow, Session
from bs4 import BeautifulSoup
from sqlalchemy import select


def review():
    with Session() as s:
        rows = [
            o
            for o in s.scalars(select(OfferRow))
            if o.payload["quality"] != "quarantined"
        ]
        captures = {c.id: c for c in s.scalars(select(CaptureRow))}
    soups = {}
    out = []
    for source in ["lidl-national", "eurospin-national"]:
        candidates = sorted(
            [o for o in rows if o.source_id == source],
            key=lambda r: (
                r.payload["category_id"],
                str(r.payload["conditions"]["loyalty_required"]),
                r.payload["title"],
            ),
        )
        # Uniform deterministic spread through categories and titles.
        chosen = [
            candidates[round(i * (len(candidates) - 1) / 49)]
            for i in range(min(50, len(candidates)))
        ]
        prior_path = Path("docs/live-sample.json")
        if prior_path.exists():
            prior_ids = [
                x["id"]
                for x in json.loads(prior_path.read_text())
                if x["source"] == source
            ]
            indexed = {r.id: r for r in candidates}
            if all(id in indexed for id in prior_ids) and len(prior_ids) == 50:
                chosen = [indexed[id] for id in prior_ids]
        for row in chosen:
            o = row.payload
            c = captures[o["evidence"]["capture_id"]]
            if c.id not in soups:
                soups[c.id] = BeautifulSoup(Path(c.path).read_text(), "html.parser")
            soup = soups[c.id]
            if source.startswith("lidl"):
                d = next(
                    json.loads(e["data-grid-data"], parse_float=Decimal)
                    for e in soup.select("[data-grid-data]")
                    if str(json.loads(e["data-grid-data"])["productId"])
                    == o["source_offer_id"]
                )
                plus = d.get("lidlPlus") or []
                p = plus[0]["price"] if plus else d["price"]
                raw_title = d[o["evidence"]["fields"]["title"]]
                raw_price = str(p.get("price"))
                raw_pack = p.get("packaging", {}).get("text", "")
                raw_condition = plus[0].get("lidlPlusText") if plus else "unknown"
                raw_end = str(next(iter(d["regionsPrices"].values())))
                match = (
                    int(Decimal(raw_price) * 100)
                    == o["price"]["advertised_amount_cents"]
                    and raw_title == o["title"]
                    and raw_pack == o["package"]["raw_text"]
                    and bool(plus) == bool(o["conditions"]["loyalty_required"])
                )
            else:
                idx = int(o["evidence"]["selector"].split("(")[-1].rstrip(")")) - 1
                e = soup.select(".sn_promo_grid_item")[idx]
                raw_title = " ".join(
                    e.select_one(".i_title").get_text(" ", strip=True).split()
                )
                raw_price = e.select_one("[itemprop=price]").get_text(" ", strip=True)
                raw_pack = (
                    " ".join(
                        e.select_one(".i_price_info").get_text(" ", strip=True).split()
                    )
                    if e.select_one(".i_price_info")
                    else ""
                )
                raw_condition = "unknown"
                raw_end = e.select_one(".date_current_promo").text.strip()
                match = (
                    raw_title == o["title"]
                    and int(
                        Decimal(raw_price.replace("€", "").strip().replace(",", "."))
                        * 100
                    )
                    == o["price"]["advertised_amount_cents"]
                )
            item = {
                "source": source,
                "id": o["id"],
                "title": o["title"],
                "category": o["category_id"],
                "price_cents": o["price"]["advertised_amount_cents"],
                "format": o["package"]["raw_text"],
                "source_price": raw_price,
                "source_format": raw_pack,
                "loyalty": o["conditions"]["loyalty_required"],
                "start": o["validity"]["start_at"],
                "end_exclusive": o["validity"]["end_at_exclusive"],
                "checked_fields_match": match,
                "source_condition": raw_condition,
                "source_end_evidence": raw_end,
                "source_url": c.url,
                "selector": o["evidence"]["selector"],
            }
            out.append(item)
    Path("docs/live-sample.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=2)
    )
    for source in ["lidl-national", "eurospin-national"]:
        print("\nSOURCE", source)
        for i, r in enumerate(x for x in out if x["source"] == source):
            print(
                i + 1,
                r["title"][:57],
                r["price_cents"],
                r["format"],
                r["category"],
                "CARD" if r["loyalty"] else "?",
                "MATCH" if r["checked_fields_match"] else "ERROR",
                r["start"][:10],
                r["end_exclusive"][:10],
            )


if __name__ == "__main__":
    review()
