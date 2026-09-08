# Operazioni locali

## Avvio, log e salute

Dalla radice: `docker compose up --build -d`. `docker compose ps` mostra salute di API, worker e web; migrate deve terminare con exit 0. `docker compose logs --tail 100 worker` mostra esiti strutturati con run/job/source, stage, durata e richieste. `GET /api/v1/source-status` espone una sintesi sicura; non è un endpoint amministrativo.

Dopo aver spento la macchina non avvengono aggiornamenti. Con restart `unless-stopped`, i servizi tornano quando riparte Docker; un job interrotto viene ripreso dopo la scadenza del lease (120 s), fino a tre acquisizioni. Un arresto ordinato concede 200 s al worker. Un processo in corso non conserva una transazione di scrittura durante il fetch.

## Configurazione

Copia facoltativamente `.env.example` in `.env`. Non servono chiavi. `MAX_TARGETS` controlla il limite backend (default 5), `DISABLED_SOURCES` è una lista separata da virgole di ID, per esempio `lidl-national`. Ricrea API e worker dopo modifiche all’ambiente:

```bash
docker compose up -d --force-recreate api worker
```

Disabilitare una fonte impedisce nuovi job/acquisizioni. Le offerte precedenti seguono ancora validità e freschezza e non vengono etichettate automaticamente come scadute. Per cambiare intervalli o host usare i manifest in `config/sources`, rispettando sempre il limite più restrittivo della fonte; ricostruire le immagini. Nessun parametro pubblico `force`.

## Backup coerente SQLite

Lo script usa la SQLite backup API e verifica il ripristino in un database temporaneo con `integrity_check` e conteggi. Non copia alla cieca il solo file principale WAL.

```bash
docker compose exec api python scripts/backup.py /data/spesaradar.db /data/backup.db
docker compose cp api:/data/backup.db ./spesaradar-backup.db
```

Il secondo comando esporta soltanto il backup coerente già chiuso. Conserva il file privatamente; contiene dati delle fonti. Le capture non fanno parte del backup del database: i riferimenti e le evidenze testuali restano interpretabili anche se i file grezzi non sono ripristinati. I backup deliberatamente creati non sono eliminati dalla retention.

Per ripristinare, prima verifica su un **nuovo percorso**, poi ferma API e worker. Conserva una copia del database precedente, evita sovrascritture mentre un processo lo usa. Una procedura non distruttiva è importare il backup con un nome nuovo nel volume e impostare `SPESARADAR_DB` al nuovo percorso tramite un override Compose; non eliminare il volume originale.

Avvio nativo:

```bash
uv run python scripts/backup.py .private/spesaradar.db .private/backup.db
```

## Capture e diagnosi parser

Capture private in `/data/captures` (nativo `.private/captures`), permessi restrittivi, retention 7 giorni e budget 500 MB. Il worker elimina i file più vecchi, preservando i metadati. Non servire questa directory via HTTP. I file iniziali di scouting non fanno parte del runtime e non vengono distribuiti.

Dopo una correzione parser, `scripts/reprocess.py` rilegge capture locali senza rete e preserva la verifica originaria; mette in quarantena i risultati da riesaminare, poi pubblica i lotti ricostruiti. È uno strumento del maintainer, da usare dopo backup, con worker fermo e capture disponibili. Non è un refresh pubblico e non prova che la fonte sia ancora raggiungibile.

`scripts/live_review.py` produce 50 record per insegna con campi sorgente e normalizzati, mantenendo gli ID del campione già scelto. Richiede le capture private; non sostituisce il confronto del contesto promozionale e delle condizioni. Le fixture sintetiche pubbliche verificano il parser, non l’accessibilità della fonte.

## Docker Desktop su questa macchina

Durante la verifica il daemon era inizialmente spento; è stata avviata l’app Docker già installata. Il credential helper configurato nel profilo personale si bloccava anche su immagini pubbliche. Il profilo personale non è stato cambiato. È stata creata una configurazione separata `.private/docker-public/config.json` senza credenziali, che include il percorso del plugin Compose installato. Comando realmente utilizzato:

```bash
docker --config .private/docker-public \
  --host unix:///Users/metin/.docker/run/docker.sock \
  compose up --build -d
```

Questi percorsi sono specifici dell’ambiente verificato, non prerequisiti del progetto. Su un Docker normale usare il comando standard. Se il proprio helper è bloccato, risolvere Docker Desktop o configurare esplicitamente un profilo separato per immagini pubbliche; non cancellare credenziali personali e non installare servizi commerciali.

## Limiti operativi

Il volume deve restare sul filesystem locale dello stesso host. Non esportare 8080 su `0.0.0.0`, aggiungere tunnel o pubblicare il progetto: l’accesso Internet non è incluso. Un controllo robots favorevole non certifica una licenza. Fonti e condizioni cambiano: sospendere il manifest se l’audit non è più valido.

Esempio di ripristino non distruttivo nel volume, con nome nuovo:

```bash
docker compose exec api python scripts/backup.py /data/backup.db /data/restored.db
```

Questo valida e crea un database distinto, senza cambiare quello in uso. Per adottarlo, ferma i servizi e crea `compose.restore.yaml`:

```yaml
services:
  migrate:
    environment:
      SPESARADAR_DB: /data/restored.db
  api:
    environment:
      SPESARADAR_DB: /data/restored.db
  worker:
    environment:
      SPESARADAR_DB: /data/restored.db
```

```bash
docker compose stop api worker
docker compose -f compose.yaml -f compose.restore.yaml up -d
```

Il database precedente resta nel volume. Per tornare al precedente usa il Compose originale dopo aver fermato i servizi. Non cancellare file WAL/SHM di un database in uso.


### Cache Coop già verificata

Il workflow può ammettere `site/reviewed-cache.json` dopo il ripristino dello snapshot pubblico. È un'eccezione limitata al singolo buono Coop acquisito prima del 403 GitHub: il codice verifica l'hash canonico dell'intero record. Non modificare date per prolungarne la visibilità; scade dal feed a 48 ore dalla verifica originale. Il file non contiene capture grezze e non azzera il blocco della fonte. Nuovi dati richiedono raccolta consentita e audit, non aggiornamento manuale dei prezzi.
