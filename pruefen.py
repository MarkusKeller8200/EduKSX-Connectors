#!/usr/bin/env python3
"""Alle Prüfungen des Repos: Tests jeder API in apis/<name>/ und gültige Version in deren api.json.

    python3 pruefen.py              alle APIs
    python3 pruefen.py escola       nur eine API

Jede API läuft in ihrem eigenen Ordner (eigene Abhängigkeiten, eigenes Paket). Fehlen die Pakete einer API,
zuerst `pip install -r apis/<name>/requirements.txt`.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

HIER = Path(__file__).resolve().parent
SEMVER = re.compile(r"^\d+\.\d+\.\d+$")


def apis(auswahl: list[str]) -> list[Path]:
    alle = sorted(p for p in (HIER / "apis").iterdir() if p.is_dir() and (p / "api.json").exists())
    return [p for p in alle if not auswahl or p.name in auswahl]


def main() -> int:
    fehler = []
    liste = apis(sys.argv[1:])
    if not liste:
        print("Keine API gefunden (apis/<name>/api.json).")
        return 1
    for api in liste:
        print(f"\n=== {api.name} ===", flush=True)
        try:
            version = json.loads((api / "api.json").read_text(encoding="utf-8")).get("version", "")
        except ValueError as e:
            version = ""
            print(f"api.json ungültig: {e}")
        if not SEMVER.match(str(version)):
            fehler.append(f"{api.name}: api.json ohne gültige Version (z. B. 1.2.0)")
        if (api / "tests").is_dir():
            r = subprocess.run([sys.executable, "-m", "pytest", "-q"], cwd=api)
            if r.returncode != 0:
                fehler.append(f"{api.name}: Tests fehlgeschlagen")
        else:
            fehler.append(f"{api.name}: Ordner tests/ fehlt")
    print()
    for f in fehler:
        print("✗", f)
    print("✓ alle Prüfungen bestanden" if not fehler else f"{len(fehler)} Fehler")
    return 1 if fehler else 0


if __name__ == "__main__":
    sys.exit(main())
