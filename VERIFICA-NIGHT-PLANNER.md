# Verifica del planner notturno — v0.4.0-alpha.1

Data del gate: 2026-09-06, fuso Europe/Rome.

## Perimetro verificato

- Piano dal crepuscolo astronomico serale a quello mattutino della data civile scelta.
- Sequenza cronologica di bersagli compatibili con altezza e azimut del balcone.
- Priorita alla copertura, blocchi preferiti di almeno due ore e riempimenti brevi espliciti soltanto quando utili.
- Gap espliciti, dati con offset e timestamp assoluti predisposti per una futura esportazione NINA.
- Vista dedicata, acknowledgement `Proposta acquisita` e chiusura del selettore data/ora dopo i minuti completi.

## Gate automatico finale

Comandi eseguiti dalla radice del repository con Python della `.venv`, directory temporanea scrivibile e browser Playwright gia installato:

```powershell
python -m compileall -q astrochecker tests
node --check astrochecker\static\app.js
git diff --check
python -m pytest -q
```

Esito: controlli sintattici e whitespace senza errori; **216 test passati in 40,66 secondi**, zero fallimenti e zero errori.

Le regressioni dedicate coprono anche:

- piu di dodici candidati visibili senza tagli arbitrari;
- divieto di abbreviare un bersaglio che dispone di una finestra di due ore;
- ponte breve ritagliato sulla griglia per evitare sovrapposizioni e coprire un gap;
- catalogo fornito fuori ordine, riordinato prima della valutazione progressiva per priorita;
- variazione della sequenza con i limiti del balcone;
- conversione assoluta dei gap e assenza di notte astronomica anche nella UI;
- input puri frazionari, booleani, duplicati o malformati rifiutati esplicitamente.

## Smoke test reale localhost

Server: `http://127.0.0.1:53163/`, catalogo SQLite reale ed effemeridi offline.

Input:

- postazione: latitudine 43.9729, longitudine 7.9944, Europe/Rome;
- data civile: 2026-09-06;
- altezza: 10–30 gradi;
- azimut: 0–360 gradi;
- durata del calcolo singolo: 60 minuti, deliberatamente non usata come durata del piano notturno.

Risposta API misurata in **1,421 secondi**:

- stato `full`, copertura 100%;
- notte: 2026-09-06 21:40 CEST → 2026-09-07 05:15 CEST;
- catena: `NGC 6590 → NGC 5447 → NGC 3587`;
- 14.443 candidati compatibili nel catalogo, 608 valutati per classi complete di priorita, 13.835 non necessari dopo il raggiungimento della copertura completa senza riempimenti brevi.

Lo smoke browser completo ha impiegato **2,11 secondi**: risposta HTTP 200, pannello dedicato visibile, risultato singolo nascosto, tre righe coerenti con l'API, catena con frecce, nessun errore JavaScript e nessun overflow orizzontale a 390 × 844. Screenshot diagnostico locale: `.runtime/night-plan-live.png` (ignorato da Git).

## Review indipendente

Due passaggi di review in sola lettura hanno individuato e fatto correggere prima del gate:

- un limite arbitrario a dodici candidati;
- blocchi brevi evitabili;
- valutazione iniziale dell'intero catalogo;
- un ponte breve sovrapposto che lasciava cinque minuti scoperti;
- dipendenza implicita dall'ordine restituito dal catalogo;
- scenari ATDD mancanti per balcone, gap assoluti e assenza di notte.

Dopo le correzioni non risultano issue critiche. L'ultima issue importante riprodotta, relativa al ponte breve, e protetta da una regressione e inclusa nel gate finale.

## Limiti dichiarati

- Meteo, Luna, qualita del cielo, attrezzatura, meridian flip, slew, autofocus, filtri e overhead operativi non sono valutati.
- La griglia temporale del piano e di cinque minuti.
- `Esporta in NINA` e intenzionalmente disabilitato in questa release; il contratto conserva gia nome, tipo, coordinate, alias, inizio e fine dei blocchi.
- A latitudini o date senza un intervallo astronomico completo nel giorno locale noon-to-noon, il risultato e esplicitamente `none`.
