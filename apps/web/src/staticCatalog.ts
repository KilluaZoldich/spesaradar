import type {
  Catalog,
  Coupon,
  CouponCatalog,
  Offer,
  SourceState,
  Target,
} from "./types";

export type Snapshot = {
  schema_version: 1;
  generated_at: string;
  targets: { items: Target[]; max_selections: number };
  retailers: {
    items: {
      id: string;
      name: string;
      message: string;
      support_status: string;
    }[];
  };
  categories: { items: { id: string; label: string }[] };
  sources: SourceState[];
  records: {
    offer: (Offer | Coupon) & {
      source_id: string;
      first_seen_at: string;
      quality: string;
      data_origin: string;
    };
    withdrawn: boolean;
  }[];
};
export function availableTargets(snapshot: Snapshot, now = Date.now()) {
  const availability = Object.fromEntries(
    snapshot.targets.items.map((t) => [
      t.id,
      { current: 0, future: 0, coupons: 0 },
    ]),
  );
  for (const { offer: o, withdrawn } of snapshot.records) {
    const age = now - Date.parse(o.last_verified_at);
    if (
      !availability[o.source_id] ||
      withdrawn ||
      o.quality === "quarantined" ||
      o.data_origin !== "official_live" ||
      !Number.isFinite(age) ||
      age > 48 * 3600000 ||
      now >= Date.parse(o.validity.end_at_exclusive || "")
    )
      continue;
    availability[o.source_id][
      o.price === null
        ? "coupons"
        : now < Date.parse(o.validity.start_at || "")
          ? "future"
          : "current"
    ]++;
  }
  return {
    ...snapshot.targets,
    items: snapshot.targets.items.map((t) => ({
      ...t,
      availability: availability[t.id],
    })),
  };
}
export function queryCoupons(
  snapshot: Snapshot,
  p: URLSearchParams,
  now = Date.now(),
): CouponCatalog {
  const ids = [...new Set(p.getAll("target_ids"))];
  if (!ids.length)
    throw new CatalogError(
      "SELECT_TARGETS",
      "Seleziona almeno un negozio o ambito.",
    );
  if (
    ids.length > snapshot.targets.max_selections ||
    ids.some((id) => !snapshot.targets.items.some((t) => t.id === id))
  )
    throw new CatalogError(
      "UNSUPPORTED_TARGET",
      "Controlla gli ambiti selezionati.",
    );
  const items: Coupon[] = [];
  for (const { offer: o, withdrawn } of snapshot.records) {
    const age = now - Date.parse(o.last_verified_at);
    if (
      o.price !== null ||
      withdrawn ||
      !ids.includes(o.source_id) ||
      o.quality === "quarantined" ||
      o.data_origin !== "official_live" ||
      !Number.isFinite(age) ||
      age > 48 * 3600000 ||
      now >= Date.parse(o.validity.end_at_exclusive || "") ||
      now < Date.parse(o.validity.start_at || "")
    )
      continue;
    items.push({
      ...o,
      freshness: age > 12 * 3600000 ? "stale" : "fresh",
      temporal_status: "active",
    });
  }
  items.sort(
    (a, b) =>
      (a.validity.end_at_exclusive || "9999").localeCompare(
        b.validity.end_at_exclusive || "9999",
      ) || a.id.localeCompare(b.id),
  );
  return {
    items,
    message: items.length
      ? "Buoni pubblicati: verifica le condizioni prima di utilizzarli."
      : "Nessun buono attuale verificato per le selezioni. I prezzi con carta restano nella vista prodotti.",
    server_time: new Date(now).toISOString(),
    source_states: snapshot.sources.filter((s) => ids.includes(s.source_id)),
  };
}
export class CatalogError extends Error {
  constructor(
    public code: string,
    message: string,
  ) {
    super(message);
  }
}
const normalize = (text: string) =>
  text
    .normalize("NFKD")
    .replace(/\p{M}/gu, "")
    .toLocaleLowerCase("it")
    .trim()
    .replace(/\s+/g, " ");
