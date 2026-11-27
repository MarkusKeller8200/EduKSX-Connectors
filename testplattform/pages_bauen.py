"""Statische Testplattform für GitHub Pages bauen (#51): Oberfläche + plugins.json, ohne Server.

    python3 testplattform/pages_bauen.py [_site]

Die Seite ruft die APIs direkt aus dem Browser auf; die APIs müssen lokal laufen (start-testplattform) und Aufrufe von
der Pages-Adresse erlauben (EDUKSX_CORS_ORIGINS, Vorgabe https://markuskeller8200.github.io). Keine Zugangsdaten, keine
Personendaten in der Ausgabe – nur Namen, Versionen, Ports und Hinweise aus apis/*/api.json.
"""
from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

HIER = Path(__file__).resolve().parent
REPO = HIER.parent


def plugins(repo: Path = REPO) -> list[dict]:
    aus = []
    for datei in sorted((repo / "apis").glob("*/api.json")):
        info = json.loads(datei.read_text(encoding="utf-8"))
        name = str(info.get("name", datei.parent.name))
        if name.startswith("_"):
            continue
        p = info.get("plugin") or {}
        aus.append({"name": name, "titel": info.get("titel", name), "version": str(info.get("version", "")),
                    "port": p.get("port", 8080), "beschreibung": p.get("beschreibung", ""),
                    "data_notice": p.get("data_notice"), "sitzung": p.get("sitzung"),
                    "status_vorgabe": p.get("status", "partial")})
    return aus


def bauen(ziel: Path) -> Path:
    if ziel.exists():
        shutil.rmtree(ziel)
    (ziel / "static").mkdir(parents=True)
    quelle = HIER / "testplattform" / "static"
    shutil.copy(quelle / "index.html", ziel / "index.html")
    for datei in ("plattform.js", "plattform.css"):
        shutil.copy(quelle / datei, ziel / "static" / datei)
    version = json.loads((HIER / "testplattform.json").read_text(encoding="utf-8"))["version"]
    (ziel / "plugins.json").write_text(json.dumps({"version": version, "modus": "direkt", "plugins": plugins()},
                                                  ensure_ascii=False, indent=2), encoding="utf-8")
    (ziel / ".nojekyll").write_text("", encoding="utf-8")
    return ziel


if __name__ == "__main__":
    print(bauen(Path(sys.argv[1] if len(sys.argv) > 1 else REPO / "_site").resolve()))
