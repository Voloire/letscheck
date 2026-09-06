@echo off
cd /d "%~dp0"
if not exist "AstroChecker.exe" (
  echo AstroChecker.exe non trovato.
  echo Scarica l'eseguibile dalla sezione Releases del repository.
  pause
  exit /b 1
)
AstroChecker.exe
