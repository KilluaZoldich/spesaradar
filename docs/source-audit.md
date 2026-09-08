# Audit fonti — 8 settembre 2026

Scouting limitato a cinque insegne, nessun aggregatore. Uso personale su loopback. Robots è un vincolo di crawling, non una licenza. Foto e loghi esclusi; nessuna autorizzazione alla pubblicazione o al riuso commerciale è stata verificata. Soli dati fattuali minimi e prove private con retention.

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
