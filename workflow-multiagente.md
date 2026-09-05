# Workflow di sviluppo multiagente

Data di consolidamento: 5 settembre 2026.

## Scopo e stato

Documento permanente per riprendere questa progettazione dopo compattazione del contesto o in una nuova conversazione. Leggere questo file prima di riprendere il lavoro sul workflow.

L'utente ha utilizzato Herd, un watcher, Git come contratto e revisione dei diff. Vuole poter mantenere le medesime garanzie anche senza Herd, usando Codex e i controlli del repository. Questo documento conserva il workflow desiderato: non dichiara che orchestrazione, CI, protezioni o release siano già configurate, né autorizza ad attivarle su un repository non specificato.

## Obiettivo attuale e proposta pragmatica per piccoli progetti

Priorità dell'utente: sviluppo unattended a costo sostenibile, con funzionalità realmente presenti e funzionanti. Non interessa accumulare codice, migliaia di test o coverage fine a sé stessa. I controlli devono essere severi sui comportamenti importanti.

La successiva valutazione dei costi orienta verso una configurazione più snella della gerarchia iniziale. È una proposta di partenza da misurare, non una configurazione già implementata o un risparmio dimostrato:

- Astra prepara con l'utente specifica della funzionalità, esempi di accettazione, confini e decisioni difficili. Evitare di ripetere l'analisi completa per ogni microtask.
- Sol è l'esecutore predefinito, un task alla volta, mantenendo il contesto utile durante le correzioni.
- Una sessione Sol indipendente revisiona il risultato dopo i gate. Riceve contratto, diff ed evidenze, con accesso al contesto di codice necessario; non eredita tutte le giustificazioni dell'esecutore. L'indipendenza di sessione non elimina i punti ciechi comuni del modello.
- Astra interviene per escalation difficili, modifiche del contratto o revisioni particolarmente delicate, anziché in ogni passaggio ordinario.
- Dispatcher, CI, merge e release seguono regole deterministiche e autorizzazioni concordate: nessun modello usato per attendere o interrogare continuamente lo stato.
- Introdurre Terra o Luna in categorie delimitate di task solo se i risultati mostrano un vantaggio reale. Nessun parallelismo obbligatorio per piccoli progetti.
- Se il watcher esistente funziona, valutarne il riuso prima di spendere per sostituire Herd: eliminarlo non è un obiettivo superiore a costo ed efficacia.

Percorso proposto: specifica ed esempi → test di accettazione protetti → implementazione Sol → gate CI → review indipendente → integrazione verificata → release secondo policy. Astra è coinvolto dove serve giudizio aggiuntivo.

Le sezioni successive sui gate e sull'isolamento valgono per entrambe le composizioni. I riferimenti originari ad Astra come revisore si applicano al revisore designato nella variante snella.

## Variante iniziale: gerarchia Astra, Luna, Sol

Conservata come alternativa, non come percorso obbligatorio della proposta più economica.

- Astra definisce piano, backlog, contratti dei task e criteri di accettazione. Revisiona le PR che superano i gate e assume la responsabilità di merge e release entro le autorizzazioni concordate.
- Luna prende un task definito, implementa nel proprio branch/worktree, esegue le verifiche e apre la PR.
- Sol interviene quando Luna non riesce a risolvere un problema tecnico. Riceve problema, tentativi, errori, file coinvolti e test falliti; può correggere direttamente oppure guidare Luna.
- L'escalation ordinaria è Luna → Sol: non si torna immediatamente ad Astra per una difficoltà tecnica.
- Astra viene coinvolto se occorre cambiare requisiti, architettura, interfacce o scope, oppure se anche Sol non riesce a risolvere.
- Durante un intervento diretto di Sol, Luna sospende le modifiche sugli stessi file. Un solo responsabile alla volta delle scritture sovrapposte.

Percorso: Astra definisce il task → Luna implementa → eventuale supporto Sol → PR → gate meccanici → review Astra → eventuali correzioni e nuovi gate → merge → release.

## Principi della revisione e contratto del task

Astra rivede il diff della PR, non un terminale. Nessuno scraping del terminale come fonte della review e nessun troncamento silenzioso del diff.

Ogni task deve definire obiettivo, scope consentito, componenti modificabili, interfacce/formati da rispettare, criteri di accettazione, verifiche richieste e limiti di dimensione del diff.

Il contratto e la revisione devono riferirsi a una base e a una revisione della PR identificabili. Qualsiasi aggiornamento del codice rende necessari nuovi controlli e una decisione di review riferita al risultato aggiornato.

Il numero di file da solo non limita la dimensione del diff: prevedere anche una soglia di dimensione. Se il lavoro la supera, suddividere il task invece di troncare il contenuto sottoposto ad Astra.

## Gate obbligatori

