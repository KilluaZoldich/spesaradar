# Aggiungere sedi e connettori

Il worker e il replay usano lo stesso punto d’ingresso in `app.adapters.registry`. Il manifest seleziona una **famiglia di parser** tramite `connector`: più negozi dello stesso formato riusano acquisizione, normalizzazione, controlli e pubblicazione. Non è uno scraper universale e non usa LLM.

## Percorso rapido verificato: Conad CNO Emilia

Il profilo `conad_pdf` risolve i volantini dalla pagina ufficiale della sede, controllando `data-store-id`, e seleziona i PDF principali `????????PCONADEMILIA.pdf`. Il collegamento non si ricava da un URL inventato: viene letto da `data-flyers`. Cataloghi premi, colazione, altri formati, online e periodi secondari restano fuori. Due campagne al massimo per job.

Per una **sede ufficiale già esaminata**, creare una configurazione inizialmente disabilitata:

```bash
PYTHONPATH=backend uv run python -m app.source_tools scaffold-conad \
  --store-id 000386 \
  --url 'https://www.conad.it/ricerca-negozi/conad-via-roosevelt-ang-vramazzini-72-41012-carpi--000386' \
  --label 'Carpi (MO) · 41012 · Via Roosevelt angolo Via Ramazzini 72' \
  --output .private/nuova-sede.json
```

Il comando non fa richieste, non abilita la fonte e non sovrascrive file esistenti. Le tre sedi Carpi consegnate hanno configurazioni distinte e lo stesso codice del parser; non occorrono modifiche a worker, API o React per un’altra sede ammessa della medesima famiglia.

Acquisire HTML della sede e PDF soltanto dopo audit, con il client protetto della pipeline e i limiti del manifest. Per iterare sul parser **senza scaricare di nuovo i volantini**, usare i file privati già acquisiti:

```bash
PYTHONPATH=backend uv run python -m app.source_tools replay-conad \
  --manifest config/sources/conad-carpi.json \
  --store-html .private/sede.html \
  --pdf .private/volantino.pdf \
  --campaign-id cno-20262619pconademilia \
  --output .private/rapporto-replay.json
```

Il rapporto include prezzo, quantità, condizioni, periodo, pagina, bounding box, accettati, esclusi e durata. È una **diagnostica offline**, senza timestamp di nuova verifica né scrittura nel catalogo. La campagna deve ancora risultare collegata alla sede e non scaduta; non usare il replay come importatore di prezzi.

Controllare un campione contro la resa visiva, misurare anche omissioni, aggiungere fixture sintetiche dichiarate e test, aggiornare audit/versione. Solo dopo i gate impostare `audit_status: partial` oppure `verified_supported` ed `enabled: true`. La validazione rifiuta una fonte candidata abilitata. La prima acquisizione ordinaria passa da `POST /refreshes`, coda durevole e pubblicazione atomica.

## Layout PDF e limitazioni

Il profilo identifica **rettangoli realmente disegnati nel PDF**, dimensioni pagina e font osservati. Interi e decimali vengono riuniti solo all’interno dello stesso riquadro, con contiguità geometrica. Prezzi di altri articoli, barrati e percentuali non diventano prezzo principale. Date stampate della pagina devono concordare con la campagna; le date verticali sono lette dai caratteri ruotati. Formato ambiguo, peso sgocciolato/netto misto, prezzo unitario incompatibile, meccanica complessa e struttura sconosciuta vengono esclusi.

Non riusare questi criteri per Despar o Coop senza un nuovo profilo e verifica del layout. I nuovi formati aggiungono un adapter e fixture; la raccolta HTTP, cache, coda e modello offerte restano condivisi. I connettori HTML continuano a non usare OCR o browser. Il solo percorso PDF usa pdfplumber, bloccato nei lockfile.

Limiti: 30 MB per PDF, 60 pagine, 20.000 caratteri per pagina, controllo della deadline tra le pagine, massimo due documenti predefinito. La deadline non interrompe in mezzo a una singola chiamata del parser: è un limite cooperativo, non un sandbox contro qualsiasi PDF ostile. Sono ammessi esclusivamente documenti dei manifest ufficiali. Rilascio locale; nessun caricamento PDF pubblico.

La rapidità misurata riguarda il replay: circa 4–6 secondi sui due PDF Conad esaminati, senza rete; non una promessa di integrare qualunque insegna in pochi minuti. Interspar Carpi usa ora il profilo HTML separato e Famila il PDF Selex (vedi architecture). Coop ha un profilo HTML per un singolo buono pubblico, mentre il catalogo prodotti resta non acquisito. Il parser del buono richiede anche l’hash delle condizioni normalizzate verificate: una modifica richiede nuova verifica e versione, non un aggiornamento automatico delle condizioni sconosciute.
