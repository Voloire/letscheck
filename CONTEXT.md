# Contesto per riprendere letscheck

Consolidamento iniziale: 5 settembre 2026, v0.1.0.

## Obiettivo

Sperimentare sviluppo unattended di piccoli progetti, con controllo del costo per funzionalità accettata. L'utente vuole feature effettive e utilizzabili, non quantità di codice, test o coverage.

## Orientamento più recente

- ATDD: esempi di accettazione concordati prima dell'implementazione, suite protetta e verifica del comportamento reale.
- Configurazione snella proposta: Sol implementa; una sessione indipendente revisiona dopo CI; Astra definisce l'accettazione iniziale e interviene nelle eccezioni difficili.
- Luna/Terra non sono passaggi obbligatori: usarli quando misure su categorie di task ne dimostrano la convenienza.
- Variante iniziale conservata: Astra pianifica/revisiona, Luna implementa, Sol risolve i blocchi tecnici prima dell'escalation ad Astra.
- Git/PR sono il passaggio verificabile; review del diff completo, nessuno scraping del terminale, gate meccanici prima del giudizio.
- Scope e dimensione del diff limitati, branch/worktree isolati, controlli obbligatori e verifiche legate alla revisione effettivamente integrata.
- Il dispatcher coordina in modo deterministico e persistente; non consumare chiamate al modello per attendere CI. Valutare il riuso del watcher/Herd già esistenti prima di sostituirli.
- Unattended include arresto e diagnosi dei task irrisolti: nessun ciclo infinito, indebolimento dei test o pubblicazione forzata.

## ATDD e UAT

Per ogni feature: percorso principale, errori importanti e casi limite pertinenti. Scrivere e revisionare i criteri prima di implementare; verificare che il test fallisca per la feature mancante. L'esecutore non può ridefinire unilateralmente la promozione.

Test API/integrazione per dati e regole, pochi test browser headless per i flussi essenziali. Selenium e Playwright sono candidati, non una scelta effettuata. Ambiente isolato, dati riproducibili, report e artefatti dei fallimenti. Nessun mock universale che faccia sembrare funzionante un'integrazione non verificata.

UAT automatizzata significa ripetere criteri verificabili; l'utente valuta utilità ed esperienza nella prima versione e nei cambiamenti significativi. Mutation testing mirato è un'opzione per la logica critica, non un requisito indiscriminato.

## Da decidere con il progetto pilota

1. Prodotto, utenti, feature iniziale e scenari di accettazione.
2. Stack, repository applicativo, CI, ambiente isolato e servizi esterni.
3. Budget API o limiti dell'abbonamento, limite per task/giorno e misure di costo per task accettato.
4. Composizione definitiva dei modelli e policy di escalation; due cicli di correzione più un intervento Astra è una proposta da tarare.
5. Protezione del contratto e della suite, gestione dei test instabili, autorizzazioni di merge/staging/produzione.
6. Dispatcher esistente o nuovo, riavvio dopo interruzioni e registro degli stati.

## Chiarimento vincolante sulle attribuzioni

L'utente ha chiarito che il divieto riguarda le attribuzioni dei contributi, non il parlare di AI. I documenti possono discutere Codex, Astra, Sol, Luna e sviluppo assistito. Autore, committer, firma e attribuzioni dei contributi devono rimanere esclusivamente quelli dell'utente; non aggiungere coautori, crediti o trailer AI e non cambiare l'identità Git.

## Stato e limiti dell'archivio

Questo repository conserva il contesto, non implementa il workflow. La trascrizione contiene anche argomenti precedenti estranei al progetto pilota. Non copiarne automaticamente valutazioni tecniche o configurazioni nel nuovo prodotto.

Leggere il workflow completo per i dettagli e la conversazione per la motivazione delle decisioni. La richiesta corrente autorizza creazione dell'archivio privato, commit iniziale, push e tag; non autorizza la realizzazione o pubblicazione di un futuro prodotto non ancora definito.
