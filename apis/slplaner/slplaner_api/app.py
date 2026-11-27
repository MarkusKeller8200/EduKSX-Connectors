"""SL-Planer-API: liest Ressourcen, Einheiten, Pensenplanung, Pensen und Personaldossier aus dem SL-Planer
(Seabird AG) und stellt sie IDA, CONNECT und weiteren EduKSX-Modulen einheitlich bereit.

Nur lesend – der SL-Planer bietet keine schreibenden Endpunkte an. Regeln: docs/konventionen.md.
"""
from __future__ import annotations

import base64
import csv
import io
import json
import os
from pathlib import Path
from typing import Literal

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Response
from fastapi.responses import JSONResponse

from .client import BEREICHE, NichtGefunden, SessionAbgelaufen, SLPlanerClient, SLPlanerConfig

PRAEFIX = "SLPLANER_"
API_KEY = os.environ.get(PRAEFIX + "API_KEY", "")
# Mitarbeiterbeurteilungen und Personaldossier sind besonders schützenswert: nur mit eigenem Schalter.
PERSONALDOSSIER = os.environ.get(PRAEFIX + "PERSONALDOSSIER", "0") == "1"
VERSION = json.loads((Path(__file__).resolve().parent.parent / "api.json").read_text(encoding="utf-8"))["version"]

Format = Literal["json", "csv"]
Bereich = Literal[tuple(BEREICHE)]  # type: ignore[valid-type]


def config_aus_env() -> SLPlanerConfig:
    return SLPlanerConfig(
        base_url=os.environ.get(PRAEFIX + "BASE_URL", ""),
        token=os.environ.get(PRAEFIX + "TOKEN", ""),
        auth_schema=os.environ.get(PRAEFIX + "AUTH_SCHEMA", "Bearer"),
        timeout=float(os.environ.get(PRAEFIX + "TIMEOUT", "30")),
    )


_client: SLPlanerClient | None = None


def client() -> SLPlanerClient:
    global _client
    if _client is None:
        _client = SLPlanerClient(config_aus_env())
    if not _client.konfiguriert:
        raise HTTPException(501, f"SL-Planer nicht eingerichtet ({PRAEFIX}BASE_URL und {PRAEFIX}TOKEN setzen)")
    return _client


def api_key_pruefen(x_api_key: str | None = Header(None)):
    if API_KEY and x_api_key != API_KEY:
        raise HTTPException(401, "X-API-Key fehlt oder ist falsch")


def dossier_check():
    if not PERSONALDOSSIER:
        raise HTTPException(403, f"Personaldossier/MAB ist ausgeschaltet ({PRAEFIX}PERSONALDOSSIER=1 setzen)")
    if not API_KEY:
        raise HTTPException(403, f"Für Personaldossier/MAB muss {PRAEFIX}API_KEY gesetzt sein")


app = FastAPI(title="SL-Planer-API", version=VERSION, dependencies=[Depends(api_key_pruefen)],
              description="Lesender Zugriff auf den SL-Planer (Seabird AG): Ressourcen, Einheiten, "
                          "Pensenplanung, Pensen, Personaldossier/MAB. Listen auch mit `?format=csv`.")


@app.exception_handler(SessionAbgelaufen)
def _abgelaufen(_, e):
    return JSONResponse({"detail": str(e)}, status_code=401)


@app.exception_handler(NichtGefunden)
def _fehlt(_, e):
    return JSONResponse({"detail": f"Im SL-Planer nicht gefunden: {e}"}, status_code=404)


# ---------------------------------------------------------------- Hilfen

def _flach(d: dict, praefix: str = "") -> dict:
    """Verschachtelte Objekte (person, einheit, ressourcentyp) für CSV in Spalten auflösen."""
    aus = {}
    for k, v in d.items():
        if isinstance(v, dict):
            aus.update(_flach(v, f"{praefix}{k}_"))
        elif not isinstance(v, list):
            aus[praefix + k] = v
    return aus


