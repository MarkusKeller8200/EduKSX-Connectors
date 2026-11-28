"""Testplattform gegen nachgebaute APIs (httpx MockTransport, ohne Netzwerk). Erfundene Daten."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient

HIER = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HIER))
from testplattform.app import Plugin, create_app, endpunkt_finden, plugins_aus_repo  # noqa: E402

KEY = "geheim-123"
OPENAPI = {
    "openapi": "3.1.0", "info": {"title": "Fake-API", "version": "0.1.0"},
    "paths": {
        "/status": {"get": {"summary": "Status", "operationId": "status_status_get", "tags": ["Status"]}},
        "/kontakte": {
            "get": {"summary": "Kontakte suchen", "operationId": "k_kontakte_get", "tags": ["Kontakte"],
                    "parameters": [{"name": "name", "in": "query", "schema": {"type": "string"}}]},
            "post": {"summary": "Kontakt anlegen", "operationId": "a_kontakte_post", "tags": ["Kontakte"],
                     "parameters": [{"name": "probelauf", "in": "query", "schema": {"type": "boolean", "default": False}}],
                     "requestBody": {"content": {"application/json": {"schema": {
                         "type": "object", "required": ["name"], "properties": {"name": {"type": "string"}}}}}}}},
        "/kontakte/sync": {"post": {"summary": "Abgleichen", "operationId": "s_kontakte_sync_post", "tags": ["Kontakte"]}},
        "/kontakte/{guid}": {"get": {"summary": "Ein Kontakt", "operationId": "e_kontakte__guid__get", "tags": ["Kontakte"],
                                     "parameters": [{"name": "guid", "in": "path", "required": True, "schema": {"type": "string"}}]},
                             "delete": {"summary": "Löschen", "operationId": "d_kontakte__guid__delete", "tags": ["Kontakte"]}},
        "/auth/login": {"post": {"summary": "Anmelden", "operationId": "l_auth_login_post", "tags": ["Anmeldung"],
                                 "x-eduksx": {"effect": "read", "danger": False}}},
        "/geplant": {"get": {"summary": "Später", "operationId": "g_geplant_get", "x-eduksx": {"status": "planned"}}},
    },
}


class FakeApi:
    """Nimmt alle Anfragen entgegen, merkt sie sich; mit_plugin_json=False → 404 auf /plugin.json."""

    def __init__(self, mit_plugin_json: bool = False):
        self.anfragen: list[httpx.Request] = []
        self.mit_plugin_json = mit_plugin_json

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.anfragen.append(request)
        if request.headers.get("x-api-key") != KEY:
            return httpx.Response(401, json={"detail": "X-API-Key fehlt oder ist falsch"})
        p = request.url.path
        if p == "/plugin.json":
            if not self.mit_plugin_json:
                return httpx.Response(404, json={"detail": "Not Found"})
            from shared.plugin_export import manifest
            return httpx.Response(200, json=manifest(OPENAPI, {"name": "fake", "version": "0.1.0"}))
        if p == "/openapi.json":
            return httpx.Response(200, json=OPENAPI)
        if p == "/status":
            return httpx.Response(200, json={"ok": True, "version": "0.1.0", "konfiguriert": True})
        if p == "/kontakte" and request.method == "GET":
            return httpx.Response(200, json=[{"guid": "g-1", "name": "Muster"}])
        if p == "/kontakte/sync":
            return httpx.Response(200, json={"vollstaendig": True})
        if p == "/kontakte" and request.method == "POST":
            return httpx.Response(201 if request.url.params.get("probelauf") != "true" else 200,
                                  json={"probelauf": request.url.params.get("probelauf") == "true",
                                        "body": json.loads(request.content or b"{}")})
        if p.startswith("/kontakte/"):
            return httpx.Response(200, json={"guid": p.rsplit("/", 1)[1]})
        if p == "/auth/login":
            return httpx.Response(200, json={"status": "angemeldet", "session": "s-1",
                                             "gesehen": request.headers.get("x-fake-session")})
        return httpx.Response(404, json={"detail": "unbekannt"})


def fake_plugin(key: str = KEY) -> Plugin:
    return Plugin(name="fake", titel="Fake-API", version="0.1.0", base_url="http://fake.test", api_key=key,
                  info={"name": "fake", "version": "0.1.0", "plugin": {"sitzung": {"header": "X-Fake-Session"}}})


@pytest.fixture
def api():
    return FakeApi()


@pytest.fixture
def tc(api):
    return TestClient(create_app([fake_plugin()], httpx.MockTransport(api), token=""))


def test_startseite_und_statische_dateien(tc):
    assert "Testplattform" in tc.get("/").text
    assert tc.get("/static/plattform.js").status_code == 200
    assert tc.get("/static/../app.py").status_code == 404


def test_plugins_ohne_api_key_in_der_antwort(tc):
    r = tc.get("/api/plugins")
    assert r.status_code == 200
    p = r.json()[0]
    assert p["erreichbar"] and p["status"]["version"] == "0.1.0" and p["api_key_gesetzt"] is True
    assert KEY not in r.text


def test_nicht_erreichbar():
    def kaputt(_):
        raise httpx.ConnectError("weg")
    tc = TestClient(create_app([fake_plugin()], httpx.MockTransport(kaputt), token=""))
    assert tc.get("/api/plugins").json()[0]["erreichbar"] is False
    r = tc.get("/api/plugins/fake/manifest")
    assert r.status_code == 503 and "nicht erreichbar" in r.json()["detail"]


def test_manifest_aus_openapi_wenn_plugin_json_fehlt(tc):
    m = tc.get("/api/plugins/fake/manifest").json()["manifest"]
    assert m["x-eduksx"]["quelle_beschreibung"] == "openapi.json"
    ids = {e["id"]: e for e in m["service"]["endpoints"]}
    assert ids["post-kontakte"]["danger"] and ids["post-kontakte"]["probelauf"]
    assert "danger" not in ids["post-auth-login"]


def test_manifest_aus_plugin_json():
    tc = TestClient(create_app([fake_plugin()], httpx.MockTransport(FakeApi(mit_plugin_json=True)), token=""))
    assert tc.get("/api/plugins/fake/manifest").json()["manifest"]["x-eduksx"]["quelle_beschreibung"] == "plugin.json"


def test_lesen_setzt_api_key_und_gibt_werte_durch(tc, api):
    r = tc.get("/api/plugins/fake/aufruf/kontakte", params={"name": "Muster"})
    assert r.status_code == 200 and r.json()[0]["guid"] == "g-1"
    assert r.headers["x-endpunkt"] == "kontakte" and "x-dauer-ms" in r.headers
    letzte = api.anfragen[-1]
    assert letzte.headers["x-api-key"] == KEY and letzte.url.params["name"] == "Muster"


def test_platzhalter_und_feste_pfade(tc):
    assert tc.get("/api/plugins/fake/aufruf/kontakte/g-7").json() == {"guid": "g-7"}
    m = tc.get("/api/plugins/fake/manifest").json()["manifest"]
    assert endpunkt_finden(m, "POST", "/kontakte/sync")["id"] == "post-kontakte-sync"
    assert endpunkt_finden(m, "GET", "/kontakte/a/b") is None


def test_nur_endpunkte_aus_der_beschreibung(tc):
    r = tc.get("/api/plugins/fake/aufruf/admin")
    assert r.status_code == 404 and "Beschreibung" in r.json()["detail"]
    assert tc.get("/api/plugins/fake/aufruf/kontakte/%2E%2E/status").status_code in (400, 404)
    assert tc.get("/api/plugins/unbekannt/aufruf/status").status_code == 404


def test_geplant_nicht_aufrufbar(tc):
    assert tc.get("/api/plugins/fake/aufruf/geplant").status_code == 409


def test_schreiben_ohne_probelauf_braucht_bestaetigung(tc, api):
    vorher = len(api.anfragen)
    r = tc.post("/api/plugins/fake/aufruf/kontakte", json={"name": "Muster"})
    assert r.status_code == 428 and r.json()["fehler"] == "bestaetigung_noetig"
    assert not [a for a in api.anfragen[vorher:] if a.method == "POST"], "ohne Bestätigung nichts senden"
    # Probelauf geht ohne Bestätigung
    r = tc.post("/api/plugins/fake/aufruf/kontakte?probelauf=true", json={"name": "Muster"})
    assert r.status_code == 200 and r.json()["probelauf"] is True and r.json()["body"] == {"name": "Muster"}
    # mit Bestätigung
    r = tc.post("/api/plugins/fake/aufruf/kontakte", json={"name": "Muster"}, headers={"X-Testplattform-Bestaetigt": "ja"})
    assert r.status_code == 201
    # DELETE ebenfalls nur mit Bestätigung
    assert tc.delete("/api/plugins/fake/aufruf/kontakte/g-1").status_code == 428


def test_anmeldung_lesend_und_sitzung_weitergeben(tc, api):
    r = tc.post("/api/plugins/fake/aufruf/auth/login", json={"benutzername": "test", "passwort": "x"},
                headers={"X-Fake-Session": "s-0", "X-Andere": "nicht weitergeben"})
    assert r.status_code == 200 and r.json()["gesehen"] == "s-0"
    assert "x-andere" not in api.anfragen[-1].headers


def test_protokoll_ohne_werte(tc):
    tc.get("/api/plugins/fake/aufruf/kontakte", params={"name": "Geheimname"})
    tc.post("/api/plugins/fake/aufruf/auth/login", json={"benutzername": "lea", "passwort": "Passwort1"})
    r = tc.get("/api/protokoll")
    text = r.text
    assert "Geheimname" not in text and "Passwort1" not in text and KEY not in text
    assert r.json()[0]["endpunkt"] == "post-auth-login" and r.json()[1]["pfad"] == "/kontakte"


def test_falscher_key_der_api_wird_durchgereicht():
    tc = TestClient(create_app([fake_plugin("falsch")], httpx.MockTransport(FakeApi()), token=""))
    assert tc.get("/api/plugins").json()[0]["status_code"] == 401


def test_zugangsschluessel(api):
    tc = TestClient(create_app([fake_plugin()], httpx.MockTransport(api), token="tp"))
    assert tc.get("/api/info").json()["token_noetig"] is True
    assert tc.get("/api/plugins").status_code == 401
    assert tc.get("/api/plugins", headers={"X-Testplattform-Token": "tp"}).status_code == 200


def test_plugins_aus_repo_liest_api_json_und_env(tmp_path):
    (tmp_path / "apis" / "cmi").mkdir(parents=True)
    (tmp_path / "apis" / "_vorlage").mkdir(parents=True)
    (tmp_path / "apis" / "cmi" / "api.json").write_text(json.dumps(
        {"name": "cmi", "titel": "CMI-API", "version": "0.9.0", "plugin": {"port": 8082}}), encoding="utf-8")
    (tmp_path / "apis" / "_vorlage" / "api.json").write_text(json.dumps({"name": "_vorlage", "version": "0.1.0"}))
    (tmp_path / "apis" / "cmi" / ".env").write_text("CMI_API_KEY=aus-datei\n# Kommentar\nCMI_SCHREIBEN=1\n")
    p = plugins_aus_repo(tmp_path, {})
    assert [x.name for x in p] == ["cmi"] and p[0].base_url == "http://127.0.0.1:8082" and p[0].api_key == "aus-datei"
    p = plugins_aus_repo(tmp_path, {"CMI_URL": "http://cmi.local:9000/", "CMI_API_KEY": "aus-env", "TESTPLATTFORM_VORLAGE": "1"})
    cmi = next(x for x in p if x.name == "cmi")
    assert len(p) == 2 and cmi.base_url == "http://cmi.local:9000" and cmi.api_key == "aus-env"
    assert "aus-env" not in repr(cmi)


def test_alle_apis_im_repo_sind_plugins():
    namen = [p.name for p in plugins_aus_repo(umgebung={})]
    assert {"escola", "cmi", "slplaner"} <= set(namen)


def test_pages_bauen_ohne_geheimnisse(tmp_path):
    """#51: statische Seite mit plugins.json, relative Pfade, keine Keys."""
    import pages_bauen
    ziel = pages_bauen.bauen(tmp_path / "_site")
    daten = json.loads((ziel / "plugins.json").read_text(encoding="utf-8"))
    namen = {p["name"]: p for p in daten["plugins"]}
    assert {"escola", "cmi", "slplaner"} <= set(namen) and "_vorlage" not in namen
    assert namen["cmi"]["port"] == 8082 and namen["escola"]["sitzung"]["header"] == "X-Escola-Session"
    assert (ziel / "static" / "plattform.js").exists() and (ziel / ".nojekyll").exists()
    html = (ziel / "index.html").read_text(encoding="utf-8")
    assert 'src="static/plattform.js"' in html and 'href="/static' not in html
    assert "API_KEY" not in (ziel / "plugins.json").read_text(encoding="utf-8")
    # Doku ohne laufende API: Beschreibung jeder API statisch, Escola mit Themen in fester Reihenfolge
    esc = json.loads((ziel / "manifeste" / "escola.json").read_text(encoding="utf-8"))
    themen = [g["name"] for g in esc["x-eduksx"]["gruppen"]]
    assert themen[0] == "Anmeldung und System" and "Absenzen" in themen
    assert {e["group"] for e in esc["service"]["endpoints"]} == set(themen)
    for datei in (ziel / "manifeste").glob("*.json"):
        assert "API_KEY=" not in datei.read_text(encoding="utf-8")


