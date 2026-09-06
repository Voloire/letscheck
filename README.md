# AstroChecker

AstroChecker è un semplice esperimento per verificare la visibilità di
bersagli del cielo profondo e costruire una sequenza per l’intera notte dal
balcone. Il progetto è in evoluzione e non offre garanzie di compatibilità,
precisione o funzionamento su una macchina specifica.

## Esecuzione locale

L’applicazione gira dal sorgente su un server locale e apre l’interfaccia nel
browser. I calcoli, il catalogo e i dati astronomici usati dal motore sono
locali; dopo l’installazione delle dipendenze non è richiesta una connessione
per eseguire le funzioni principali.

Prerequisiti indicativi:

- Python recente compatibile con le versioni fissate in `requirements.txt`;
- un browser moderno;
- accesso a Internet solo per installare le dipendenze, se non sono già
  disponibili localmente.

Su Windows crea l’ambiente e avvia il server con PowerShell:

```powershell
py -3 -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe run.py
```

Su Linux o macOS usa i comandi equivalenti:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python run.py
```

Il terminale mostra l’indirizzo `http://127.0.0.1:<porta>` da aprire se il
browser non viene avviato automaticamente. Arresta il server con `Ctrl+C`.

Per mantenere l’uso strettamente locale, inserisci manualmente coordinate e
fuso della postazione. La geolocalizzazione opzionale del browser può usare i
servizi di posizione del sistema o del browser.

## Verifiche e contributi

Per installare gli strumenti di sviluppo:

```bash
python -m pip install -r requirements-dev.txt
python -m pytest -q
```

I test browser richiedono inoltre l’installazione di Chromium tramite
Playwright. Le modifiche arrivano tramite pull request; consulta
[`CONTRIBUTING.md`](CONTRIBUTING.md) per il flusso essenziale.

La documentazione applicativa è in [`ASTROCHECKER.md`](ASTROCHECKER.md). Le
fonti e le condizioni dei dataset sono in [`FONTI-DATI.md`](FONTI-DATI.md).
