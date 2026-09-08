# Audit fonti — 8 settembre 2026

Primo scouting limitato a cinque insegne; il secondo ciclo richiesto dall’utente è documentato in fondo. Nessun aggregatore. Il primo rilascio era su loopback; la successiva pubblicazione Pages è documentata in `pages.md`. Robots è un vincolo di crawling, non una licenza. Foto e loghi esclusi; nessuna licenza generale di riuso commerciale verificata. Soli dati fattuali minimi e prove private con retention.

| Insegna | Risultato iniziale | Perimetro esaminato |
|---|---|---|
| ALDI | blocked_access | Homepage locale: HTTP 403, nessun retry con identità alternativa. Robots e condizioni leggibili via ricerca, non prova di accessibilità dalla pipeline. |
| Lidl | partial, connettore live verificato | Homepage, campagne Carne e Pesce e Lidl Plus, informazioni legali. HTML con `data-grid-data`, prezzo e formato, date UTC, metadati regionali. |
| Conad | candidate, non abilitato | Homepage, `/ricerca-negozi`, `/prodotti-e-marchi/bassi-e-fissi`: catalogo promozionale dipendente dalla sede; nessun prezzo nazionale verificato. |
| Eurospin | partial, connettore live verificato | `/promozioni/`: HTML semantico, periodo esplicito 10–20 settembre 2026, prezzo per scheda, formato e marca. |
| PENNY | candidate, non abilitato | Homepage, robots, `/note-legali`; shell dinamica, nessuna estrazione prezzo verificata. |

## URL e accesso

- ALDI: https://www.aldi.it/ ; https://www.aldi.it/robots.txt ; https://www.aldi.it/servizi-aldi/servizio-clienti/condizioni-duso . Condizioni identificano ALDI s.r.l.; robots esclude `/tools` e query di ricerca. Blocco locale rispettato.
- Lidl: https://www.lidl.it/ ; https://www.lidl.it/robots.txt ; https://www.lidl.it/c/informazioni-legali/s10018358 ; https://www.lidl.it/c/carne-e-pesce-kw-36-26/a10101811 ; https://www.lidl.it/c/lidl-plus-kw-36-26/a10101812 . Gestore e responsabile promozioni dichiarato Lidl Italia S.r.l. Robots non esclude `/c/` e `/p/`. Non trovata licenza per immagini/redistribuzione. Accesso limitato al catalogo pubblico, senza login. Valori regionali diversi non diventano prezzi nazionali. L’inizio è il più recente fra `storeStartDate` e la data pubblicizzata nel link della campagna. La fine usa l’estremo commerciale del prezzo regionale, limitato da `storeEndDate` quando presente. Il solo inizio del prodotto può precedere la promozione di mesi; non viene utilizzato isolatamente. L’anno del link senza anno viene correlato al periodo prezzo con anno esplicito, con limite di coerenza di 31 giorni.
- Conad: https://www.conad.it/ ; https://www.conad.it/robots.txt ; https://www.conad.it/ricerca-negozi ; https://www.conad.it/prodotti-e-marchi/bassi-e-fissi . Footer identifica CONAD Società Cooperativa. Robots esclude `/excel-volantini.xlsx`, non visitato. Non scelto alcun negozio casuale. Sedi, PDF e canali online non verificati.
- Eurospin: https://www.eurospin.it/ ; https://www.eurospin.it/robots.txt ; https://www.eurospin.it/promozioni/ ; https://www.eurospin.it/termini-di-utilizzo/ . Footer e termini identificano Eurospin Italia S.p.A. Robots esclude `/wp-admin`; termini consentono memorizzazione per uso personale, vietano distribuzione senza consenso. Solo consultazione privata locale; foto escluse. Catalogo nazionale del sito, adesione di singoli negozi non verificata. Le date per scheda sono correlate al periodo con anno dichiarato della pagina, non all'anno del download.
- PENNY: https://www.penny.it/ ; https://www.penny.it/robots.txt ; https://www.penny.it/note-legali . Robots recuperato direttamente HTTP 200 (il browser di ricerca non lo apriva). Note identificano Penny Market Srl; consentita memorizzazione personale, marchi e ripubblicazione soggetti a consenso. Nessun connettore promesso.

