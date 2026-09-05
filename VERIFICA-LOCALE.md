# Verifica della versione locale — v0.3.0-alpha.1

Verifiche funzionali e revisione indipendente dell'insieme approvate. Nessun commit, merge o push eseguito per questa versione.

## Dati locali

- SQLite: controllo di integrità superato, 15.569 record, nessuna coordinata fuori intervallo o non finita.
- 40 prove catalogo superate; ricostruzione dagli snapshot locali identica byte per byte.
- SHA-256: `ebe056261e6f8e558f99d3a6aee2196d862da46374705afe2570e0f8741b65ea`.
- Revisione di conformità e qualità conclusa senza rilievi bloccanti.
- Eccezioni e licenze: [FONTI-DATI.md](FONTI-DATI.md). Nessuna distribuzione esterna effettuata durante questa lavorazione.

## Criteri funzionali

Prima delle modifiche: 73 prove della precedente alfa superate. Le 14 nuove prove protette sono state osservate fallire per funzionalità locali mancanti prima dell'implementazione. Proteggono risoluzione dei cataloghi, assenza di rete, visibilità M13 completa/parziale, errori oggetto, fuso e buio astronomico.

I quattro confronti astronomici M13 conservano risultati ottenuti con SkyChart nella prima alfa. Sono riferimenti registrati, non nuove interrogazioni a SkyChart. Il servizio locale li ha superati con rete bloccata: la prima finestra disponibile termina a offset 18.683 secondi, come nel riferimento.

Il gate del motore/API ha superato 153 prove in 24,24 secondi. La misura sul caso M13 ha richiesto 2,082 secondi alla prima chiamata e 1,356 secondi a processo caldo; sono misure su questa macchina, non garanzie universali.

Una prova distinta sul server HTTP reale ha verificato stato dei cataloghi, ricerca M13, postazione temporanea assente e calcolo completo: 2,262 secondi. Evidenza locale in `artifacts/local-http.json`.

## Gate finale e browser

Il gate completo della versione UI ha dato **165 passed in 38.61s**:

```powershell
.\.venv\Scripts\python.exe -m pytest -p no:cacheprovider -q tests\test_local_ui.py tests\test_local_backend.py tests\test_local_acceptance.py tests\test_acceptance.py tests\test_catalog.py tests\test_backend.py
```

Anche compilazione Python, coerenza delle dipendenze e controllo del diff sono passati. L'interpolazione è verificata anche vicino allo zenit, al passaggio azimutale 360/0, al polo e alla soglia solare −18°.

I cinque scenari browser coprono avvio/recupero cataloghi, ricerca, postazione persistente su porta diversa, geolocalizzazione e risultati con fusi/buio/NINA. Le prove di persistenza usano file temporanei; il profilo reale non è stato modificato.

Il percorso M13 → NGC 6205 è stato eseguito con SQLite, Astropy e server reali: risultato completo, alias visibile, buio separato e NINA disabilitato. Le schermate a 1440×1100 e 390×844 non mostrano overflow; nessun errore JavaScript o richiesta applicativa esterna rilevato. Evidenze: `artifacts/ui-local-desktop.png` e `artifacts/ui-local-mobile.png`.

Una prova indipendente dell'avvio tramite `run.py --no-browser` ha verificato nuova versione, cataloghi pronti, modulo abilitato e HTTP 409 per M102 ambiguo, senza salvare dati. Evidenza: `artifacts/final-launcher-smoke.json`.

La revisione finale ha individuato e fatto correggere una scelta obsoleta durante modifiche rapide della ricerca. La regressione M13 → M31 con risposta dei suggerimenti sospesa è stata osservata rossa prima del fix e verde dopo. Le cinque prove UI e le quattro regressioni UI storiche sono state rieseguite con successo; gli altri componenti sono rimasti invariati. La re-review ha approvato UI e intera versione.

Un'ulteriore prova indipendente nel browser sul server finale, con catalogo e astronomia reali, ha confermato che digitare M31 e premere Invio con suggerimenti ancora in attesa calcola **NGC 224 / M31**, non il precedente M13. Risultato completo, RA 10,68478°, nessun salvataggio del profilo. Evidenza: `artifacts/final-selection-smoke.json`.

## Limiti della verifica

La geolocalizzazione è simulata: proposta, conferma, annullamento e permesso negato non equivalgono a una misura dell'accuratezza fisica del laptop. Alcuni casi UI di errore, DST e buio usano risposte deterministiche; i calcoli corrispondenti sono verificati separatamente nel backend. La verifica responsive riguarda Chromium e i due viewport indicati.

Una regressione deterministica ha riprodotto e protetto il problema Windows delle risposte anticipate 403/404/415 con corpi validi entro il limite. Framing HTTP malformato o corpi oltre 64 KiB possono chiudere la connessione senza JSON: limite accettato dell'alfa localhost, estraneo alle richieste prodotte dalla UI.

Non sono inclusi catalogo stellare generale, nomi comuni, valutazione dell'intero campo fotografico, meteo, effetto della Luna o controllo strumenti. NINA e la lista dei desideri restano futuri. Prima di ridistribuire il database occorre chiarire le licenze specifiche CDS. Copertura IERS e limiti di precisione sono descritti in [ASTROCHECKER.md](ASTROCHECKER.md).
