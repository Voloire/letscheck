@echo off
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo Ambiente Python mancante.
  echo Crearlo con: py -m venv .venv
  echo Poi installare le dipendenze con: .venv\Scripts\python.exe -m pip install -r requirements.txt
  pause
  exit /b 1
)
".venv\Scripts\python.exe" run.py
set "ASTROCHECKER_EXIT=%errorlevel%"
if not "%ASTROCHECKER_EXIT%"=="0" (
  echo AstroChecker si e chiuso a causa di un errore.
  pause
  exit /b %ASTROCHECKER_EXIT%
)