## Social

Homepage ufficiali collegano Facebook/Instagram Lidl Italia e Conad. Nessuna raccolta social abilitata: `permission_required`. https://www.facebook.com/legal/automated_data_collection_terms rimanda al login durante la verifica; nessuna autorizzazione alla raccolta acquisita. Nessun accesso a commenti, follower, profili o account. Canali WhatsApp sono collegamenti, non fonti acquisite. Core indipendente dai social.

## Limiti operativi iniziali

HTTP seriale per host, 3 secondi fra richieste, massimo 60 risorse e 180 secondi/job; solo HTTPS su host esatti dei manifest. Blocco su 403, robots o CAPTCHA; 429 sospende secondo Retry-After. Nessun browser remoto, OCR, LLM o API commerciale. Capture private non servite via HTTP, 7 giorni/500 MB. Risultati finali, campione e omissioni sono nel rapporto di verifica.


## Copertura effettiva verificata

Lidl parser 4 e classificatore 4: 27 pagine campagna individuate dai link della homepage, 28 richieste complessive compreso robots. Otto risorse campagna non producono un lotto verificabile (struttura/periodo/base prezzo o canale non sufficienti); sono fallimenti parziali, non cataloghi vuoti. Nel perimetro parseabile: 315 nodi articolo, 264 candidati validi, 51 isolati, 32 duplicati coerenti, 232 promozioni distinte. Al momento della verifica: 133 correnti e 99 future. Copertura totale del sito **non misurabile**: non viene dichiarato un denominatore di tutti gli articoli Lidl, sedi, online o PDF. I prezzi Plus visibili sono conservati con requisito fedeltà; attivazione e condizioni generali rimangono da verificare.

Eurospin parser 3 e classificatore 4: una pagina promozioni, 221 schede nel DOM della risorsa esaminata, 218 prodotti riconosciuti, 3 esclusi per prezzo non interpretabile. Riconoscimento del perimetro HTML: 218/221 (98,6%); non è una misura dell’intero assortimento, dei volantini locali o della disponibilità a scaffale. Tutti i prodotti della campagna esaminata sono futuri al giorno 8 settembre: dal 10 al 20 settembre 2026 inclusi.

I manifest restano `partial`, pur avendo estrazione live funzionante, perché alcune schede/risorse e condizioni non sono verificabili. Nessun candidato non testato è abilitato. Nessun ambito di sede, regionale o online viene presentato come coperto. [Elenco risorse e hash](source-resources.json), [campione di 50 per insegna](live-sample.json), [rapporto](verification.md).

Correzioni derivate dalle prove: `store=false` non esclude una promozione fisica futura se il badge ufficiale indica IN_STORE; fullTitle uguale alla sola marca utilizza il titolo prodotto distinto della medesima risorsa; pasta lavamani non è pasta alimentare, crauti al vino non sono bevande, pet food e burger vegetali hanno precedenza sui termini carne. Gli articoli realmente ambigui restano in Altri.

## Ampliamento richiesto — 8 settembre 2026, 09:30 Europe/Rome

Il nuovo incarico di ampliare la copertura ha aperto un secondo ciclo, **limitato a cinque nuove insegne**: MD, iN’s, Carrefour, DPiù e Todis. Non è stata proseguita una ricerca senza limite e nessun aggregatore è una fonte dati. Dei nuovi candidati, soltanto MD supera il gate di estrazione in questo ciclo.

| Insegna | Stato dopo verifica | Risultato e perimetro |
|---|---|---|
| MD | `partial`, abilitato | Sede ufficiale Milano, via Rubens 8 (ID 151); 105 offerte distinte utilizzabili, con limitazioni. Nessuna generalizzazione ad altre sedi. |
| iN’s | `unsupported_format` | HTML di selezione sedi e volantino grafico FlowPaper; nessun parser prezzo verificato. |
| Carrefour | `permission_required` | Prezzi strutturati accessibili; CGU vietano riproduzione anche parziale dei contenuti. Non abilitato per la pubblicazione. |
| DPiù | `candidate` | Homepage ufficiale accessibile; catena TLS del catalogo online non validata dal client. Verifica TLS mantenuta attiva. Nessun connettore abilitato. |
| Todis | `candidate` | Homepage e collegamenti ai volantini per sede; prezzi di articoli prenotabili non equiparati a promozioni alimentari nazionali. Nessun connettore abilitato. |

