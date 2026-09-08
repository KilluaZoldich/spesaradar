import { ArrowUpRight, Clock3, Ticket } from "lucide-react";
import { CategoryIcon } from "./CategoryNavigation";
import type { Offer } from "./types";
export const euros = (cents: number) =>
  new Intl.NumberFormat("it-IT", { style: "currency", currency: "EUR" }).format(
    cents / 100,
  );
export const date = (value: string) =>
  new Intl.DateTimeFormat("it-IT", {
    day: "numeric",
    month: "short",
    timeZone: "Europe/Rome",
  }).format(new Date(value));
export const basisLabels: Record<string, string> = {
  pack: "a confezione",
  piece: "al pezzo",
  kg: "al kg",
  l: "al litro",
  bundle: "per combinazione",
  from: "a partire da",
  unknown: "base non disponibile",
};
export function validityLabel(o: Offer) {
  if (o.validity.end_at_exclusive) {
    const end = new Date(
      new Date(o.validity.end_at_exclusive).getTime() - 1,
    ).toISOString();
    return o.temporal_status === "future" && o.validity.start_at
      ? `Dal ${date(o.validity.start_at)} al ${date(end)}`
      : `Fino al ${date(end)}`;
  }
  return "Scadenza non disponibile";
}
export function Conditions({
  offer: o,
  includeTags = true,
}: {
  offer: Offer;
  includeTags?: boolean;
}) {
  return (
    <div className="conditions">
      {o.conditions.loyalty_required === true && (
        <span className="badge loyalty">
          <Ticket size={14} /> Solo con{" "}
          {o.retailer_id === "lidl"
            ? "Lidl Plus"
            : o.retailer_id === "md"
              ? "Buona Spesa Card"
              : "carta fedeltà"}
        </span>
      )}
      {o.conditions.minimum_pack_count !== null &&
        o.conditions.minimum_pack_count > 1 && (
          <span className="badge loyalty">
            Acquisto minimo {o.conditions.minimum_pack_count} confezioni
          </span>
        )}
      {o.conditions.app_activation_required === true && (
        <span className="badge loyalty">Attivazione nell’app richiesta</span>
      )}
      {o.conditions.minimum_spend_cents !== null && (
        <span className="badge loyalty">
          Spesa minima {euros(o.conditions.minimum_spend_cents)}
        </span>
      )}
      {o.conditions.status !== "complete" && (
        <span className="condition-uncertainty">
          {o.conditions.loyalty_required
            ? "Altre condizioni non verificate"
            : "Condizioni non verificate"}
        </span>
      )}
      {includeTags &&
        o.tags.map((tag) => (
          <span className="badge" key={tag}>
            {tag}
          </span>
        ))}
    </div>
  );
}
export default function OfferCard({
  offer: o,
  category,
  onOpen,
  retailerName,
}: {
  offer: Offer;
  category: string;
  retailerName?: string;
  onOpen: () => void;
}) {
  const unit = o.price.published_unit_price || o.price.calculated_unit_price;
  const hasUnit =
    unit != null &&
    Number.isFinite(Number(unit)) &&
    Number(unit) > 0 &&
    (o.price.unit_price_basis === "kg" || o.price.unit_price_basis === "l");
  return (
    <article className="offer-card">
      <div className="card-top">
        <span className="retailer">{retailerName || o.retailer_id}</span>
        <span className="category-label">{category}</span>
        <span className="category-mark" aria-hidden="true">
          <CategoryIcon id={o.category_id} size={23} />
        </span>
      </div>
      <div className="product-line">
        <div>
          {o.brand &&
            !o.title
              .toLocaleLowerCase("it")
              .startsWith(o.brand.toLocaleLowerCase("it")) && (
              <p className="brand">{o.brand}</p>
            )}
          <h3>
            <button onClick={onOpen}>{o.title}</button>
          </h3>
        </div>
      </div>
      <p className="format">
        {o.package.raw_text || "Formato non disponibile"}
        {o.tags.map((tag) => (
          <span className="format-tag" key={tag}>
            {" "}
            · {tag}
          </span>
        ))}
      </p>
      <div className="price-block">
        <div className="price-line">
          <strong>{euros(o.price.advertised_amount_cents)}</strong>
          <span>{basisLabels[o.price.basis]}</span>
        </div>
        {hasUnit && (
          <p className="unit-price">
            {`${Number(unit).toLocaleString("it-IT", { minimumFractionDigits: 2, maximumFractionDigits: 2 })} €/${o.price.unit_price_basis}${o.price.published_unit_price ? "" : " · calcolato"}`}
          </p>
        )}
      </div>
      <div className="card-facts">
        <Conditions offer={o} includeTags={false} />
        <p className={o.temporal_status === "future" ? "future" : ""}>
          <Clock3 size={14} />
          {validityLabel(o)}
        </p>
      </div>
      <div className="card-bottom">
        <p className="scope-caption">{o.scope.label}</p>
        {o.freshness === "stale" && (
          <p className="warning-text">Dato non aggiornato di recente</p>
        )}
        <div className="card-links">
          <a
            href={o.source_url}
            target="_blank"
            rel="noopener noreferrer"
            aria-label={`Fonte ufficiale: ${o.title}`}
          >
            <ArrowUpRight size={18} />
          </a>
        </div>
      </div>
    </article>
  );
}
