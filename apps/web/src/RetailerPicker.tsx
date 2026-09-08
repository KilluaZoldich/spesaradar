import { useState } from "react";
import { Check, ChevronDown, MapPin } from "lucide-react";
import type { Target } from "./types";

export function oneTargetPerRetailer(ids: string[], targets: Target[]) {
  const seen = new Set<string>();
  return ids.filter((id) => {
    const target = targets.find((t) => t.id === id && t.enabled);
    if (!target || seen.has(target.retailer_id)) return false;
    seen.add(target.retailer_id);
    return true;
  });
}

export default function RetailerPicker({
  targets,
  selected,
  query,
  max,
  onChange,
}: {
  targets: Target[];
  selected: string[];
  query: string;
  max: number;
  onChange: (ids: string[]) => void;
}) {
  const [expanded, setExpanded] = useState<string | null>(null);
  const needle = query.trim().toLocaleLowerCase("it");
  const postal = /^\d{5}$/.test(needle);
  const matches = (t: Target) =>
    (postal && t.type === "national") ||
    `${t.retailer_name} ${t.label}`.toLocaleLowerCase("it").includes(needle);
  const groups = [
    ...new Set(targets.filter((t) => t.enabled).map((t) => t.retailer_id)),
  ]
    .map((id) => ({
      id,
      options: targets.filter((t) => t.enabled && t.retailer_id === id),
    }))
    .filter(({ options }) => options.some(matches))
    .map(({ id, options }) => ({
      id,
      options: options.filter((t) => matches(t) || selected.includes(t.id)),
    }))
    .sort((a, b) =>
      a.options[0].retailer_name.localeCompare(
        b.options[0].retailer_name,
        "it",
      ),
    );
  function choose(id: string, value: string) {
    const other = selected.filter(
      (key) => !targets.some((t) => t.id === key && t.retailer_id === id),
    );
    onChange(value ? [...other, value] : other);
    setExpanded(null);
  }
  return (
    <div className="retailer-picker">
      {groups.map(({ id, options }) => {
        const chosen = options.find((t) => selected.includes(t.id));
        const single = options.length === 1;
        const first = options[0];
        const blocked = !chosen && selected.length >= max;
        const availability = (chosen || (single ? first : null))?.availability;
        const content = (
          <>
            <span className="retailer-initial" aria-hidden="true">
              {first.retailer_name.slice(0, 1)}
            </span>
            <span className="retailer-copy">
              <strong>{first.retailer_name}</strong>
              <small>
                {chosen?.type === "store"
                  ? chosen.label
                  : single
                    ? first.type === "national"
                      ? "Catalogo nazionale · adesione locale non verificata"
                      : first.label
                    : `${options.length} sedi disponibili · scegli la tua`}
              </small>
              {first.capabilities?.includes("coupons") &&
                !first.capabilities.includes("products") && (
                  <span className="retailer-stock">
                    Solo buoni e vantaggi · prodotti non acquisiti
                  </span>
                )}
              {availability &&
                !(
                  first.capabilities?.includes("coupons") &&
                  !first.capabilities.includes("products")
                ) && (
                  <span className="retailer-stock">
                    {availability.current
                      ? `${availability.current} offerte oggi`
                      : availability.future
                        ? `Dal prossimo volantino`
                        : "Pronto per la ricerca"}
                    {availability.future > 0 && availability.current > 0
                      ? ` · ${availability.future} in arrivo`
                      : ""}
                  </span>
                )}
            </span>
            {chosen && !single ? (
              <Check size={20} aria-hidden="true" />
            ) : !single ? (
              <ChevronDown size={18} aria-hidden="true" />
            ) : null}
          </>
        );
        return (
          <article
            className={`retailer-choice ${chosen ? "chosen" : ""}`}
            data-retailer={id}
            key={id}
          >
            {single ? (
              <label className="retailer-row">
                <input
                  type="checkbox"
                  aria-label={`${first.retailer_name} ${first.type === "national" ? "Catalogo nazionale" : "Punto vendita"} ${first.label}`}
                  checked={!!chosen}
                  disabled={blocked}
                  onChange={() => choose(id, chosen ? "" : first.id)}
                />
                {content}
              </label>
            ) : (
              <button
                className="retailer-row"
                aria-label={`${first.retailer_name}: ${chosen ? "cambia sede" : "scegli sede"}`}
                aria-expanded={expanded === id}
                disabled={blocked}
                onClick={() => setExpanded(expanded === id ? null : id)}
              >
                {content}
              </button>
            )}
            {!single && expanded === id && (
              <div className="store-chooser">
                <label>
                  <MapPin size={16} aria-hidden="true" /> Punto vendita{" "}
                  {first.retailer_name}
                  <select
                    autoFocus
                    value={chosen?.id || ""}
                    onChange={(e) => choose(id, e.target.value)}
                  >
                    <option value="">Scegli una sede</option>
                    {options.map((t) => (
                      <option value={t.id} key={t.id}>
                        {t.label}
                      </option>
                    ))}
                  </select>
                </label>
                {chosen && (
                  <button
                    className="text-button"
                    onClick={() => choose(id, "")}
                  >
                    Deseleziona {first.retailer_name}
                  </button>
                )}
              </div>
            )}
          </article>
        );
      })}
      {!groups.length && (
        <p className="target-empty">
          Nessun supermercato disponibile per “{query}”. Prova con l’insegna o
          il comune.
        </p>
      )}
    </div>
  );
}