### MD: catena di provenienza, ambito e gate

- https://www.mdspa.it/volantino/ e https://www.mdspa.it/robots.txt . Identità nel footer: MD S.p.A., partita IVA 03185210618. Esaminati footer, collegamento all’informativa privacy e informazioni del catalogo; nessuna licenza immagini o autorizzazione generale al riuso dichiarata. Sono pubblicati soltanto dati fattuali minimi, senza fotografie, loghi o testi editoriali.
- https://www.mdspa.it/punti-vendita/Lombardia/MI-Milano/151-Milano/ . Il JavaScript ufficiale `wp-content/themes/MD-Theme/assets/js/get_pv.js` usa la risposta pubblica di `POST /punti_vendita_admin/get_pv.php`, campo `pv=151`. La risposta conferma **MILANO, VIA RUBENS 8**, ID 151, codice 300949. Questa chiamata è servita solo allo scouting; il connettore non dipende da POST, cookie o geocoding.
- https://www.mdspa.it/sfogliatore/?id_pv=151 riporta la sede in `#go_back` e `data-flyer-code=nord_atm_nogas`. Il connettore controlla ogni volta la corrispondenza con l’indirizzo verificato. Se cambia o scompare, fallisce prima di associare prezzi alla sede sbagliata.
- Il medesimo documento carica https://volantino.mdspa.it/js/loader.js, che costruisce https://service-volantino.mdspa.it/nord_atm_nogas . Il redirect porta a https://volantino.mdspa.it/m_nord_atm_nogas.html . Questa relazione è verificata nel codice del sito ufficiale: non dedotta dal nome host. Sono ammessi esattamente i tre host nel manifest. Robots del servizio rimanda a `/robots.txt.html` sul dominio del catalogo; 404 trattato secondo la policy di robots. Nessuna destinazione privata o bypass di TLS/accesso.
- Sede Roma Bufalotta, ID 676: i collegamenti rinvenuti non producono una sede identificabile nello sfogliatore (`() -`, codice catalogo assente). **Non aggiunta**. Non sono state assunte la città dell’utente o la validità nazionale dei prezzi MD.
- `var data = [...]` contiene **307 righe** con `idProduct`, `idVolantino`, pagina, nome, categoria, `um`, peso, prezzi e flag economici. Il parser legge JSON, senza eseguire JavaScript. Non estrae i prezzi di esempio del template del drawer.
- Normalmente il prezzo è `priceOff`. Con `cardMD=true`, il prezzo visualizzato sotto “Solo con Buona Spesa Card” è **`prezzoPartenzaSIF`**, popolato nello span `#discountPercSIF_Card_MD`: il nome del campo non viene interpretato come percentuale. Badge carta sempre visibile. `contribute` conserva l’eventuale spesa minima.
- Sono ammesse solo basi esplicite `um=PZ` o `KG`. In quest’ultimo caso il peso di riferimento non diventa una confezione. I prodotti webstore, le meccaniche complesse, le basi mancanti e i periodi specifici non verificati sono esclusi. Il peso non è dichiarato netto o sgocciolato se la fonte non lo specifica; descrizioni con “sgocciolato” non producono calcoli unitari.
- **106 candidati, 1 duplicato concorde, 105 pubblicati, 201 esclusi**. Il 34,2% delle 307 righe nel perimetro esaminato arriva a offerte distinte; comprende esclusioni intenzionali di canali diversi. Non è una percentuale di copertura dell’insegna o dell’intero volantino alimentare. Copertura totale non misurabile.
- La prima pagina grafica della campagna 3530 è stata ispezionata privatamente: riporta 8–20 settembre 2026 e prezzi concordi con il JSON. La pipeline non legge automaticamente le date impresse nell’immagine: **validità non confermata per gli articoli MD**, con soglia massima di freschezza 48 ore e nessuna data inventata. Non è stato introdotto OCR per la sola data.
- Raccolta verificata localmente: 7 richieste, 10,99 secondi, zero browser/OCR/LLM. Sample e metodo in [md-sample.json](md-sample.json): confronto indipendente di tutti i 105 record pubblicati con i campi JSON della capture; campione stratificato di 50. Non equivale a cinquanta drawer controllati manualmente.

