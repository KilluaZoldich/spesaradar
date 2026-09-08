import { Ticket, ArrowUpRight } from "lucide-react";
import type { Coupon } from "./types";
import { euros } from "./OfferCard";
const until = (end: string | null) =>
  end
    ? new Intl.DateTimeFormat("it-IT", {
        day: "numeric",
        month: "long",
        year: "numeric",
        timeZone: "Europe/Rome",
      }).format(new Date(Date.parse(end) - 1))
    : "data non disponibile";
export default function CouponCard({ coupon: c }: { coupon: Coupon }) {
  const b = c.benefit;
  const earningEnded =
    !!b.earning_validity.end_at_exclusive &&
    Date.now() >= Date.parse(b.earning_validity.end_at_exclusive);
  return (
    <article className="coupon-card">
      <div className="coupon-heading">
        <span>{c.scope.label}</span>
        <Ticket size={24} aria-hidden="true" />
      </div>
      <p className="coupon-kind">Buono per una spesa successiva</p>
      <h2>
        {euros(b.amount_cents)} <span>di buono</span>
      </h2>
      {c.freshness === "stale" && (
        <p className="condition-badge">Verifica non recente</p>
      )}
      {earningEnded ? (
        <p className="condition-badge">
          Ottenimento terminato · solo utilizzo dei buoni già ricevuti
        </p>
      ) : (
        <p>
          Ogni <strong>{euros(b.earning_minimum_spend_cents)}</strong> in{" "}
          {b.earning_category.toLocaleLowerCase("it")} ottieni un buono.
        </p>
      )}
      <dl className="coupon-steps">
        <div>
          <dt>Per ottenerlo</dt>
          <dd>Entro il {until(b.earning_validity.end_at_exclusive)}</dd>
        </div>
        <div>
          <dt>Per spenderlo</dt>
          <dd>
            Entro il {until(b.redemption_validity.end_at_exclusive)}, su una
            spesa minima di{" "}
            <strong>{euros(b.redemption_minimum_spend_cents)}</strong>
          </dd>
        </div>
      </dl>
      <p>
        Massimo {b.maximum_vouchers_per_receipt} buoni nello stesso scontrino,
        fino a {euros(b.maximum_discount_cents)} di sconto.
      </p>
      <p className="coupon-essential">
        Non cumulabile con buoni diversi o altre iniziative. Sono previste
        esclusioni.
      </p>
      <p className="coupon-essential">
        Buono cartaceo in cassa oppure digitale da attivare sul sito/app Coop.
      </p>
      <details>
        <summary>Condizioni e prodotti esclusi</summary>
        <p>{b.exclusions}</p>
        <p>{b.redemption_instructions}</p>
        {c.limitations.map((text) => (
          <p key={text}>{text}</p>
        ))}
        <p>
          Ultima verifica:{" "}
          {new Date(c.last_verified_at).toLocaleString("it-IT", {
            timeZone: "Europe/Rome",
          })}
        </p>
      </details>
      <a
        href={c.source_url}
        target="_blank"
        rel="noopener noreferrer"
        className="coupon-source"
      >
        Vedi come usarlo sul sito Coop{" "}
        <ArrowUpRight size={18} aria-hidden="true" />
      </a>
    </article>
  );
}
