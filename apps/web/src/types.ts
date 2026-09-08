export type Target = {
  id: string;
  retailer_id: string;
  retailer_name: string;
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
  catalog_revision: string;
  server_time: string;
  source_states: SourceState[];
  limitations: string[];
};