### Altre nuove fonti: risorse effettivamente esaminate

- iN’s: https://www.insmercato.it/ , https://www.insmercato.it/volantino/ , https://www.insmercato.it/legal/ , https://www.insmercato.it/robots.txt . Footer iN’s Mercato S.p.A. Il sito collega `insmercato-cdn.it` e il proprio JavaScript compone i percorsi dei volantini. Esaminati `/insmercato/volantino/19/aosdio/A`, `docs/section_1.bin` e il catalogo speciale `speciali/catalogo-bts/`. La sezione decompressa contiene sfondi grafici e SVG, senza testo prodotto/prezzo utilizzabile. Il PDF ha superato il limite HTML predefinito di 10 MB durante lo scouting; download interrotto, nessuna dichiarazione di supporto PDF/OCR.
- Carrefour: https://www.carrefour.it/promozioni/offerte-sottocosto/ , https://www.carrefour.it/robots.txt , https://www.carrefour.it/condizioni-generali.html . CGU di GS S.p.A.; riproduzione dei contenuti vietata. Il percorso ha metadati “Spesa Online”; non sarebbe comunque un catalogo locale implicito. Nessuna acquisizione periodica o pubblicazione.
- DPiù: https://www.d-piu.com/ , https://www.d-piu.com/robots.txt , https://online.d-piu.com/robots.txt . Relazione col catalogo online verificata dal link “PRENOTA&RITIRA”; accesso al secondo dominio non validato per errore di catena certificati, senza disattivare controlli. Non esaminati singoli prodotti o tutte le condizioni del servizio.
- Todis: https://www.todis.it/ e https://www.todis.it/robots.txt . Homepage collega volantini per Baia Domizia/Sessa Aurunca e articoli prenotabili; questi ultimi comprendono mobili ed elettronica. Nessuna generalizzazione a un feed alimentare nazionale; sedi, prezzi promozionali alimentari e condizioni non verificati fino al record finale.

Lo stato dei social rimane invariato. Le capture aggiuntive di sviluppo e della verifica isolata sono state eliminate alla chiusura; rimangono metadati minimi. Le capture dell’installazione locale ordinaria seguono la retention del worker.

La successiva esecuzione GitHub Actions ha confermato il medesimo risultato MD: 105 offerte, 7 richieste, 12,61 secondi, esito parziale. [Verifica remota](expansion-deployment.json). Questo conferma l’accessibilità al momento della prova, senza estendere la copertura ad altre sedi.

## Terzo ciclo — Carpi, CAP 41012 (8 settembre 2026)

Richiesto dall’utente: Conad, Coop e SPAR/Despar. Il CAP è stato fornito esplicitamente; nessuna sede scelta a caso. Questo aggiornamento supera lo stato iniziale di Conad nella tabella storica sopra.

### Conad — `partial`, tre sedi abilitate

Pagine ufficiali, tutte recuperate e controllate:

- https://www.conad.it/ricerca-negozi/conad-via-carlo-marx-99-41012-carpi--000350
- https://www.conad.it/ricerca-negozi/conad-via-roosevelt-ang-vramazzini-72-41012-carpi--000386
- https://www.conad.it/ricerca-negozi/conad-via-mar-ionio-14-41012-carpi--010088

Identità CONAD Società Cooperativa nel footer; intestazione e `data-store-id` confermano indirizzo e sede. `data-flyers` collega in tutte e tre le sedi i PDF principali CNO Emilia: `20262618PCONADEMILIA.pdf` (27 agosto–9 settembre 2026) e `20262619PCONADEMILIA.pdf` (10–23 settembre 2026), sotto `https://www.conad.it/assets/common/volantini/cno/v20262/`. I parametri hash effettivi vengono letti dal sito, non costruiti. Nessun dominio terzo necessario.

