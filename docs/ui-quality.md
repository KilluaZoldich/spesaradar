# Qualità dell’interfaccia — 8 settembre 2026

La revisione implementa le skill Frontend App Builder, Frontend Testing & Debugging e React Best Practices del plugin Build Web Apps. Il sito funzionante è su http://127.0.0.1:8080. Nessuna pubblicazione esterna. Il rilascio dati resta **parziale**, secondo source-audit.md: cataloghi nazionali Lidl ed Eurospin, adesione locale e condizioni non sempre verificabili.

## Cambiamenti effettivi

- Griglia desktop a tre colonne, due su tablet, una sui telefoni stretti. Prezzi a 36 px, titoli delle schede a 19 px; testo del dettaglio a 14 px. Titoli originali completi, base del prezzo, condizioni, validità e fonte preservati.
- Manrope Variable 5.3.0 incluso localmente: un solo WOFF2 latino da 24,83 kB, licenza OFL distribuita in `apps/web/public/manrope-LICENSE.txt`. Nessuna richiesta a Google Fonts o altro servizio font durante l’uso.
- Diciotto categorie con icone decorative, scorrimento dedicato ed espansione completa. Carne e Dolci fra le categorie iniziali. Conteggi e selezioni multiple conservati.
- Filtri economici/insegna visibili anche a pannello chiuso e rimovibili singolarmente. Badge numerico sul pulsante Filtri. Nessun nuovo crawl al cambio filtro.
- Stato fonte compatto con orario e dettaglio espandibile. Gli errori persistenti restano esposti. Eliminato l’avviso generico di cache ripetuto a ogni apertura.
- Quando cambia la query del catalogo, uno skeleton sostituisce i risultati precedenti fino alla risposta corretta. I refresh della stessa query mantengono la cache visibile; cancellazione e controllo delle risposte tardive restano attivi.
- Link per saltare al contenuto, etichette accessibili con separazione fra categoria e conteggio, dettaglio centrato con focus e scorrimento interno. Rimosso il doppione della marca solo quando è già all’inizio del titolo. Tag documentati vicino al formato.

## Ambiente e comandi

macOS arm64, Node host v23.7.0; build riproducibile nell’immagine Node 24 già fissata per digest. React/Vite e dipendenze preesistenti conservate. Browser integrato IAB per verifica interattiva, screenshot e misure DOM; suite Playwright Chromium preesistente per regressioni automatizzate richieste dal brief, non come sostituto della verifica IAB.

| Comando | Esito |
| --- | --- |
| `npm --prefix apps/web test` | 4 test passati, compresa selezione multipla/espansione categorie |
| `npm --prefix apps/web run build` | TypeScript e Vite riusciti; anche build Docker Node 24 riuscita |
| `npm --prefix apps/web run test:e2e` | 9 percorsi passati in 8,7 s sull’interfaccia finale; [output](ui-browser-tests.txt), [JSON](e2e-results.json) |
| `docker --config .private/docker-public --host unix:///Users/metin/.docker/run/docker.sock compose up --build --no-deps -d web` | Ricostruzione riuscita; API e worker conservati attivi |
| `docker --config .private/docker-public --host unix:///Users/metin/.docker/run/docker.sock compose ps` | API, worker e web healthy; unica porta host 127.0.0.1:8080 |

I test comprendono selezione doppia, ricerca, categorie, condizioni visibili, dettaglio/Escape, ripristino preferenze, errore di una fonte, cache, risposte tardive, scadenza dopo resume, viewport 360 px, filtri rimovibili e caricamento di una categoria senza mostrare risultati della precedente. Axe non rileva violazioni automatiche su selezione, catalogo e dettaglio; non è una certificazione WCAG. Nessun errore JavaScript nel percorso live; log IAB error/warn vuoti. Backend non modificato in questa revisione: i suoi test sono documentati nella verifica iniziale.

## Verifica visiva e confronto con il concept

Riferimento generato esclusivamente per il design, non incluso nel prodotto:
`/Users/metin/.codex/generated_images/01a07f59-490b-7500-b199-be86c235b2aa/exec-0bce47f5-281a-453b-9910-2aef4cb86fc2.png`.

Concept e screenshot finale sono stati entrambi aperti con `view_image` nella verifica conclusiva. L’implementazione è stata confrontata direttamente con la riferimento progettuale adottato, senza richiedere ulteriori conferme per le modifiche locali autorizzate. Verificati IAB 1280×720, dimensione nativa del concept 1504×1046, tablet 768×1024 e mobile 360×800. Nessun overflow orizzontale della pagina nelle misure effettuate.

| Punto confrontato | Evidenza, correzione o differenza intenzionale |
| --- | --- |
| Testi e ordine | “Le tue offerte”, sottotitolo, negozi, stato fonte, viste, ricerca, categorie, periodo e risultati nello stesso ordine. Nessun nuovo claim commerciale. Il diff del testo sopra la piega conserva le etichette principali; aggiunge orari reali e “Dettagli” fonte, mantiene tutte le categorie scorribili. |
| Contenitore e griglia | Tre schede; a 1504 px prima scheda x=40, y=620, larghezza 456, altezza 355 px. Prima iterazione troppo alta corretta accorpando informazioni e riducendo ripetizioni/spazi. Seconda riga visibile nella schermata finale. |
| Tipografia | Titolo pagina 40 px, articolo 19 px, prezzo 36 px, font locale coerente. Rimossi i titoli troppo piccoli e la marca duplicata; testo originale senza troncamento. |
| Colori e bordi | Verde #163d34, sfondo #f8f9f6, schede bianche, bordi #dce4dd. Condizioni in colore caldo più scuro del concept per leggibilità; comunicazione sempre anche testuale. |
| Prezzo e condizioni | Prezzo principale, base sotto, unitario affiancato quando lo spazio lo permette, condizioni e data prima del footer. Nessun prezzo inventato o vantaggio trasformato in certezza. |
| Icone e immagini | Icone Lucide coerenti con la UI esistente, decorative, non fotografie del prodotto. Marchio radar esistente conservato; nessuna fotografia o illustrazione generata inserita nel catalogo. Metafore specifiche disponibili nella libreria al posto dei disegni del concept. |
| Mobile e dettaglio | Comandi più compatti, espansione abbreviata visivamente in “Tutte” con nome accessibile completo; prezzi e condizioni continuano a capo. Dialogo mobile a x=16/y=40, larghezza313/altezza720 nel viewport360×800, focus iniziale sul comando di chiusura. |

Il confronto verifica fedeltà della struttura, gerarchia e linguaggio visivo; non afferma uguaglianza pixel per pixel. Differenze intenzionali: orari e contenuti derivano dal catalogo reale, categorie ulteriori disponibili nello scorrimento, logo/icona della libreria esistente, tag Surgelato documentato conservato, ordine reale dei prodotti nella seconda riga. Nessuna discrepanza funzionale o problema di overflow noto rimasto dai controlli svolti.

Evidenze IAB conservate come richiesto dal brief: [desktop reale](ui-desktop.png), [mobile reale](ui-mobile.png), [dettaglio mobile](ui-mobile-detail.png). Le immagini di concept non provano l’estrazione; le tre schermate finali sono dell’app collegata all’API e ai dati persistenti. I file temporanei delle iterazioni non fanno parte della consegna.
