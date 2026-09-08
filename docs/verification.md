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

## Carpi e profilo PDF riutilizzabile — 8 settembre 2026

Ambiente: Mac Apple Silicon, Python 3.13, Node 24, Docker Linux ARM64. Stesse immagini base fissate per digest del rilascio precedente. Nuova dipendenza diretta pdfplumber 0.11.10 e dipendenze transitive bloccate con uv; nessun aggiornamento indiscriminato dei pacchetti precedenti. Nessun browser/OCR/LLM nella nuova raccolta.

- `uv add pdfplumber`, `uv export --frozen --no-dev --no-emit-project -o requirements.lock`: installazione e lock riusciti; Docker installa con `--require-hashes`.
- `ruff check backend` e `ruff format backend`: superati dopo formattazione delle fixture nuove.
- `.venv/bin/pytest -q`: **150 passed**, 1,25 s. Due avvisi di deprecazione già presenti nel client di test Starlette/httpx/AnyIO; non aggirati aggiornando dipendenze estranee.
- `npm --prefix apps/web test`: **14 passed**. Build React/TypeScript ordinaria e statica riuscite.
- `docker compose build`, `docker compose up -d` e riavvio del reverse proxy dopo la ricreazione API: immagini costruite, migrazioni riuscite e servizi avviati. Il comando Docker su questa macchina usa la configurazione separata per immagini pubbliche descritta in operations.
- `POST /api/v1/refreshes` per le tre sedi Conad: job distinti, completati con esito `partial`. **100 offerte per sede**, ciascuna con 130 riquadri esaminati, 30 esclusi, 4 richieste HTTP, nessun errore risorsa. Durate **15,52 / 15,55 / 15,84 secondi**. [Contatori e campione](conad-sample.json).
- `npm --prefix apps/web run test:e2e`: **9 passed**, 9,1 s, inclusi flussi deterministici e catalogo locale persistente.
- `python -m app.source_tools scaffold-conad ...`: generato manifest candidato disabilitato in `.private`; nessun crawling o pubblicazione. `replay-conad ...` sulla campagna futura: rapporto diagnostico riuscito, 51 accettati. Lo stesso profilo serve le altre due sedi senza modifiche di codice.

Il campione Conad è visivo: confrontate 50 schede con sette pagine renderizzate dei due PDF ufficiali, comprese varianti, formato, prezzo, carta e periodo. Applicabilità verificata dai collegamenti delle tre pagine sede. Nessun errore critico noto finale nel campione; non è una garanzia per layout futuri. Le 100 promozioni comuni alle tre sedi non vengono conteggiate come 300 promozioni diverse nella misura di copertura. In UI le offerte mantengono l’indirizzo della selezione.

Correzioni emerse nella verifica: esclusione dei cataloghi colazione/premi dalla scelta delle due campagne principali; gestione delle date verticali; requisito carta sconosciuto se il badge non è presente; confronto unitario fra basi compatibili; categorie per omogeneizzati, affettati di pollame, pizza con salame e kebab vegetale. Test contro l’associazione al prezzo vicino, parte intera mancante, quantità/peso ambigui, cache di una sede usata per un’altra e robots UTF-8 con BOM.

Limiti ancora espliciti: Coop Carpi e Interspar Carpi non acquisiti per accessi/formati non completati; niente scraping social; copertura PDF Conad selettiva; deadline PDF cooperativa fra pagine. Le immagini dei volantini non sono distribuite. [Audit](source-audit.md), [procedura di estensione](source-onboarding.md).

Revisione separata del codice: corretti i tre rilievi su percorso POST non necessario (rimosso), legame fra nome PDF e URL prima/dopo i redirect, e pagine con periodi misti (escluse). Test di regressione aggiunti. Replay ripetuto dopo le correzioni: invariati 49 prodotti attuali e 51 futuri, circa 5,64 / 4,35 secondi.

Prova statica locale con `VITE_BASE_PATH=/spesaradar/ vite preview --host 127.0.0.1 --port 8082`: 4 percorsi browser passati, inclusi CAP precompilato, tre sedi Carpi, prezzo/carta/fonte PDF, date future, zero overflow a 360 px e zero violazioni axe. Un primo tentativo usava directory/base errate per il server di anteprima; corretto l’avvio e ripetuta la prova. Screenshot: `carpi-selection-mobile.png`, `conad-mobile.png`.