Robots verificato dal client per ogni host: le pagine sede e i PDF risultano ammessi; `/excel-volantini.xlsx` resta escluso e non acquisito. Footer e pagina non mostrano una licenza generale di redistribuzione. Si mantengono dati fattuali minimi, fonti e prove private; nessuna fotografia, logo o volantino integrale pubblicato. Questa verifica tecnica non certifica diritti commerciali.

I volantini esaminati dichiarano `hasDisaggregated=false`, senza catalogo prodotti JSON. Il nuovo percorso **PDF testuale, senza OCR** usa pdfplumber 0.11.10 (MIT). Guardie su dimensioni/font/riquadri e confronto formato/prezzo unitario; prezzi precedenti non pubblicati. Date commerciali sono correlate ai millisecondi del JSON e confermate dalla data stampata sulla pagina. Sconto aggiuntivo Club Famiglia conservato come condizione testuale: non sottratto automaticamente dal prezzo esposto. Assenza di badge carta = requisito sconosciuto.

**49 offerte attuali + 51 future**, per ciascuna delle tre sedi che linkano gli stessi PDF. Sono **100 promozioni**, non 300 promozioni diverse: le sedi hanno identità e applicabilità separate. Dei 130 riquadri riconosciuti nelle pagine con periodo confermato, 100 superano i controlli e 30 sono esclusi. Non sono inclusi copertine, riquadri di altri formati, prezzi al peso variabile, pagine senza periodo concordante o campagne secondarie. Copertura dell’intero volantino non misurata.

Campione visivo: 50 prodotti, 28 dalla campagna attuale (pagine 2, 4, 16, 18) e 22 dalla futura (3, 5, 10). Confrontati identità/variante, prezzo, formato, badge carta, periodo e collegamento alle sedi. Nessun errore critico noto nel campione finale. Nelle sette pagine campionate si contano 75 aree promozionali visibili, di cui 50 pubblicate; le altre 25 includono riquadri non supportati, prezzi senza formato univoco e una promozione senza importo articolo. Questi conteggi non descrivono altre campagne o insegne. Metadati in `conad-sample.json`.

### Coop Alleanza 3.0 — `blocked_access`, nessun prezzo pubblicato

- https://www.coopalleanza3-0.it/ e `/fare-spesa/elenco-negozi.html`.
- Pagine sede `/fare-spesa/elenco-negozi/dettaglio-negozio/3967-ipercoop-il-borgogioioso.html` (Via dell’Industria 31) e `/4899-carpi-via-carlo-sigonio.html` (Via Carlo Sigonio 15).
- Il JavaScript ufficiale della mappa usa `POST /storeLocatorServlet/?operation=getStores`, pubblico e senza credenziali: verificato il catalogo sedi, filtrato a Carpi. Nessun crawl nazionale delle sedi.
- La pagina prodotti Crescendo della sede Sigonio contiene una shell JavaScript, con `data-pdv_id=9530`. Il sito dichiara il servizio `https://svdgt.coopalleanza3-0.it/apim/leaflets/9530`; acquisizione protetta interrotta con **403**, senza cambio identità, endpoint alternativi o token privati. L’esito riguarda il percorso di acquisizione comprensivo di robots, non dimostra che il prodotto sia assente.
- La sede Don Albertario compare nel catalogo ufficiale ma il suo volantino non è stato approfondito. Unicoop Firenze è stata esaminata e ha offerte HTML, ma appartiene a una cooperativa/area diversa: non presentata come copertura Coop Carpi.

### Despar / Interspar — `blocked_access`, nessun prezzo pubblicato

