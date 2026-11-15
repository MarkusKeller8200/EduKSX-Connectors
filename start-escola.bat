@echo off
rem Escola-API lokal starten (Windows). Doppelklick genuegt.
rem Beim ersten Start: Python-Umgebung + Pakete einrichten, .env anlegen.
setlocal
cd /d "%~dp0apis\escola"

set "PY="
where py >nul 2>nul && set "PY=py -3"
if not defined PY (where python >nul 2>nul && set "PY=python")
if not defined PY (
  echo Python 3.12 oder neuer fehlt. Bitte von https://www.python.org/downloads/ installieren
  echo und beim Installieren "Add python.exe to PATH" ankreuzen.
  pause
  exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
  echo Richte Python-Umgebung ein ...
  %PY% -m venv .venv || (echo Konnte .venv nicht anlegen. & pause & exit /b 1)
  ".venv\Scripts\python.exe" -m pip install --upgrade pip >nul
  ".venv\Scripts\python.exe" -m pip install -r requirements.txt || (echo Paket-Installation fehlgeschlagen. & pause & exit /b 1)
)

".venv\Scripts\python.exe" start_lokal.py %*
pause
