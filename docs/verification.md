# Rapporto di verifica — 8 settembre 2026

**Stato: rilascio locale parziale, con percorso centrale funzionante e due insegne live.** Non è una dichiarazione di copertura nazionale completa o idoneità alla pubblicazione. Nessun commit, push o deploy esterno effettuato.

## Ambiente

Nuova cartella `/Users/metin/Projects/spesaradar`, inizialmente vuota. macOS 26.2, Apple M2 Pro arm64, 16 GiB RAM. Python 3.13.12 con uv; primo sviluppo Node 23.7.0, build riproducibile Docker Node 24, Python 3.13-slim e Nginx stable-alpine con digest fissati. Docker Engine 24.0.7, Compose 2.23.3; Playwright 1.63.0 e relativo Chromium installato. Dipendenze effettive nei lockfile. Nessuna dipendenza LLM, browser remoto o API di scraping commerciale.

## Comandi e risultati

| Verifica | Comando / evidenza | Esito |
|---|---|---|
| Migrazione da vuoto | `uv run alembic upgrade head`; ripetuta anche in fixture temporanee e init Compose | Schema 0001, esecuzione idempotente |
| Backend | `uv run pytest -q` | 95 test passati; [output](backend-tests.txt) |
| Lint Python | `uv run ruff check backend scripts` | Passato |
| Componenti frontend | `npm --prefix apps/web test` | 3 test passati |
| Build frontend | `npm --prefix apps/web run build` | TypeScript e Vite passati |
| Docker completo | `docker --config .private/docker-public --host unix:///Users/metin/.docker/run/docker.sock compose up --build -d` | Immagini costruite; migrate exit 0; web, API e worker sani |
| Primo avvio reale | Nuovo volume `spesaradar_catalog`, lettura iniziale catalogo con totale 0; apertura browser e selezioni salvate | Due job reali accodati, nessun seed sintetico |
| Raccolta Docker | Log worker 07:36–07:38 Europe/Rome | Eurospin 3,62 s / 2 richieste; Lidl 81,38 s / 28 richieste; entrambi parziali |
| Backup/ripristino | `compose exec -T api python scripts/backup.py /data/spesaradar.db /data/backup-verified.db` | Backup API SQLite; ripristino temporaneo e integrity_check passati; copia esportata privatamente |
| Benchmark | `uv run python scripts/benchmark.py` | p95 **134,30 ms**, mediana 103,87 ms; [misura](benchmark.json) |

Il comando Docker standard è implementato nel Compose. Su questa macchina il credential helper personale si bloccava sul download di immagini pubbliche: usata configurazione separata senza credenziali, senza alterare il profilo personale. Dettagli e variante esatta in [operations](operations.md). Non è stato simulato il build.

Il benchmark usa 5.000 offerte **sintetiche**, una fonte, SQLite temporaneo WAL, pagine da 24, 10 warm-up e 100 richieste misurate, concorrenza 1, FastAPI TestClient in processo incluso JSON. Non misura una rete Internet, un crawl o 100 utenti simultanei. Il database live non è stato modificato dal benchmark.

## Test pertinenti

Normalizzazione italiana dei prezzi, Unicode, migliaia, multipack e Decimal; basi kg/l indipendenti; prezzi mancanti/ambigui mai zero; identità stabile e formati distinti; classificazione delle ambiguità richieste; tag solo da evidenza. Date inclusive, ora legale/solare, validità futura, scaduta e freschezza.

Integrazione: dodici refresh concorrenti producono un solo job attivo; recovery con lease/token impedisce al worker precedente di pubblicare; riavvio logico idempotente; pubblicazione atomica; job parziale conserva gli assenti e condizioni note; due scansioni complete distanziate per ritiro; conflitto economico non sceglie il minimo; facets multiselezione; cursori vincolati a filtri/revisione; GET senza crawl; scheduler non prolunga l’attività utente; Host/Origin e input controllati.

Rete simulata offline: redirect fuori allowlist e indirizzi privati IPv4/IPv6, DNS con connessione vincolata all’IP, 401/403, 429 e Retry-After, 5xx e numero massimo di retry, 304 con capture, robots, risposte troppo grandi e decompression bomb. Layout 200 rotto genera errore strutturale. La simulazione di crash è deterministica sul lease; non è una prova di perdita di alimentazione del disco.

Due warning upstream nei test: deprecazione di HTTPX nel TestClient Starlette e alias AnyIO BlockingPortal. Non impediscono i test; non nascosti. Nessun warning è presentato come errore della pipeline live.

## Fonti e campione

Scouting fermato a **5 candidati**: ALDI bloccato HTTP 403, Conad e PENNY non abilitati, Lidl ed Eurospin estratti tramite HTTP pubblico ufficiale. Nessun punto vendita inventato, canale online o catalogo di una sede arbitraria attribuito all’utente. [Audit](source-audit.md) e [risorse esaminate](source-resources.json).

Lidl: 232 promozioni distinte dopo deduplicazione nel perimetro esaminato, 133 correnti e 99 future alle ore di verifica. 315 nodi articolo nel perimetro parseabile, 264 candidati validi, 51 esclusi e 32 duplicati; 8 risorse campagna non verificabili. **Copertura totale non misurabile**, perché pagine non interpretabili, altri canali e sedi non costituiscono un denominatore verificato.

Eurospin: 221 schede HTML osservate, 218 normalizzate, 3 escluse per prezzo ambiguo. 218/221 = 98,6% nel solo perimetro della pagina `/promozioni/`, non accuratezza universale. Campagna futura dal 10 al 20 settembre 2026, correttamente separata dalla vista oggi.

