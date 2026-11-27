"""Plugin-Beschreibung aus OpenAPI + api.json (#42). Mit einer kleinen FastAPI-App, ohne Netzwerk."""
from __future__ import annotations

import sys
from pathlib import Path

from fastapi import FastAPI, File, Form, Header, Query, UploadFile
from fastapi.testclient import TestClient
from pydantic import BaseModel, Field

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from shared.plugin_export import einbinden, manifest, pruefen  # noqa: E402

INFO = {"name": "demo", "titel": "Demo-API", "version": "1.2.3",
        "plugin": {"port": 8099, "status": "partial", "kategorie": "school", "data_notice": "Erfundene Daten",
                   "sitzung": {"header": "X-Demo-Session"}}}


class Kontakt(BaseModel):
    fremdkey: str = Field(..., description="Schlüssel im Quellsystem")
    name: str
    klasse: str = Field("", examples=["TEST_A1a"])
    art: str = Field("schueler", json_schema_extra={"enum": ["schueler", "eltern"]})


def demo_app() -> FastAPI:
    app = FastAPI(title="Demo-API", version="1.2.3")

    @app.get("/status", tags=["Status"], summary="Version und Schalter")
    def status():
        return {"ok": True}

    @app.get("/kontakte", tags=["Kontakte"])
    def kontakte(name: str | None = Query(None, examples=["Muster"]), format: str = "json",
                 x_api_key: str = Header(default=""), x_demo_session: str = Header(default="")):
        """Kontakte suchen. Zweiter Satz mit Details."""
        return []

    @app.get("/kontakte/{guid}", tags=["Kontakte"])
    def kontakt(guid: str):
        return {}

    @app.post("/kontakte", tags=["Kontakte"], summary="Kontakt anlegen")
    def anlegen(body: Kontakt, probelauf: bool = False):
        return {}

    @app.post("/pruefen", tags=["Kontakte"], summary="Nur prüfen",
              openapi_extra={"x-eduksx": {"effect": "read", "danger": False, "use": "Vorprüfung"}})
    def nur_pruefen(body: Kontakt):
        return {}

    @app.post("/dokumente", tags=["Dokumente"], summary="Datei hochladen")
    def hochladen(datei: UploadFile = File(...), titel: str = Form("", examples=["Zeugnis"]),
                  dateien: list[UploadFile] = File(default=[]), probelauf: bool = False):
        return {}

    @app.get("/spaeter", summary="Kommt noch", openapi_extra={"x-eduksx": {"status": "planned"}})
    def spaeter():
        return {}

    return app


def _eps(app=None):
    app = app or demo_app()
    m = manifest(app.openapi(), INFO)
    return m, {(e["method"], e["path"]): e for e in m["service"]["endpoints"]}


def test_grunddaten_im_format_des_intranets():
    m, _ = _eps()
    assert m["id"] == "eduksx-demo" and m["api"] == 1 and m["version"] == "1.2.3" and m["category"] == "school"
    assert m["service"]["auth"] == {"type": "header", "header": "X-API-Key", "setting": "api_key"}
    assert [s["key"] for s in m["settings"]] == ["base_url", "api_key"]
    assert next(s for s in m["settings"] if s["key"] == "api_key")["type"] == "password"
    assert m["data_notice"] == "Erfundene Daten" and m["x-eduksx"]["sitzung"]["header"] == "X-Demo-Session"


def test_beschriftung_gruppe_und_auto_summary():
    _, e = _eps()
    assert e[("GET", "/status")]["label"] == "Version und Schalter" and e[("GET", "/status")]["group"] == "Status"
    assert e[("GET", "/kontakte")]["label"] == "Kontakte suchen"            # erste Zeile/Satz des Docstrings
    assert e[("GET", "/kontakte/{guid}")]["label"] == "Kontakt"              # von FastAPI erzeugt …
    assert e[("GET", "/kontakte/{guid}")]["x-eduksx-ohne-beschreibung"]       # … und als fehlend markiert


def test_parameter_ohne_api_key_und_sitzung():
    _, e = _eps()
    namen = [p["name"] for p in e[("GET", "/kontakte")]["params"]]
    assert namen == ["name", "format"]
    assert e[("GET", "/kontakte")]["params"][0]["example"] == "Muster"
    assert e[("GET", "/kontakte")]["params"][1]["default"] == "json"
    assert e[("GET", "/kontakte/{guid}")]["params"] == [{"name": "guid", "in": "path", "required": True}]