def _csv(zeilen: list[dict], name: str) -> Response:
    buf = io.StringIO()
    if zeilen:
        spalten: list[str] = []
        for z in zeilen:
            spalten += [k for k in z if k not in spalten]
        w = csv.DictWriter(buf, fieldnames=spalten, delimiter=";", extrasaction="ignore")
        w.writeheader()
        w.writerows(zeilen)
    return Response("﻿" + buf.getvalue(), media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition": f'attachment; filename="slplaner_{name}.csv"'})


def _antwort(daten: list[dict], format: Format, name: str, zeilen=None):
    if format == "csv":
        return _csv(zeilen(daten) if zeilen else [_flach(d) for d in daten], name)
    return daten


SJ = Query(None, description="Schuljahr, z. B. 2025/26 (Weitergabe an den SL-Planer – Parametername ZU PRÜFEN)")
F = Query("json", description="json oder csv")


# ---------------------------------------------------------------- Status

@app.get("/status", tags=["Status"], summary="Version, eingerichtet ja/nein, Schalter, Anzahl Aufrufe")
def status():
    c = _client or SLPlanerClient(config_aus_env())
    return {"ok": True, "version": VERSION, "konfiguriert": c.konfiguriert, "schreiben": False,
            "personaldossier": PERSONALDOSSIER, "aufrufe_slplaner": c.zaehler}


# ---------------------------------------------------------------- 5.1.3 Ressourcen, 5.1.4 Einheiten

def _ressource_mit_rest(r: dict) -> dict:
    soll, ist = r.get("einh_soll"), r.get("einh_ist")
    if isinstance(soll, (int, float)) and isinstance(ist, (int, float)):
        r = {**r, "einh_rest": round(soll - ist, 4)}
    return r


@app.get("/ressourcentypen", tags=["Ressourcen"],
         summary="Ressourcen der Schule (Soll/Ist), mit berechnetem Rest einh_rest = Soll − Ist")
def ressourcentypen(sj: str | None = SJ, format: Format = F):
    daten = [_ressource_mit_rest(r) for r in client().liste("/ressourcentypen", {"sj": sj})]
    return _antwort(daten, format, "ressourcentypen")


@app.get("/ressourcentypen/{id}", tags=["Ressourcen"], summary="Ein Ressourcentyp")
def ressourcentyp(id: str, sj: str | None = SJ):
    return _ressource_mit_rest(client().einzeln(f"/ressourcentypen/{id}", {"sj": sj}))


@app.get("/einheiten", tags=["Ressourcen"], summary="Einheiten (VZE, WL, Stunden …)")
def einheiten(format: Format = F):
    return _antwort(client().liste("/einheiten"), format, "einheiten")


@app.get("/einheiten/{id}", tags=["Ressourcen"], summary="Eine Einheit")
def einheit(id: str):
    return client().einzeln(f"/einheiten/{id}")


# ---------------------------------------------------------------- Personen (5.1.1 – Felder ZU PRÜFEN)

@app.get("/personen", tags=["Personen"], summary="Alle Personen (Liste)")
def personen(sj: str | None = SJ, format: Format = F):
    return _antwort(client().liste("/personen", {"sj": sj}), format, "personen")


@app.get("/personen/{id}", tags=["Personen"], summary="Eine Person")
def person(id: str, sj: str | None = SJ):
    return client().einzeln(f"/personen/{id}", {"sj": sj})


# ---------------------------------------------------------------- 5.1.5 Pensenplanung

def _zuweisungs_zeilen(daten: list[dict]) -> list[dict]:
    """CSV: eine Zeile pro Zuweisung (Aufgabe × Person); Aufgaben ohne Zuweisung mit leeren Personenspalten."""
    zeilen = []
    for a in daten:
        basis = _flach({k: v for k, v in a.items() if k != "zuweisung"})
        zw = a.get("zuweisung") or [{}]
        for z in zw:
            zeilen.append({**basis, **_flach(z, "zuweisung_")})
    return zeilen


@app.get("/planung/{bereich}", tags=["Pensenplanung"],
         summary="Aufgaben eines Bereichs inkl. Zuweisung an Personen (CSV: eine Zeile pro Zuweisung)")
def planung(bereich: Bereich, sj: str | None = SJ, format: Format = F):
    daten = client().liste("/" + BEREICHE[bereich], {"sj": sj})
    return _antwort(daten, format, bereich, _zuweisungs_zeilen)


@app.get("/planung/{bereich}/{id}", tags=["Pensenplanung"], summary="Eine Aufgabe eines Bereichs mit Zuweisungen")
def planung_einzeln(bereich: Bereich, id: str, sj: str | None = SJ):
    return client().einzeln(f"/{BEREICHE[bereich]}/{id}", {"sj": sj})


# ---------------------------------------------------------------- 5.1.6 Pensen

PENSUM_GRUPPEN = ("unterricht", "weitere_anstellungen", "zusaetzlich_entschaedigte_aemter", "ba_klp", "ba_schule",
                  "ba_zusammenarbeit", "ba_weiterbildung", "ba_flex")


def _pensum_zeilen(daten: list[dict]) -> list[dict]:
    """CSV-Übersicht: eine Zeile pro Person mit Beschäftigungsgrad, WL, Arbeitszeit Soll/Ist und Stunden je Gruppe."""
    zeilen = []
    for p in daten:
        z = _flach(p.get("person") or {}, "person_")
        anst = p.get("anstellungen") or []
        z["wl_total"] = sum(a.get("wl") or 0 for a in anst)
        z["bg_total"] = sum(a.get("bg") or 0 for a in anst)
        z["anstellungstypen"] = ", ".join(sorted({a.get("anstellungstyp", "") for a in anst} - {""}))
        z.update(_flach(p.get("arbeitszeit") or {}, "arbeitszeit_"))
        for g in PENSUM_GRUPPEN:
            z[f"stunden_{g}"] = sum(e.get("stunden") or 0 for e in p.get(g) or [])
        zeilen.append(z)
    return zeilen


@app.get("/pensen", tags=["Pensen"],
         summary="Pensen aller Personen (ab Freigabe zur Anstellung). CSV: Übersicht eine Zeile pro Person")
def pensen(sj: str | None = SJ, format: Format = F):
    return _antwort(client().liste("/pensen", {"sj": sj}), format, "pensen", _pensum_zeilen)


@app.get("/pensen/{id}", tags=["Pensen"], summary="Pensum einer Person")
def pensum(id: str, sj: str | None = SJ):
    return client().einzeln(f"/pensen/{id}", {"sj": sj})


# ---------------------------------------------------------------- 5.3 Personaldossier / MAB (geschützt)

def _ohne_pdf(d: dict) -> dict:
    return {k: v for k, v in d.items() if k != "associated_document"}


def _pdf(d: dict, name: str) -> Response:
    inhalt = d.get("associated_document")
    if not inhalt:
        raise HTTPException(404, "Zu diesem Dokument gibt es kein PDF")
    return Response(base64.b64decode(inhalt), media_type="application/pdf",
                    headers={"Content-Disposition": f'attachment; filename="{name}.pdf"'})


@app.get("/mab", tags=["Personaldossier"], dependencies=[Depends(dossier_check)],
         summary="Alle Mitarbeiterbeurteilungen eines Schuljahres (Übersicht, ohne PDF)")
def mab_liste(sj: str | None = SJ):
    return client().liste("/pfiles/mab", {"sj": sj})


@app.get("/mab/{mab_id}", tags=["Personaldossier"], dependencies=[Depends(dossier_check)], summary="Eine Mitarbeiterbeurteilung")
def mab(mab_id: str):
    return _ohne_pdf(client().einzeln(f"/pfiles/mab/{mab_id}"))


@app.get("/mab/{mab_id}/pdf", tags=["Personaldossier"], dependencies=[Depends(dossier_check)], summary="Mitarbeiterbeurteilung als PDF")
def mab_pdf(mab_id: str):
    return _pdf(client().einzeln(f"/pfiles/mab/{mab_id}"), f"mab_{mab_id}")


@app.get("/personen/{person_id}/mab", tags=["Personaldossier"], dependencies=[Depends(dossier_check)],
         summary="Mitarbeiterbeurteilungen einer Person – im Schuljahr oder mit alle_schuljahre=true über alle")
def person_mab(person_id: str, sj: str | None = SJ, alle_schuljahre: bool = False):
    if alle_schuljahre:  # Doku: /pfiles_by_local_user/mab/{person_id} – erwartet vermutlich local_user_id (ZU PRÜFEN)
        return client().liste(f"/pfiles_by_local_user/mab/{person_id}")
    return client().liste(f"/pfiles_by_person/mab/{person_id}", {"sj": sj})


@app.get("/personen/{person_id}/dokumente", tags=["Personaldossier"], dependencies=[Depends(dossier_check)], summary="Dokumente im Personaldossier einer Person")
def person_dokumente(person_id: str, sj: str | None = SJ):
    return client().liste(f"/pfiles_by_person/{person_id}", {"sj": sj})


@app.get("/dokumente/{dokument_id}", tags=["Personaldossier"], dependencies=[Depends(dossier_check)], summary="Metadaten eines Dokuments im Personaldossier")
def dokument(dokument_id: str):
    return _ohne_pdf(client().einzeln(f"/pfiles/{dokument_id}"))


@app.get("/dokumente/{dokument_id}/pdf", tags=["Personaldossier"], dependencies=[Depends(dossier_check)], summary="Dokument im Personaldossier als PDF")
def dokument_pdf(dokument_id: str):
    return _pdf(client().einzeln(f"/pfiles/{dokument_id}"), f"dokument_{dokument_id}")


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
