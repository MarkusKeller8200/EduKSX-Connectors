#!/usr/bin/env python3
"""Alle Prüfungen des Repos: Tests jeder API in apis/<name>/, gültige Version in deren api.json, gültige
Plugin-Beschreibung (#42: jeder Endpunkt beschrieben, schreibende mit «danger», Version = api.json) sowie Tests von
shared/ und der Testplattform.

    python3 pruefen.py              alles
    python3 pruefen.py escola       nur eine API (bzw. «testplattform», «shared»)

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
sys.path.insert(0, str(HIER))
from shared.plugin_export import manifest, pruefen as manifest_pruefen  # noqa: E402

SEMVER = re.compile(r"^\d+\.\d+\.\d+$")


def apis(auswahl: list[str]) -> list[Path]:
    alle = sorted(p for p in (HIER / "apis").iterdir() if p.is_dir() and (p / "api.json").exists())
    return [p for p in alle if not auswahl or p.name in auswahl]


def plugin_pruefen(api: Path, info: dict) -> list[str]:
    """OpenAPI der API erzeugen (ohne Netzwerk), daraus das Plugin-Manifest, dann prüfen."""
    paket = f"{info.get('name', api.name).lstrip('_')}_api"
    code = f"import json; from {paket}.app import app; print(json.dumps(app.openapi()))"
    r = subprocess.run([sys.executable, "-c", code], cwd=api, capture_output=True, text=True)
    if r.returncode != 0:
        return [f"{api.name}: OpenAPI nicht erzeugbar: {r.stderr.strip().splitlines()[-1] if r.stderr else '?'}"]
    m = manifest(json.loads(r.stdout), info)
    probleme = manifest_pruefen(m, info)
    print(f"Plugin-Beschreibung: {len(m['service']['endpoints'])} Endpunkte, "
          f"{'in Ordnung' if not probleme else f'{len(probleme)} Probleme'}")
    return [f"{api.name}: {p}" for p in probleme]


def weitere(auswahl: list[str]) -> list[Path]:
    return [p for p in (HIER / "shared", HIER / "testplattform")
            if (p / "tests").is_dir() and (not auswahl or p.name in auswahl)]


def main() -> int:
    fehler = []
    auswahl = sys.argv[1:]
    liste = apis(auswahl)
    if not liste and not weitere(auswahl):
        print("Keine API gefunden (apis/<name>/api.json).")
        return 1
    for ordner in weitere(auswahl):
        print(f"\n=== {ordner.name} ===", flush=True)
        if subprocess.run([sys.executable, "-m", "pytest", "-q"], cwd=ordner).returncode != 0:
            fehler.append(f"{ordner.name}: Tests fehlgeschlagen")
    for api in liste:
        print(f"\n=== {api.name} ===", flush=True)
        try:
            version = json.loads((api / "api.json").read_text(encoding="utf-8")).get("version", "")
        except ValueError as e:
            version = ""
            print(f"api.json ungültig: {e}")
        else:
            fehler += plugin_pruefen(api, json.loads((api / "api.json").read_text(encoding="utf-8")))
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