- https://www.despar.it/it/punto-vendita-interspar/819/carpi/ : Interspar, Tangenziale Bruno Losi, angolo Via Nuova Ponente, 41012 Carpi; identità Aspiag Service nel sito ufficiale. JSON-LD GroceryStore/SaleEvent conferma sede e campagna 27 agosto–10 settembre.
- La sede collega `https://volantino.despar.it/leaflet-interspar/2026-os78-118-2026-is-carpi/`, lettore iPaper. Dominio ammesso nello scouting per il collegamento osservato, non per somiglianza del nome.
- Selezione del negozio verificata usando il normale modulo pubblico della sede e il suo token effimero, in sessione isolata. Nessun login. `/it/offerte-per-te/` conferma Carpi, ma mostra collegamenti editoriali ai volantini.
- Il lettore contiene 34 pagine e testi di ricerca. L’ordine testuale separa nomi e prezzi e non permette associazioni affidabili: non usato come feed prodotto. La negoziazione HTTP `Accept-Encoding: identity` risolve un errore di compressione, mantenendo TLS e User-Agent identificabile. Robots con BOM viene interpretato correttamente.
- Il servizio script `cdn.ipaper.io`, collegato dal lettore, restituisce 403 al percorso protetto di acquisizione. Nessuna elusione; non vengono inventati URL di download PDF. La seconda sede citata nel volantino non è automaticamente abilitata.

Fonti social: nessuna nuova integrazione. I collegamenti ufficiali a Coop/Interspar in UI sono dichiarazioni di copertura e verifica della sede; **non contano come cataloghi funzionanti**.

Verifica dal runner GitHub successiva al push: anche le tre sedi Conad completano la raccolta con 100 offerte ciascuna, 4 richieste e circa 27–29 secondi. Nessun proxy, browser o OCR. Stato parziale invariato. [Evidenza del deploy](carpi-deployment.json).

## 8 settembre 2026 — Carpi: Despar HTML e mensile Famila

La nuova verifica riguarda **quattro insegne**, senza ampliare lo scouting a catena: Despar/Interspar, Famila, Sigma e il percorso alternativo Coop. Nessun bypass dei precedenti blocchi. I risultati di ricerche web non sono usati come prezzi live.

### Despar / Interspar Carpi — `partial`, abilitato

