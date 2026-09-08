// SYNTHETIC TEST FIXTURE. Imported only by tests; never a live catalog fallback.
import type { Coupon } from "./types";
export const couponFixture: Coupon = {
  id: "synthetic-voucher",
  offer_type: "future_voucher",
  title: "Buono sintetico",
  brand: null,
  retailer_id: "coop",
  category_id: "altri",
  tags: [],
  source_url: "https://fixture.invalid/voucher",
  last_verified_at: "2026-09-08T10:00:00Z",
  temporal_status: "active",
  freshness: "fresh",
  limitations: [],
  scope: { type: "store", label: "Sede sintetica" },
  package: { raw_text: null },
  price: null,
  conditions: {
    status: "complete",
    loyalty_required: false,
    app_activation_required: false,
    minimum_pack_count: null,
    minimum_spend_cents: 3000,
    raw_text: null,
  },
  validity: {
    start_at: "2026-07-15T22:00:00Z",
    end_at_exclusive: "2026-10-07T22:00:00Z",
    raw_text: null,
  },
  evidence: {
    url: "https://fixture.invalid/voucher",
    selector: "synthetic",
    raw_price: null,
  },
  benefit: {
    amount_cents: 1000,
    earning_minimum_spend_cents: 3000,
    redemption_minimum_spend_cents: 3000,
    earning_category: "Cartoleria",
    earning_validity: {
      start_at: "2026-07-15T22:00:00Z",
      end_at_exclusive: "2026-09-20T22:00:00Z",
      raw_text: null,
    },
    redemption_validity: {
      start_at: null,
      end_at_exclusive: "2026-10-07T22:00:00Z",
      raw_text: null,
    },
    maximum_vouchers_per_receipt: 3,
    maximum_discount_cents: 3000,
    exclusions: "Esclusi latte infanzia tipo 1 e EasyCoop.",
    redemption_instructions:
      "Buoni digitali da attivare sul sito ufficiale; SpesaRadar non li attiva.",
    raw_text: "Meccanica sintetica per test",
  },
};
