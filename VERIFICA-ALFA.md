# Verifica storica — alfa con SkyChart

## Criteri ATDD

La suite `tests/test_acceptance.py` è stata scritta prima del motore: i primi 21 esempi hanno fallito su funzioni ancora non implementate. I casi aggiunti durante la revisione hanno rilevato difetti reali prima della correzione. Il motore non può modificare questa suite per cambiare il significato dell'accettazione.

La verifica finale ha prodotto **73 test superati in 11,43 secondi**: 26 esempi protetti e 47 controlli di protocollo, input, conversione astronomica, HTTP e interfaccia. Sono inclusi quattro test browser per altezze negative, valori iniziali, risultati parziali brevi e orari al cambio dell'ora legale. La compilazione sintattica di Python e il controllo sintattico JavaScript sono riusciti.

## Collegamento reale a SkyChart

Prove effettuate su SkyChart 4.2.1, senza sostituire il server con risposte simulate:

| Scenario | Esito osservato |
| --- | --- |
| Arturo, Chiusanico, 5 settembre 2026 alle 17:20 CEST | Altezza geometrica 64,0704°, azimut 198,6865°; confronto manuale SkyChart entro 0,15° |
| M13, 22:00–02:00, altezza 30°–90°, intero azimut | Parziale: 9.335 secondi continui, fino alle 00:35:35; nessuna finestra di quattro ore nel periodo analizzato |
| M13, richiesta di 30 minuti dalle 15:00, altezza 0°–90° | Non visibile nel periodo diurno richiesto; prima finestra completa successiva trovata |
| Latitudine 91° | Errore di validazione HTTP 400, nessun risultato astronomico fittizio |
| Fine delle analisi | Carta attiva, elenco carte, data, osservatorio e fuso originali conservati |

I due calcoli HTTP reali di M13 hanno richiesto rispettivamente 84,61 e 74,11 secondi. Il calcolo completo di Arturo ha richiesto 64,02 secondi. Si tratta di misure di questa macchina/installazione, non di una garanzia di latenza.

Il confronto dell'interpolazione del Sole con 24 coordinate intermedie interrogate direttamente il 5 settembre 2026 ha mostrato uno scarto angolare massimo di 0,0000438261° e uno scarto massimo in altezza di 0,0000250029°. È una verifica locale, non un limite garantito per ogni data. Pianeti, Luna, comete e altri bersagli mobili restano esclusi dal perimetro dell'alfa.

Ripetizione delle prove API, con il server AstroChecker avviato:

```powershell
.\.venv\Scripts\python.exe tests\verify_live.py http://127.0.0.1:PORTA
```

Le risposte complete e il confronto dello stato sono in `artifacts/`, esclusa da Git.

## Browser reale

`tests/verify_browser.py` ha verificato il blocco iniziale del modulo, una risposta di connessione fallita esplicitamente simulata e il successivo collegamento reale. Le richieste astronomiche successive hanno usato SkyChart reale: M13 visibile per tutta la mezz'ora dalle 23:00, nessuna soluzione con altezza massima 1°, errore distinto per un nome inesistente. Nessun errore JavaScript e nessuno scorrimento orizzontale a 390 pixel di larghezza.

Le prove con risposte simulate servono solo a verificare presentazione e casi limite dell'interfaccia; non costituiscono evidenza astronomica.

Dopo il riavvio del server con tutte le correzioni, un'ulteriore prova browser reale ha confermato M13 visibile per l'intera durata, il rifiuto esplicito del Sole come bersaglio mobile, assenza di errori JavaScript e impaginazione desktop/mobile. Le schermate finali mostrano correttamente anche la traiettoria sotto l'orizzonte. Risposta finale: `artifacts/live-final.json`.
