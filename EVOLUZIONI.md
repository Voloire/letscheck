# Direzione della prossima versione

Stato: refactoring locale autorizzato; lista dei desideri esclusa dall'implementazione. Il prodotto aiuta gli astrofotografi a pianificare sessioni; semplicità e correttezza dei dati precedono l'aggiunta di funzioni.

## Refactoring in corso

- SQLite locale alimentato una tantum con M, NGC, IC, Sh2, vdB e LDN. Conservare fonti, versioni, licenze, sistemi di riferimento e gestione delle identificazioni ambigue. Nickname facoltativi; FTS5 rimandato.
- Calcoli locali dell'oggetto e del Sole tramite libreria astronomica. Il database contiene dati di catalogo, non tutte le posizioni future del Sole. Verificare funzionamento offline e validità temporale dei dati ausiliari.
- Preservare esiti completo/parziale/nullo, durata continua, limiti del balcone, buio astronomico e prima finestra sufficiente nelle 24 ore. Conservare ATDD e confronti astronomici già verificati.
- Mantenere l'aspetto dell'interfaccia, adeguando il prerequisito SkyChart alla disponibilità del catalogo locale. Postazione manuale e salvabile; rilevamento facoltativo con accuratezza mostrata.
- Conservare adattatore e conoscenze SkyChart come riferimento; nessun secondo percorso runtime necessario alla nuova versione.
- Pulsante disabilitato "Export TARGET to NINA", indicato come futuro, vicino al risultato. Formato ed esportazione effettiva da discutere in una release successiva.

## Decisioni e limiti del refactoring

- Crepuscoli: conservare Sole <= -18 gradi e mostrare inizio e fine della notte astronomica; soglie civile (-6) e nautica (-12) restano informazioni eventualmente aggiungibili, non nuovi criteri approvati. Gestire eventi assenti nel periodo analizzato.
- Copertura: questa versione comprende i sei cataloghi DSO richiesti. Non sostituiscono il catalogo stellare di SkyChart: Arturo e molte altre stelle richiederebbero una fonte stellare aggiuntiva.
- Ricerca: oggetti e alias riconosciuti saranno quelli importati, non tutti quelli presenti nei cataloghi configurabili di SkyChart. Non promettere equivalenza senza un confronto di copertura.
- Fuso: aggiungere selezione esplicita del fuso IANA della postazione; non assumere che coincida con quello del computer. Europe/Rome rimane il valore iniziale modificabile.
- Il controllo attuale riguarda la posizione del bersaglio, non l'intero campo fotografico o l'estensione di una nebulosa. Nessuna regressione, ma mantenere chiaro questo limite.
- Meteo, effetto della Luna, qualità del cielo, controllo montatura e pianeti/comete non erano funzionalità dell'alfa: non sono perdite dovute al refactoring.

## Lista dei desideri — da esplorare, fuori dal refactoring

- EQMOD.
- Posizione della Luna durante la sessione osservativa (altezza e azimut), da esplorare in una release futura.
- MCP: chiarire ruolo e integrazione desiderata prima di definirne l'ambito.
- Animazione della traiettoria e della finestra osservabile.
- Suggerimenti per una sessione completa: "Le migliori opportunità per te". Definire criteri deterministici di selezione e ordinamento; non presupporre controllo automatico degli strumenti.
- Esportazione reale verso NINA, da discutere separatamente.
- Caricamento di FITS o altre immagini e plate solving blind per identificare il campo: "Riuscirò a riprendere questo?". Formati, risolutore e confronto del campo con l'orizzonte da valutare in futuro.

## Riferimenti

- [Astropy: altezza/azimut e posizione del Sole](https://docs.astropy.org/en/stable/coordinates/example_gallery_plot_obs_planning.html)
- [National Weather Service: tipi di crepuscolo](https://www.weather.gov/lmk/twilight-types)
