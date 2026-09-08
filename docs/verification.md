# Rapporto di verifica — 8 settembre 2026

**Stato corrente: rilascio parziale, con tre connettori reali e versione GitHub Pages.** Le sezioni iniziali documentano il primo rilascio locale; pubblicazione e ampliamento sono riportati in fondo. I limiti storici su numero di insegne, sedi e pubblicazione vanno letti con questi aggiornamenti. Non è una dichiarazione di copertura nazionale completa.

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

## Pubblicazione remota — 8 settembre 2026

GitHub Pages attivato in HTTPS e workflow Actions riuscito: [esecuzione verificata](https://github.com/KilluaZoldich/spesaradar/actions/runs/34195536421). Entrambi i connettori hanno raccolto direttamente dal runner standard GitHub: Eurospin 218 prodotti, 2 richieste e 4,09 s; Lidl 232 prodotti, 28 richieste e 81,48 s. Esito `partial` per entrambe, secondo i limiti già documentati. Pubblicazione di **450 record reali**, senza database, capture o token. [Evidenza](pages-deployment.json).

**98 test backend**, **11 test frontend** e **3 percorsi browser Pages** passati; questi ultimi eseguiti sia su build statica locale priva di API, sia sull’URL HTTPS pubblico. [Output remoto](pages-browser-tests.txt), [report JSON](pages-e2e-results.json), [desktop](pages-desktop.png), [mobile](pages-mobile.png). IAB usato anche per verificare selezione doppia, filtro Carne nella build statica, filtro Dolci e controllo della pubblicazione sul sito remoto. Nessuna richiesta a `/api/` o ai supermercati dal browser nel percorso testato; nessun errore JavaScript. Axe senza violazioni automatiche nel catalogo remoto, layout 360 px senza overflow. Test specifici verificano scadenze, soglia 48 ore, condizioni sconosciute, confronto di basi, cursori e riuso della pubblicazione.

Il primo tentativo di workflow è stato rifiutato per un riferimento al contesto `runner` nell’ambiente del job; corretto con un percorso relativo isolato. Il successivo avvio ha completato raccolta, test, build e deploy. La modalità pubblica conserva il catalogo normalizzato come stato tra esecuzioni, non un worker sempre acceso: [architettura e limiti Pages](pages.md). L’accessibilità da GitHub è verificata per questa esecuzione, non garantita per ogni futuro cambio dei siti.

## Ampliamento e navigazione — 8 settembre 2026

Tre insegne: Lidl ed Eurospin nei rispettivi ambiti nazionali, **MD esclusivamente per Milano, via Rubens 8**. Nessuna sede scelta per conto dell’utente. MD è stato verificato dalla pagina ufficiale della sede fino al catalogo JSON, alle offerte persistenti e alle schede della build Pages. 307 righe osservate, 106 candidati, un duplicato coerente, **105 offerte distinte pubblicabili**; 201 righe escluse per ambito, base prezzo, periodo o condizioni non interpretabili. La verifica locale del nuovo connettore ha richiesto 7 richieste e 10,98 s, senza browser o OCR. Snapshot locale: 555 offerte complessive, incluse le future.

[Campione MD di 50 offerte](md-sample.json): tutti i 105 record pubblicati sono stati confrontati con i campi del JSON decodificato indipendentemente; il campione salvato copre pagine, categorie, carta e basi differenti. Controllo visivo separato della prima pagina grafica. **Non completato il gate di 50 drawer renderizzati verificati manualmente**. Le date MD non sono confermate dalla pipeline; condizioni parziali e limite di freschezza 48 ore rimangono visibili. I quattro altri candidati del nuovo ciclo non sono stati abilitati: [audit](source-audit.md).

| Verifica eseguita | Esito |
| --- | --- |
| `.venv/bin/pytest -q` | **125 passati** in 0,97 s; i due warning upstream già descritti |
| `.venv/bin/ruff check backend scripts` | Passato |
| `npm --prefix apps/web test` | **14 passati** in 3 file |
| Build statica `VITE_STATIC_CATALOG=true VITE_BASE_PATH=/spesaradar/ npm --prefix apps/web run build` | TypeScript e Vite riusciti |
| Ricostruzione Compose completa, con la variante Docker documentata sopra | Migrazioni exit 0, API/worker/web avviati, API healthy prima del web |
| `npm --prefix apps/web run test:e2e` contro Docker 8080 | **9 passati** in 8,3 s; [report](e2e-results.json) |
| `npm --prefix apps/web run test:pages` contro build statica 8082 | **4 passati**, compreso MD, carta e passaggio da zero offerte oggi alle future |

La prima esecuzione contemporanea delle due suite browser ha prodotto una collisione nella directory delle tracce, con errore ENOENT alla chiusura del contesto. Separato `outputDir` della suite Pages; rieseguita la suite locale completa con tutti e 9 i test passati. Non è stata nascosta una regressione applicativa.

Nuove regressioni: prezzo MD con carta distinto dal prezzo ordinario, peso variabile senza confezione inventata, peso sgocciolato senza confronto implicito, cambio sede bloccato, meccaniche non ammesse escluse; chiusura della risposta prima del controllo robots di un nuovo host per evitare il blocco del pool HTTP; classificatore versione 5; conteggi di periodo e disponibilità con scadenze, ricerca e filtri. Cache e coda esistenti restano operative.

### Esperienza e verifica visiva

Ricerca insegna/sede, conteggi oggi/in arrivo nella selezione, pulsante mobile sempre raggiungibile, filtri rapidi per supermercato, categorie senza risultati disponibili nell’espansione, passaggio diretto alle offerte future e stati fonte compatti. Indirizzo e requisito Buona Spesa Card compaiono sulle schede MD; nomi e ambiti non sono più limitati a due insegne nel frontend.

Browser integrato temporaneamente indisponibile perché il Mac era bloccato e lo sblocco automatico non riusciva. Nessun tentativo di aggirare il blocco. Usata la suite Playwright prevista dal brief contro l’app realmente avviata; screenshot aperti con `view_image` e confrontati col concept già adottato, senza nuova generazione di immagini.

| Controllo visivo | Esito / modifica intenzionale |
| --- | --- |
| Gerarchia e testo | Articolo/prezzo preservati; spazio corretto nel titolo mobile; istruzioni di pubblicazione spostate nel footer |
| Spazi e mobile | Intestazione compatta, ricerca e comandi touch; viewport 360×800 senza overflow della pagina |
| Navigazione | Tre insegne distinguibili, indirizzo MD esplicito, categorie con risultati prioritarie |
| Tipografia e colori | Manrope locale, verde petrolio e accento condizioni coerenti con il design precedente; nessuna imitazione dei marchi |
| Schede e accessibilità | Prezzo carta verificato e visibile, dettaglio/focus conservati; Axe senza violazioni automatiche nei percorsi verificati, non certificazione WCAG |

Evidenze: [selezione mobile](selection-expanded-mobile.png), [MD mobile](md-mobile.png), [scheda MD](md-offer.png), [desktop Pages](pages-desktop.png). Nessuna immagine del prodotto inventata o riutilizzata. Restano i limiti sulle condizioni non integralmente estraibili, sui social, sui buoni e sulla copertura descritti nell’audit.

### Esito pubblico dell’ampliamento

[Workflow 34200562089](https://github.com/KilluaZoldich/spesaradar/actions/runs/34200562089) riuscito sul commit `0e37350`. MD raccolto direttamente dal runner GitHub: **105 offerte, 7 richieste, 12,61 s**, stato `partial`. Lidl ed Eurospin hanno riusato la cache valida senza ulteriori crawl. Snapshot pubblico delle 09:41:35 Europe/Rome: **555 offerte** (232 Lidl, 218 Eurospin, 105 MD), comprese le promozioni future; nessuna capture privata pubblicata.

`PAGES_TEST_URL=https://killuazoldich.github.io/spesaradar/ npm --prefix apps/web run test:pages`: **4 passati in 5,3 s** sull’URL HTTPS, inclusi MD, carta, ricerca sede, preferenze, passaggio alle future, dettaglio, Axe e layout mobile. I 105 record MD pubblici corrispondono alla verifica locale per identità, prezzo, formato, condizioni, ambito, date, categoria e tag. [Evidenza di pubblicazione](expansion-deployment.json), [report browser remoto](pages-e2e-results.json). Eliminati anche i file grezzi dello scouting e le capture della verifica MD isolata; la retention ordinaria del worker locale rimane invariata.
