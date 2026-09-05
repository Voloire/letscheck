# AstroChecker locale — piano della prossima alfa

Specifica: EVOLUZIONI.md e recap approvato nella conversazione. Versione di lavoro: 0.3.0-alpha.1.

## Contratto

SQLite prealimentato contiene M, NGC, IC, Sh2, vdB e LDN; nessuna ricerca astronomica online durante l'uso. Una libreria astronomica locale calcola oggetto e Sole. Conservare le decisioni del planner e i test di accettazione, la ricerca di 24 ore, durata continua, Sole <= -18°, altezze geometriche e settore che può attraversare nord. Il grafico e le finestre sono stime, non una precisione assoluta al secondo. Conservare le conoscenze SkyChart senza obbligarne l'avvio.

La UI conserva stile e struttura dell'alfa. Cataloghi pronti all'apertura, ricerca con sigle normalizzate, postazione manuale/salvabile e geolocalizzazione facoltativa con accuratezza e conferma. Fuso IANA della postazione visibile e modificabile. Inizio/fine buio astronomico separati dai limiti del balcone, eventi assenti dichiarati. Export TARGET to NINA soltanto disabilitato, etichettato Prossimamente. Nessuna implementazione della lista dei desideri. Nessuna introduzione di servizi, ORM, framework frontend, FTS5 o aggiornamenti automatici dei cataloghi.

## Esecuzione

1. Cataloghi: acquisizione documentata, importazione ripetibile e SQLite incluso, identificativi/alias e test di qualità dei dati. Fonte, versione, hash e licenza di ogni insieme; nessuna fusione per sola prossimità. Gestire M102 e identificazioni ambigue in modo esplicito.
2. Motore: calcoli Astropy offline, nuova sorgente SQLite e API, crepuscolo astronomico e fuso della postazione. Confronto con evidenze SkyChart e casi astronomici esterni, tempi reali misurati. Conservare separatamente adattatore e prove SkyChart; nessun doppio backend selezionabile nella UI.
3. UI: adeguamento mirato, prove browser di ricerca/selezione, salvataggio postazione, consenso alla posizione, errore catalogo, risultati e crepuscoli, export disabilitato, desktop/mobile.
4. Revisione finale delle funzioni, avvio della nuova versione e consegna. Commit/merge/push non inclusi in questa richiesta.

## Accettazione da proteggere

- Tutti gli esempi osservativi della prima alfa rimangono validi.
- M13 e NGC 6205 risolvono il medesimo bersaglio; spazi e maiuscole non cambiano una sigla. Un nome inesistente dà errore distinto da non visibile.
- Per ogni catalogo è verificata la copertura rispetto al file di origine, con eccezioni elencate; coordinate finite e intervalli validi. Non rendere pianificabili voci inesistenti o ambigue.
- Pianificazione riuscita con socket esterni bloccati e nessun SkyChart richiesto.
- La notte astronomica dipende da Sole/postazione/data, non da oggetto e balcone; eventi senza attraversamento non diventano orari inventati.
- Fuso diverso da Europe/Rome, mezzanotte e ora legale preservano la durata fisica.
- NINA non riceve dati in questa versione; il pulsante è solo un segnaposto.
