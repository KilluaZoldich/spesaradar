# SpesaRadar

Le offerte dei tuoi supermercati, già divise per categoria. Web app locale in italiano, con raccolta automatica da siti ufficiali, database persistente e nessun LLM o servizio di scraping a pagamento.

**Rilascio 0.1 parziale.** Sono funzionanti due connettori reali, **Lidl Italia** ed **Eurospin**, per cataloghi nazionali. L’adesione del singolo negozio non è verificata. Copertura selettiva, condizioni non sempre integralmente disponibili, social e buoni generici non acquisiti. Nessun dato inventato viene inserito nel catalogo live. Vedi [audit delle fonti](docs/source-audit.md) e [verifica](docs/verification.md).

## Avvio con Docker

Prerequisiti: Docker Engine/Desktop attivo e Docker Compose v2, rete Internet per immagini e fonti. Nessuna API key. Dalla cartella del progetto:

```bash
docker compose up --build
```

Apri **http://127.0.0.1:8080**. Le migrazioni terminano prima dell’API e del worker; soltanto il frontend/reverse proxy espone una porta, su loopback. Il volume `spesaradar_catalog` conserva SQLite e le capture private. L’avvio non precarica offerte: scegli Lidl e/o Eurospin e premi **Cerca offerte**. La prima raccolta può richiedere qualche minuto; i risultati vengono pubblicati per fonte dopo i controlli.

Per avvio in background: `docker compose up --build -d`. Per fermare: `docker compose down` (senza `-v`, che eliminerebbe il volume). Su questa macchina Docker aveva un credential helper bloccato: la variante locale documentata in [operations](docs/operations.md) usa una configurazione separata per le sole immagini pubbliche, senza modificare le credenziali personali.

## Uso

- Selezione multipla salvata nel browser, con schema versionato; nessuna città presunta.
- Catalogo comune, 18 categorie espandibili, ricerca per parole in AND, categorie multiple in OR, filtri per insegna, fedeltà e quantità minima rimovibili anche a pannello chiuso.
- **Disponibili oggi** e **In arrivo** separano validità corrente e futura. Un catalogo futuro non è un errore: durante la verifica Eurospin esponeva la campagna dal 10 al 20 settembre.
- Prezzi a confezione, kg, litro o pezzo, formato, calcolo unitario quando documentabile, condizioni visibili e dettaglio con fonte/ultima verifica. Ordinamento per prezzo solo sulla base esplicitamente scelta.
- **Buoni e vantaggi** indica la mancata copertura. I prezzi Lidl Plus verificati restano nella vista prodotti con badge.
- **Aggiorna offerte** riusa cache e job: cooldown minimo 30 minuti, aggiornamento dopo 12 ore. Cambiare filtro non effettua crawling. Il worker pianifica soltanto gli ambiti richiesti negli ultimi 7 giorni.
- Un errore è circoscritto alla fonte. I dati oltre 12 ore sono segnalati; oltre 48 ore o dopo scadenza non compaiono nel feed ordinario. Offline, l’app già aperta può mantenere risultati ancora entro soglia; non è una PWA con cache completa.

Nessuna foto viene riutilizzata senza licenza verificata. Le icone di categoria sono neutre e non rappresentano fotografie del prodotto. Le offerte pubblicate non attestano disponibilità a scaffale, cumulabilità o attivazione di buoni.

## Avvio nativo

Python 3.13, `uv`, Node.js 24 LTS e npm. Le dipendenze effettivamente provate sono fissate in `uv.lock`, `requirements.lock` e `apps/web/package-lock.json`. Le immagini Docker sono fissate per digest.

```bash
uv sync --frozen
uv run alembic upgrade head
npm --prefix apps/web ci
```

Avvia in tre terminali dalla radice:

```bash
PYTHONPATH=backend uv run uvicorn app.api:app --host 127.0.0.1 --port 8000
```

```bash
PYTHONPATH=backend uv run python -m app.jobs.worker
```

```bash
npm --prefix apps/web run dev
```

Apri http://127.0.0.1:8080. Il database nativo è `.private/spesaradar.db`, distinto dal volume Docker. `.env.example` documenta i parametri; Compose legge `.env`, per avvio nativo esportali nella shell. Non avviare due installazioni per aggirare i limiti delle fonti.

## Test

```bash
uv run pytest -q
uv run ruff check backend scripts
npm --prefix apps/web test
npm --prefix apps/web run build
cd apps/web
npx playwright install chromium
npm run test:e2e -- --grep-invert 'live:'
```

I test ordinari usano database temporanei e fixture sintetiche esplicite in `tests/fixtures` e nei test. Non accedono ai supermercati. I test browser richiedono l’app locale già avviata.

Smoke test live, **dopo aver raccolto entrambi i cataloghi**:

```bash
npm --prefix apps/web run test:e2e -- --grep 'live:'
uv run python scripts/benchmark.py
```

Lo smoke live usa il percorso utente e rispetta cache/cooldown; dipende dalla disponibilità reale delle campagne. Benchmark: 5.000 record sintetici in database temporaneo, mai nel catalogo live. Screenshot e risultati sono in `docs/`.

## Struttura e manutenzione

- `backend/app/adapters`: parser specifici, isolati dal database.
- `backend/app/domain`: modelli, prezzi Decimal, tempo e classificazione deterministica versionata.
- `backend/app/security/fetch.py`: HTTPS, robots, allowlist, DNS vincolato alla connessione, budget, retry e capture private.
- `backend/app/jobs`: coda SQLite, lease/heartbeat, pubblicazione atomica, scheduler.
- `backend/app/api.py`: API e filtri; schema OpenAPI generato su `/api/openapi.json`, senza asset Swagger da CDN.
- `apps/web`: React/TypeScript, Vite e Tailwind, stesso origin dell’API.
- `backend/migrations`, `config/sources`, `scripts`, `docs`: schema, manifest, backup e rapporti.

Per aggiungere un’insegna: verificare termini/robots e risorse ufficiali, definire ambito e manifest disabilitato, implementare parser con evidenze dei campi e stato di completezza, registrarlo nel worker, aggiungere fixture/test e campione live. Abilitare soltanto dopo verifica; mai accettare URL arbitrari dal browser. Per un futuro layout PDF/OCR aggiungere un adapter specifico: tali dipendenze non sono installate nel core HTML.

[Architettura](docs/architecture.md) · [Operazioni e backup](docs/operations.md) · [Verifiche e limiti](docs/verification.md)

La revisione dell’interfaccia con Build Web Apps, le schermate desktop/mobile e i controlli sono documentati nel [rapporto qualità UI](docs/ui-quality.md).
