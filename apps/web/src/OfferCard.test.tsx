import { describe, it, expect, vi } from "vitest";
import { render, screen, cleanup } from "@testing-library/react";
import OfferCard from "./OfferCard";
import { readPreferences, savePreferences } from "./api";
import type { Offer } from "./types";
const offer = {
  id: "fixture",
  last_verified_at: "2026-09-08T05:00:00Z",
  limitations: [],
  evidence: {
    url: "https://fixture.invalid",
    selector: "fixture",
    raw_price: "3,49 €",
  },
  title: "Petto di pollo",
  brand: null,
  retailer_id: "lidl",
  category_id: "carne",
  tags: [],
  package: { raw_text: "500 g" },
  price: {
    advertised_amount_cents: 349,
    basis: "pack",
    published_unit_price: null,
    calculated_unit_price: "6.9800",
    unit_price_basis: "kg",
    calculation: null,
  },
  conditions: {
    status: "partial",
    loyalty_required: true,
    app_activation_required: null,
    minimum_pack_count: 2,
    minimum_spend_cents: null,
    raw_text: null,
  },
  validity: {
    start_at: "2026-09-07T00:00:00Z",
    end_at_exclusive: "2026-09-13T22:00:00Z",
    raw_text: null,
  },
  scope: { label: "Fixture", type: "national" },
  source_url: "https://fixture.invalid",
  freshness: "fresh",
  temporal_status: "active",
} as Offer;
describe("Scheda prodotto", () => {
  it("espone prezzo, formato, carta e quantità prima del dettaglio", () => {
    render(<OfferCard offer={offer} category="Carne" onOpen={vi.fn()} />);
    expect(screen.getByText("500 g")).toBeVisible();
    expect(screen.getByText(/Solo con Lidl Plus/)).toBeVisible();
    expect(screen.getByText(/Acquisto minimo 2 confezioni/)).toBeVisible();
    expect(screen.getByText(/6,98/)).toBeVisible();
    cleanup();
  });
  it("testo ostile non diventa HTML eseguibile", () => {
    const { container } = render(
      <OfferCard
        offer={{ ...offer, title: "<script>alert(1)</script>" }}
        category="Carne"
        onOpen={vi.fn()}
      />,
    );
    expect(container.querySelector("script")).toBeNull();
    expect(screen.getByText("<script>alert(1)</script>")).toBeVisible();
    cleanup();
  });
  it("preferenze versionate e recupero storage corrotto", () => {
    savePreferences(["lidl-national"]);
    expect(readPreferences()).toEqual(["lidl-national"]);
    localStorage.setItem("spesaradar.preferences", "bad-json");
    expect(readPreferences()).toEqual([]);
    localStorage.setItem(
      "spesaradar.preferences",
      JSON.stringify({ version: 99, target_ids: ["x"] }),
    );
    expect(readPreferences()).toEqual([]);
  });
});

it.each([
  ["bad", "kg"],
  ["1.25", null],
  ["Infinity", "kg"],
  ["", "l"],
])("non mostra prezzi unitari non validi", (unit, basis) => {
  const { container } = render(
    <OfferCard
      offer={
        {
          ...offer,
          price: {
            ...offer.price,
            calculated_unit_price: unit,
            unit_price_basis: basis,
          },
        } as Offer
      }
      category="Carne"
      onOpen={vi.fn()}
    />,
  );
  expect(container.querySelector(".unit-price")).toBeNull();
  cleanup();
});