Pubblicazione remota verificata: [run 34205334236](https://github.com/KilluaZoldich/spesaradar/actions/runs/34205334236), commit codice `8a5dbce`, concluso con successo. I tre job Conad sul runner Ubuntu hanno raccolto 100 offerte per sede, 4 richieste ciascuno, in **29,28 / 27,35 / 27,52 secondi**. Lo snapshot delle 08:37:19 UTC contiene 855 record per ambito (555 precedenti + 3 × 100 Conad); sono 100 promozioni Conad comuni alle tre sedi, non 300 promozioni uniche. Le altre fonti hanno riusato gli orari di verifica esistenti. [Metadati remoti](carpi-deployment.json).

`PAGES_TEST_URL=https://killuazoldich.github.io/spesaradar/ npm --prefix apps/web run test:pages`: **5 passed**, 7,4 s sul sito pubblico, inclusi MD e il nuovo percorso Carpi. Il link `?cap=41012` precompila solo la ricerca delle sedi, senza selezionare automaticamente negozi. Le capture grezze dello scouting sono state eliminate (circa 39 MB); rimangono metadati e campione fattuale. Le capture private del worker locale seguono la retention ordinaria di 7 giorni/500 MB.

## Sei insegne, selezione semplificata e replay locale — 8 settembre 2026

Verifica sullo stesso Mac ARM64, Python 3.13 e Node 24, senza nuove dipendenze. Aggiunti due connettori reali: Interspar Carpi via HTML ufficiale e Famila Carpi tramite il PDF mensile Selex collegato dalla pagina sede. La selezione presenta una voce per insegna; Conad richiede la scelta di una sola sede e migra le vecchie preferenze senza aggiungere negozi casuali. Filtri per insegna integrati nell'intestazione del catalogo, schede più compatte e condizioni economiche ancora visibili.

| Comando / controllo | Esito |
| --- | --- |
| `PYTHONPATH=backend .venv/bin/pytest backend/tests -q` | 182 passati in 1,39 s; due warning upstream già documentati |
| `.venv/bin/ruff check backend/app backend/tests` | Passato |
| `npm --prefix apps/web test` | 22 passati |
| Build statica React/TypeScript/Vite | Passata; snapshot di anteprima con 1160 record per ambito |
| `npm --prefix apps/web run test:pages` su anteprima 8082 | 6 passati, inclusi Famila, Interspar, sostituzione sede Conad, ricerca CAP e dettaglio |
| Replay Famila sulla capture PDF già acquisita | 130 accettati su 176 celle riconosciute, 46 isolati; circa 2,15 s senza rete |
| Replay Despar sulla prima pagina HTML già acquisita | 9 accettati su 12 riquadri, circa 0,025 s senza rete |

Il replay è diagnostico: non pubblica dati e non aggiorna la loro freschezza. Il profilo PDF Selex riusa il riconoscimento geometrico della griglia e verifica il prezzo al kg/l con aritmetica Decimal. Il percorso HTML usa il normale modulo pubblico di selezione sede; il POST è limitato all'endpoint dichiarato nel manifest, con controlli robots, destinazione, redirect, budget e nessun retry del POST.

Raccolta Interspar: 25 richieste in 72,9 s, 20 pagine delle 77 indicate dalla fonte, 175 record ammessi e 65 isolati su 240 riquadri. Campione di 50 record confrontato con nome, prezzo/base, formato, periodo e sede nei riquadri ufficiali. Raccolta Famila: PDF mensile di 18 pagine, 130 record ammessi; campione visuale di 59 record sulle pagine 2, 4, 5, 6 e 7. Nessun errore economico critico noto nei campioni finali. Copertura totale Famila non misurabile: le 176 celle riconosciute non sono il totale certificato delle offerte del volantino. Sottocosto, sponsor e layout non supportati sono esclusi. Entrambe le fonti restano `partial`.

Le 1160 righe dell'anteprima sono record per ambito, non 1160 promozioni uniche: comprendono le 100 promozioni Conad replicate nei tre contesti sede. La nuova selezione di una sola sede evita questa ripetizione nel feed. I timestamp di verifica delle capture locali sono preservati nell'anteprima, senza aggiornarli durante il replay. HTML, PDF, cookie e immagini delle fonti restano privati.

Revisione separata del codice: corretti filtro CAP nelle opzioni sede, prezzo unitario con valore/base non validi, e aggiunti test del ciclo completo dei due collector. Verificate paginazione parziale, cambio sede/campagna, redirect, rifiuto di meccaniche economiche ambigue e isolamento dei lotti. Classificatore deterministico versione 6, con regressioni per alimenti per animali, piatti pronti, cioccolato al latte e altre categorie.

Sigma Carpi resta non acquisito: il percorso del localizzatore osservato richiede una destinazione vietata da robots; nessun invio eseguito a quella destinazione. Coop Carpi resta non acquisito dopo il 403 del servizio catalogo già documentato. Lo scouting di alternative ufficiali non ha verificato un volantino corrente indipendente per questi due casi. Il rilascio resta parziale e non dichiara queste insegne come funzionanti. Dettagli e limiti di riuso in [source-audit.md](source-audit.md).

Ricostruzione finale `docker compose up --build -d` riuscita: migrazioni exit 0, API healthy, worker e web avviati su loopback. `npm --prefix apps/web run test:e2e`: **9 passati in 8,7 s** sulla build finale. Il primo controllo dopo lo spostamento dei filtri usava ancora il selettore CSS della vecchia riga duplicata; aggiornato il test alla regione accessibile «Filtra per supermercato» e ripetuta tutta la suite. Nessun errore console o overflow nei percorsi verificati; controlli Axe superati, senza implicare una certificazione completa di accessibilità.

### Pubblicazione pubblica verificata

[Run 34213224269](https://github.com/KilluaZoldich/spesaradar/actions/runs/34213224269) riuscito sul commit `8b1dc6f`. Il runner Ubuntu ha raccolto **175 offerte Interspar** in 74,22 s con 25 richieste e **130 offerte Famila** in 12,62 s con 4 richieste. Le altre fonti hanno riusato la cache. Lo snapshot pubblico delle 10:03:18 UTC contiene 1160 record per ambito e sei insegne: Lidl, Eurospin, MD, Conad, Despar/Interspar, Famila. MD resta la sede Milano verificata in precedenza, non viene presentato come negozio di Carpi.

Confronto di tutti i 305 nuovi record pubblicati con quelli verificati localmente: stessi ID, titolo, prezzo/base, formato, condizioni, date, categoria, tag, fonte e ambito; zero record mancanti o differenze nei campi confrontati. Questo controllo confronta le due estrazioni; la verifica contro le fonti è il campione manuale descritto sopra.

`PAGES_TEST_URL=https://killuazoldich.github.io/spesaradar/ npm --prefix apps/web run test:pages`: **6 passati in 9,1 s** sul sito pubblico HTTPS, inclusi i nuovi supermercati, il cambio sede Conad, ricerca CAP 41012, persistenza delle selezioni, categorie, prezzi, dettaglio PDF, controlli Axe e assenza di overflow a 360 px. Screenshot pubblici aggiornati e aperti per ispezione visiva: [Interspar mobile](despar-mobile.png), [selezione per insegna](selection-one-brand-mobile.png). [Metadati e confronto](six-retailer-deployment.json), [report browser](pages-e2e-results.json).

## Buono Coop e percorso Sigma indipendente — 8 settembre 2026

Ambiente e dipendenze invariati. La ricerca Sigma ha individuato l'API REST pubblica dichiarata dal sito e metadati di volantini recenti; il filtro Realco arriva però a giugno 2026 e la ricerca sedi Carpi restituisce una lista vuota. Nessun prezzo dedotto da questi risultati. Le pagine Coop prodotti restano prive di un catalogo HTML estraibile; il dettaglio pubblico del buono cartoleria contiene invece condizioni complete, verificate manualmente per tutto il perimetro del profilo (**un buono**).

Il modello `VoucherBenefit` separa importo del beneficio, minimi di spesa e finestre di ottenimento/utilizzo. `price=null` per il buono, con validatore che impedisce di convertirlo in prodotto. Pubblicazione atomica, filtro temporale/freschezza e snapshot Pages riusano la pipeline esistente. Non servono modifiche alle tabelle SQLite: i payload JSON mantengono compatibilità con i prodotti precedenti. Il buono non incrementa i conteggi prodotti e non entra nell'ordinamento per prezzo. Il frontend distingue i negozi con soli buoni e apre direttamente la vista pertinente quando è selezionato solo Coop.

| Verifica | Esito |
| --- | --- |
| `PYTHONPATH=backend .venv/bin/pytest backend/tests -q --tb=short` | **193 passati**, 1,55 s; due warning upstream già documentati |
| `.venv/bin/ruff check backend/app backend/tests` | Passato |
| `npm --prefix apps/web test` | **25 passati**, inclusi separazione prodotti/buoni e fase di solo utilizzo |
| Build statica e build Compose | Riuscite; API healthy e migrazioni exit 0 |
| `python -m app.pages --restore ... --collect --export ...` su DB isolato | **Un buono Coop**, 3 richieste, 6,59 s; 1160 record prodotti precedenti preservati |
| `npm --prefix apps/web run test:pages` su anteprima 8082 | **7 passati**, 8,7 s, compresa nuova scheda Coop |
| `npm --prefix apps/web run test:e2e` su Docker 8080 | **9 passati**, 8,7 s |

Il confronto manuale comprende beneficio 10 €, soglia ottenimento 30 € in cartoleria, soglia utilizzo 30 €, massimo tre buoni/30 €, esclusioni, non cumulabilità, opzioni cartacea/digitale e date. L'anno del termine 7 ottobre è interpretato nel contesto della stessa campagna con anno 2026 esplicito, non preso dal download; inizio utilizzo sconosciuto. Le condizioni sono protette anche da hash del corpo normalizzato verificato: qualsiasi modifica richiede nuovo audit e parser aggiornato. Nessuna promessa di coprire futuri buoni automaticamente.

Revisione separata: nessun rilievo Critical/Required residuo; controllo della capture reale, 27 test backend mirati e 12 frontend mirati passati. Screenshot [buono Coop mobile](coop-voucher-mobile.png) aperto e ispezionato: beneficio, due finestre e minimi leggibili, nessun prezzo prodotto falso. Test browser controlla anche esclusioni, link ufficiale, reload, apertura automatica della vista buoni, ritorno dalla vista prodotti, Axe e assenza di overflow a 360 px. Corretto il test storico che cercava Coop fra le insegne totalmente non disponibili; adesso verifica l'etichetta «solo buoni».

Restano **sei insegne con prodotti**, più Coop per un solo buono. Catalogo prodotti Coop e Sigma Carpi ancora non completati. L'obiettivo complessivo non viene dichiarato concluso.


### Coop: limite del runner e conservazione della verifica originale

Il [run 34215716567](https://github.com/KilluaZoldich/spesaradar/actions/runs/34215716567) ha pubblicato correttamente il codice `9c9818e`, ma il primo accesso Coop dal runner GitHub è stato rifiutato con HTTP 403 (una richiesta, circa 0,23 s). Lo snapshot conteneva quindi 1160 prodotti e nessun buono. La prima suite sul sito pubblico ha prodotto **6 passati e 1 fallito**, proprio perché il buono non era presente. Questo esito non viene interpretato come supporto remoto del connettore.

Il buono acquisito nativamente prima del blocco viene conservato come cache già verificata: `site/reviewed-cache.json` contiene soltanto il record pubblico con verifica originale **2026-09-08T10:24:37.335767Z**. Il ripristino eccezionale ammette un solo record protetto da SHA-256 dell'intero payload canonico; non consente di cambiare identità, importi, condizioni o timestamp senza un nuovo audit nel codice. Non modifica stato bloccato, ultimo tentativo, ultimo successo, fallimenti o cooldown del runner. Non esegue richieste remote, non sovrascrive record esistenti/ritirati o scansioni riuscite più recenti, e nasconde il dato dopo le originarie 48 ore. Non è una soluzione alla raccolta automatica Coop da GitHub.

Verifica del ripristino su database isolato dallo snapshot remoto bloccato: **1160 prodotti + 1 buono**, stato Coop ancora `blocked`, `last_success=null`, timestamp del buono invariato. Suite backend finale **199 passati** (1,46 s), Ruff passato; anteprima Pages con questo stato **7 passati** (8,8 s). Revisione indipendente: corretto il primo importatore troppo generico, nessun rilievo Critical/Required residuo dopo vincolo sull'hash e test di mutazione; nove test del modulo Pages passati. Screenshot Coop aperto e ispezionato con avviso di accesso non consentito visibile sopra il buono.
