import { Component, useEffect, useRef, useState } from "react";
import type { ReactNode } from "react";
import {
  Radar,
  Search,
  Store,
  ArrowRight,
  RefreshCw,
  SlidersHorizontal,
  X,
  Info,
  WifiOff,
  Ticket,
  ShoppingBasket,
  ChevronDown,
} from "lucide-react";
import RetailerPicker, { oneTargetPerRetailer } from "./RetailerPicker";
import CategoryNavigation, { shortCategory } from "./CategoryNavigation";
import {
  api,
  ApiError,
  readPreferences,
  savePreferences,
  STATIC_CATALOG,
  reloadPublishedCatalog,
} from "./api";
import type { Target, Offer, Catalog, SourceState } from "./types";
import OfferCard, {
  Conditions,
  euros,
  validityLabel,
  basisLabels,
} from "./OfferCard";
const stages: Record<string, string> = {
  queued: "In coda",
  fetch: "Raccolta",
  parse: "Elaborazione",
  validate: "Verifica",
  published: "Completato",
  failed: "Fonte non raggiungibile",
  blocked: "Accesso non consentito",
  running: "Aggiornamento in corso",
  partial: "Aggiornamento parziale",
  succeeded: "Aggiornato",
  idle: "Da aggiornare",
};
export class ErrorBoundary extends Component<
  { children: ReactNode },
  { failed: boolean }