def test_schreibend_mit_probelauf_body_und_feldern():
    _, e = _eps()
    post = e[("POST", "/kontakte")]
    assert post["danger"] is True and post["probelauf"] is True and post["status"] == "partial"
    assert post["body"] == {"fremdkey": "escola-650", "name": "Muster", "klasse": "TEST_A1a", "art": "schueler"}
    felder = {f["name"]: f for f in post["fields"]}
    assert felder["fremdkey"]["required"] and felder["fremdkey"]["help"] == "Schlüssel im Quellsystem"
    assert "probelauf" not in [p["name"] for p in post.get("params", [])]


def test_x_eduksx_uebersteuert():
    _, e = _eps()
    pr = e[("POST", "/pruefen")]
    assert "danger" not in pr and pr["effect"] == "read" and pr["use"] == "Vorprüfung"
    assert e[("GET", "/spaeter")]["status"] == "planned"


def test_multipart_mit_dateien():
    _, e = _eps()
    up = e[("POST", "/dokumente")]
    form = {f["name"]: f for f in up["form"]}
    assert form["datei"]["type"] == "file" and form["datei"]["required"]
    assert form["dateien"]["type"] == "file" and form["dateien"]["multiple"]
    assert form["titel"]["example"] == "Zeugnis" and up["file"] == {"field": "datei"} and up["probelauf"]


def test_ids_eindeutig_und_sprechend():
    m, e = _eps()
    ids = [x["id"] for x in m["service"]["endpoints"]]
    assert len(ids) == len(set(ids))
    assert e[("GET", "/kontakte/{guid}")]["id"] == "kontakte-guid" and e[("POST", "/kontakte")]["id"] == "post-kontakte"


def test_pruefen_meldet_fehlende_beschreibung_und_version():
    m, _ = _eps()
    fehler = pruefen(m, INFO)
    assert fehler == ["GET /kontakte/{guid}: keine Beschreibung (summary=… oder Docstring ergänzen)"]
    assert pruefen(m, {**INFO, "version": "9.9.9"})[0].startswith("Version 1.2.3")
    m["service"]["endpoints"][0]["status"] = "fertig"
    assert any("status muss" in f for f in pruefen(m, INFO, streng=False))


def test_schreibend_ohne_danger_wird_gemeldet():
    m, _ = _eps()
    for e in m["service"]["endpoints"]:
        if e["method"] == "POST" and e["path"] == "/kontakte":
            e.pop("danger")
    assert any("ohne «danger»" in f for f in pruefen(m, INFO))


def test_einbinden_liefert_plugin_json(tmp_path):
    import json
    (tmp_path / "api.json").write_text(json.dumps(INFO), encoding="utf-8")
    app = demo_app()
    einbinden(app, tmp_path)
    r = TestClient(app).get("/plugin.json")
    assert r.status_code == 200 and r.json()["id"] == "eduksx-demo"
    assert "/plugin.json" not in app.openapi()["paths"]


def test_cors_fuer_testplattform_auf_github_pages(tmp_path):
    """#51: die Pages-Seite darf die lokal laufende API direkt aufrufen, fremde Seiten nicht."""
    import json
    (tmp_path / "api.json").write_text(json.dumps(INFO), encoding="utf-8")
    app = demo_app()
    einbinden(app, tmp_path, origins=["https://markuskeller8200.github.io"])
    tc = TestClient(app)
    pages = {"Origin": "https://markuskeller8200.github.io", "Access-Control-Request-Method": "POST",
             "Access-Control-Request-Headers": "x-api-key,content-type", "Access-Control-Request-Private-Network": "true"}
    r = tc.options("/kontakte", headers=pages)
    assert r.status_code == 200
    assert r.headers["access-control-allow-origin"] == "https://markuskeller8200.github.io"
    assert r.headers["access-control-allow-private-network"] == "true"
    fremd = {**pages, "Origin": "https://boese.example"}
    r = tc.options("/kontakte", headers=fremd)
    assert r.status_code == 400 and "access-control-allow-origin" not in r.headers  # Browser blockiert
    assert tc.get("/status", headers={"Origin": "https://markuskeller8200.github.io"}).headers[
        "access-control-allow-origin"] == "https://markuskeller8200.github.io"


def test_cors_aus_umgebung():
    from shared.plugin_export import cors_origins
    assert cors_origins({}) == ["https://markuskeller8200.github.io"]
    assert cors_origins({"EDUKSX_CORS_ORIGINS": ""}) == []
    assert cors_origins({"EDUKSX_CORS_ORIGINS": "https://a.example/, http://127.0.0.1:8090"}) == ["https://a.example", "http://127.0.0.1:8090"]
