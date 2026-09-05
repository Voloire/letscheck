# letscheck

**[AstroChecker — pagina pubblica del progetto](https://voloire.github.io/letscheck/)** · [Release v0.4.0-alpha.1](https://github.com/Voloire/letscheck/releases/tag/v0.4.0-alpha.1)

Archivio privato del contesto e delle decisioni per sperimentare uno sviluppo unattended di piccoli progetti, con costi sostenibili e accettazione basata sulle funzionalità.

## ATDD in evidenza

**Prima definiamo cosa l'utente deve poter fare; poi proteggiamo i test che dimostrano quel comportamento. L'implementazione deve soddisfare i criteri, non modificarli per ottenere il verde.**

ATDD guida il processo. TDD tecnico, test API e integrazione lo sostengono; pochi scenari browser headless coprono i percorsi essenziali. La UAT umana rimane mirata a utilità e comprensibilità del prodotto.

## Documenti

- [CONTEXT.md](CONTEXT.md): punto di ripartenza, priorità e decisioni aperte.
- [workflow-multiagente.md](workflow-multiagente.md): riepilogo completo, variante snella, gerarchia alternativa, gate e ATDD/UAT.
- [conversazione.md](conversazione.md): messaggi storici originali, comprese le parti iniziali su Slack, Windows e Ubuntu.
- [AGENTS.md](AGENTS.md): accordi di lavoro e regole sulle attribuzioni.
- [CHANGELOG.md](CHANGELOG.md): versioni dell'archivio.

## Riprendere il progetto

Aprire questa cartella e chiedere: «Leggi AGENTS.md, CONTEXT.md e workflow-multiagente.md. Mantieni ATDD come criterio centrale. Pianifichiamo un progetto di prova senza implementare finché non lo richiedo».

La versione v0.1.0 è un archivio di progettazione: non contiene un'applicazione né configura CI, watcher, merge o deployment automatici. Stack, budget e progetto pilota sono ancora da scegliere.

La trascrizione è storica: dichiarazioni tecniche, disponibilità dei prodotti e prezzi devono essere verificati quando riutilizzati. In caso di evoluzioni della discussione, CONTEXT.md e il workflow descrivono l'orientamento più recente.

AstroChecker include anche **Cerchi Idee?**, un planner locale che costruisce una catena di bersagli per l'intera notte astronomica, dal crepuscolo serale a quello mattutino. Rispetta la finestra reale del balcone, mostra blocchi e intervalli scoperti e prepara i dati per una futura esportazione NINA senza effettuarla.

## Versionamento

Repository previsto: `Voloire/letscheck`, privato. Prima versione: `v0.1.0`. Usare commit descrittivi e tag per i consolidamenti successivi, mantenendo esclusivamente l'identità Git già configurata dall'utente.
