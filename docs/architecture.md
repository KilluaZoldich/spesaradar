# Architettura

## Percorso dei dati

Browser → API FastAPI → SQLite WAL. Il solo `POST /api/v1/refreshes` accoda lavoro. Un worker persistente separato acquisisce job dal database, recupera le risorse ufficiali, salva capture private, estrae candidati tipizzati, normalizza prezzi/date, classifica con regole e pubblica un lotto atomico per fonte. L’interfaccia legge immediatamente la cache e segue i job con polling.

React 19, TypeScript, Vite e Tailwind compongono l’interfaccia; Nginx serve file statici e proxy API sullo stesso origin. Python 3.13, SQLAlchemy 2 e Alembic gestiscono persistenza e schema. HTTPX/Beautiful Soup bastano per i due adapter attuali: Playwright è una dipendenza di test frontend, non dello scraping. Nessun Redis, servizio cloud, OCR, modello generativo o account esterno.

## Modello compatto

`offers` contiene l’identità stabile della promozione e un payload canonico validato: identità ufficiale quando disponibile, insegna, ambito/campagna, titolo originale/normalizzato, formato, prezzo, condizioni tri-state, validità, evidenze e versioni. Prodotti uguali con formati diversi restano distinti; il prezzo mutabile non forma l’ID. Non viene costruito un anagrafico universale degli SKU fra insegne.

`SourceRow` mantiene revisione, salute, attività, tentativo e successo distinti; `jobs` conserva stage, lease, token di fencing, heartbeat, tentativi e contatori; `refreshes` aggrega riferimenti condivisi; `captures` conserva metadati/hash e percorsi privati. Retailer, target e coverage nazionale sono proiezioni dei manifest verificati, senza una tabella artificiale di sedi.

Prezzi pubblicizzati in centesimi interi. Quantità e prezzi unitari in stringhe Decimal; arrotondamento `ROUND_HALF_UP` a quattro decimali per il calcolo unitario. Il frontend formatta per la visualizzazione, non calcola nuovi benefici economici. Il testo di formato ambiguo resta disponibile, ma non genera una quantità normalizzata. Peso sgocciolato/range non vengono convertiti automaticamente.

Condizioni sconosciute restano `null`. Nessuna inferenza di prezzo pieno, carta assente, quantità minima assente, cumulabilità o disponibilità. Non sono acquisiti buoni generici: l’endpoint e la vista lo dichiarano. Non sono implementati calcoli di carrelli 3×2 o vantaggi futuri; meccaniche economiche che l’adapter non sa interpretare vengono escluse dal lotto pubblicabile.

## Coda e riconciliazione

Transazione `BEGIN IMMEDIATE` per accodare/acquisire/pubblicare, indice unico parziale su un job `queued/running` per fonte. Nessun lock di scrittura durante rete o parsing. Un token diverso ad ogni acquisizione impedisce a un worker precedente di pubblicare dopo recovery. Lease 120 s, heartbeat 30 s, massimo 3 acquisizioni dello stesso job. Elaborazione seriale: limite effettivo 1 richiesta alla volta, inferiore al massimo consentito di 2.

Un lotto parziale può aggiungere e aggiornare, non rimuovere gli assenti. Due lotti completi della stessa campagna, distanziati almeno 30 minuti, possono ritirare una promozione mancante. Riduzioni anomale nella stessa campagna rendono il lotto parziale. Conflitti economici a parità d’identità sono isolati. Le condizioni precedentemente note sopravvivono a un’estrazione successiva meno informativa.

Scheduler ogni minuto: ambiti richiesti negli ultimi 7 giorni, dopo 12 ore più jitter; non rinnova l’attività utente. Fallimenti ripetuti e blocchi sospendono la fonte. Il limite pubblico di refresh non aggira cooldown e deduplicazione.

## Tempo e catalogo

UTC per gli istanti, Europe/Rome per giorni commerciali. Fine inclusiva trasformata nella mezzanotte locale successiva, corretta attraverso DST. Validità commerciale, freschezza e salute sono indipendenti. Soft TTL 12 h, esclusione 48 h, scadenza esplicita immediata. Nessun fallimento aggiorna il momento di verifica.

