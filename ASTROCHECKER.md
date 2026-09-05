# AstroChecker — v0.2.0-alpha.1

Un piccolo pianificatore locale per verificare se un oggetto celeste resta nella porzione di cielo accessibile dal balcone, al buio, per una durata continua.

## Avvio su questo computer

1. Avvia SkyChart / Cartes du Ciel.
2. Nelle impostazioni General → Server abilita **Use TCP/IP Server**, indirizzo **127.0.0.1**, porta **3292**. Riavvia SkyChart se hai modificato le impostazioni.
3. Esegui `avvia.cmd` dalla cartella dell'applicazione. Si apre il browser su una porta libera di localhost.
4. Premi **Verifica connessione**, compila i dati e avvia il calcolo.

Il programma non usa Internet durante l'esecuzione. La ricerca oggetti usa i cataloghi disponibili nella propria installazione SkyChart. Nessun account o modello linguistico. Il server accetta connessioni soltanto da questo computer.

Per l'avvio da terminale:

```powershell
.\.venv\Scripts\python.exe run.py
```

Per chiudere il server usa Ctrl+C nella finestra di avvio. Chiudere la scheda del browser non arresta Python.

## Come leggere i risultati

- **Completa:** tutto l'intervallo richiesto è disponibile.
- **Parziale:** soltanto una parte è disponibile; gli intervalli separati non vengono sommati per soddisfare la durata continua.
- **Non visibile:** nessun tratto utile nell'intervallo richiesto.
- **Prima finestra completa:** primo intervallo sufficiente trovato nel periodo di ricerca. La sua fine deve rientrare nelle 24 ore successive all'inizio indicato.
- **Nessuna soluzione:** nessuna finestra continua sufficiente in queste 24 ore, non una previsione per tutti i giorni futuri.

La durata è tempo continuo trascorso, non somma delle esposizioni. L'alfa richiede Sole a un'altezza non superiore a -18°. Non considera nuvole, Luna, inquinamento luminoso, qualità fotografica, ingombri dell'attrezzatura o movimenti della montatura. Non esporta sequenze NINA.

Latitudine e longitudine usano i segni geografici usuali: Nord/Est positivi. I valori precompilati sono indicativi di Chiusanico e possono essere cambiati. Per il balcone si specificano altezza minima/massima e settore di azimut: Nord 0°, Est 90°, Sud 180°, Ovest 270°. Un settore 350°–20° attraversa il Nord; 0°–360° include tutte le direzioni.

Il fuso dell'alfa è Europe/Rome. Gli orari ambigui o inesistenti durante il cambio dell'ora vengono rifiutati, anziché indovinare l'istante desiderato.

## Metodo e precisione

Questa alfa accetta **stelle di catalogo e oggetti del cielo profondo**. Pianeti, Luna, comete e altri oggetti mobili vengono rifiutati esplicitamente: occorre prima verificare un metodo adatto al loro movimento. Un'analisi completa su questa installazione richiede circa uno o due minuti.

SkyChart fornisce le coordinate equatoriali dell'oggetto e del Sole. Il checker converte localmente queste coordinate in altezza e azimut per la postazione indicata. Le interrogazioni usano una carta temporanea; la posizione del mouse non entra nel calcolo.

Le altezze sono **geometriche**, senza rifrazione atmosferica: vicino all'orizzonte possono differire dall'altezza apparente mostrata da SkyChart. Le posizioni intermedie vengono interpolate tra effemeridi orarie. La griglia di verifica è di un secondo; questo indica la risoluzione temporale del motore, non una garanzia di accuratezza astronomica al secondo. Per ostruzioni reali lascia un margine nei limiti inseriti.

L'alfa richiede coordinate SkyChart all'equinozio della data. Se il server è configurato per forzare J2000, il checker deve segnalare l'incompatibilità anziché usare il sistema di riferimento errato.

Riferimento del protocollo: [comandi server SkyChart](https://www.ap-i.net/skychart/en/documentation/server_commands). L'applicazione non consulta questa pagina durante l'uso.

## Preparazione di un nuovo ambiente

Python 3.13 e SkyChart con server TCP sono necessari. L'installazione iniziale delle dipendenze richiede accesso ai pacchetti:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

## Verifiche

I criteri funzionali sono in `ALPHA.md`; gli esempi protetti in `tests/test_acceptance.py` verificano decisioni e intervalli con traiettorie sintetiche dichiarate. Le prove con SkyChart reale sono distinte da quelle del motore, così un doppio di test non può essere scambiato per un'integrazione funzionante.

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m playwright install chromium
.\.venv\Scripts\python.exe -m pytest -q
```

La suite include quattro regressioni dell'interfaccia con Playwright e Chromium. Le evidenze locali sono nella cartella `artifacts/`, esclusa da Git.