1. Un controllo meccanico verifica scope e dimensione rispetto al contratto. File fuori scope: respingere la PR prima della review semantica.
2. CI esegue test, lint e build pertinenti al task. I fallimenti tornano a Luna/Sol.
3. Solo dopo il superamento dei gate, Astra esamina contratto, diff completo ed evidenze dei controlli. Valuta correttezza, qualità e aderenza all'intento.
4. Le protezioni del branch impongono le condizioni di merge. Le sole istruzioni nel prompt o in AGENTS.md non sostituiscono questi vincoli tecnici.
5. La release segue un workflow e autorizzazioni espliciti; assegnare questo ruolo ad Astra non autorizza automaticamente ogni pubblicazione.

Principio centrale: automazione per i controlli deterministici, Astra per il giudizio.

## Isolamento, integrazione e verbale

Git e PR sono il punto di passaggio verificabile del lavoro. Non occorre aprire manualmente un terminale Codex per ogni sottoagente.

I sottoagenti non implicano automaticamente worktree separati. Per questo workflow di implementazione, predisporre branch e worktree dedicati ai task, preservando dev fino all'accettazione.

Una PR rifiutata può essere chiusa e il lavoro isolato scartato senza modificare dev. Questo vale per le modifiche isolate al codice: non annulla eventuali effetti su database, servizi o ambienti condivisi. Il workflow deve impedire tali effetti non autorizzati.

Il verbale deve consentire di ricostruire task, modifiche, verifiche e ragioni dell'accettazione attraverso PR, risultati CI, decisioni di review e cronologia Git. Gli interventi e i modelli utilizzati possono essere registrati nel registro esterno dell'orchestrazione, senza introdurre attribuzioni AI nella repository o nella cronologia Git.

## Composizione senza Herd

- Codex orchestra la squadra e lo scambio di incarichi e risultati.
- Git/worktree isolano le modifiche; PR e diff espongono il risultato da revisionare.
- CI applica i gate; protezioni del branch e workflow di pubblicazione regolano merge e release.
- Una sessione Codex attiva può coordinare il ciclo interattivo.
- Per elaborare il backlog anche dopo la chiusura della sessione serve un dispatcher/watcher persistente che rilevi eventi, esiti CI e richieste di revisione e avvii il lavoro necessario. La funzione non scompare per il solo fatto di usare sottoagenti.
- I modelli dei sottoagenti vanno selezionati o configurati esplicitamente: Astra come principale non implica automaticamente Luna e Sol nei rispettivi ruoli.

## Costi, efficienza e limiti del ciclo unattended

Il costo va misurato per task accettato, includendo letture del contesto, implementazione, correzioni, review, escalation e risorse CI. Il modello con il prezzo per token più basso non è necessariamente il più economico a lavoro concluso.

Non sono state stabilite tariffe, stime di spesa o percentuali di risparmio. Distinguere tariffazione API (modello, input/output e cache) da limiti e consumi dell'abbonamento Codex. Confrontare configurazioni su task rappresentativi, registrando anche tempo, fallimenti e difetti emersi dopo l'accettazione.

Evitare passaggi sistematici Luna → Sol → Astra, letture ripetute dell'intera repository, PR per ogni modifica minima e log integrali nel contesto. Conservare gli artefatti completi e passare al modello gli errori pertinenti; non troncare il diff necessario alla review. Una PR deve restare una funzionalità o modifica coerente e sufficientemente piccola.

Limiti iniziali proposti, ancora da approvare e tarare: due cicli di correzione Sol, poi un intervento Astra entro un budget esplicito. Se resta bloccato, parcheggiare il task con diagnosi e proseguire solo con attività indipendenti. Definire anche limiti di tempo e consumo.

Unattended significa lavorare senza presenza continua dell'utente, non dover completare o pubblicare a qualsiasi costo. Vietare controlli saltati, indebolimento delle verifiche e ripetizioni fino a ottenere casualmente un esito verde. Controlli mancanti o falliti impediscono l'accettazione. I test instabili richiedono diagnosi e gestione esplicita.

Verificare anche il risultato dell'integrazione e pubblicare l'artefatto verificato. Staging con smoke test è il punto di partenza proposto; condizioni di produzione e autorizzazioni restano da definire.

## Funzionalità prima del codice: ATDD e TDD

Orientamento consolidato: guidare il processo con test di accettazione (ATDD), usando TDD tecnico dove aiuta. Il successo è un comportamento osservabile dall'utente, non la presenza di metodi, pulsanti o chiamate a mock.

Esempi:

- Debole: il metodo di salvataggio viene chiamato. Accettazione: dopo salvataggio e riapertura, il dato esiste ancora.
- Debole: esiste un pulsante. Accettazione: azionandolo, l'operazione termina e il risultato corretto è visibile.
- Feature clienti: si può creare un cliente, un duplicato viene rifiutato e il cliente rimane disponibile dopo il riavvio.

Procedura:

1. Definire con l'utente esempi osservabili, percorso principale, errori importanti e casi limite rilevanti prima di implementare.
2. Preparare una suite di accettazione derivata dai requisiti e revisionata separatamente dall'implementazione. Verificare che i nuovi test falliscano per il comportamento mancante, non per un ambiente rotto.
3. Proteggere la suite e il contratto: l'esecutore può aggiungere test tecnici, ma non cambiare autonomamente le condizioni di promozione. Correzioni legittime al contratto passano da un percorso separato.
4. Implementare fino al superamento dei test e conservare anche le regressioni pertinenti.
5. Revisionare sia la soluzione sia l'adeguatezza degli scenari alla richiesta. Se il contratto è ambiguo o sbagliato, segnalarlo senza ridefinire unilateralmente il successo.

Pochi scenari scelti bene possono bastare per una piccola feature. Coverage alta non dimostra correttezza; nessuna suite dimostra assenza di bug. Valutare mutation testing mirato alla logica critica per verificare che i test rilevino errori deliberati, senza applicarlo indiscriminatamente.

## Browser headless e automazione dell'accettazione/UAT

Per app web, Selenium è una possibilità e Playwright un candidato per nuovi piccoli progetti. Nessuno strumento è stato scelto definitivamente; la scelta dipende dallo stack e dagli strumenti già presenti.

Il browser può girare headless, senza finestra visibile, ed eseguire azioni reali: aprire pagine, compilare moduli, premere pulsanti e verificare risultati visibili.

Esempio di scenario: aprire Clienti → creare Mario Rossi → verificare conferma → ricaricare → cercare Mario Rossi → verificare la presenza del cliente salvato.

Automazione proposta per ogni PR:

1. Avviare un ambiente isolato con applicazione, database di test e dati iniziali riproducibili.
2. Eseguire test API e integrazione per dati e regole di business, più pochi scenari browser sui percorsi utente essenziali.
3. Usare componenti reali dove necessario a dimostrare il comportamento. Un mock che risponde sempre OK non prova l'integrazione reale; distinguere cosa è simulato e cosa è verificato.
4. Conservare report, log e screenshot; aggiungere trace/video se disponibili e utili a diagnosticare i fallimenti.
5. Bloccare il merge se uno scenario obbligatorio fallisce o non viene eseguito.

Non spostare tutti i controlli nel browser: aumenterebbe tempi e fragilità. Usare il livello più semplice che dimostri il comportamento, mantenendo end-to-end essenziali sul prodotto reale.

Si automatizzano i criteri di accettazione ripetibili. La UAT comprende anche il giudizio dell'utente su utilità, comprensibilità e adeguatezza del prodotto: prevedere una verifica umana mirata della prima versione e dei cambiamenti di comportamento significativi, senza far ricliccare gli stessi percorsi a ogni PR.

## Decisioni ancora da prendere prima dell'implementazione

- Repository, hosting Git/CI e branch di destinazione effettivi.
- Sessione interattiva oppure dispatcher persistente; eventuali parti di Herd/watcher da conservare.
- Formato e posizione del backlog e dei contratti, con protezione delle regole rispetto al codice del task.
- Soglie di scope/dimensione, comandi di verifica e criteri misurabili di escalation. Due tentativi diversi senza progresso era un esempio discusso, non una soglia approvata.
- Permessi dei ruoli, condizioni obbligatorie di review/merge, politica di release e autorizzazioni di pubblicazione.
- Persistenza degli stati, gestione di interruzioni e ripartenze, limiti di concorrenza/costo e registro dell'orchestrazione.
- Conferma della variante snella, criteri per review/escalation Astra e categorie eventualmente affidate a Terra/Luna.
- Stack applicativo, suite esistente, scelta Selenium/Playwright o riuso degli strumenti presenti, ambienti e dati di test.
- Responsabilità e protezione della suite di accettazione, scenari critici e momenti di UAT umana.
- Modalità di utilizzo API/abbonamento, budget per task e giornaliero, metriche del confronto tra configurazioni.

## Accordi globali dell'utente

- Pianificare ogni nuovo task e attendere una richiesta esplicita di implementazione/esecuzione prima di realizzare il piano.
- Non creare commit o push con autore, committer, coautore, firmatario o attribuzione diversi dall'identità Git già configurata dall'utente.
- Non cambiare user.name, user.email, identità di firma o metadati di autore/committer.
- Prima di un commit verificare l'identità effettiva; se mancante o diversa, fermarsi e chiedere all'utente.
- Chiarimento esplicito successivo dell'utente: il vincolo riguarda le attribuzioni dei contributi, che devono riferirsi esclusivamente all'utente. È consentito parlare di modelli AI, Codex e sviluppo assistito nei documenti e archiviare questa conversazione. Non aggiungere coautori AI, firme, crediti di contribuzione o trailer generated-by/co-authored-by.

Questo documento può essere conservato nel repository privato Voloire/letscheck, come espressamente richiesto dall'utente. I nomi dei modelli descrivono argomenti e ruoli del workflow, non attribuzioni di contribuzione Git.
