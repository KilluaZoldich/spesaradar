import { describe, expect, it } from "vitest";
import { queryCatalog, type Snapshot } from "./staticCatalog";
// Synthetic records, restricted to this test module. No export into the live site.
const now = Date.parse("2026-09-08T10:00:00Z");
function record(
  id: string,
  source = "lidl-national",
  category = "carne",
  loyalty: boolean | null = null,
): Snapshot["records"][number] {
  return {
    withdrawn: false,
    offer: {
      id,
      source_id: source,
      retailer_id: source.split("-")[0],
      title: id === "cat" ? "Alimento per gatti con pollo" : "Petto di pollo",
      brand: null,
      category_id: category,
      tags: [],
      source_url: "https://fixture.invalid/" + id,
      last_verified_at: new Date(now).toISOString(),
      first_seen_at: new Date(now).toISOString(),
      data_origin: "official_live",
      quality: "limited",
      temporal_status: "active",
      freshness: "fresh",
      limitations: [],
      scope: { type: "national", label: "Fixture sintetica" },
      package: { raw_text: "500 g" },
      price: {
        advertised_amount_cents: 349,
        basis: "pack",
        published_unit_price: null,
        calculated_unit_price: "6.98",
        unit_price_basis: "kg",
        calculation: null,
      },
      conditions: {
        status: "partial",
        loyalty_required: loyalty,
        app_activation_required: null,
        minimum_pack_count: null,
        minimum_spend_cents: null,
        raw_text: null,
      },
      validity: {
        start_at: new Date(now - 86400000).toISOString(),
        end_at_exclusive: new Date(now + 86400000).toISOString(),
        raw_text: null,
      },
      evidence: {
        url: "https://fixture.invalid",
        selector: "synthetic",
        raw_price: "3,49 €",
      },
    },
  };
}
function snapshot(): Snapshot {
  return {
    schema_version: 1,
    generated_at: new Date(now).toISOString(),
    targets: {
      max_selections: 5,
      items: ["lidl", "eurospin"].map((id) => ({
        id: id + "-national",
        retailer_id: id,
        retailer_name: id,
        type: "national",
        label: "Fixture",
        enabled: true,
        support_status: "partial",
      })),
    },
    retailers: { items: [] },
    categories: {
      items: [
        { id: "carne", label: "Carne" },
        { id: "animali", label: "Animali" },
      ],
    },
    sources: [],
    records: [
      record("chicken"),
      record("cat", "eurospin-national", "animali"),
      record("no-card", "lidl-national", "carne", false),
    ],
  };
}
const params = (extra = "") =>
  new URLSearchParams(
    "target_ids=lidl-national&target_ids=eurospin-national&" + extra,
  );
describe("Catalogo pubblicato su Pages", () => {
  it("ricerca AND e faccette rispettano categorie multiple senza perdere Animali", () => {
    const result = queryCatalog(
      snapshot(),
      params("q=pollo&category_ids=carne"),
      now,
    );
    expect(result.total).toBe(2);
    expect(result.category_counts).toEqual({ carne: 2, animali: 1 });
    expect(
      queryCatalog(snapshot(), params("q=gatti+pollo"), now).items.map(
        (o) => o.category_id,
      ),
    ).toEqual(["animali"]);
  });
  it("non interpreta condizioni sconosciute come assenza di carta", () => {
    expect(
      queryCatalog(snapshot(), params("loyalty=not_required"), now).items.map(
        (o) => o.id,
      ),
    ).toEqual(["no-card"]);
  });
  it("separa future, scadute, ritirate e dati oltre 48 ore", () => {
    const s = snapshot();
    s.records[0].offer.validity.start_at = new Date(
      now + 3600000,
    ).toISOString();
    s.records[1].withdrawn = true;
    expect(queryCatalog(s, params(), now).total).toBe(1);
    expect(queryCatalog(s, params("validity=future"), now).items[0].id).toBe(
      "chicken",
    );
    expect(
      queryCatalog(s, params("validity=all"), now + 49 * 3600000).total,
    ).toBe(0);
  });
  it("confronta soltanto basi compatibili e senza quantità minime", () => {
    const s = snapshot();
    s.records[0].offer.price.basis = "kg";
    s.records[1].offer.conditions.minimum_pack_count = 2;
    expect(
      queryCatalog(s, params("sort=price&price_basis=pack"), now).items.map(
        (o) => o.id,
      ),
    ).toEqual(["no-card"]);
  });
  it("il cursore è legato ai filtri, alla pubblicazione e al tempo", () => {
    const s = snapshot(),
      p = params("limit=1");
    const first = queryCatalog(s, p, now);
    p.set("cursor", first.next_cursor!);
    expect(queryCatalog(s, p, now).items[0].id).not.toBe(first.items[0].id);
    expect(() =>
      queryCatalog({ ...s, generated_at: "changed" }, p, now),
    ).toThrow("Le offerte sono cambiate");
    expect(() => queryCatalog(s, p, now + 60000)).toThrow(
      "Le offerte sono cambiate",
    );
    p.set("q", "pollo");
    expect(() => queryCatalog(s, p, now)).toThrow("I filtri sono cambiati");
  });
  it("rifiuta selezioni vuote e nasconde record non live o in quarantena", () => {
    expect(() => queryCatalog(snapshot(), new URLSearchParams(), now)).toThrow(
      "Seleziona",
    );
    const s = snapshot();
    s.records[0].offer.data_origin = "synthetic_fixture";
    s.records[1].offer.quality = "quarantined";
    expect(queryCatalog(s, params(), now).total).toBe(1);
  });
});
