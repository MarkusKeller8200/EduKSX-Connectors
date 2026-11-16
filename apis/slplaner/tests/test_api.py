"""Tests gegen einen nachgebauten SL-Planer (httpx MockTransport), ohne Netzwerk.

Antworten aus den Beispielen der «SL-Planer API-Dokumentation» (Seabird AG, 18.2.2026), Personen erfunden.
Die Paginierung (meta.current_page/last_page) ist angenommen – Format laut Doku nicht beschrieben (ZU PRÜFEN).
"""
from __future__ import annotations

import base64
import json
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient

from slplaner_api import app as A
from slplaner_api.client import SLPlanerClient, SLPlanerConfig

FIX = Path(__file__).parent / "fixtures"


def lade(name: str):
    return json.loads((FIX / name).read_text(encoding="utf-8"))


class FakeSLPlaner:
    def __init__(self):
        self.aufrufe: list[httpx.Request] = []

    def __call__(self, req: httpx.Request) -> httpx.Response:
        self.aufrufe.append(req)
        if req.headers.get("Authorization") != "Bearer geheim":
            return httpx.Response(401, json={"detail": "unauthorized"})
        pfad, q = req.url.path, req.url.params
        if pfad == "/api/ressourcentypen":
            return httpx.Response(200, json=lade(f"ressourcentypen_seite{q.get('page', '1')}.json"))
        if pfad == "/api/klassenlektionen":
            return httpx.Response(200, json=lade("klassenlektionen.json"))
        if pfad == "/api/pensen":
            return httpx.Response(200, json=lade("pensen.json"))
        if pfad == "/api/pfiles/mab/m1":
            return httpx.Response(200, json=lade("mab.json"))
        if pfad == "/api/einheiten":  # Paginierung über Link «next»
            if q.get("cursor") == "2":
                return httpx.Response(200, json={"data": [{"name": "Stunde (60 Minuten)"}], "next": None})
            return httpx.Response(200, json={"data": [{"name": "Wochenlektion (WL)"}],
                                             "next": "https://slplaner.test/api/einheiten?cursor=2"})
        return httpx.Response(404, json={"detail": "not found"})


@pytest.fixture
def fake(monkeypatch):
    f = FakeSLPlaner()
    cfg = SLPlanerConfig(base_url="https://slplaner.test/api", token="geheim")
    monkeypatch.setattr(A, "_client", SLPlanerClient(cfg, transport=httpx.MockTransport(f)))
    monkeypatch.setattr(A, "API_KEY", "")
    monkeypatch.setattr(A, "PERSONALDOSSIER", False)
    return f


@pytest.fixture
def api():
    return TestClient(A.app)


def test_status_ohne_konfiguration(monkeypatch, api):
    monkeypatch.setattr(A, "_client", None)
    monkeypatch.delenv("SLPLANER_BASE_URL", raising=False)
    s = api.get("/status").json()
    assert s["ok"] is True and s["konfiguriert"] is False and s["schreiben"] is False
    assert api.get("/pensen").status_code == 501


def test_ressourcentypen_alle_seiten_und_rest(fake, api):
    r = api.get("/ressourcentypen", params={"sj": "2025/26"}).json()
    assert [x["name"] for x in r] == ["VZE Unterricht Primar", "DaZ"]
    assert r[0]["einh_rest"] == 1.5 and r[1]["einh_rest"] == -1.0  # DaZ überplant
    assert fake.aufrufe[0].url.params["sj"] == "2025/26"


def test_paginierung_ueber_next_link(fake, api):
    assert [e["name"] for e in api.get("/einheiten").json()] == ["Wochenlektion (WL)", "Stunde (60 Minuten)"]


def test_planung_csv_eine_zeile_pro_zuweisung(fake, api):
    r = api.get("/planung/klassenlektionen", params={"format": "csv"})
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/csv")
    zeilen = r.text.lstrip("﻿").strip().splitlines()
    assert len(zeilen) == 1 + 3  # Kopf + 2 Zuweisungen BS + M ohne Zuweisung
    kopf = zeilen[0].split(";")
    assert "zuweisung_name" in kopf and "ressourcentyp_name" in kopf


def test_unbekannter_bereich(fake, api):
    assert api.get("/planung/stundenplan").status_code == 422


def test_pensen_csv_uebersicht(fake, api):
    zeilen = api.get("/pensen", params={"format": "csv"}).text.lstrip("﻿").splitlines()
    kopf, werte = zeilen[0].split(";"), zeilen[1].split(";")
    z = dict(zip(kopf, werte))
    assert z["bg_total"] == "92" and z["wl_total"] == "24"
    assert z["arbeitszeit_differenz"] == "-3" and z["stunden_unterricht"] == "290.0"
    assert z["anstellungstypen"] == "Kantonal, Kommunal"


def test_nicht_gefunden_und_token_falsch(fake, api, monkeypatch):
    assert api.get("/pensen/unbekannt").status_code == 404
    monkeypatch.setattr(A._client.cfg, "token", "falsch")
    falsch = SLPlanerClient(SLPlanerConfig(base_url="https://slplaner.test/api", token="falsch"),
                            transport=httpx.MockTransport(fake))
    monkeypatch.setattr(A, "_client", falsch)
    assert api.get("/pensen").status_code == 401


def test_api_key_schuetzt(fake, api, monkeypatch):
    monkeypatch.setattr(A, "API_KEY", "k")
    assert api.get("/status").status_code == 401
    assert api.get("/status", headers={"X-API-Key": "k"}).status_code == 200


def test_personaldossier_standardmaessig_aus(fake, api):
    assert api.get("/mab/m1").status_code == 403
    assert fake.aufrufe == []  # SL-Planer gar nicht gefragt


def test_personaldossier_braucht_api_key(fake, api, monkeypatch):
    monkeypatch.setattr(A, "PERSONALDOSSIER", True)
    assert api.get("/mab/m1").status_code == 403


def test_mab_ohne_pdf_und_pdf_separat(fake, api, monkeypatch):
    monkeypatch.setattr(A, "PERSONALDOSSIER", True)
    monkeypatch.setattr(A, "API_KEY", "k")
    h = {"X-API-Key": "k"}
    m = api.get("/mab/m1", headers=h).json()
    assert m["beurteilungsresultat"] == "II" and "associated_document" not in m
    pdf = api.get("/mab/m1/pdf", headers=h)
    assert pdf.headers["content-type"] == "application/pdf"
    assert pdf.content == base64.b64decode(lade("mab.json")["associated_document"])


def test_lesen_loest_keine_schreibaufrufe_aus(fake, api):
    for pfad in ("/ressourcentypen", "/einheiten", "/planung/klassenlektionen", "/pensen"):
        api.get(pfad)
    assert fake.aufrufe and all(r.method == "GET" for r in fake.aufrufe)


def test_client_verweigert_schreiben():
    c = SLPlanerClient(SLPlanerConfig(base_url="https://slplaner.test/api", token="geheim"),
                       transport=httpx.MockTransport(lambda r: httpx.Response(200, json={})))
    with pytest.raises(RuntimeError):
        c._http.post("/pensen")


def test_fremder_server_im_next_link_wird_abgelehnt():
    def h(req):
        return httpx.Response(200, json={"data": [], "next": "https://boese.test/x"})
    c = SLPlanerClient(SLPlanerConfig(base_url="https://slplaner.test/api", token="geheim"),
                       transport=httpx.MockTransport(h))
    with pytest.raises(RuntimeError):
        c.liste("/einheiten")