export function queryCatalog(
  snapshot: Snapshot,
  p: URLSearchParams,
  now = Date.now(),
): Catalog {
  const ids = [...new Set(p.getAll("target_ids"))].sort();
  if (!ids.length)
    throw new CatalogError(
      "SELECT_TARGETS",
      "Seleziona almeno un negozio o ambito.",
    );
  if (
    ids.length > snapshot.targets.max_selections ||
    ids.some((id) => !snapshot.targets.items.some((t) => t.id === id))
  )
    throw new CatalogError(
      "UNSUPPORTED_TARGET",
      "Controlla gli ambiti selezionati.",
    );
  const query = normalize(p.get("q") || ""),
    tokens = query.split(" ").filter(Boolean);
  const categories = p.getAll("category_ids"),
    retailers = p.getAll("retailer_ids");
  const validity = p.get("validity") || "current",
    loyalty = p.get("loyalty") || "all",
    minimum = p.get("minimum_quantity") || "all";
  const sort = p.get("sort") || "recent",
    basis = p.get("price_basis");
  if (sort === "price" && !["pack", "kg", "l", "piece"].includes(basis || ""))
    throw new CatalogError(
      "PRICE_BASIS_REQUIRED",
      "Scegli una base di prezzo.",
    );
  const counts = Object.fromEntries(
    snapshot.categories.items.map((c) => [c.id, 0]),
  );
  const periodCounts = { current: 0, future: 0 };
  const items: (Offer & { first_seen_at: string })[] = [];
  for (const record of snapshot.records) {
    const original = record.offer;
    if (
      original.price === null ||
      record.withdrawn ||
      original.data_origin !== "official_live" ||
      original.quality === "quarantined" ||
      !ids.includes(original.source_id)
    )
      continue;
    const age = now - Date.parse(original.last_verified_at),
      end = original.validity.end_at_exclusive
        ? Date.parse(original.validity.end_at_exclusive)
        : null;
    const start = original.validity.start_at
      ? Date.parse(original.validity.start_at)
      : null;
    if (
      !Number.isFinite(age) ||
      age > 48 * 3600000 ||
      (end !== null && now >= end)
    )
      continue;
    const temporal_status =
      start !== null && now < start
        ? "future"
        : start !== null
          ? "active"
          : "unknown";
    if (retailers.length && !retailers.includes(original.retailer_id)) continue;
    const words = normalize(
      original.title + " " + (original.brand || ""),
    ).split(" ");
    if (
      !tokens.every((t) =>
        words.some((w) => w === t || (t.length >= 3 && w.startsWith(t))),
      )
    )
      continue;
    const c = original.conditions;
    if (
      loyalty !== "all" &&
      c.loyalty_required !==
        (
          { required: true, not_required: false, unknown: null } as Record<
            string,
            boolean | null
          >
        )[loyalty]
    )
      continue;
    if (
      (minimum === "required" &&
        (c.minimum_pack_count === null || c.minimum_pack_count < 2)) ||
      (minimum === "not_required" && c.minimum_pack_count !== 1) ||
      (minimum === "unknown" && c.minimum_pack_count !== null)
    )
      continue;
    if (
      sort === "price" &&
      (original.price.basis !== basis || (c.minimum_pack_count || 0) > 1)
    )
      continue;
    if (!categories.length || categories.includes(original.category_id))
      periodCounts[temporal_status === "future" ? "future" : "current"]++;
    if (
      (validity === "current" && temporal_status === "future") ||
      (validity === "future" && temporal_status !== "future")
    )
      continue;
    counts[original.category_id] = (counts[original.category_id] || 0) + 1;
    if (!categories.length || categories.includes(original.category_id))
      items.push({
        ...original,
        temporal_status,
        freshness: age > 12 * 3600000 ? "stale" : "fresh",
      });
  }
  const compare = (a: string, b: string) => (a < b ? -1 : a > b ? 1 : 0);
  items.sort((a, b) => {
    if (sort === "price")
      return (
        a.price.advertised_amount_cents - b.price.advertised_amount_cents ||
        compare(a.id, b.id)
      );
    if (sort === "expiry")
      return (
        compare(
          a.validity.end_at_exclusive || "9999",
          b.validity.end_at_exclusive || "9999",
        ) || compare(a.id, b.id)
      );
    if (sort === "relevance" && tokens.length) {
      const rank = (o: Offer) =>
        normalize(o.title) === query
          ? 0
          : normalize(o.title).startsWith(query)
            ? 1
            : 2;
      return rank(a) - rank(b) || compare(a.id, b.id);
    }
    return compare(b.first_seen_at, a.first_seen_at) || compare(b.id, a.id);
  });
  const limit = Math.min(100, Math.max(1, Number(p.get("limit") || 24))),
    revision = snapshot.generated_at + ":" + Math.floor(now / 60000);
  const filters = new URLSearchParams(p);
  filters.delete("cursor");
  filters.sort();
  const fingerprint = filters.toString();
  let offset = 0;
  if (p.has("cursor")) {
    let cursor;
    try {
      cursor = JSON.parse(atob(p.get("cursor")!));
    } catch {
      throw new CatalogError("INVALID_CURSOR", "Pagina non valida.");
    }
    if (cursor.filters !== fingerprint)
      throw new CatalogError("INVALID_CURSOR", "I filtri sono cambiati.");
    if (cursor.revision !== revision)
      throw new CatalogError(
        "CATALOG_CHANGED",
        "Le offerte sono cambiate. Ricarico la prima pagina.",
      );
    if (!Number.isInteger(cursor.offset) || cursor.offset < 0)
      throw new CatalogError("INVALID_CURSOR", "Pagina non valida.");
    offset = cursor.offset;
  }
  return {
    items: items.slice(offset, offset + limit),
    total: items.length,
    next_cursor:
      offset + limit < items.length
        ? btoa(
            JSON.stringify({
              offset: offset + limit,
              filters: fingerprint,
              revision,
            }),
          )
        : null,
    category_counts: counts,
    period_counts: periodCounts,
    catalog_revision: revision,
    server_time: new Date(now).toISOString(),
    source_states: snapshot.sources.filter((s) => ids.includes(s.source_id)),
    limitations: [
      "Catalogo pubblicato periodicamente. Adesione del negozio non verificata.",
    ],
  };
}
let snapshotPromise: Promise<Snapshot> | undefined;
let requestedAt = 0;
let anchor = { server: Date.now(), monotonic: performance.now() };
const clock = () => anchor.server + performance.now() - anchor.monotonic;
export function reloadSnapshot() {
  snapshotPromise = undefined;
  return loadSnapshot();
}
function loadSnapshot(): Promise<Snapshot> {
  if (snapshotPromise && performance.now() - requestedAt > 60000)
    snapshotPromise = undefined;
  if (!snapshotPromise) {
    requestedAt = performance.now();
    snapshotPromise = fetch(import.meta.env.BASE_URL + "catalog.json", {
      cache: "no-cache",
    })
      .then(async (response) => {
        if (!response.ok)
          throw new CatalogError(
            "CATALOG_UNAVAILABLE",
            "La pubblicazione non è raggiungibile. Riprova tra poco.",
          );
        const raw = await response.text();
        if (raw.length > 10 * 1024 * 1024)
          throw new Error("Catalogo troppo grande");
        const snapshot = JSON.parse(raw) as Snapshot;
        if (
          snapshot.schema_version !== 1 ||
          !Array.isArray(snapshot.records) ||
          !snapshot.targets?.items
        )
          throw new Error("Catalogo non compatibile");
        const server = Date.parse(response.headers.get("date") || "");
        anchor = {
          server: Number.isFinite(server) ? server : Date.now(),
          monotonic: performance.now(),
        };
        return snapshot;
      })
      .catch((error) => {
        snapshotPromise = undefined;
        throw error;
      });
  }
  return snapshotPromise;
}
export async function staticApi<T>(
  path: string,
  init?: RequestInit,
): Promise<T> {
  if (init?.method && init.method !== "GET")
    throw new CatalogError(
      "READ_ONLY",
      "La raccolta online è programmata: non viene avviata dal browser.",
    );
  const snapshot = await loadSnapshot();
  init?.signal?.throwIfAborted();
  const [route, query = ""] = path.split("?");
  const p = new URLSearchParams(query);
  let result: unknown;
  if (route === "/targets") result = availableTargets(snapshot, clock());
  else if (route === "/retailers") result = snapshot.retailers;
  else if (route === "/categories") result = snapshot.categories;
  else if (route === "/offers") result = queryCatalog(snapshot, p, clock());
  else if (route.startsWith("/offers/")) {
    const record = snapshot.records.find(
      (r) => r.offer.id === route.slice("/offers/".length),
    );
    if (!record) throw new CatalogError("NOT_FOUND", "Offerta non trovata.");
    const age = clock() - Date.parse(record.offer.last_verified_at);
    const start = Date.parse(record.offer.validity.start_at || ""),
      end = Date.parse(record.offer.validity.end_at_exclusive || "");
    result = {
      ...record.offer,
      withdrawn: record.withdrawn,
      temporal_status:
        clock() >= end
          ? "expired"
          : clock() < start
            ? "future"
            : Number.isFinite(start)
              ? "active"
              : "unknown",
      freshness:
        age > 48 * 3600000 ? "hidden" : age > 12 * 3600000 ? "stale" : "fresh",
    };
  } else if (route === "/coupons") result = queryCoupons(snapshot, p, clock());
  else throw new CatalogError("NOT_FOUND", "Risorsa non disponibile.");
  return result as T;
}
