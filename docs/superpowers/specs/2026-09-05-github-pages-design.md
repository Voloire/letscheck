# AstroChecker GitHub Pages Design

## Obiettivo

Pubblicare una pagina statica pubblica che spieghi AstroChecker, il problema osservativo che risolve, i requisiti funzionali della release `v0.3.0-alpha.2`, i limiti e il modo di provarla.

## Scelta

La pagina vive in `docs/index.html` con CSS inline nello stesso file e nessun JavaScript applicativo. GitHub Pages la pubblica tramite Actions su ogni push a `main`. Il contenuto resta autonomo dal server Python e non raccoglie dati del visitatore.

## Contenuti

La pagina contiene: hero e call to action, problema del balcone, requisiti funzionali, flusso in quattro passi, risultati completo/parziale/nullo, cataloghi e fonti, privacy/offline, limiti, avvio locale, stato della release e link a repository/release.

## Vincoli

- HTML e CSS senza framework o CDN.
- Layout leggibile su mobile e desktop, con contrasto elevato e focus visibile.
- Nessuna promessa di funzionalità non implementate: NINA, meteo, Luna, stelle e plate solving restano futuri.
- Deploy limitato al sito statico della repository.