- Origine ufficiale: [pagina Interspar Carpi](https://www.despar.it/it/punto-vendita-interspar/819/carpi/), Tangenziale Bruno Losi, angolo via Nuova Ponente, CAP 41012. Il sito permette una normale selezione del negozio tramite il proprio modulo pubblico, senza account. Il modulo osservato è `/store/stores/setStore/punto-vendita-interspar-819-carpi/819`.
- Dopo la selezione, la pagina ufficiale collega `/it/volantino-digitale/819/`: questa restituisce HTML con schede prodotto, prezzi e periodo **27 agosto–10 settembre 2026**. Ogni pagina conferma la sede selezionata. Le successive pagine provengono esclusivamente dal link `rel=next` osservato, senza URL arbitrari del visitatore.
- Metodo: HTTP protetto, cookie jar isolata per ambito, Beautiful Soup. Il POST è limitato all'endpoint del manifest, rispetta robots, budget, intervallo e TLS; nessun reinvio POST a un redirect. Nessun iPaper, CDN bloccato, browser, OCR o servizio esterno a pagamento.
- Robots è stato acquisito e controllato per pagina sede, modulo e catalogo. Il controllo non è interpretato come licenza di riutilizzo. Si pubblicano soltanto fatti minimi ed evidenze; immagini, SVG promozionali, pagine originali e cookie restano esclusi dal sito pubblico. Capture private con retention già esistente.
- Prova live: **20 pagine, 240 schede visibili, 175 ammesse, 65 escluse**, 25 richieste complessive in **72,9 s**. Il sito indica **77 pagine**; le restanti 57 non sono acquisite in questo profilo. Nessuna copertura completa dichiarata.
- Esclusioni: prezzi solo percentuali, extra app, offerte esclusive, multiprezzo e meccaniche 2+1. Il prezzo equivalente condizionato non viene scambiato con il prezzo di una confezione. Quantità netta/sgocciolata non confermata: nessun prezzo unitario calcolato; quello al kg esplicitamente esposto resta disponibile. Requisiti ulteriori sconosciuti rimangono `null`.
- Campione di 50 record distribuito sulle 20 pagine confrontato con titolo, formato e prezzo/base nella scheda HTML; periodo e sede verificati nella relativa pagina. Due dettagli ufficiali (mozzarelle e alici 2+1) confrontati anche con le schede: mozzarella ammessa, meccanica 2+1 esclusa. Nessun errore economico critico noto nel campione ammesso. Reparti freschi: applicabilità subordinata alla presenza del reparto, indicata tra i limiti.

### Famila Carpi — `partial`, abilitato

- Origine ufficiale: [pagina Famila Carpi](https://www.famila.it/famila-nord/punti-vendita/emilia-romagna/famila-carpi). L'oggetto `__NEXT_DATA__.props.pageProps.store` identifica **Via Giovanni XXIII, 185, Carpi**; è il dato di sede adottato. Un elenco territoriale riportava un civico differente: non è stato sostituito al dettaglio del negozio.
- La pagina contiene `store.flyers`, con titolo, date e link PDF. `promo.smt.cloud` è ammesso soltanto perché collegato esplicitamente da questa pagina ufficiale. Il profilo acquisisce il **mensile FAMILA SELEX SETTEMBRE**, validità pubblicata **3–30 settembre 2026**, PDF nativo di 18 pagine, 4,29 MB. Il sottocosto (24 pagine) e lo sponsor sono **esclusi**: nel sottocosto esistono periodi diversi (3–12 e fino al 16 settembre) e limiti per pezzi; non si eredita indiscriminatamente la data generale.
- Percorso alternativo esaminato: `promo.famila.it` espone i metadati del servizio `famila.maxidi.it`. L'endpoint promozioni ha risposto 403; una risposta prodotti osservata era vuota e non costituisce copertura valida. Nessun connettore per tale API è abilitato. Il PDF è una risorsa indipendente già collegata alla pagina ufficiale, non un aggiramento dell'API.
- Metodo PDF: profilo **Selex 29×32**, dimensioni della pagina, linee verticali dei riquadri, font del titolo/prezzo/prezzo unitario. Rimozione dei caratteri sovrastampati duplicati. Prezzo, formato e unità devono concordare con aritmetica Decimal; tolleranza assoluta 0,011 €/unità per l'arrotondamento del prezzo unitario stampato. Altri layout, unità non confrontabili, prezzi ambigui o condizioni complesse restano esclusi. Non è uno scraper PDF universale.
- **176 celle riconosciute, 130 ammesse, 46 escluse**. Copertina, righe a due colonne e parti fuori profilo non sono conteggiate come riconosciute. Copertura totale del mensile non misurata; gli altri volantini non sono coperti.
- Verifica visiva delle pagine 2, 4, 5, 6 e 7: **59 record ammessi** confrontati con PDF renderizzato, prezzo, titolo, formato e €/kg/l. Nessun errore economico critico noto nel campione; nessun badge fedeltà nelle celle ispezionate, ma requisiti complessivi non integralmente verificati: stato `unknown`, mai “senza carta” per deduzione. La validità proviene dalla pagina sede, non dalla data tecnica di creazione del PDF.
- Robots controllato per sito e risorsa PDF. Nessun riuso di immagini o pubblicazione della capture/volantino nell'app; il link porta al PDF ufficiale. L'accessibilità tecnica non è presentata come una licenza generale di riuso del materiale editoriale.

### Sigma e Coop — limiti rimasti

- Sigma: esaminati `https://www.supersigma.com/`, `/punti-vendita/`, l'iframe ufficiale `/wp-content/themes/montale-wp/store-locator/`, il relativo bundle JS e il JSON delle province. Il cercanegozi usa `/wp-admin/admin-ajax.php`, **escluso da robots.txt**: il client ha fermato la richiesta prima del POST. Nessuna chiave Maps viene copiata o usata dal prodotto. La ricerca di altre risorse ufficiali ha trovato volantini storici del 2025, non un catalogo corrente verificato per Carpi. Stato `blocked_access`, nessun prezzo live.
- Coop: resta valido l'audit delle sedi Carpi e del servizio rifiutato. La nuova ricerca di PDF ufficiali ha trovato campagne passate, senza un nuovo collegamento verificato alla campagna corrente di Carpi. Nessun URL inventato, nessun accesso alternativo al servizio bloccato. Non è conteggiata fra le insegne supportate.
