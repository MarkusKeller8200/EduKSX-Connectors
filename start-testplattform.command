#!/usr/bin/env bash
# Testplattform lokal starten (macOS: Doppelklick im Finder; Linux: ./start-testplattform.command)
# Startet alle APIs aus apis/ und die Testplattform (Browser öffnet sich). Beim ersten Start: Python-Umgebung + Pakete.
set -e
cd "$(dirname "$0")/testplattform"

PY=""
for p in python3.13 python3.12 python3; do
  if command -v "$p" >/dev/null 2>&1; then PY="$p"; break; fi
done
if [ -z "$PY" ]; then
  echo "Python 3.12 oder neuer fehlt. Bitte von https://www.python.org/downloads/ installieren."
  read -r -p "Enter zum Schliessen" _; exit 1
fi

if [ ! -x ".venv/bin/python" ]; then
  echo "Richte Python-Umgebung ein ..."
  "$PY" -m venv .venv
  .venv/bin/python -m pip install --upgrade pip >/dev/null
  .venv/bin/python -m pip install -r requirements.txt
fi

exec .venv/bin/python start_lokal.py "$@"