def test_start_lokal_legt_env_mit_schreiben_aus_an(tmp_path):
    """#50: fehlende .env aus .env.example, neuer API-Key, Schreiben aus; vorhandene bleibt unverändert."""
    import start_lokal
    (tmp_path / ".env.example").write_text("# Kommentar\nCMI_API_KEY=\nCMI_SCHREIBEN=1\nCMI_MANDANT=demo\n", encoding="utf-8")
    assert start_lokal.env_anlegen(tmp_path, "CMI_") is True
    werte = start_lokal.env_lesen(tmp_path / ".env")
    assert len(werte["CMI_API_KEY"]) > 20 and werte["CMI_SCHREIBEN"] == "0" and werte["CMI_MANDANT"] == "demo"
    vorher = (tmp_path / ".env").read_text(encoding="utf-8")
    assert start_lokal.env_anlegen(tmp_path, "CMI_") is False
    assert (tmp_path / ".env").read_text(encoding="utf-8") == vorher


def test_startseite_mit_relativen_pfaden_und_plugins_json_fehlt(tc):
    """Lokale Plattform: kein plugins.json → Oberfläche nutzt die Plattform (/api/…)."""
    assert tc.get("/plugins.json").status_code == 404
    assert 'src="static/plattform.js"' in tc.get("/").text
