# voloirex.com: decisione e contesto per riprendere il lavoro

Data: 2026-09-10.

## Ambito

Questo documento conserva una decisione sul futuro sito personale voloirex.com.
Il sito è un progetto distinto da letscheck/AstroChecker: questa nota non avvia
la sua implementazione nel repository corrente. Inizialmente la discussione
era stata mantenuta fuori dal repository; l'utente ha poi chiesto esplicitamente
di salvare il contesto e creare un commit per riprendere da un'altra postazione.

## Decisione

- La root `voloirex.com` ospiterà blog, microblog e portfolio delle applicazioni.
- Il sito pubblico sarà statico, con contenuto già presente nell'HTML generato.
- La soluzione scelta nella discussione è Cloudflare per l'hosting statico.
- Tutte le applicazioni, incluso AstroChecker, continueranno a essere eseguite
  su Google Cloud Run. La scelta di un altro hosting riguarda soltanto il sito.
- Non occorre mantenere un'istanza Cloud Run sempre accesa per l'indicizzazione
  del blog. Le pagine pubbliche saranno disponibili indipendentemente dai backend.
- Contenuti, aspetto, HTML e CSS saranno gestiti tramite Codex. Non è previsto
  inizialmente un CMS, un pannello amministrativo o un database per il blog.

## Workflow concordato a livello concettuale

1. Preparare articoli e note in Markdown e aggiornare il sito tramite Codex.
2. Rivedere le modifiche prima della pubblicazione.
3. Generare le pagine HTML con una build e distribuirle sull'hosting statico.

Per il microblog sono stati proposti URL permanenti per ogni nota, un flusso
cronologico e un feed RSS. Il portfolio presenterà le applicazioni con contenuti
pubblici e collegamenti alle app eseguite su Cloud Run.

## Costi e alternative valutate

Il solo hosting statico Cloudflare può costare $0/mese entro i limiti della
piattaforma. Restano separati dominio, eventuali costi di build e strumenti,
backend Cloud Run, API esterne e qualsiasi servizio aggiuntivo.
Il costo complessivo delle applicazioni non è stato stimato.

Firebase Hosting è l'alternativa per mantenere il sito nell'ecosistema Google.
DigitalOcean App Platform offre anch'esso hosting statico; una VPS DigitalOcean
o Hetzner non è necessaria per il workflow scelto e aggiungerebbe manutenzione.
L'HTML statico agevola l'accesso dei crawler, ma non garantisce l'indicizzazione.

Fonti consultate durante la valutazione (ricontrollare prezzi e limiti prima
dell'attivazione):

- https://developers.cloudflare.com/workers/static-assets/billing-and-limitations/
- https://developers.cloudflare.com/workers/platform/limits/
- https://firebase.google.com/pricing
- https://www.digitalocean.com/pricing/app-platform
- https://cloud.google.com/run/pricing
- https://developers.google.com/search/docs/crawling-indexing/javascript/javascript-seo-basics

## Da definire nella prossima sessione

- Repository separato e generatore statico: nessun framework è stato scelto.
- Struttura grafica, organizzazione dei contenuti e metadati SEO.
- Configurazione Cloudflare, dominio, build, anteprime e pubblicazione.
- URL delle applicazioni e collegamento con i servizi Cloud Run esistenti.

Non sono stati creati servizi, modificati DNS, attivati piani o implementati
componenti del sito. Riprendere dalla progettazione del sito e del workflow,
mantenendo i backend su Cloud Run.
