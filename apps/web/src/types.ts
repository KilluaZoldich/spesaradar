export type Target = {
  id: string;
  retailer_id: string;
  retailer_name: string;
  availability?: { current: number; future: number; coupons?: number };
  capabilities?: string[];
  type: string;
  label: string;
  enabled: boolean;
  support_status: string;
};
export type SourceState = {
  source_id: string;
  name: string;
  state: string;
  stage: string | null;
  message: string | null;
  last_success_at: string | null;
  completeness: string;
  count: number | null;
};
export type Offer = {
  offer_type?: "product_offer" | "product_coupon";
  id: string;
  title: string;
  brand: string | null;
  retailer_id: string;
  category_id: string;
  tags: string[];
  source_url: string;
  last_verified_at: string;
  temporal_status: string;
  freshness: string;
  limitations: string[];
  scope: { label: string; type: string };
  package: { raw_text: string | null };
  price: {
    advertised_amount_cents: number;
    basis: string;
    published_unit_price: string | null;
    calculated_unit_price: string | null;
    unit_price_basis: string | null;
    calculation: string | null;
  };
  conditions: {
    status: string;
    loyalty_required: boolean | null;
    app_activation_required: boolean | null;
    minimum_pack_count: number | null;
    minimum_spend_cents: number | null;
    raw_text: string | null;
  };
  validity: {
    start_at: string | null;
    end_at_exclusive: string | null;
    raw_text: string | null;
  };
  evidence: { url: string; selector: string; raw_price: string };
  withdrawn?: boolean;
};
export type Catalog = {
  items: Offer[];
  next_cursor: string | null;
  total: number;
  category_counts: Record<string, number>;
  period_counts?: { current: number; future: number };
  catalog_revision: string;
  server_time: string;
  source_states: SourceState[];
  limitations: string[];
};

export type Coupon = Omit<Offer, "price" | "offer_type" | "evidence"> & {
  offer_type: "future_voucher" | "basket_coupon" | "loyalty_benefit";
  evidence: { url: string; selector: string; raw_price: null };
  price: null;
  benefit: {
    amount_cents: number;
    earning_minimum_spend_cents: number;
    redemption_minimum_spend_cents: number;
    earning_category: string;
    earning_validity: Offer["validity"];
    redemption_validity: Offer["validity"];
    maximum_vouchers_per_receipt: number;
    maximum_discount_cents: number;
    exclusions: string;
    redemption_instructions: string;
    raw_text: string;
  };
};
export type CouponCatalog = {
  items: Coupon[];
  message: string;
  server_time?: string;
  source_states?: SourceState[];
};
