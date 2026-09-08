# Accesso remoto gratuito con GitHub Pages

Sito: https://killuazoldich.github.io/spesaradar/

La modalità online è una variante di consultazione del catalogo, autorizzata dopo il prototipo locale. Conserva selezione multipla, categorie, ricerca AND, filtri, prezzo per base compatibile, dettaglio e fonte. Nessun account, tessera o API key è richiesto ai visitatori.

## Come funziona

GitHub Actions esegue i medesimi connettori, normalizzazione, classificazione e controlli del worker locale. Un controllo ogni ora al minuto 37 avvia raccolte solo dopo il TTL minimo di 12 ore per fonte, rispettando cooldown, sospensioni, robots e budget. Ritardi di Actions possono allungare questo intervallo. Alla prima pubblicazione viene verificata l’accessibilità dal runner, anche se la copia iniziale è recente, sempre rispettando il cooldown.

Pages serve file statici HTTPS, compreso un catalogo JSON di prodotti reali con provenienza e condizioni. Il browser applica filtri, ricerca e paginazione su questa copia; non fa scraping e non avvia job. **Controlla aggiornamenti** scarica la pubblicazione corrente: non promette una nuova raccolta immediata. Per avviare un controllo da manutentore, usare il workflow **Pubblica SpesaRadar → Run workflow**, con autenticazione GitHub; non esiste alcun token amministrativo nel frontend.

Il primo catalogo di riserva in `site/bootstrap.json` proviene dal database locale verificato l’8 settembre 2026. Conserva gli orari originali: un errore remoto non li rinnova. Le successive esecuzioni ripristinano l’ultima pubblicazione HTTPS e ne conservano record, contatori di riconciliazione, condizioni note e limiti di frequenza. Errori di download diversi dal primo 404 fermano la pubblicazione. Una fonte fallita non cancella i prodotti ancora validi delle altre.

## Freschezza e limiti

Il feed esclude immediatamente offerte scadute e dati verificati da oltre 48 ore; oltre 12 ore espone l’avviso di dato non recente. La data di pubblicazione del file non sostituisce la verifica del prodotto. I controlli vengono ricalcolati nelle letture e dopo resume. La copia nel browser viene ricontrollata dopo un minuto nelle letture successive, condividendo il download fra filtri e metadati. La versione locale Docker conserva le API e i job durevoli originali.

In Actions SQLite e capture sono temporanei e non vengono caricati negli artifact. La persistenza remota è la sola rappresentazione normalizzata JSON, pubblicata atomicamente con gli asset. Un crash prima del deploy lascia la precedente versione: non offre la stessa persistenza dei job a metà esecuzione del worker locale. Concorrenza serializzata, timeout del workflow e frequenza pianificata limitano i tentativi; non è un backend sempre acceso.

GitHub può ritardare o disabilitare i workflow pianificati dopo 60 giorni senza attività nel repository pubblico. Controllare Actions in caso di dati non aggiornati; riabilitare il workflow e avviarlo manualmente. Nessuna attività fittizia viene creata per aggirare questa regola. Le fonti possono limitare gli IP dei runner: lo stato mostra il blocco e non vengono usati proxy o bypass.

## Costi e pubblicazione

Repository pubblico, Pages e runner **standard ubuntu-24.04**, nessun runner grande, VPS, servizio di scraping o LLM. Nessuna cache Actions persistente; artifact del sito inferiore al limite applicativo di 10 MB per catalogo, conservato un solo giorno. Le esecuzioni pianificate senza variazioni non caricano artifact. Non viene attivato alcun acquisto o piano a pagamento. La disponibilità gratuita dipende dalle condizioni GitHub; non è una promessa immutabile né di costo totale nullo per hardware/rete personali.

Fonti ufficiali delle condizioni della piattaforma:
- https://docs.github.com/en/actions/reference/runners/github-hosted-runners
- https://docs.github.com/en/billing/concepts/product-billing/github-actions
- https://docs.github.com/en/pages/getting-started-with-github-pages/using-custom-workflows-with-github-pages
- https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule

La pubblicazione rimane un progetto personale senza checkout, affiliazioni o SaaS commerciale. Foto e capture non vengono pubblicate. Le informazioni di prodotto essenziali e la provenienza sono pubbliche; restano validi i limiti dell’audit delle fonti.

## Riprodurre una build statica

```bash
VITE_STATIC_CATALOG=true VITE_BASE_PATH=/spesaradar/ npm --prefix apps/web run build
cp site/bootstrap.json apps/web/dist/catalog.json
```

Per raccogliere da ambiente isolato: configurare `SPESARADAR_DB` in una cartella temporanea, eseguire migrazioni e `PYTHONPATH=backend python -m app.pages --restore previous.json --collect --export catalog.json`. Non puntare questo comando al database locale già in uso. L’export non accetta fixture sintetiche né URL fuori dai manifest; le evidenze pubbliche escludono capture e percorsi privati.

## Verifica eseguita

Prima raccolta e deploy remoti riusciti: [run](https://github.com/KilluaZoldich/spesaradar/actions/runs/34195536421), 450 prodotti reali da entrambe le insegne, artifact compresso 188.518 byte e retention 1 giorno. [Rapporto ed evidenze](verification.md#pubblicazione-remota--8-settembre-2026). Test del sito: `PAGES_TEST_URL=https://killuazoldich.github.io/spesaradar/ npm --prefix apps/web run test:pages`.

## Copertura ampliata (8 settembre 2026)

Lidl ed Eurospin restano ambiti nazionali; MD è disponibile esclusivamente per la sede verificata Milano, via Rubens 8. Il connettore risolve ogni volta il volantino dalla pagina ufficiale della sede. Nessuna località viene assegnata automaticamente all’utente. Le altre insegne esaminate hanno stati di supporto espliciti e non sono selezionabili. Il nuovo catalogo MD conserva date sconosciute, condizioni carta e limiti di freschezza. [Audit dettagliato](source-audit.md).