Query/facets/pagina/revisione condividono una lettura SQLite. Filtri di tipo diverso AND, categorie OR, query per token AND con prefisso minimo 3 caratteri. Conteggi senza filtro categoria, ma con tutti gli altri. Il cursore incorpora filtri/revisione e scade anche al cambio di minuto per rivalutare i confini temporali. In caso di revisione cambiata il client riparte da pagina 1. A 5.000 righe il filtro Python dopo selezione degli ambiti rientra nel benchmark; nessuna infrastruttura aggiunta preventivamente.

## Confini di sicurezza

Il browser non propone URL. HTTPS su domini esatti dei manifest, senza credenziali o porte alternative; ogni redirect è verificato. La risoluzione DNS rifiuta qualsiasi IP non pubblico e passa un IP letterale verificato al backend di connessione: la seconda risoluzione indipendente non avviene. TLS conserva il nome originale per SNI e certificato. Nessun proxy ambientale o verifica TLS disattivata.

Robots controllato prima delle pagine, intervallo minimo 3 s, timeout e budget limitati. Corpo compresso e decompresso limitato a 10 MB; durante lo stream si controlla anche la deadline. Una lettura di rete già bloccata può terminare al relativo timeout: 180 s è il budget, non una garanzia rigida di wall-clock. 401/403/CAPTCHA fermano l’accesso, 429 applica Retry-After, soltanto errori transitori hanno fino a 3 tentativi.

Niente HTML sorgente renderizzato, proxy immagini o capture eseguibili. React esegue escaping; link esterni `noopener noreferrer`. Host e Origin ammessi, CSP su Nginx, nessuna porta esterna per API/worker. Il servizio è destinato a un solo host privato, non a esposizione Internet o filesystem di rete. Una futura distribuzione richiede un progetto distinto per accesso/autenticazione, HTTPS, riuso dei dati, PostgreSQL e coda adatta al multi-host.

## Riferimenti primari verificati

[FastAPI Background Tasks](https://fastapi.tiangolo.com/tutorial/background-tasks/), [SQLite WAL](https://www.sqlite.org/wal.html), [HTTPX transports](https://www.python-httpx.org/advanced/transports/), [httpcore network backends](https://www.encode.io/httpcore/network-backends/), [Vite](https://vite.dev/guide/), [Playwright](https://playwright.dev/docs/intro), [OWASP SSRF](https://cheatsheetseries.owasp.org/cheatsheets/Server_Side_Request_Forgery_Prevention_Cheat_Sheet.html), [RFC 9309](https://www.rfc-editor.org/info/rfc9309/). Versioni effettive nei lockfile; le API httpcore usate sono state provate dal fetch live e dai test offline.

### Aggiunta rapida di profili di estrazione

La raccolta comune chiama un adapter tramite il campo `connector` del manifest. Una nuova sede che condivide un formato verificato riusa trasporto, normalizzazione, classificazione, staging, pubblicazione e UI. Despar aggiunge un resolver di sessione/sede e HTML; Famila aggiunge un resolver dei metadati della sede e il profilo geometrico `extraction/selex_grid.py`. I parser non scrivono nel database. L'abilitazione resta separata dalla sola raggiungibilità del dominio.

Il replay offline evita di ripetere il crawl ad ogni correzione:

```bash
PYTHONPATH=backend .venv/bin/python -m app.replay \
  --manifest config/sources/despar-carpi.json \
  --capture /percorso/privato/pagina-catalogo.html --output /tmp/esito-despar.json
PYTHONPATH=backend .venv/bin/python -m app.replay \
  --manifest config/sources/famila-carpi.json \
  --store-html /percorso/privato/sede.html \
  --capture /percorso/privato/mensile.pdf --output /tmp/esito-famila.json
```

Il rapporto contiene record accettati, prezzi, condizioni, evidenze e contatori; non effettua rete e non pubblica. Il file di output non viene sovrascritto. Per Conad rimane `app.source_tools replay-conad`. Prima di abilitare una nuova sede occorrono comunque verifica del collegamento ufficiale, scope, accesso e campione reale.