> {
  state = { failed: false };
  static getDerivedStateFromError() {
    return { failed: true };
  }
  render() {
    return this.state.failed ? (
      <main className="empty">
        <h1>La pagina ha incontrato un problema</h1>
        <p>Le tue selezioni sono conservate nel browser.</p>
        <button onClick={() => location.reload()}>Ricarica l’app</button>
      </main>
    ) : (
      this.props.children
    );
  }
}
function SourceStatus({ states }: { states: SourceState[] }) {
  return (
    <details
      className="source-summary"
      open={
        states.some((s) =>
          ["failed", "blocked", "running", "queued"].includes(s.state),
        ) || undefined
      }
    >
      <summary>
        <span className="status-dot" />
        {states.some((s) => ["failed", "blocked"].includes(s.state))
          ? "Alcuni supermercati non sono aggiornabili"
          : states.some((s) => ["running", "queued"].includes(s.state))
            ? "Aggiornamento in corso"
            : "Aggiornamenti e copertura"}
        <ChevronDown size={15} />
      </summary>
      <div className="source-status" aria-live="polite">
        {states.map((s) => (
          <div
            key={s.source_id}
            className={
              ["failed", "blocked"].includes(s.state) ? "source-error" : ""
            }
          >
            <span className={"status-dot " + s.state} />
            <strong>{s.name}</strong>
            <span>
              {stages[s.stage || s.state] || s.state}
              {s.last_success_at && s.state !== "running"
                ? ` · ${new Intl.DateTimeFormat("it-IT", { hour: "2-digit", minute: "2-digit", timeZone: "Europe/Rome" }).format(new Date(s.last_success_at))}`
                : ""}
            </span>
            {s.message &&
              (["failed", "blocked"].includes(s.state) ? (
                <small>{s.message}</small>
              ) : (
                <details className="source-details">
                  <summary aria-label={`Dettagli aggiornamento ${s.name}`}>
                    Dettagli
                  </summary>
                  <p>{s.message}</p>
                </details>
              ))}
          </div>
        ))}
      </div>
    </details>
  );
}
export default function App() {
  const [targetQuery, setTargetQuery] = useState(() => {
    const cap = new URLSearchParams(window.location.search).get("cap") || "";
    return /^\d{5}$/.test(cap) ? cap : "";
  });
  const [maxSelections, setMaxSelections] = useState(5);
  const [targets, setTargets] = useState<Target[]>([]),
    [categories, setCategories] = useState<{ id: string; label: string }[]>([]),
    [retailers, setRetailers] = useState<
      {
        id: string;
        name: string;
        message: string;
        support_status: string;
        source_url?: string;
      }[]
    >([]);
  const [selected, setSelected] = useState<string[]>([]),
    [draft, setDraft] = useState<string[]>([]),
    [editing, setEditing] = useState(true),
    [initialized, setInitialized] = useState(false),
    [notice, setNotice] = useState("");
  const [query, setQuery] = useState(""),
    [debounced, setDebounced] = useState(""),
    [cats, setCats] = useState<string[]>([]),
    [retailer, setRetailer] = useState(""),
    [validity, setValidity] = useState("current"),
    [loyalty, setLoyalty] = useState("all"),
    [minimum, setMinimum] = useState("all"),
    [sort, setSort] = useState("recent"),
    [filters, setFilters] = useState(false),
    [view, setView] = useState("products");
  const [catalog, setCatalog] = useState<Catalog | null>(null),
    [loading, setLoading] = useState(false),
    [error, setError] = useState(""),
    [states, setStates] = useState<SourceState[]>([]),
    [refreshId, setRefreshId] = useState<string | null>(null),
    [refreshing, setRefreshing] = useState(false),
    [tick, setTick] = useState(0),
    [offline, setOffline] = useState(!navigator.onLine),
    [detail, setDetail] = useState<Offer | null>(null),
    [couponMessage, setCouponMessage] = useState("");
  const initialRefresh = useRef(false);
  const generation = useRef(0),
    dialog = useRef<HTMLDialogElement>(null),
    selectionKey = selected.slice().sort().join(","),
    currentKey = useRef(selectionKey);
  currentKey.current = selectionKey;
  useEffect(() => {
    let live = true;
    Promise.all([
      api<{ items: Target[]; max_selections: number }>("/targets"),
      api<{ items: { id: string; label: string }[] }>("/categories"),
      api<{ items: typeof retailers }>("/retailers"),
    ])
      .then(([t, c, r]) => {
        if (!live) return;
        setTargets(t.items);
        setMaxSelections(t.max_selections);
        setCategories(c.items);
        setRetailers(r.items);
        const saved = readPreferences(),
          valid = oneTargetPerRetailer(saved, t.items).slice(
            0,
            t.max_selections,
          );
        if (saved.length !== valid.length) savePreferences(valid);
        setSelected(valid);
        setDraft(valid);
        setEditing(!valid.length);
        if (saved.length !== valid.length)
          setNotice(
            "Le selezioni sono state aggiornate: una sede per supermercato. Puoi cambiarla da Negozi.",
          );
        setInitialized(true);
      })
      .catch((e) => {
        if (live) {
          setError(e.message);
          setInitialized(true);
        }
      });
    return () => {
      live = false;
    };
  }, []);
  useEffect(() => {
    const timer = setTimeout(() => setDebounced(query), 250);
    return () => clearTimeout(timer);
  }, [query]);
  useEffect(() => {
    const resume = () => {
      setOffline(!navigator.onLine);
      if (!document.hidden) setTick((x) => x + 1);
    };
    document.addEventListener("visibilitychange", resume);
    window.addEventListener("online", resume);
    window.addEventListener("offline", resume);
    window.addEventListener("pageshow", resume);
    const timer = setInterval(() => {
      if (!document.hidden) setTick((x) => x + 1);
    }, 60000);
    return () => {
      clearInterval(timer);
      document.removeEventListener("visibilitychange", resume);
      window.removeEventListener("online", resume);
      window.removeEventListener("offline", resume);
      window.removeEventListener("pageshow", resume);
    };
  }, []);
  useEffect(() => {
    if (!initialized || !editing) return;
    const controller = new AbortController();
    api<{ items: Target[] }>("/targets", { signal: controller.signal })
      .then((result) => {
        if (!controller.signal.aborted) setTargets(result.items);
      })
      .catch(() => {}); // The existing selection remains usable if this optional read fails.
    return () => controller.abort();
  }, [editing, initialized, tick]);
  const params = () => {
    const p = new URLSearchParams();
    selected.forEach((id) => p.append("target_ids", id));
    cats.forEach((id) => p.append("category_ids", id));
    if (retailer) p.append("retailer_ids", retailer);
    p.set("q", debounced);
    p.set("validity", validity);
    p.set("loyalty", loyalty);
    p.set("minimum_quantity", minimum);
    p.set("sort", sort.startsWith("price-") ? "price" : sort);
    if (sort.startsWith("price-")) p.set("price_basis", sort.slice(6));
    return p;
  };
  const queryKey = params().toString();
  const displayedQuery = useRef("");
  useEffect(() => {
    if (!selected.length) return;
    const controller = new AbortController();
    const gen = ++generation.current;
    // Keep cache during a refresh, but never label old results with new filters.
    if (displayedQuery.current !== queryKey) {
      setCatalog(null);
      displayedQuery.current = queryKey;
    }
    setLoading(true);
    setError("");
    api<Catalog>("/offers?" + queryKey, { signal: controller.signal })
      .then((data) => {
        if (gen === generation.current) {
          setCatalog(data);
          setStates(data.source_states);
        }
      })
      .catch((e) => {
        if (e.name !== "AbortError" && gen === generation.current)
          setError(e.message);
      })
      .finally(() => {
        if (gen === generation.current) setLoading(false);
      });
    return () => controller.abort();
  }, [queryKey, tick]);
  useEffect(() => {
    if (view !== "coupons" || !selected.length) return;
    const controller = new AbortController();
    const p = new URLSearchParams();
    selected.forEach((id) => p.append("target_ids", id));
    api<{ message: string }>("/coupons?" + p, { signal: controller.signal })
      .then((x) => setCouponMessage(x.message))
      .catch((e) => {
        if (e.name !== "AbortError") setError(e.message);
      });
    return () => controller.abort();
  }, [view, selectionKey]);
  async function refresh(ids = selected, userRequested = false) {
    if (!ids.length) return;
    const key = ids.slice().sort().join(",");
    setRefreshing(true);
    setError("");
    try {
      if (STATIC_CATALOG) {
        await reloadPublishedCatalog();
        if (currentKey.current === key) {
          setTick((x) => x + 1);
          if (userRequested)
            setNotice(
              "Ultima pubblicazione caricata. La raccolta delle fonti avviene ogni 12 ore circa, con possibili ritardi.",
            );
        }
        return;
      }
      const r = await api<{ id: string; targets: { disposition: string }[] }>(
        "/refreshes",
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ target_ids: ids }),
        },
      );
      if (currentKey.current !== key) return;
      setRefreshId(r.id);
    } catch (e) {
      if (currentKey.current === key) setError((e as Error).message);
    } finally {
      if (currentKey.current === key) setRefreshing(false);
    }
  }
  useEffect(() => {
    if (initialized && selected.length && !initialRefresh.current) {
      initialRefresh.current = true;
      refresh(selected);
    }
  }, [initialized]);
  useEffect(() => {
    if (!refreshId) return;
    const controller = new AbortController();
    let timer: ReturnType<typeof setTimeout>;
    let closed = false;
    const started = Date.now(),
      key = selectionKey;
    async function poll() {
      if (closed || document.hidden) return;
      try {
        const r = await api<{
          terminal: boolean;
          source_states: SourceState[];
        }>("/refreshes/" + refreshId, { signal: controller.signal });
        if (closed || currentKey.current !== key) return;
        setStates(r.source_states);
        setTick((x) => x + 1);
        if (r.terminal) {
          setRefreshId(null);
          return;
        }
      } catch (e) {
        if ((e as Error).name !== "AbortError") setError((e as Error).message);
      }
      if (!closed)
        timer = setTimeout(poll, Date.now() - started > 30000 ? 5000 : 2000);
    }
    const onVisibility = () => {
      clearTimeout(timer);
      if (!document.hidden) poll();
    };
    poll();
    document.addEventListener("visibilitychange", onVisibility);
    return () => {
      closed = true;
      controller.abort();
      clearTimeout(timer);
      document.removeEventListener("visibilitychange", onVisibility);
    };
  }, [refreshId, selectionKey]);
  useEffect(() => {
    if (detail) {
      dialog.current?.showModal();
      return () => dialog.current?.close();
    }
  }, [detail?.id]);
  async function openDetail(offer: Offer) {
    setDetail(offer);
    try {
      const fresh = await api<Offer>("/offers/" + offer.id);
      setDetail((current) => (current?.id === fresh.id ? fresh : current));
    } catch (e) {
      setError((e as Error).message);
    }
  }
  async function more() {
    if (!catalog?.next_cursor) return;
    const key = currentKey.current,
      gen = generation.current;
    setLoading(true);
    try {
      const p = params();
      p.set("cursor", catalog.next_cursor);
      const next = await api<Catalog>("/offers?" + p);
      if (key === currentKey.current && gen === generation.current)
        setCatalog((previous) =>
          previous
            ? { ...next, items: [...previous.items, ...next.items] }
            : next,
        );
    } catch (e) {
      if (e instanceof ApiError && e.code === "CATALOG_CHANGED")
        setTick((x) => x + 1);
      else setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  }
  function search() {
    const ids = oneTargetPerRetailer(draft, targets)
      .slice(0, maxSelections)
      .sort();
    generation.current++;
    setSelected(ids);
    currentKey.current = ids.join(",");
    savePreferences(ids);
    setCatalog(null);
    setStates([]);
    setRefreshId(null);
    setCats([]);
    setRetailer("");
    setEditing(false);
    setTick((x) => x + 1);
    refresh(ids);
  }
  const visibleItems = (catalog?.items || [])
    .filter((o) => {
      const now = Date.now();
      return (
        (!o.validity.end_at_exclusive ||
          new Date(o.validity.end_at_exclusive).getTime() > now) &&
        now - new Date(o.last_verified_at).getTime() < 172800000
      );
    })
    .map((o) => ({
      ...o,
      freshness:
        Date.now() - new Date(o.last_verified_at).getTime() > 43200000
          ? "stale"
          : o.freshness,
    }));
  const categoryMap = Object.fromEntries(
      categories.map((c) => [c.id, c.label]),
    ),
    activeTargets = targets.filter((t) => selected.includes(t.id));
  const retailerMap = Object.fromEntries(retailers.map((r) => [r.id, r.name]));
  const selectedRetailers = [
    ...new Map(activeTargets.map((t) => [t.retailer_id, t])).values(),
  ];
  const busy = refreshing || !!refreshId;
  const anyFilters =
    !!query ||
    cats.length > 0 ||
    !!retailer ||
    loyalty !== "all" ||
    minimum !== "all";
  return (
    <>
      <a className="skip-link" href="#contenuto">
        Vai al contenuto
      </a>
      <header className="app-header">
        <a
          className="wordmark"
          href={import.meta.env.BASE_URL}
          aria-label="SpesaRadar, pagina iniziale"
        >
          <span>
            <Radar size={25} />
          </span>
          Spesa<span className="wordmark-radar">Radar</span>
        </a>
        <span className="private-label">La tua spesa, più chiara.</span>
      </header>
      <main className="app-main" id="contenuto" tabIndex={-1}>
        {offline && (
          <div className="banner warning" role="status">
            <WifiOff size={18} /> Sei offline. La verifica delle offerte
            riprende quando torna la connessione.
          </div>
        )}
        {notice && (
          <div className="banner notice">
            <Info size={17} />
            <span>{notice}</span>
            <button aria-label="Chiudi avviso" onClick={() => setNotice("")}>
              <X size={16} />
            </button>
          </div>
        )}
        {error && (
          <div className="banner error" role="alert">
            <Info size={18} />
            <span>{error}</span>
            <button
              onClick={() =>
                initialized ? setTick((x) => x + 1) : location.reload()
              }
            >
              Riprova
            </button>
          </div>
        )}
        {editing ? (
          <section className="selection">
            <div className="selection-intro">
              <span className="selection-eyebrow">
                Organizza la tua prossima spesa
              </span>
              <h1>
                I tuoi supermercati.
                <br /> Le offerte, tutte qui.
              </h1>
              <p>
                Scegli dove fai la spesa. A prezzi, categorie e scadenze
                pensiamo noi.
              </p>
            </div>
            <div className="selection-form">
              <h2>Scegli i supermercati</h2>
              <p className="muted">
                Una sola scelta per insegna. La sede la decidi tu.
              </p>
              <label className="search-input selection-search">
                <Search size={18} aria-hidden="true" />
                <span className="sr-only">Cerca supermercato o sede</span>
                <input
                  value={targetQuery}
                  onChange={(e) => setTargetQuery(e.target.value)}
                  placeholder="Cerca insegna, comune o CAP…"
                  maxLength={120}
                />
                {targetQuery && (
                  <button
                    aria-label="Cancella ricerca negozi"
                    onClick={() => setTargetQuery("")}
                  >
                    <X size={16} />
                  </button>
                )}
              </label>
              <div className="selection-caption">
                <span>
                  {
                    new Set(
                      targets
                        .filter((t) => t.enabled)
                        .map((t) => t.retailer_id),
                    ).size
                  }{" "}
                  insegne disponibili
                </span>
                <span>
                  {draft.length}/{maxSelections} selezionati
                </span>
              </div>
              <RetailerPicker
                targets={targets}
                selected={draft}
                query={targetQuery}
                max={maxSelections}
                onChange={setDraft}
              />
              {!initialized && <div className="skeleton selection-skeleton" />}
              <div className="scope-note">
                <Info size={18} />
                <p>
                  Le offerte nazionali non confermano l’adesione di ogni
                  negozio. Per una sede specifica, scegli soltanto l’indirizzo
                  che ti interessa. La copertura è parziale.
                </p>
              </div>
              <button
                className="primary search-offers"
                disabled={!draft.length || !initialized}
                onClick={search}
              >
                Cerca offerte <ArrowRight size={19} />
              </button>
              {selected.length > 0 && (
                <button
                  className="text-button"
                  onClick={() => setEditing(false)}
                >
                  Torna alle offerte
                </button>
              )}
              <details className="unsupported">
                <summary>
                  Altre insegne e copertura <ChevronDown size={16} />
                </summary>
                {retailers
                  .filter((r) => !targets.some((t) => t.retailer_id === r.id))
                  .map((r) => (
                    <p key={r.id}>
                      <strong>{r.name}</strong> · {r.message}
                      {r.source_url && (
                        <a
                          href={r.source_url}
                          target="_blank"
                          rel="noopener noreferrer"
                        >
                          {" "}
                          Sede ufficiale
                        </a>
                      )}
                    </p>
                  ))}
                <p>
                  Fonti social non acquisite. Nessun negozio viene scelto
                  automaticamente.
                </p>
              </details>
            </div>
          </section>
        ) : (
          <>
            <section className="catalog-heading">
              <div>
                <h1>Le tue offerte</h1>
                {selectedRetailers.length === 1 && (
                  <div className="selected-stores">
                    <Store size={17} />
                    {selectedRetailers[0].retailer_name}
                  </div>
                )}
                {selectedRetailers.length > 1 && (
                  <nav
                    className="retailer-shortcuts"
                    aria-label="Filtra per supermercato"
                  >
                    <button
                      aria-pressed={!retailer}
                      onClick={() => setRetailer("")}
                    >
                      <span className="desktop-label">
                        Tutti i supermercati
                      </span>
                      <span className="mobile-label">Tutti</span>
                    </button>
                    {selectedRetailers.map((t) => (
                      <button
                        key={t.retailer_id}
                        aria-pressed={retailer === t.retailer_id}
                        onClick={() => setRetailer(t.retailer_id)}
                      >
                        {t.retailer_name}
                      </button>
                    ))}
                  </nav>
                )}
              </div>
              <div className="heading-actions">
                <button
                  className="secondary"
                  aria-label="Modifica negozi"
                  onClick={() => {
                    setDraft(selected);
                    setTargetQuery("");
                    setEditing(true);
                  }}
                >
                  <span className="desktop-label">Modifica negozi</span>
                  <span className="mobile-label">Negozi</span>
                </button>
                <button
                  className="icon-button"
                  aria-label={
                    STATIC_CATALOG
                      ? "Controlla aggiornamenti"
                      : "Aggiorna offerte"
                  }
                  title={
                    STATIC_CATALOG
                      ? "Controlla l’ultima pubblicazione"
                      : "Aggiorna offerte"
                  }
                  disabled={busy || offline}
                  onClick={() => refresh(selected, true)}
                >
                  <RefreshCw size={18} className={busy ? "rotating" : ""} />
                </button>
              </div>
            </section>
            <SourceStatus states={states} />
            <nav className="view-tabs" aria-label="Tipo di promozione">
              <button
                className={view === "products" ? "active" : ""}
                aria-pressed={view === "products"}
                onClick={() => setView("products")}
              >
                <ShoppingBasket size={18} />
                Prodotti in offerta
              </button>
              <button
                className={view === "coupons" ? "active" : ""}
                aria-pressed={view === "coupons"}
                onClick={() => setView("coupons")}
              >
                <Ticket size={18} />
                Buoni e vantaggi
              </button>
            </nav>
            {view === "products" ? (
              <>
                <div className="search-row">
                  <label className="search-input">
                    <Search size={20} />
                    <span className="sr-only">Cerca prodotti</span>
                    <input
                      value={query}
                      onChange={(e) => setQuery(e.target.value)}
                      maxLength={120}
                      placeholder="Cerca pollo, biscotti, detersivo…"
                    />
                    {query && (
                      <button
                        aria-label="Cancella ricerca"
                        onClick={() => setQuery("")}
                      >
                        <X size={18} />
                      </button>
                    )}
                  </label>
                  <button
                    className={
                      "secondary filter-toggle " + (filters ? "pressed" : "")
                    }
                    aria-label="Filtri"
                    aria-expanded={filters}
                    onClick={() => setFilters((x) => !x)}
                  >
                    <SlidersHorizontal size={18} />
                    Filtri
                    {[
                      retailer !== "",
                      loyalty !== "all",
                      minimum !== "all",
                    ].filter(Boolean).length > 0 && (
                      <span className="filter-count" aria-hidden="true">
                        {
                          [
                            retailer !== "",
                            loyalty !== "all",
                            minimum !== "all",
                          ].filter(Boolean).length
                        }
                      </span>
                    )}
                  </button>
                </div>
                <CategoryNavigation
                  categories={categories}
                  counts={catalog?.category_counts || {}}
                  selected={cats}
                  onChange={setCats}
                />
                {filters && (
                  <div className="filter-panel">
                    <label>
                      Supermercato
                      <select
                        aria-label="Supermercato"
                        value={retailer}
                        onChange={(e) => setRetailer(e.target.value)}
                      >
                        <option value="">Tutti i selezionati</option>
                        {selectedRetailers.map((t) => (
                          <option key={t.id} value={t.retailer_id}>
                            {t.retailer_name}
                          </option>
                        ))}
                      </select>
                    </label>
                    <label>
                      Carta fedeltà
                      <select
                        aria-label="Carta fedeltà"
                        value={loyalty}
                        onChange={(e) => setLoyalty(e.target.value)}
                      >
                        <option value="all">Tutte le condizioni</option>
                        <option value="required">Solo con carta</option>
                        <option value="not_required">
                          Senza carta, verificato
                        </option>
                        <option value="unknown">
                          Requisito non verificato
                        </option>
                      </select>
                    </label>
                    <label>
                      Quantità minima
                      <select
                        aria-label="Quantità minima"
                        value={minimum}
                        onChange={(e) => setMinimum(e.target.value)}
                      >
                        <option value="all">Tutte le quantità</option>
                        <option value="required">
                          Più confezioni richieste
                        </option>
                        <option value="not_required">
                          Una confezione, verificato
                        </option>
                        <option value="unknown">Quantità non verificata</option>
                      </select>
                    </label>
                    <p>“Non verificato” non significa assenza di condizioni.</p>
                  </div>
                )}
                {(loyalty !== "all" || minimum !== "all") && (
                  <div className="active-filters" aria-label="Filtri applicati">
                    {loyalty !== "all" && (
                      <button
                        onClick={() => setLoyalty("all")}
                        aria-label="Rimuovi filtro carta"
                      >
                        {
                          {
                            required: "Solo con carta",
                            not_required: "Senza carta, verificato",
                            unknown: "Carta non verificata",
                          }[loyalty]
                        }
                        <X size={14} aria-hidden="true" />
                      </button>
                    )}
                    {minimum !== "all" && (
                      <button
                        onClick={() => setMinimum("all")}
                        aria-label="Rimuovi filtro quantità"
                      >
                        {
                          {
                            required: "Più confezioni",
                            not_required: "Una confezione, verificato",
                            unknown: "Quantità non verificata",
                          }[minimum]
                        }
                        <X size={14} aria-hidden="true" />
                      </button>
                    )}
                  </div>
                )}
                <div className="results-toolbar">
                  <div className="period-control" aria-label="Periodo">
                    <button
                      className={validity === "current" ? "active" : ""}
                      aria-pressed={validity === "current"}
                      aria-label="Disponibili oggi"
                      onClick={() => setValidity("current")}
                    >
                      <span className="desktop-label">Disponibili oggi</span>
                      <span className="mobile-label">Oggi</span>
                      {catalog?.period_counts && (
                        <span className="period-count">
                          {catalog.period_counts.current}
                        </span>
                      )}
                    </button>
                    <button
                      className={validity === "future" ? "active" : ""}
                      aria-pressed={validity === "future"}
                      aria-label="In arrivo"
                      onClick={() => setValidity("future")}
                    >
                      In arrivo
                      {catalog?.period_counts && (
                        <span className="period-count">
                          {catalog.period_counts.future}
                        </span>
                      )}
                    </button>
                  </div>
                  <label className="sort-label">
                    Ordina
                    <select
                      aria-label="Ordina offerte"
                      value={sort}
                      onChange={(e) => setSort(e.target.value)}
                    >
                      {query && <option value="relevance">Pertinenza</option>}
                      <option value="recent">Più recenti</option>
                      <option value="expiry">Scadenza più vicina</option>
                      <option value="price-pack">Prezzo a confezione</option>
                      <option value="price-kg">Prezzo al kg</option>
                      <option value="price-l">Prezzo al litro</option>
                      <option value="price-piece">Prezzo al pezzo</option>
                    </select>
                  </label>
                </div>
                <div className="results-caption">
                  <p>
                    {catalog
                      ? `${catalog.total} offerte${validity === "future" ? " in arrivo" : ""}`
                      : "Cerco le offerte disponibili…"}
                    {loading && catalog ? " · aggiornamento risultati" : ""}
                  </p>
                  {anyFilters && (
                    <button
                      onClick={() => {
                        setQuery("");
                        setCats([]);
                        setRetailer("");
                        setLoyalty("all");
                        setMinimum("all");
                      }}
                    >
                      Azzera filtri
                    </button>
                  )}
                </div>
                {sort.startsWith("price-") && (
                  <p className="comparison-note">
                    Confronto solo i prezzi esposti con questa base. Articoli
                    con quantità minima e prezzi non compatibili sono esclusi.
                  </p>
                )}
                {!catalog && loading ? (
                  <div
                    className="offer-grid"
                    role="status"
                    aria-label="Caricamento delle offerte"
                  >
                    {[1, 2, 3, 4].map((i) => (
                      <div key={i} className="skeleton card-skeleton" />
                    ))}
                  </div>
                ) : visibleItems.length ? (
                  <>
                    <h2 className="sr-only">Prodotti trovati</h2>
                    <div className="offer-grid">
                      {visibleItems.map((o) => (
                        <OfferCard
                          key={o.id}
                          offer={o}
                          retailerName={retailerMap[o.retailer_id]}
                          category={shortCategory(
                            categoryMap[o.category_id] || "Altri prodotti",
                          )}
                          onOpen={() => openDetail(o)}
                        />
                      ))}
                    </div>
                    {catalog?.next_cursor && (
                      <button
                        className="secondary load-more"
                        disabled={loading}
                        onClick={more}
                      >
                        {loading ? "Caricamento…" : "Mostra altre offerte"}
                      </button>
                    )}
                  </>
                ) : (
                  <div className="empty">
                    <ShoppingBasket size={36} strokeWidth={1.3} />
                    <h2>
                      {busy
                        ? "La raccolta è in corso"
                        : anyFilters
                          ? "Nessun risultato con questi filtri"
                          : validity === "future"
                            ? "Nessuna offerta futura disponibile"
                            : "Nessuna offerta attuale disponibile"}
                    </h2>
                    <p>
                      {busy
                        ? "I prodotti appariranno quando la verifica di ciascuna fonte sarà terminata."
                        : anyFilters
                          ? "Prova un’altra ricerca o azzera i filtri."
                          : "Consulta lo stato dei supermercati qui sopra. Le promozioni future si trovano in “In arrivo”."}
                    </p>
                    {validity === "current" &&
                      (catalog?.period_counts?.future || 0) > 0 && (
                        <button
                          className="primary"
                          onClick={() => setValidity("future")}
                        >
                          Vedi {catalog!.period_counts!.future} offerte in
                          arrivo <ArrowRight size={18} />
                        </button>
                      )}
                  </div>
                )}
              </>
            ) : (
              <div className="empty coupon-empty">
                <Ticket size={38} strokeWidth={1.3} />
                <h2>Buoni e vantaggi</h2>
                <p>{couponMessage || "Verifico la copertura dei buoni…"}</p>
                <p className="muted">
                  SpesaRadar non attiva coupon e non richiede credenziali o
                  carte fedeltà.
                </p>
              </div>
            )}
          </>
        )}
      </main>
      <footer>
        {STATIC_CATALOG && (
          <p className="publication-note">
            Versione online · Offerte aggiornate periodicamente. Raccolta ogni
            12 ore circa, con possibili ritardi.
          </p>
        )}
        <span>SpesaRadar</span>
        <p>
          Fonti ufficiali, consultazione personale. Disponibilità a scaffale e
          adesione del negozio da verificare. Nessuna affiliazione con le
          insegne.
        </p>
        <button
          onClick={() => {
            savePreferences([]);
            setSelected([]);
            setDraft([]);
            setEditing(true);
            setCatalog(null);
            setRefreshId(null);
            setNotice("Preferenze locali cancellate.");
          }}
        >
          Cancella preferenze
        </button>
      </footer>
      <dialog
        ref={dialog}
        className="detail-dialog"
        onCancel={() => setDetail(null)}
        onClick={(e) => {
          if (e.target === dialog.current) setDetail(null);
        }}
        aria-labelledby="detail-title"
      >
        {detail && (
          <div className="detail-content">
            <div className="detail-top">
              <span className="retailer">
                {retailerMap[detail.retailer_id] || detail.retailer_id}
              </span>
              <button
                className="icon-button"
                autoFocus
                aria-label="Chiudi dettaglio"
                onClick={() => setDetail(null)}
              >
                <X size={20} />
              </button>
            </div>
            <p className="brand">{detail.brand}</p>
            <h2 id="detail-title">{detail.title}</h2>
            <p className="format">
              {detail.package.raw_text || "Formato non disponibile"}
            </p>
            <div className="price-line">
              <strong>{euros(detail.price.advertised_amount_cents)}</strong>
              <span>{basisLabels[detail.price.basis]}</span>
            </div>
            <Conditions offer={detail} />
            {detail.temporal_status === "expired" && (
              <p className="banner warning">Questa offerta è scaduta.</p>
            )}
            {detail.freshness !== "fresh" && (
              <p className="banner warning">Dato non verificato di recente.</p>
            )}
            <dl>
              <dt>Validità</dt>
              <dd>{validityLabel(detail)}</dd>
              <dt>Dove si applica</dt>
              <dd>{detail.scope.label}</dd>
              <dt>Condizioni della fonte</dt>
              <dd>
                {detail.conditions.raw_text ||
                  "Condizioni non integralmente disponibili. Verifica nella fonte ufficiale prima dell’acquisto."}
              </dd>
              <dt>Prezzo unitario</dt>
              <dd>
                {detail.price.published_unit_price
                  ? `${detail.price.published_unit_price.replace(".", ",")} €/${detail.price.unit_price_basis}, riportato dalla fonte.`
                  : "Prezzo unitario non riportato."}
                {detail.price.calculation && <p>{detail.price.calculation}</p>}
              </dd>
              <dt>Ultima verifica</dt>
              <dd>
                {new Intl.DateTimeFormat("it-IT", {
                  dateStyle: "medium",
                  timeStyle: "short",
                  timeZone: "Europe/Rome",
                }).format(new Date(detail.last_verified_at))}
              </dd>
              <dt>Provenienza</dt>
              <dd>Pagina ufficiale · {detail.evidence.selector}</dd>
            </dl>
            <a
              className="primary"
              href={detail.source_url}
              target="_blank"
              rel="noopener noreferrer"
            >
              Apri la fonte ufficiale <ArrowRight size={18} />
            </a>
            <p className="detail-note">
              Offerta pubblicata: non è una conferma della disponibilità nel
              negozio in questo momento.
            </p>
          </div>
        )}
      </dialog>
    </>
  );
}
