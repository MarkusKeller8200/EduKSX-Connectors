"""Plugin-Beschreibung einer API aus ihrer OpenAPI-Beschreibung und api.json (Entscheid #42, 27.11.2026).

Eine Quelle: die Beschreibung entsteht im Code der API.
- Standard-OpenAPI: ``summary`` (bzw. erste Zeile des Docstrings) → ``label``, ``tags`` → ``group``,
  Beispiele (``example``/``examples``/``default``) → ``example``/``body``/``fields``, ``deprecated``.
- Eigenes nur in ``x-eduksx`` am Endpunkt (``openapi_extra={"x-eduksx": {...}}``): ``danger``, ``status``,
  ``effect``, ``permission``, ``use``, ``note``, ``label``, ``example``/``body`` (übersteuern).
- API-weite Angaben in ``api.json`` → Abschnitt ``plugin``: ``kategorie``, ``beschreibung``, ``data_notice``,
  ``status`` (Vorgabe je Endpunkt), ``port``, ``sitzung`` (Kopfzeile einer Anmeldesitzung), ``auth_note``.

Ergebnis: Manifest im Format von ``plugin.json`` des Intranets (sek-intranet, PLUGINS.md), damit es dort ohne Umbau
übernommen werden kann (sek-intranet#229). Zusätze, die das Intranet (noch) nicht kennt, stehen unter eigenen
Schlüsseln (``group``, ``probelauf``, ``form``) bzw. ``x-eduksx`` und stören dort nicht.

Nur Standardbibliothek – die APIs binden das Modul ein, wenn es vorhanden ist (``einbinden``), die Testplattform
nutzt es auch für APIs, die selbst kein ``/plugin.json`` anbieten (z. B. Docker-Image ohne ``shared/``).
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

API = 1  # Manifest-Version des Intranets (PluginManifest::API_VERSION)
METHODEN = ("get", "post", "put", "patch", "delete")
STATUS = ("full", "partial", "planned")
AUTH_TYPEN = ("none", "bearer", "header", "basic", "oauth2_client_credentials", "oauth2_password")
EINSTELLUNG_TYPEN = ("text", "url", "password", "select", "check", "number", "textarea")
KATEGORIEN = ("identity", "devices", "inventory", "school", "other")
# Kopfzeilen, die nicht als Parameter erscheinen (Anmeldung bzw. Sitzung regelt die Plattform)
VERSTECKTE_KOPFZEILEN = {"x-api-key"}
MAIL = "lea.muster@sekbuelach.example"
PLATZHALTER = "Beispiel"


# ----------------------------------------------------------------------------------------------- Hilfen
def _ref(spec: dict, schema: dict | None, tiefe: int = 0) -> dict:
    """$ref und einfache anyOf/allOf (Optional[...]) auflösen."""
    schema = schema or {}
    for _ in range(10):
        if "$ref" in schema:
            name = schema["$ref"].split("/")[-1]
            schema = {**(spec.get("components", {}).get("schemas", {}).get(name) or {}),
                      **{k: v for k, v in schema.items() if k != "$ref"}}
            continue
        for kombi in ("anyOf", "oneOf"):
            if kombi in schema:
                teile = [t for t in schema[kombi] if t.get("type") != "null"]
                if len(teile) == 1:
                    schema = {**teile[0], **{k: v for k, v in schema.items() if k != kombi}}
                    break
        else:
            if "allOf" in schema and len(schema["allOf"]) == 1:
                schema = {**schema["allOf"][0], **{k: v for k, v in schema.items() if k != "allOf"}}
                continue
            return schema
    return schema


def _typ(schema: dict) -> str:
    t = schema.get("type")
    if t in ("integer", "number", "boolean", "array", "object"):
        return t
    if _ist_datei(schema):
        return "file"
    return "string"


def _ist_datei(schema: dict) -> bool:
    return schema.get("format") == "binary" or "contentMediaType" in schema


def _vorgabe(schema: dict) -> Any:
    """Vorhandenes Beispiel bzw. Vorgabewert aus dem Schema, sonst None."""
    if "example" in schema:
        return schema["example"]
    if isinstance(schema.get("examples"), list) and schema["examples"]:
        return schema["examples"][0]
    if schema.get("default") is not None:
        return schema["default"]
    if schema.get("enum"):
        return schema["enum"][0]
    if "const" in schema:
        return schema["const"]
    return None


def _beispiel(spec: dict, schema: dict | None, name: str = "", tiefe: int = 0) -> Any:
    """Beispielwert aus dem Schema; fehlt einer, ein erfundener Platzhalter nach Typ und Feldname."""
    s = _ref(spec, schema)
    v = _vorgabe(s)
    if v is not None:
        return v
    t = s.get("type")
    if tiefe > 4:
        return None
    if t == "object" or "properties" in s:
        props = s.get("properties") or {}
        pflicht = set(s.get("required") or [])
        # Pflichtfelder immer, sonst höchstens 8 Felder, damit das Beispiel lesbar bleibt
        aus = {n: _beispiel(spec, props[n], n, tiefe + 1) for n in props if n in pflicht}
        # weitere Felder nur mit sprechendem Beispiel (nicht «Beispiel»), höchstens 6
        for n in props:
            if n in pflicht or len(aus) >= len(pflicht) + 6:
                continue
            v = _beispiel(spec, props[n], n, tiefe + 1)
            if v not in (None, PLATZHALTER, False, 1, 1.0, [], {}, [PLATZHALTER]):
                aus[n] = v
        return aus
    if t == "array":
        return [_beispiel(spec, s.get("items"), name, tiefe + 1)]
    if t == "integer":
        return 1
    if t == "number":
        return 1.0
    if t == "boolean":
        return False
    fmt = s.get("format")
    n = name.lower()
    if n == "geburtsdatum":
        return "2012-03-04"
    if fmt == "date" or n.endswith(("datum", "_von", "_bis", "beginn", "ab", "bis", "stichtag")):
        return "2026-08-17"
    if fmt == "date-time":
        return "2026-08-17T08:00:00"
    if fmt == "email" or "mail" in n:
        return MAIL
    if n in ("fremdkey", "schluessel"):
        return "escola-650"
    if n == "name" or n == "nachname":
        return "Muster"
    if n == "vorname":
        return "Lea"
    return PLATZHALTER


def _id(methode: str, pfad: str, belegt: set[str]) -> str:
    teile = [re.sub(r"[{}]", "", t) for t in pfad.strip("/").split("/") if t]
    basis = "-".join(teile) or "start"
    basis = re.sub(r"[^a-z0-9_-]", "-", basis.lower()).strip("-")[:36] or "start"
    if methode != "get":
        basis = f"{methode}-{basis}"[:40]
    if not basis[0].isalpha():
        basis = "e-" + basis
    i, kandidat = 2, basis
    while kandidat in belegt:
        kandidat, i = f"{basis}-{i}", i + 1
    belegt.add(kandidat)
    return kandidat


def _auto_summary(op: dict, methode: str, pfad: str) -> str:
    """Die summary, die FastAPI aus dem Funktionsnamen erzeugt (operationId = Name + Pfad + _methode)."""
    op_id = op.get("operationId") or ""
    rest = re.sub(r"\W", "_", pfad) + "_" + methode
    name = op_id[:-len(rest)] if op_id.endswith(rest) else op_id
    return name.replace("_", " ").title()


def _label(op: dict, methode: str = "", pfad: str = "") -> tuple[str, bool]:
    """Beschriftung: x-eduksx.label, eigene summary, erste Zeile des Docstrings; sonst die von FastAPI aus dem
    Funktionsnamen erzeugte summary (zweiter Wert False = nicht von Hand beschrieben)."""
    x = op.get("x-eduksx") or {}
    if x.get("label"):
        return str(x["label"]), True
    summary = (op.get("summary") or "").strip()
    beschreibung = (op.get("description") or "").strip()
    auto = bool(summary) and summary == _auto_summary(op, methode, pfad)
    if summary and not auto:
        return summary, True
    if beschreibung:
        zeile = beschreibung.splitlines()[0].strip()
        zeile = re.split(r"(?<=[.!?])\s", zeile, maxsplit=1)[0].rstrip(".")
        return zeile[:160], True
    return summary or op.get("operationId", ""), False


# ----------------------------------------------------------------------------------------------- Manifest
def api_info(api_ordner: str | Path) -> dict:
    return json.loads((Path(api_ordner) / "api.json").read_text(encoding="utf-8"))


def manifest(openapi: dict, info: dict, base_url: str = "") -> dict:
    """OpenAPI (mit x-eduksx) + api.json → Manifest im Format von plugin.json des Intranets."""
    plugin = info.get("plugin") or {}
    name = str(info.get("name", "api"))
    status_vorgabe = plugin.get("status", "partial")
    sitzung = (plugin.get("sitzung") or {}).get("header", "").lower()
    endpunkte: list[dict] = []
    belegt: set[str] = set()

    for pfad, item in (openapi.get("paths") or {}).items():
        gemeinsam = item.get("parameters") or []
        for methode in METHODEN:
            op = item.get(methode)
            if not isinstance(op, dict):
                continue
            x = op.get("x-eduksx") or {}
            label, beschrieben = _label(op, methode, pfad)
            e: dict[str, Any] = {
                "id": x.get("id") or _id(methode, pfad, belegt),
                "method": methode.upper(),
                "path": pfad,
                "label": label,
                "status": x.get("status", status_vorgabe),
            }
            if x.get("id"):
                belegt.add(x["id"])
            if op.get("tags"):
                e["group"] = op["tags"][0]
            beschreibung = (op.get("description") or "").strip()
            if beschreibung and beschreibung.splitlines()[0].strip().rstrip(".") not in label:
                e["note"] = beschreibung
            elif beschreibung and "\n" in beschreibung:
                e["note"] = beschreibung
            for k in ("use", "permission", "note", "effect"):
                if x.get(k):
                    e[k] = x[k]
            if op.get("deprecated"):
                e["deprecated"] = True

            params = []
            for p in [*gemeinsam, *(op.get("parameters") or [])]:
                p = _ref(openapi, p)
                pname, ort = p.get("name", ""), p.get("in", "query")
                if ort == "header" and (pname.lower() in VERSTECKTE_KOPFZEILEN or pname.lower() == sitzung):
                    continue
                if ort == "cookie":
                    continue
                if pname == "probelauf":
                    e["probelauf"] = True
                    continue
                schema = _ref(openapi, p.get("schema"))
                eintrag: dict[str, Any] = {"name": pname}
                if ort != "query":
                    eintrag["in"] = ort
                if p.get("required") or ort == "path":
                    eintrag["required"] = True
                if schema.get("default") is not None:
                    eintrag["default"] = str(schema["default"]).lower() if isinstance(schema["default"], bool) \
                        else str(schema["default"])
                elif ort != "path":
                    v = p.get("example", _beispiel(openapi, schema, pname))
                    if v == PLATZHALTER and not p.get("required"):
                        v = None  # kein erfundener Platzhalter in freiwilligen Feldern (würde sonst mitgesendet)
                    if v is not None and not isinstance(v, (dict, list)):
                        eintrag["example"] = str(v).lower() if isinstance(v, bool) else str(v)
                if p.get("description") or schema.get("description"):
                    eintrag["help"] = p.get("description") or schema.get("description")
                if schema.get("enum"):
                    eintrag["choices"] = [str(c) for c in schema["enum"]]
                params.append(eintrag)
            if params:
                e["params"] = params

            inhalt = (op.get("requestBody") or {}).get("content") or {}
            if "application/json" in inhalt:
                medium = inhalt["application/json"]
                schema = _ref(openapi, medium.get("schema"))
                body = x.get("body", medium.get("example", _beispiel(openapi, schema)))
                e["body"] = body
                props = schema.get("properties") or {}
                pflicht = set(schema.get("required") or [])
                felder = []
                for fname, fschema in props.items():
                    fs = _ref(openapi, fschema)
                    feld: dict[str, Any] = {"name": fname, "type": _typ(fs)}
                    if fname in pflicht:
                        feld["required"] = True
                    if fs.get("description"):
                        feld["help"] = fs["description"]
                    bsp = _beispiel(openapi, fs, fname)
                    if bsp is not None and (bsp != PLATZHALTER or fname in pflicht):
                        feld["example"] = bsp
                    if fs.get("enum"):
                        feld["choices"] = fs["enum"]
                    felder.append(feld)
                if felder:
                    e["fields"] = felder
            elif "multipart/form-data" in inhalt or "application/x-www-form-urlencoded" in inhalt:
                medium = inhalt.get("multipart/form-data") or inhalt["application/x-www-form-urlencoded"]
                schema = _ref(openapi, medium.get("schema"))
                pflicht = set(schema.get("required") or [])
                form = []
                for fname, fschema in (schema.get("properties") or {}).items():
                    fs = _ref(openapi, fschema)
                    datei = _ist_datei(fs) or _ist_datei(_ref(openapi, fs.get("items")))
                    feld = {"name": fname, "type": "file" if datei else _typ(fs)}
                    if datei and fs.get("type") == "array":
                        feld["multiple"] = True
                    if fname in pflicht:
                        feld["required"] = True
                    if fs.get("description"):
                        feld["help"] = fs["description"]
                    if not datei:
                        bsp = _beispiel(openapi, fs, fname)
                        if bsp == PLATZHALTER and fname not in pflicht:
                            bsp = None
                        if bsp is not None:
                            feld["example"] = bsp
                    form.append(feld)
                e["form"] = form
                datei = next((f for f in form if f["type"] == "file"), None)
                if datei:
                    e["file"] = {"field": datei["name"]}

            schreibend = x.get("effect", "write" if methode != "get" else "read") == "write"
            danger = x.get("danger", schreibend)
            if danger:
                e["danger"] = True
            if not beschrieben:
                e["x-eduksx-ohne-beschreibung"] = True
            endpunkte.append(e)

    sitzung_cfg = plugin.get("sitzung")
    m: dict[str, Any] = {
        "id": "eduksx-" + re.sub(r"[^a-z0-9_-]", "", name.lower()).strip("_-"),
        "name": info.get("titel") or openapi.get("info", {}).get("title") or name,
        "version": str(info.get("version", "0.0.0")),
        "api": API,
        "category": plugin.get("kategorie", "school"),
        "author": "EduKSX-Connectors",
        "description": plugin.get("beschreibung") or (openapi.get("info", {}).get("description") or "").strip()
        or f"Schnittstelle {name} aus EduKSX-Connectors.",
        "service": {
            "name": f"{info.get('titel') or name} {info.get('version', '')} (EduKSX-Connectors)".strip(),
            "docs": "/docs",
            "auth": {"type": "header", "header": "X-API-Key", "setting": "api_key"},
            "auth_note": plugin.get("auth_note") or "API-Key der Connector-API (Umgebungsvariable "
            f"{name.upper()}_API_KEY auf dem Connector-Server), Kopfzeile X-API-Key.",
            "endpoints": endpunkte,
        },
        "settings": [
            {"key": "base_url", "type": "url", "label": "Adresse der API", "required": True,
             "example": base_url or f"http://127.0.0.1:{plugin.get('port', 8080)}"},
            {"key": "api_key", "type": "password", "label": "API-Key (X-API-Key)", "required": True},
        ],
        "x-eduksx": {"quelle": "EduKSX-Connectors", "api": name, "port": plugin.get("port"),
                     "sitzung": sitzung_cfg},
    }
    if plugin.get("data_notice"):
        m["data_notice"] = plugin["data_notice"]
    if base_url:
        m["service"]["base"] = base_url
    return m


# ----------------------------------------------------------------------------------------------- Prüfung
def pruefen(m: dict, info: dict | None = None, streng: bool = True) -> list[str]:
    """Regeln von PluginManifest (Intranet) + eigene Regeln (#42). Leere Liste = in Ordnung."""
    f: list[str] = []
    if not re.fullmatch(r"[a-z][a-z0-9_-]{1,40}", str(m.get("id", ""))):
        f.append("«id» fehlt oder ist ungültig")
    if m.get("api") != API:
        f.append(f"«api» muss {API} sein")
    if m.get("category") not in KATEGORIEN:
        f.append(f"«category» unbekannt ({m.get('category')})")
    auth = (m.get("service") or {}).get("auth") or {}
    if auth.get("type", "none") not in AUTH_TYPEN:
        f.append("unbekannter Anmeldetyp")
    keys = [s.get("key") for s in m.get("settings") or []]
    if len(keys) != len(set(keys)) or any(s.get("type") not in EINSTELLUNG_TYPEN for s in m.get("settings") or []):
        f.append("Einstellungen: Schlüssel doppelt oder Typ ungültig")
    if info is not None and str(m.get("version")) != str(info.get("version")):
        f.append(f"Version {m.get('version')} ≠ api.json {info.get('version')}")
    ids: set[str] = set()
    for e in (m.get("service") or {}).get("endpoints") or []:
        wo = f"{e.get('method')} {e.get('path')}"
        if not e.get("id") or not e.get("path"):
            f.append(f"{wo}: «id» oder «path» fehlt")
        if e.get("id") in ids:
            f.append(f"{wo}: Endpunkt-ID «{e.get('id')}» doppelt")
        ids.add(e.get("id"))
        if str(e.get("method", "GET")).lower() not in METHODEN:
            f.append(f"{wo}: unbekannte Methode")
        if e.get("status", "full") not in STATUS:
            f.append(f"{wo}: status muss full, partial oder planned sein")
        if e.get("effect") not in (None, "read", "write"):
            f.append(f"{wo}: effect muss read oder write sein")
        if not streng:
            continue
        if e.get("x-eduksx-ohne-beschreibung"):
            f.append(f"{wo}: keine Beschreibung (summary=… oder Docstring ergänzen)")
        if e.get("method") != "GET" and e.get("effect") != "read" and not e.get("danger"):
            f.append(f"{wo}: schreibend ohne «danger» (x-eduksx danger: false nur mit effect: read)")
    return f


# ----------------------------------------------------------------------------------------------- Einbinden
CORS_VORGABE = "https://markuskeller8200.github.io"  # Testplattform auf GitHub Pages (#51)


def cors_origins(umgebung: dict | None = None) -> list[str]:
    """Erlaubte Herkunft für Aufrufe aus dem Browser: ``EDUKSX_CORS_ORIGINS`` (Komma-Liste, leer = keine),
    Vorgabe die Testplattform auf GitHub Pages."""
    import os

    wert = (os.environ if umgebung is None else umgebung).get("EDUKSX_CORS_ORIGINS", CORS_VORGABE)
    return [o.strip().rstrip("/") for o in wert.split(",") if o.strip()]


class _LokalesNetz:
    """Private Network Access (Chrome): Vorabanfrage einer öffentlichen Seite an 127.0.0.1 erlauben, wenn die
    Herkunft freigegeben ist (Antwort-Kopfzeile Access-Control-Allow-Private-Network)."""

    def __init__(self, app, origins: list[str]):
        self.app, self.origins = app, set(origins)

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or scope.get("method") != "OPTIONS":
            return await self.app(scope, receive, send)
        kopf = {k.decode().lower(): v.decode() for k, v in scope.get("headers", [])}
        erlauben = kopf.get("access-control-request-private-network") == "true" and kopf.get("origin") in self.origins

        async def senden(nachricht):
            if erlauben and nachricht["type"] == "http.response.start":
                nachricht.setdefault("headers", []).append((b"access-control-allow-private-network", b"true"))
            await send(nachricht)

        return await self.app(scope, receive, senden)


def einbinden(app, api_ordner: str | Path, origins: list[str] | None = None) -> None:
    """``GET /plugin.json`` an einer FastAPI-App anbieten und Aufrufe aus der Testplattform im Browser erlauben (CORS
    für die freigegebenen Herkünfte, #51). Der API-Key bleibt nötig, wo die App ihn verlangt.
    """
    ordner = Path(api_ordner)

    @app.get("/plugin.json", include_in_schema=False)
    def plugin_json():
        return manifest(app.openapi(), api_info(ordner))

    erlaubt = cors_origins() if origins is None else origins
    if erlaubt:
        import inspect

        from fastapi.middleware.cors import CORSMiddleware

        optionen = dict(allow_origins=erlaubt, allow_methods=["*"], allow_headers=["*"],
                        expose_headers=["Content-Disposition"], max_age=600)
        if "allow_private_network" in inspect.signature(CORSMiddleware.__init__).parameters:
            app.add_middleware(CORSMiddleware, allow_private_network=True, **optionen)  # Starlette ≥ 0.47
        else:
            app.add_middleware(CORSMiddleware, **optionen)
            app.add_middleware(_LokalesNetz, origins=erlaubt)


if __name__ == "__main__":  # python3 shared/plugin_export.py apis/cmi > cmi-plugin.json
    import subprocess
    import sys

    ordner = Path(sys.argv[1]).resolve()
    info = api_info(ordner)
    paket = f"{info['name'].lstrip('_')}_api"
    code = f"import json; from {paket}.app import app; print(json.dumps(app.openapi()))"
    roh = subprocess.run([sys.executable, "-c", code], cwd=ordner, capture_output=True, text=True, check=True).stdout
    print(json.dumps(manifest(json.loads(roh), info, sys.argv[2] if len(sys.argv) > 2 else ""),
                     ensure_ascii=False, indent=2))
