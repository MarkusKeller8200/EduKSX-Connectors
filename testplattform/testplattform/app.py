"""Testplattform für die APIs in apis/ (#41, #43): jede API ist ein Plugin mit eigener Testseite.

- Plugins: alle apis/<name>/api.json (ohne _vorlage, ausser TESTPLATTFORM_VORLAGE=1).
- Beschreibung: GET <api>/plugin.json; bietet die API das nicht an (z. B. Docker-Image ohne shared/), erzeugt die
  Plattform sie selbst aus <api>/openapi.json (shared/plugin_export.py, Entscheid #42).
- Aufrufe laufen über die Plattform (Proxy): sie setzt den API-Key (aus der Umgebung bzw. apis/<name>/.env), der
  Browser sieht ihn nie. Nur Endpunkte aus der Beschreibung; schreibende ohne ?probelauf=true nur mit Bestätigung.
- Protokoll im Arbeitsspeicher: Zeit, Plugin, Endpunkt-ID, Status, Dauer – ohne Parameterwerte, Bodys und Zugangsdaten.

Start:  uvicorn testplattform.app:app --port 8090   (lokal: start-testplattform.command / .bat)
"""
from __future__ import annotations

import json
import os
import re
import sys
import time
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

import httpx
from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, Response
from starlette.concurrency import run_in_threadpool

HIER = Path(__file__).resolve().parent
REPO = HIER.parents[1]
if str(REPO) not in sys.path:
    sys.path.append(str(REPO))
from shared.plugin_export import manifest as manifest_aus_openapi  # noqa: E402

VERSION = json.loads((HIER.parent / "testplattform.json").read_text(encoding="utf-8"))["version"]
MAX_BYTES = 60 * 1024 * 1024
WEITERGEBEN = ("content-type", "accept")
ZURUECK = ("content-type", "content-disposition")
BESTAETIGT = "x-testplattform-bestaetigt"


def _env_datei(pfad: Path) -> dict[str, str]:
    werte: dict[str, str] = {}
    if not pfad.exists():
        return werte
    for zeile in pfad.read_text(encoding="utf-8").splitlines():
        zeile = zeile.strip()
        if not zeile or zeile.startswith("#") or "=" not in zeile:
            continue
        k, _, v = zeile.partition("=")
        werte[k.strip()] = v.strip().strip('"').strip("'")
    return werte


@dataclass
class Plugin:
    name: str
    titel: str
    version: str
    base_url: str
    api_key: str = field(default="", repr=False)
    info: dict = field(default_factory=dict)

    @property
    def sitzung(self) -> dict | None:
        return (self.info.get("plugin") or {}).get("sitzung")

    def oeffentlich(self) -> dict:
        p = self.info.get("plugin") or {}
        return {"name": self.name, "titel": self.titel, "version": self.version, "base_url": self.base_url,
                "api_key_gesetzt": bool(self.api_key), "sitzung": self.sitzung,
                "beschreibung": p.get("beschreibung", ""), "data_notice": p.get("data_notice"),
                "status_vorgabe": p.get("status", "partial")}


def plugins_aus_repo(repo: Path = REPO, umgebung: dict[str, str] | None = None) -> list[Plugin]:
    """apis/<name>/api.json → Plugins. Adresse: <NAME>_URL bzw. http://127.0.0.1:<NAME>_PORT (Vorgabe aus api.json);
    API-Key: <NAME>_API_KEY – jeweils aus der Umgebung, sonst aus apis/<name>/.env."""
    env = dict(os.environ if umgebung is None else umgebung)
    vorlage = env.get("TESTPLATTFORM_VORLAGE", "0") == "1"
    aus: list[Plugin] = []
    for datei in sorted((repo / "apis").glob("*/api.json")):
        info = json.loads(datei.read_text(encoding="utf-8"))
        name = str(info.get("name", datei.parent.name))
        if name.startswith("_") and not vorlage:
            continue
        praefix = name.lstrip("_").upper() + "_"
        lokal = _env_datei(datei.parent / ".env")
        wert = lambda k, std="": env.get(praefix + k) or lokal.get(praefix + k) or std  # noqa: E731
        port = wert("PORT", str((info.get("plugin") or {}).get("port", 8080)))
        aus.append(Plugin(name=name, titel=info.get("titel", name), version=str(info.get("version", "")),
                          base_url=wert("URL", f"http://127.0.0.1:{port}").rstrip("/"),
                          api_key=wert("API_KEY"), info=info))
    return aus