[Campione salvato](live-sample.json): 50 record per insegna, distribuiti nell’ordinamento per categoria/condizioni/titolo. Confrontati campi della capture originale e payload: titolo, importo, formato, evidenza temporale e fedeltà rilevata. Il controllo automatico dei campi implementati ha 100 corrispondenze su 100; **non equivale a accuratezza 100% né a verifica integrale delle condizioni**. Prezzo e identità del campione sono stati riesaminati anche leggendo i valori originali; le correzioni trovate sono state testate e rielaborate sulle capture, preservando il timestamp originario.

Correzioni rilevanti: vecchio inizio prodotto Lidl sostituito dall’intersezione con campagna effettiva; futuro fisico non escluso da `store=false`; titolo ridotto alla marca recuperato dall’altro campo ufficiale; regole per pet food, latte detergente, uovo di cioccolato, burger vegetale, aceto di vino, focaccia con salumi, pasta lavamani e crauti al vino. Ambiguità residuali rimangono in Altri, senza inventare categoria o tag.

**Gate manuale residuo:** non è stato completato un confronto visuale indipendente di 50 schede renderizzate per insegna con tutte le condizioni/pagine dettaglio. Il campione documenta la corrispondenza ai dati della risorsa, non certifica che ogni condizione eventualmente presente altrove sia stata acquisita. La UI marca tali condizioni come non verificate e i manifest restano `partial`. Foto non usate; riuso commerciale non verificato. Social `permission_required`.

## Limiti residui del rilascio

- Nessuna integrazione reale di buoni generici; vista ed endpoint dichiarano la copertura assente. Solo prezzi prodotto Lidl Plus verificabili, con requisito visibile. Nessun coupon personale o attivazione.
- Nessuna selezione di sede fisica: due ambiti nazionali con adesione del negozio non verificata. ALDI, Conad e PENNY restano non selezionabili.
- Condizioni economiche non completamente disponibili in tutti i contesti: `unknown/partial`, mai “senza carta” per default; meccaniche riconosciute come non interpretabili escluse.
- Nessuna copertura PDF/OCR/social, PWA, lista spesa o servizio multiutente pubblico. Sono estensioni escluse o non bloccanti, non funzioni dichiarate presenti.
- I limiti di rete sono budget più timeout, non un wall-clock rigido garantito. Nessun benchmark multi-host o filesystem di rete; servizio esclusivamente loopback.

Le fonti possono cambiare dopo questa verifica. Un parser fallito non produce un catalogo vuoto riuscito e non aggiorna la verifica delle offerte precedenti. La consegna è utilizzabile localmente, con questi limiti espliciti.

## Browser e accessibilità — verifica iniziale

`npm --prefix apps/web run test:e2e`: **7 percorsi passati** in 5,6 secondi contro l’app Docker realmente avviata. [Output](browser-tests.txt), [report JSON](e2e-results.json), [catalogo live desktop](catalog-live.png), [catalogo live mobile](mobile-live.png), [viewport mobile con fixture](mobile-fixture.png). La fixture è confinata alle risposte intercettate dal test e non viene salvata nel catalogo.

Percorsi: selezione doppia; Carne e Dolci senza nuovo crawl; ricerca pollo con alimento gatti etichettato Animali; carta/quantità sulla scheda; cache prima del completamento; errore circoscritto; cambio selezione con risposta tardiva scartata; reload delle preferenze; dettaglio tastiera/Escape; viewport 360 px senza overflow; cataloghi live con periodo futuro e fonte; scadenza oltre 48 h dopo resume anche offline. Il refresh ripetuto è coperto anche dai test di deduplicazione/cooldown del backend.

Axe 4.13 ha verificato selezione, catalogo e dettaglio senza violazioni automatiche dopo correzione di ruolo ARIA del placeholder e gerarchia dei titoli. Comprende controlli automatici di contrasto; non equivale a certificazione WCAG o a test completo con screen reader. Nessun errore JavaScript `pageerror` nel percorso live. Screenshot prodotti dal browser dell’app funzionante, non mockup statici.

## Persistenza e consegna

Riavvio reale di API, worker e web con `compose restart api worker web`: catalogo prima/dopo di **450 offerte**, ID del primo risultato e momento di verifica invariati. [Evidenza](restart.json). Il volume sopravvive anche alle ricostruzioni delle immagini; l’init migrazioni è idempotente. Backup nel container e ripristino temporaneo verificati, esportato soltanto il database coerente. Nessuna capture grezza esposta dal web; eliminati i file temporanei della prova verticale e dello scouting, conservate le sole capture runtime con retention.

Smoke sull’immagine finale: health, ready e schema OpenAPI HTTP 200; refresh multinegozio HTTP 202 con riuso cooldown per entrambi; 450 record reali disponibili nella vista attuali+future. [Esito](final-smoke.json). API, worker e web risultano healthy, sola porta pubblicata `127.0.0.1:8080`.

## Revisione qualità UI — 8 settembre 2026

Interfaccia migliorata con Build Web Apps, senza cambiamenti ai connettori o ai dati. **4 test frontend e 9 percorsi browser passati**, inclusi due nuovi test di regressione; build locale e Docker riuscite. IAB verificato a 1280, 1504, 768 e 360 px, con confronto diretto concept/screenshot e controllo del dettaglio. [Rapporto completo](ui-quality.md), [output browser aggiornato](ui-browser-tests.txt). Restano invariati i limiti di copertura e il gate manuale delle fonti indicati sopra.
