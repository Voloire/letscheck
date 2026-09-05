# Contratto storico — AstroChecker v0.2.0-alpha.1

Questo documento descrive l'alfa con SkyChart. Il refactoring con cataloghi locali è descritto in PIANO-LOCALE.md; i criteri osservativi sottostanti rimangono protetti dai test.

Applicazione Python per Windows, disponibile esclusivamente su localhost in un browser. Nessun servizio esterno, account, LLM, telemetria o esportazione NINA durante l'uso. SkyChart installato e avviato è un prerequisito.

La funzione locale **Cerchi Idee?** propone piu bersagli DSO in una sessione con un blocco continuo minimo di due ore per oggetto. Usa solo catalogo SQLite ed effemeridi locali, privilegia nebulose di emissione/riflessione e oggetti beginner, limita la ricerca futura a 90 giorni e mostra buio astronomico e nautico. Meteo, Luna, qualita del cielo e attrezzatura non vengono stimati.

## Flusso

1. Spiegare come abilitare il server SkyChart su 127.0.0.1:3292. Verificare una risposta reale prima di rendere disponibile la pianificazione. Connessione perduta e oggetto sconosciuto sono errori, non esiti astronomici negativi.
2. Inserire oggetto, latitudine/longitudine, data/ora Europe/Rome, durata continua in minuti, altezza minima/massima e settore di azimut osservabile. Coordinate iniziali indicative: Chiusanico 43.9729 N, 7.9944 E; modificabili. Azimut: nord 0, est 90, sud 180, ovest 270. Il settore può attraversare il nord; 0–360 rappresenta tutto l'orizzonte.
3. Controllare la visibilità geometrica e il buio (Sole non più alto di -18 gradi). Restituire visibilità completa/parziale/nulla, intervalli disponibili e durata continua massima. Cercare la prima finestra continua sufficiente entro le 24 ore dall'inizio richiesto. Anche la fine deve rientrare nel periodo di ricerca. Nessuna soluzione significa nessuna soluzione in queste 24 ore.
4. Mostrare grafico temporale semplice e ragioni di esclusione. Non promettere condizioni meteo o qualità fotografica. La durata è tempo continuo trascorso, non somma delle esposizioni.

## Decisioni iniziali

Il perimetro verificato dell'alfa comprende stelle di catalogo e oggetti del cielo profondo. Pianeti, Luna, comete e altri oggetti mobili sono rifiutati esplicitamente: l'interpolazione oraria usata qui non ha una precisione verificata per quei bersagli. Il Sole resta una sorgente interna per il criterio di buio. Le finestre sono stime, non garanzie al secondo.

Il settore iniziale è 0–360°, da restringere alle direzioni realmente accessibili. Il soffitto iniziale è 30°, coerente con il vincolo descritto; ogni limite resta visibile e modificabile.

Ricerca 24 ore, buio a -18 gradi e durata continua sono le impostazioni iniziali del piano eseguito. La pagina deve dichiararle. Niente database, scheduler, framework frontend, plug-in o gestione strumenti. Configurazione del balcone salvabile solo localmente nel browser, se utile.

I dati astronomici devono essere indipendenti dalla posizione manuale del cursore. Il controllo deve gestire azimut 360/0, transizioni, intervalli disgiunti e mezzanotte. Precisione temporale e margini devono essere dichiarati; non etichettare campionamento grossolano come certezza continua. Le modifiche temporanee a SkyChart non devono lasciare la carta dell'utente alterata dopo l'analisi, per quanto supportato dal protocollo.

## Accettazione protetta

- SkyChart spento: istruzioni e possibilità di riprovare. Avviato: accesso al modulo senza riavviare AstroChecker.
- Oggetto visibile e buio per tutta la durata: esito completo.
- Uscita dal limite del balcone prima della fine: parziale con istante di uscita e minuti utilizzabili.
- Oggetto sempre escluso: nullo. Nessuna finestra sufficiente: nessuna soluzione nel periodo esplicitato.
- Due intervalli brevi non si sommano per soddisfare una durata continua.
- Una finestra successiva sufficiente viene proposta dalla prima entrata utile, non da un orario arbitrario.
- Il limite superiore di altezza è vincolante quanto quello inferiore.
- Un settore 350–20 gradi include il nord ed esclude il sud.
- Sole sopra -18: quel tratto non è valido anche se l'oggetto è nel balcone.
- Intervalli che attraversano mezzanotte e cambi d'ora non perdono o aggiungono durata fisica. Orari inesistenti o ambigui richiedono una scelta/correzione esplicita.
- Dati mancanti, non numerici, non finiti, durata non positiva e limiti impossibili sono rifiutati in modo leggibile.
- Oggetto non risolto e server non disponibile non diventano 'non visibile'.
- Test reali SkyChart e browser sono obbligatori per dichiarare completato il flusso.

## Consegna

Avvio locale semplice, dipendenze minime, istruzioni in italiano, suite ATDD ripetibile e resoconto dei limiti dell'alfa. Dopo la verifica locale, integrazione su main e pubblicazione del tag v0.2.0-alpha.1 autorizzate. Identità Git e documenti storici non modificati.
