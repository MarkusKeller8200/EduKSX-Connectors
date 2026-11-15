"""Modul Ressourcen: Ressourcenliste und Zeiteinteilung (Aufbau wie live am 14.11.2026)."""
from pathlib import Path
from urllib.parse import parse_qs

import httpx
from fastapi.testclient import TestClient

from escola_api import parsers as P
from escola_api.client import EscolaClient, EscolaConfig

FX = Path(__file__).parent / "fixtures"
fx = lambda n: (FX / n).read_text(encoding="utf-8")


def test_parser_ressourcen():
    r = P.parse_ressourcen(fx("ressourcen.html"))
    assert [x["id"] for x in r] == [9, 37, 106, 170]
    a = r[0]
    assert a == {"id": 9, "kuerzel": "A101", "name": "EG - 101 - Klassenzimmer", "geschoss": "EG", "nummer": "101",
                 "bezeichnung": "Klassenzimmer", "kategorie_id": 1, "kategorie": "Hibi - Trakt A", "kategorie_typ": "Räume",
                 "zeitprofil": "HIBI - Lektionen", "reservierbar": False, "schulhaus": "Hinterbirch"}
    assert r[1]["reservierbar"] is True and r[1]["kuerzel"] == "A105"
    assert r[2]["schulhaus"] == "Mettmenriet" and r[2]["kuerzel"] == "OGRO1" and r[2]["bezeichnung"] == "Gruppenraum"
    assert r[3]["kategorie_id"] == 169 and r[3]["kategorie"] == "Mettmi - Trakt ZENTRUM"


def test_parser_zeiten():
    profile, gewaehlt = P.parse_zeitprofile(fx("zeiteinteilung.html"))
    assert profile == [{"id": 1, "name": "HIBI - Lektionen", "schulhaus": "Hinterbirch"},
                       {"id": 2, "name": "METTMI - Lektionen", "schulhaus": "Mettmenriet"}] and gewaehlt == 1
    z = P.parse_zeiten(fx("zeiteinteilung.html"))
    assert z[0] == {"id": 12, "nr": 1, "von": "07.30", "bis": "08.15"} and z[2]["von"] == "13.10"


class Fake:
    def __init__(self):
        self.profil = 1
        self.calls = []

    def __call__(self, req):
        p = req.url.path
        f = {k: v[0] for k, v in parse_qs(req.content.decode(), keep_blank_values=True).items()}
        self.calls.append(p)
        if p.endswith("rooms.php"):
            return httpx.Response(200, text=fx("ressourcen.html"))
        if p.endswith("stundeneinteilung.php"):
            if f.get("mode") == "0":
                self.profil = int(f["selectedProfile"])
            html = fx("zeiteinteilung.html")
            if self.profil == 2:
                html = html.replace('value="1" selected=""', 'value="1"').replace('value="2"', 'value="2" selected=""') \
                           .replace("13.10 - 13.55", "13.00 - 13.45")
            return httpx.Response(200, text=html)
        return httpx.Response(404)


def test_api_ressourcen(monkeypatch):
    monkeypatch.delenv("ESCOLA_API_KEY", raising=False)
    from escola_api.app import create_app
    fake = Fake()
    c = EscolaClient(EscolaConfig(base_url="https://x.test/", cookie="PHPSESSID=a"), transport=httpx.MockTransport(fake))
    api = TestClient(create_app(c))
    assert len(api.get("/ressourcen").json()) == 4
    assert [r["id"] for r in api.get("/ressourcen", params={"schulhaus": "Mettmenriet"}).json()] == [106, 170]
    assert [r["id"] for r in api.get("/ressourcen", params={"nur_reservierbar": True}).json()] == [37]
    k = api.get("/ressourcen/kategorien").json()
    assert {"id": 1, "name": "Hibi - Trakt A", "typ": "Räume", "schulhaus": "Hinterbirch", "anzahl": 2} in k
    z = api.get("/ressourcen/zeiteinteilung").json()
    assert [p["name"] for p in z] == ["HIBI - Lektionen", "METTMI - Lektionen"]
    assert z[1]["zeiten"][2]["von"] == "13.00" and fake.profil == 1  # Auswahl wieder wie vorher
    # /raeume nutzt jetzt das Ressourcen-Modul -> beide Schulhäuser
    r = api.get("/raeume").json()
    assert {x["schulhaus"] for x in r} == {"Hinterbirch", "Mettmenriet"} and len(r) == 4
    csv = api.get("/ressourcen", params={"format": "csv"}).text.lstrip("﻿").splitlines()
    assert csv[0].startswith("id;kuerzel;name;geschoss") and len(csv) == 5
