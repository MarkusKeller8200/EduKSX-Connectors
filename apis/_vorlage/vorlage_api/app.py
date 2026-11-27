"""Gerüst einer neuen API – siehe apis/_vorlage/README.md und docs/konventionen.md."""
from __future__ import annotations

import json
from pathlib import Path

import os

from fastapi import Depends, FastAPI, Header, HTTPException

PRAEFIX = "VORLAGE_"  # z. B. "INTUNE_"
API_KEY = os.environ.get(PRAEFIX + "API_KEY", "")
SCHREIBEN = os.environ.get(PRAEFIX + "SCHREIBEN", "0") == "1"


def api_key_pruefen(x_api_key: str | None = Header(None)):
    if API_KEY and x_api_key != API_KEY:
        raise HTTPException(401, "X-API-Key fehlt oder ist falsch")


def schreib_check(probelauf: bool = False):
    if probelauf:
        return
    if not SCHREIBEN:
        raise HTTPException(403, f"Schreiben ist deaktiviert ({PRAEFIX}SCHREIBEN=1 setzen)")
    if not API_KEY:
        raise HTTPException(403, f"Zum Schreiben muss {PRAEFIX}API_KEY gesetzt sein")


app = FastAPI(title="Vorlage-API", version=json.loads((Path(__file__).resolve().parent.parent / "api.json").read_text(encoding="utf-8"))["version"], dependencies=[Depends(api_key_pruefen)])


@app.get("/status", tags=["Status"], summary="Version und Schalter")
def status():
    return {"ok": True, "schreiben": SCHREIBEN}


# Plugin-Beschreibung für Testplattform und Intranet (GET /plugin.json, #42). Fehlt shared/ (z. B. im Docker-Image),
# entfällt /plugin.json; die Testplattform erzeugt die Beschreibung dann selbst aus /openapi.json.
def _plugin_json_einbinden(app) -> None:
    import sys
    wurzel = str(Path(__file__).resolve().parents[3])
    if wurzel not in sys.path:
        sys.path.append(wurzel)
    try:
        from shared.plugin_export import einbinden
    except ImportError:
        return
    einbinden(app, Path(__file__).resolve().parents[1])


_plugin_json_einbinden(app)
