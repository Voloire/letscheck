# Ripresa dopo compattazione — 5 settembre 2026

## Stato e autorizzazione corrente

L'alfa locale 0.3.0-alpha.1 è stata completata, verificata, revisionata e consegnata. L'utente ha apprezzato molto comprensione dei requisiti, qualità e UI. Ha poi indicato tre interventi e chiesto di aspettare. L'ultima richiesta autorizza **soltanto il salvataggio del contesto prima della compattazione**, non l'esecuzione dei nuovi fix.

Alla ripresa: leggere questo file, CONTEXT.md e workflow-multiagente.md. Presentare un piano breve dei nuovi interventi e attendere una richiesta esplicita di esecuzione. Nessuna PR dei nuovi fix è stata aperta. Non riavviare la lavorazione della versione già completata.

## Dove si trova il lavoro

- Worktree attivo: `C:\Users\franc\astrochecker-local`, branch `astrochecker-local`.
- Checkout principale: `C:\Users\franc\letscheck`. Non contiene ancora il nuovo codice; non usarlo per implementare i fix. Il suo EVOLUZIONI.md è una nota precedente, da non scambiare per lo stato attuale.
- Base: `5ea3f0088e04e53f867f66628c70f1e4aa4bf1f1`, tag precedente `v0.2.0-alpha.1`. Il refactoring locale è ancora **non committato**. Preservare tutti i file modificati/non tracciati e il database incluso.
- Server consegnato: `http://127.0.0.1:65154/`, PID registrato 8568. Indirizzo/PID sono storici: verificarli prima di agire. Riavvio mediante `avvia.cmd` nel worktree attivo; viene scelta una porta libera. SkyChart non è necessario.
- Python: `.venv\Scripts\python.exe` nel worktree. Nessun commit/merge/push autorizzato per questa versione o per i nuovi fix. Non cambiare identità Git né aggiungere attribuzioni di contribuzione diverse dall'utente.

## Tre interventi richiesti, ancora da pianificare

1. **Finestre continue troncate dall'analisi.** L'utente vuole poter riconoscere e suggerire un'unica occasione quando il limite temporale spezza una finestra realmente continua. Ha riconosciuto che lo screenshot mostrava invece intervalli separati da circa 21 ore: non vanno uniti. Chiarire l'estensione temporale necessaria prima di cambiare il contratto attuale di 24 ore; non unire gli estremi come se il tempo fosse circolare. Non è approvata una ricerca di 48 ore o illimitata.
2. **Selettore data/ora.** Dopo la scelta dell'ora, il popup dovrebbe chiudersi automaticamente; ora occorre cliccare fuori. Riprodurre il comportamento del controllo nativo nel browser effettivo prima di scegliere la soluzione. Non sostituire preventivamente tutto il datepicker.
3. **Nickname DSO.** La ricerca per nomi comuni non trova risultati perché questa versione non li importa. Aggiungere alias verificati: non è un guasto di FTS5, che è rimandato. Raw OpenNGC disponibili, ma il nome Flame Nebula associato a IC434 è controverso/errato rispetto a NGC2024: non importarlo ciecamente. Fonte, licenza e ambiguità restano da preservare.

Screenshot osservativo salvato in `artifacts/feedback/intervalli.png`. Le immagini sul consumo sono nella stessa cartella; sono evidenze locali escluse da Git.

## Funzionalità e verifiche già concluse

- SQLite prealimentato M/NGC/IC/Sh2/vdB/LDN, 15.569 record, alias di catalogo e ambiguità esplicite (M102 incluso). Nessun catalogo stellare generale né nickname attuale.
- Astropy offline, geometria senza rifrazione, Sole <= -18°, durata continua e prima finestra sufficiente entro 86.400 secondi fisici, settore azimutale attraverso il nord, fuso IANA/DST. Eventi del buio separati dal bersaglio.
- UI originale preservata, ricerca, una postazione salvabile, geolocalizzazione facoltativa con accuratezza e conferma. Profilo Windows `%LOCALAPPDATA%/AstroChecker/site.json`; test sempre su file temporanei.
- NINA soltanto pulsante disabilitato. EQMOD, MCP, animazione, suggerimenti di sessione, posizione Luna, FITS/immagini e blind plate solving restano nella lista dei desideri di EVOLUZIONI.md, non implementati.
- Gate completo: 165 test passati in 38,61 s. Ultimo fix sui suggerimenti obsoleti verificato dopo quel gate con 5 prove UI e 4 regressioni storiche; revisione finale approvata. Prova reale M13→M31 con suggerimenti sospesi calcola NGC224/M31 correttamente. Questo difetto è **già risolto**, distinto dai tre nuovi interventi.
- M13 circa 1,36 s a caldo; nessuna richiesta di rete nel calcolo. Geolocalizzazione simulata, non verificata fisicamente sul laptop.
- Limite accettato: richieste HTTP valide entro 64 KiB hanno errori JSON leggibili; framing malformato/oltre limite può chiudere senza JSON. Non riaprire un lavoro di hardening fuori perimetro.
- IERS incluso: 1973-01-02 UTC fino a prima di 2027-08-28 UTC, anche fine delle 24 h deve essere coperta. Licenze CDS specifiche da chiarire prima di redistribuzione esterna; OpenNGC CC-BY-SA4. Fonte dettagliata in FONTI-DATI.md.

## File da leggere solo quando servono

ASTROCHECKER.md: uso e limiti. VERIFICA-LOCALE.md: evidenze. PIANO-LOCALE.md: contratto realizzato. RIFERIMENTO-SKYCHART.md: conoscenze storiche.

Codice: `astrochecker/catalog.py`, `local_astronomy.py`, `service.py`, `server.py`, `static/app.js`, `static/index.html`, `static/style.css`; `tools/build_catalog.py` ricostruisce da snapshot senza download. Planner e test storici protetti sono rimasti invariati.

Test: `tests/test_acceptance.py`, `test_local_acceptance.py` (protetti), `test_catalog.py`, `test_local_backend.py`, `test_local_ui.py`, `test_backend.py`. Per modifiche piccole eseguire prima i test pertinenti, senza ripetere suite verdi senza motivo.

Report approfonditi in `.runtime/`: `local-progress.md`, `catalog-report.md`, `backend-local-report.md`, `ui-local-report.md`, `final-review.md`. Il ledger contiene anche stati intermedi storici: prevalgono conclusione finale e questo riepilogo. Non rileggere l'intero archivio o ridistribuire tutti i task.

## Consumo e metodo alla ripresa

La quota è passata dal 100% al 20% durante **l'intero percorso della conversazione**, comprese ricerca iniziale, prima alfa, pubblicazione e refactoring. Non attribuire l'80% al solo refactoring: mancano misure per fase. L'utente riferisce ora un reset settimanale e intende usare un modello meno costoso per i nuovi fix; non ne ha specificato qui il nome. Nessun cambio di modello/configurazione effettuato.

Conservare qualità e ATDD con meno orchestrazione: interventi piccoli, un esecutore e revisione mirata quando utile, niente riletture globali, fan-out o documentazione ripetitiva. Il vincolo prioritario resta: niente overengineering, verificare le funzioni, mantenere la UI apprezzata.