def _vorlage_regex(pfad: str) -> re.Pattern:
    teile = re.split(r"(\{[^}]+\})", pfad)
    return re.compile("^" + "".join("[^/]+" if t.startswith("{") else re.escape(t) for t in teile) + "/?$")


def endpunkt_finden(m: dict, methode: str, pfad: str) -> dict | None:
    """Endpunkt der Beschreibung zu Methode und konkretem Pfad (feste Pfade vor Platzhaltern)."""
    kandidaten = [e for e in (m.get("service") or {}).get("endpoints") or []
                  if e.get("method", "GET").upper() == methode.upper() and _vorlage_regex(e["path"]).match(pfad)]
    kandidaten.sort(key=lambda e: e["path"].count("{"))
    return kandidaten[0] if kandidaten else None


def create_app(plugins: list[Plugin] | None = None, transport: httpx.BaseTransport | None = None,
               token: str | None = None) -> FastAPI:
    app = FastAPI(title="EduKSX-Connectors – Testplattform", version=VERSION, docs_url="/api/docs",
                  openapi_url="/api/openapi.json")
    liste = plugins if plugins is not None else plugins_aus_repo()
    nach_name = {p.name: p for p in liste}
    zugang = os.environ.get("TESTPLATTFORM_TOKEN", "") if token is None else token
    protokoll: deque[dict] = deque(maxlen=300)
    cache: dict[str, tuple[float, dict]] = {}
    client = httpx.Client(transport=transport, timeout=httpx.Timeout(120.0, connect=3.0), follow_redirects=False)

    def pruefe_zugang(request: Request) -> None:
        if zugang and request.headers.get("x-testplattform-token") != zugang:
            raise HTTPException(401, "Zugang zur Testplattform fehlt (TESTPLATTFORM_TOKEN)")

    def plugin(name: str) -> Plugin:
        if name not in nach_name:
            raise HTTPException(404, f"Plugin «{name}» unbekannt")
        return nach_name[name]

    def kopf(p: Plugin) -> dict[str, str]:
        return {"X-API-Key": p.api_key} if p.api_key else {}

    def beschreibung(p: Plugin, neu: bool = False) -> dict:
        if not neu and p.name in cache and time.monotonic() - cache[p.name][0] < 60:
            return cache[p.name][1]
        try:
            r = client.get(p.base_url + "/plugin.json", headers=kopf(p))
            if r.status_code == 200:
                m, quelle = r.json(), "plugin.json"
            elif r.status_code in (404, 405):
                o = client.get(p.base_url + "/openapi.json", headers=kopf(p))
                o.raise_for_status()
                m, quelle = manifest_aus_openapi(o.json(), p.info, p.base_url), "openapi.json"
            else:
                raise HTTPException(502, f"{p.titel}: /plugin.json antwortet mit {r.status_code}")
        except httpx.HTTPError as e:
            raise HTTPException(503, f"{p.titel} nicht erreichbar unter {p.base_url} ({type(e).__name__}) – "
                                     "API starten bzw. Adresse prüfen") from e
        m.setdefault("x-eduksx", {})["quelle_beschreibung"] = quelle
        cache[p.name] = (time.monotonic(), m)
        return m

    @app.get("/", include_in_schema=False)
    def startseite():
        return FileResponse(HIER / "static" / "index.html", media_type="text/html; charset=utf-8")

    @app.get("/static/{datei}", include_in_schema=False)
    def statisch(datei: str):
        pfad = (HIER / "static" / datei).resolve()
        if pfad.parent != (HIER / "static").resolve() or not pfad.is_file():
            raise HTTPException(404)
        return FileResponse(pfad)

    @app.get("/api/info", summary="Version der Testplattform, Zugang nötig ja/nein")
    def info():
        return {"version": VERSION, "token_noetig": bool(zugang)}

    @app.get("/api/plugins", summary="Eingebundene APIs mit Version, Adresse und Status (GET /status)")
    def plugins_liste(request: Request):
        pruefe_zugang(request)
        aus = []
        for p in liste:
            eintrag = p.oeffentlich()
            try:
                r = client.get(p.base_url + "/status", headers=kopf(p), timeout=3.0)
                eintrag["erreichbar"] = True
                eintrag["status_code"] = r.status_code
                try:
                    eintrag["status"] = r.json()
                except ValueError:
                    eintrag["status"] = None
            except httpx.HTTPError:
                eintrag.update(erreichbar=False, status_code=None, status=None)
            aus.append(eintrag)
        return aus

    @app.get("/api/plugins/{name}/manifest", summary="Plugin-Beschreibung (Format plugin.json des Intranets)")
    def plugin_manifest(name: str, request: Request, neu: bool = False):
        pruefe_zugang(request)
        p = plugin(name)
        return {"plugin": p.oeffentlich(), "manifest": beschreibung(p, neu)}

    @app.get("/api/protokoll", summary="Letzte Aufrufe (ohne Werte, Bodys und Zugangsdaten)")
    def protokoll_liste(request: Request):
        pruefe_zugang(request)
        return list(reversed(protokoll))

    @app.api_route("/api/plugins/{name}/aufruf/{pfad:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
                   summary="Aufruf eines Endpunkts der API (Proxy mit API-Key, Prüfung und Protokoll)")
    async def aufruf(name: str, pfad: str, request: Request,
                     x_testplattform_bestaetigt: str = Header(default="")):
        pruefe_zugang(request)
        p = plugin(name)
        methode = request.method.upper()
        ziel = "/" + pfad
        if any(t in (".", "..") for t in pfad.split("/")):
            raise HTTPException(400, "Pfad ungültig")
        m = await run_in_threadpool(beschreibung, p)
        e = endpunkt_finden(m, methode, ziel)
        if e is None:
            raise HTTPException(404, f"{methode} {ziel} steht nicht in der Beschreibung von {p.titel}")
        if e.get("status") == "planned":
            raise HTTPException(409, f"«{e.get('label')}» ist nur geplant und nicht aufrufbar")
        probelauf = request.query_params.get("probelauf", "").lower() in ("true", "1", "ja")
        if e.get("danger") and not probelauf and x_testplattform_bestaetigt.lower() != "ja":
            return JSONResponse(status_code=428, content={
                "fehler": "bestaetigung_noetig",
                "meldung": f"«{e.get('label')}» schreibt im Fremdsystem. Probelauf wählen oder ausdrücklich bestätigen."})
        inhalt = await request.body()
        if len(inhalt) > MAX_BYTES:
            raise HTTPException(413, "Anfrage zu gross (höchstens 60 MB)")
        headers = {k: v for k, v in request.headers.items() if k.lower() in WEITERGEBEN}
        if p.sitzung and request.headers.get(p.sitzung["header"]):
            headers[p.sitzung["header"]] = request.headers[p.sitzung["header"]]
        headers.update(kopf(p))
        start = time.monotonic()
        try:
            r = await run_in_threadpool(client.request, methode, p.base_url + ziel,
                                        params=list(request.query_params.multi_items()),
                                        content=inhalt or None, headers=headers)
        except httpx.HTTPError as ex:
            protokoll.append(_eintrag(p, e, methode, None, start, probelauf))
            return JSONResponse(status_code=503, content={"fehler": "nicht_erreichbar",
                                                          "meldung": f"{p.titel} nicht erreichbar ({type(ex).__name__})"})
        protokoll.append(_eintrag(p, e, methode, r.status_code, start, probelauf))
        aus = {k: v for k, v in r.headers.items() if k.lower() in ZURUECK}
        aus["X-Dauer-Ms"] = str(int((time.monotonic() - start) * 1000))
        aus["X-Endpunkt"] = str(e.get("id"))
        return Response(content=r.content, status_code=r.status_code, headers=aus)

    return app


def _eintrag(p: Plugin, e: dict, methode: str, status: int | None, start: float, probelauf: bool) -> dict[str, Any]:
    return {"zeit": datetime.now().isoformat(timespec="seconds"), "plugin": p.name, "endpunkt": e.get("id"),
            "methode": methode, "pfad": e.get("path"), "status": status, "probelauf": probelauf,
            "schreibend": bool(e.get("danger")), "dauer_ms": int((time.monotonic() - start) * 1000)}


app = create_app()
