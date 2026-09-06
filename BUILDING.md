# Build Windows

La release Windows viene costruita su `windows-latest` dal workflow
`Windows release`. Per una prova locale su Windows installa Python 3.13, poi
esegui:

```powershell
python -m pip install -r requirements.txt -r requirements-build.txt
pyinstaller --clean --noconfirm packaging/AstroChecker.spec
dist\AstroChecker.exe --no-browser --port 0
```

La build è un singolo eseguibile `dist\AstroChecker.exe`. Il catalogo e i dati
astronomici sono incorporati; le impostazioni dell’utente restano in
`%LOCALAPPDATA%\AstroChecker`.
