"""Schullaufbahn / Klassenbeginn (L19) – Antwortformen wie live am 24.11.2026 gelesen
(RPC SchoolCareer: getSchoolCareer, getEntryEditFields, updateEntry). Testobjekt SuS SuS (650), TEST_A1a (120)."""
import datetime as dt
import json

import httpx
import pytest
from fastapi.testclient import TestClient

from escola_api.app import create_app
from escola_api.client import EscolaClient, EscolaConfig, KonfliktFehler


class Fake:
    def __init__(self, eintraege=None):
        # (editId, klasse_id, titel, von, bis)
        self.eintraege = eintraege if eintraege is not None else [["176", "120", "TEST_A1a", "2026-11-24", "2027-07-31"]]
        self.updates = []
        self.next_id = 181

    def timeline(self):
        return {"__type": "TimelinePackageStruct", "accessibleModules": [], "timeline": [
            {"__type": "TimelineSchoolyearStruct", "schoolyear": 2026, "schoolyearLabel": "2026/27", "entries": [
                {"__type": "TimelineEntryStruct", "module": "studentGroupsSchoolclass", "dateFrom": von, "dateTo": bis,
                 "isDateRange": True, "title": titel, "editId": eid,
                 "fields": [{"__type": "TimelineEntryFieldStruct", "title": "Jahrgangsstufe", "content": "1. Sekundarschule"},
                            {"__type": "TimelineEntryFieldStruct", "title": "Schuleinheit", "content": "Hinterbirch"}]}
                for eid, _, titel, von, bis in self.eintraege]}]}

    def __call__(self, req: httpx.Request):
        p = req.url.path
        body = json.loads(req.content) if req.content else {}
        par = body.get("parameters", {})
        if p.endswith("getSchoolCareer.php"):
            assert par["personId"] == 650
            return httpx.Response(200, json=self.timeline())
        if p.endswith("getEntryEditFields.php"):
            e = next(x for x in self.eintraege if x[0] == par["editId"])
            return httpx.Response(200, json=[
                {"__type": "EditFieldStruct", "type": "schoolclass", "title": "Klasse", "value": e[1], "options": []},
                {"__type": "EditFieldStruct", "type": "levelYear", "title": "Jahrgangsstufe", "value": "9", "disabled": True}])
        if p.endswith("updateEntry.php"):
            self.updates.append(par)
            e = next(x for x in self.eintraege if x[0] == par["editId"])
            e[0], e[3], e[4] = str(self.next_id), par["dateFrom"], par["dateTo"]  # Escola vergibt eine neue editId
            self.next_id += 1
            return httpx.Response(200, content=b"")
        return httpx.Response(500)


def client(fake):
    c = EscolaClient(EscolaConfig(base_url="https://x/", cookie="x"), transport=httpx.MockTransport(fake))
    c._sj_start = staticmethod(lambda heute=None: 2026)
    return c


def test_schullaufbahn_lesen():
    c = client(Fake())
    e = c.schullaufbahn(650)
    assert e == [{"schuljahr": 2026, "schuljahr_text": "2026/27", "modul": "studentGroupsSchoolclass", "titel": "TEST_A1a",
                  "von": "2026-11-24", "bis": "2027-07-31", "edit_id": "176",
                  "felder": {"Jahrgangsstufe": "1. Sekundarschule", "Schuleinheit": "Hinterbirch"}}]


def test_klassenbeginn_schuljahresbeginn_wie_escola_dialog():
    f = Fake()
    c = client(f)
    r = c.klassenbeginn_setzen(650, "schuljahresbeginn")
    assert r["geaendert"] and r["von_alt"] == "2026-11-24" and r["von_neu"] == "2026-08-01"
    # genau der Aufruf, den der Escola-Dialog „Klassen bearbeiten“ sendet
    assert f.updates == [{"personId": 650, "module": "studentGroupsSchoolclass", "editId": "176", "schoolyear": 2026,
                          "dateFrom": "2026-08-01", "dateTo": "2027-07-31",
                          "values": [{"type": "schoolclass", "value": "120"}, {"type": "levelYear", "value": "9"}]}]


