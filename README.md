# AstroChecker

AstroChecker is a small local experiment for checking deep-sky visibility and building a full-night observing sequence from a balcony. It is evolving and makes no promise about compatibility, accuracy, or behavior on a particular computer.

## Run locally

AstroChecker runs from source as a local server and opens the interface in your browser. Calculations, catalogs, and astronomy data are bundled locally; after dependencies are installed, the main features do not need an Internet connection.

You will need:

- a recent Python version compatible with the pins in `requirements.txt`;
- a modern browser;
- Internet access only to install dependencies when they are not already available.

On Windows (PowerShell):

```powershell
py -3 -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe run.py
```

On Linux or macOS:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python run.py
```

The terminal prints `http://127.0.0.1:<port>` if the browser does not open automatically. Stop the server with `Ctrl+C`.

When a result needs a different observing window, AstroChecker shows up to
three real alternatives ranked from **The Best** down with one to five stars.
Choose an option, accept it explicitly, enter a sequence name, and export a
native NINA `CaptureSequenceList` XML file for the Legacy/Simple Sequencer in
the current user's `Downloads` folder. It uses 300-second LIGHT exposures and
calculates the number of complete exposures that fit the accepted window;
other settings remain at NINA defaults. The observing window is not encoded in
the sequence and must be applied manually in NINA. If fewer valid options are
available, only those options are shown.

For a fully local workflow, enter your site coordinates and time zone manually. Optional browser geolocation may use your operating system or browser location services.

## Tests and contributions

Install development tools and run the suite:

```bash
python -m pip install -r requirements-dev.txt
python -m pytest -q
```

Browser tests also need Chromium installed through Playwright. Contributions are welcome through pull requests; see [`CONTRIBUTING.md`](CONTRIBUTING.md).

See [`ASTROCHECKER.md`](ASTROCHECKER.md) for app behavior and [`FONTI-DATI.md`](FONTI-DATI.md) for data sources and licenses.
