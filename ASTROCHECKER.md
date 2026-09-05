# AstroChecker - v0.3.0-alpha.3

Un pianificatore locale per verificare se un bersaglio del cielo profondo resta nella porzione di cielo accessibile dal balcone, al buio, per una durata continua.

## Avvio

Esegui `avvia.cmd` dalla cartella dell'applicazione: il browser apre una porta libera di localhost. Il catalogo SQLite è già incluso e viene controllato automaticamente. SkyChart non è più un prerequisito.

Da terminale:

```powershell
.\.venv\Scripts\python.exe run.py
```

Per chiudere il server usa Ctrl+C nella finestra di avvio. Chiudere la scheda del browser non arresta Python. Il server accetta connessioni soltanto da questo computer.

## Pianificare una sessione

1. Digita una sigla M, NGC, IC, Sh2, vdB o LDN oppure un nome comune presente nel catalogo. Puoi selezionare una proposta oppure inserire direttamente una sigla esatta. M13 e NGC 6205 identificano lo stesso bersaglio. Sigle o nomi ambigui richiedono una scelta esplicita.
2. Imposta coordinate e fuso IANA della postazione, data/ora locale e durata continua. I valori iniziali di Chiusanico sono un esempio modificabile.
3. Imposta altezza minima/massima e settore di azimut, poi calcola.

Nord/Est sono positivi. L'azimut vale Nord 0°, Est 90°, Sud 180°, Ovest 270°. Un settore 350°-20° attraversa il Nord; 0°-360° comprende tutte le direzioni. Gli estremi uguali non sono validi.

Puoi salvare una sola postazione, compresi fuso e limiti del balcone: viene ritrovata anche se cambia la porta al successivo avvio. Su Windows il file è `%LOCALAPPDATA%/AstroChecker/site.json`. Non vengono salvati oggetto, data e durata della ricerca.

Il rilevamento facoltativo usa la geolocalizzazione del browser: mostra coordinate e raggio di accuratezza dichiarato, da accettare prima di sostituire i dati manuali. Non ricava automaticamente il fuso e non salva automaticamente la proposta. Dipende dal browser e dai servizi di posizione disponibili; l'inserimento manuale funziona senza rete.

Il fuso è quello della postazione, non necessariamente quello del computer. Gli orari ambigui o inesistenti al cambio dell'ora vengono rifiutati. La durata e l'orizzonte di ricerca sono tempo fisicamente trascorso.

## Leggere i risultati

- **Completa:** tutto l'intervallo richiesto è disponibile.
- **Parziale:** soltanto una parte è disponibile; intervalli separati non soddisfano una durata continua.
- **Non visibile:** nessun tratto utile nell'intervallo richiesto.
- **Prima finestra completa:** prima occasione sufficiente la cui fine rientra nelle 24 ore successive all'inizio scelto.
- **Nessuna soluzione:** nessuna finestra continua sufficiente in queste 24 ore, non una previsione per tutti i giorni futuri.

Quando la richiesta non e completa, il servizio propone una sola alternativa prioritaria, sempre nello stesso ordine: prima corregge l'orario nella finestra analizzata mantenendo la durata; se non basta cerca la prima data futura completa; infine mostra la finestra continua piu ampia anche se piu breve. La ricerca futura e limitata a 90 giorni e il limite e indicato nella UI. Se il bersaglio non compare in alcuna finestra, il risultato lo dichiara esplicitamente; se compare solo per meno tempo, sono mostrate durata richiesta e durata massima ottenibile.

Se un intervallo tocca l'inizio o la fine delle 24 ore, il risultato lo segnala come possibile prosecuzione oltre il periodo analizzato. Gli intervalli separati non vengono uniti automaticamente: per confermare ciò che accade oltre il bordo occorre avviare un'analisi con un inizio diverso.

Il buio astronomico richiede Sole <= -18° per tutta la finestra. Inizio e fine del buio sono mostrati separatamente: dipendono da data e postazione, non dal balcone o dal bersaglio. Dove non ci sono attraversamenti della soglia nelle 24 ore non vengono inventati orari.

La durata è tempo continuo, non somma delle esposizioni. Il pulsante **Export TARGET to NINA** è un segnaposto disabilitato: l'esportazione è futura.

## Dati e limiti

Il database locale contiene i sei cataloghi richiesti e i nomi comuni verificati dallo snapshot OpenNGC; fonti, snapshot, licenze, censimenti ed eccezioni sono descritti in [FONTI-DATI.md](FONTI-DATI.md). Il nome controverso associato a IC 434 è escluso. M102 resta ambiguo: scegliere il bersaglio esplicito fra i candidati indicati.

Questa versione non include un catalogo stellare generale: Arturo non è ricercabile. Non considera pianeti, comete, meteo, effetto della Luna, qualità del cielo o attrezzatura. Verifica la posizione di catalogo del bersaglio, non l'intero campo fotografico né l'estensione di una nebulosa.

Astropy calcola localmente bersaglio e Sole, usando dati ausiliari inclusi. Nessun download durante il calcolo e nessun modello linguistico. Le altezze sono geometriche, senza rifrazione atmosferica. Le posizioni sono interpolate fra nodi a 30 secondi e valutate su una griglia di un secondo: questa è una risoluzione del calcolo, non una garanzia di accuratezza astronomica al secondo. Per ostruzioni reali lascia un margine nei limiti inseriti.

I dati di orientamento terrestre hanno un intervallo temporale finito. Il motore segnala date non coperte e dichiara l'uso di valori predittivi nelle note; aggiornare i pacchetti è un'operazione esplicita, separata dall'uso offline.

La tabella inclusa copre dal 2 gennaio 1973 UTC fino a prima del 28 agosto 2027 UTC. Anche la fine delle 24 ore analizzate deve essere coperta. Questa copertura non rende uniformemente precise le coordinate dei cataloghi storici.

## Preparazione di un nuovo ambiente

Python 3.13. L'installazione iniziale delle dipendenze richiede accesso ai pacchetti:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Non occorre ricostruire il database a ogni avvio. Il comando separato e le condizioni di riutilizzo dei dati sono in `FONTI-DATI.md`.

## Verifiche e riferimenti

I criteri della versione locale sono in `PIANO-LOCALE.md`; gli esempi protetti sono in `tests/test_acceptance.py` e `tests/test_local_acceptance.py`.

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m playwright install chromium
.\.venv\Scripts\python.exe -m pytest -q
```

Il percorso storico SkyChart è conservato in `RIFERIMENTO-SKYCHART.md` e nei moduli di riferimento. Le evidenze della precedente release sono distinte da quelle della versione locale. Le evoluzioni da esplorare sono in `EVOLUZIONI.md`.