def test_klassenbeginn_probelauf_und_unveraendert():
    f = Fake()
    c = client(f)
    assert c.klassenbeginn_setzen(650, "2026-08-01", probelauf=True)["geaendert"] is False and not f.updates
    f.eintraege[0][3] = "2026-08-01"
    r = c.klassenbeginn_setzen(650)
    assert r["meldung"] == "Beginn stimmt bereits" and not f.updates


def test_klassenbeginn_eintritt_spaeter_als_schuljahresbeginn():
    f = Fake()
    c = client(f)
    c._eintrittsdatum = lambda pid: "2026-10-19"
    assert c.klassenbeginn_setzen(650, "eintritt")["von_neu"] == "2026-10-19"
    f2 = Fake()
    c2 = client(f2)
    c2._eintrittsdatum = lambda pid: "2024-08-01"  # Eintritt in früherem Schuljahr -> 1.8.
    assert c2.klassenbeginn_setzen(650, "eintritt")["von_neu"] == "2026-08-01"


def test_klassenbeginn_pruefungen():
    c = client(Fake())
    with pytest.raises(ValueError):
        c.klassenbeginn_setzen(650, "2025-08-01")  # nicht im Schuljahr
    with pytest.raises(ValueError):
        c.klassenbeginn_setzen(650, "morgen")
    zwei = Fake([["176", "92", "H_A1a", "2026-08-01", "2026-11-23"], ["177", "120", "TEST_A1a", "2026-11-24", "2027-07-31"]])
    with pytest.raises(KonfliktFehler) as e:
        client(zwei).klassenbeginn_setzen(650)
    assert len(e.value.personen) == 2
    # mit edit_id gezielt – hier aber unzulässig: Beginn nach Ende des Eintrags
    with pytest.raises(ValueError):
        client(zwei).klassenbeginn_setzen(650, "2026-12-01", edit_id="176")


def test_endpunkte(monkeypatch):
    monkeypatch.setenv("ESCOLA_SCHREIBEN", "1")
    monkeypatch.setenv("ESCOLA_API_KEY", "k")
    f = Fake()
    c = client(f)
    c.schueler = lambda refresh=False, schuljahr=0: [
        {"id": 650, "nachname": "SuS", "vorname": "SuS", "klasse_id": 120, "klasse": "TEST_A1a", "schulhaus": "Hinterbirch"}]
    c._eintrittsdatum = lambda pid: None
    api = TestClient(create_app(client=c))
    h = {"X-API-Key": "k"}
    assert api.get("/schueler/650/schullaufbahn", headers=h).json()[0]["von"] == "2026-11-24"
    r = api.post("/klassen/120/klassenbeginn?probelauf=true", json={}, headers=h).json()
    assert r["anzahl"] == 1 and r["geaendert"] == 0 and r["schueler"][0]["von_neu"] == "2026-08-01" and not f.updates
    r = api.put("/schueler/650/klasse/beginn", json={"ab": "schuljahresbeginn"}, headers=h)
    assert r.status_code == 200 and r.json()["geaendert"] and len(f.updates) == 1
    assert api.put("/schueler/650/klasse/beginn", json={"ab": "2025-01-01"}, headers=h).status_code == 400


def test_schreiben_aus_nur_probelauf(monkeypatch):
    monkeypatch.delenv("ESCOLA_SCHREIBEN", raising=False)
    f = Fake()
    api = TestClient(create_app(client=client(f)))
    assert api.put("/schueler/650/klasse/beginn", json={}).status_code == 403
    assert api.put("/schueler/650/klasse/beginn?probelauf=true", json={}).status_code == 200 and not f.updates


def test_sj_start():
    assert EscolaClient._sj_start(dt.date(2026, 11, 24)) == 2026
    assert EscolaClient._sj_start(dt.date(2027, 7, 31)) == 2026
    assert EscolaClient._sj_start(dt.date(2027, 8, 1)) == 2027
