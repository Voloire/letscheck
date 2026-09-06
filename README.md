# AstroChecker

AstroChecker è un pianificatore locale per verificare la visibilità di
bersagli del cielo profondo e costruire una sequenza per l’intera notte dal
balcone. I calcoli e il catalogo inclusi funzionano offline.

## Usare AstroChecker su Windows

Scarica `AstroChecker.exe` dalla [release più recente](https://github.com/Voloire/letscheck/releases), copialo in una cartella a tua scelta e avvialo con un doppio clic. Si apre il browser su un indirizzo locale; l’app non richiede Python, installazione o ambiente virtuale.

`avvia.cmd`, nella stessa cartella dell’eseguibile, è un avvio alternativo da
Windows. La postazione salvata rimane nei dati dell’utente e non viene persa
quando sostituisci l’eseguibile.

## Sviluppo

Per eseguire il codice dal sorgente servono Python 3.13 e le dipendenze in
`requirements.txt`. Le istruzioni per contribuire sono in
[`CONTRIBUTING.md`](CONTRIBUTING.md); i dettagli applicativi sono in
[`ASTROCHECKER.md`](ASTROCHECKER.md).

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe run.py
```

La suite si esegue con `python -m pytest -q`. La CI verifica ogni pull request
e costruisce l’EXE su Windows. I criteri di licenza del codice e dei dataset
sono descritti in [`FONTI-DATI.md`](FONTI-DATI.md) e nei file di licenza
distribuiti con il progetto.
