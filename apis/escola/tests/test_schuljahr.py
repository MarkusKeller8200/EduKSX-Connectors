"""Schuljahr vorbereiten (WF-11, WF-13, WF-14, WF-17): Klassenlisten, Eltern einer Klasse, Import-Vorprüfung."""
import json

import httpx
from fastapi.testclient import TestClient

from escola_api.app import create_app
from escola_api.client import EscolaClient, EscolaConfig

KLASSEN = [{"id": 92, "typ": "Klasse", "name": "H_A1a", "bezeichnung": "", "klassenlehrperson": "Muster Anna", "schulhaus": "Hinterbirch"},
           {"id": 120, "typ": "Klasse", "name": "TEST_A1a", "bezeichnung": "", "klassenlehrperson": "", "schulhaus": "Hinterbirch"},
           {"id": 3, "typ": "Arbeitsgruppe", "name": "TEST", "bezeichnung": "", "klassenlehrperson": "", "schulhaus": "Hinterbirch"}]
SUS = [{"id": 651, "nachname": "Zeta", "vorname": "Ben", "klasse_id": 92, "klasse": "H_A1a", "schulhaus": "Hinterbirch"},
       {"id": 650, "nachname": "SuS", "vorname": "SuS", "klasse_id": 120, "klasse": "TEST_A1a", "schulhaus": "Hinterbirch"},
       {"id": 652, "nachname": "Alpha", "vorname": "Eva", "klasse_id": 92, "klasse": "H_A1a", "schulhaus": "Hinterbirch"}]


def client(handler=None):
    geschrieben = []

    def h(req: httpx.Request):
        if req.url.path.endswith("checkForDuplicatePersonsRpc.php"):
            st = json.loads(req.content)["parameters"]["newPersonStruct"]
            dups = [{"id": 649, "displayName": "TEST TEST", "listOfAllRoles": "Eltern", "active": True}] \
                if st["lastName"] == "TEST" else []
            return httpx.Response(200, json={"duplicatePersonStructs": dups})
        geschrieben.append(str(req.url))
        return httpx.Response(500)

    c = EscolaClient(EscolaConfig(base_url="https://x/", cookie="x"), transport=httpx.MockTransport(handler or h))
    c.klassen = lambda refresh=False: KLASSEN
    c.schueler = lambda refresh=False, schuljahr=0: SUS
    c.bezugspersonen = lambda pid: [{"person_id": 649, "name": "TEST TEST", "funktion": "Mutter", "sorgerecht": "sorgeberechtigt",
                                     "aktiv": True, "gleiche_adresse": True}] if pid == 650 else []
    return c, geschrieben


def test_klassenlisten_sortiert_mit_klp_und_csv():
    c, _ = client()
    rows = c.klassenlisten()
    assert [r["schueler_id"] for r in rows] == [652, 651, 650]
    assert rows[0]["klassenlehrperson"] == "Muster Anna" and rows[2]["klasse"] == "TEST_A1a"
    api = TestClient(create_app(client=c))
    r = api.get("/klassenlisten?format=csv&schulhaus=Hinterbirch")
    assert r.status_code == 200 and "klassenlehrperson" in r.text and "Alpha" in r.text


def test_eltern_der_klasse_zeigt_luecken():
    c, _ = client()
    rows = c.eltern_der_klasse(120)
    assert rows == [{"schueler_id": 650, "schueler": "SuS SuS", "bezugsperson_id": 649, "bezugsperson": "TEST TEST",
                     "funktion": "Mutter", "sorgerecht": "sorgeberechtigt", "aktiv": True, "gleiche_adresse": True}]
    leer = c.eltern_der_klasse(92)
    assert len(leer) == 2 and all(r["bezugsperson_id"] is None for r in leer)


def test_import_pruefen_legt_nichts_an():
    c, geschrieben = client()
    api = TestClient(create_app(client=c))
    r = api.post("/import/pruefen", json={"personen": [
        {"nachname": "TEST", "vorname": "TEST", "geschlecht": "w", "art": "eltern"},
        {"nachname": "Neu", "vorname": "Lea", "geschlecht": "w", "schulhaus": "Hinterbirch"},
        {"nachname": "Ohne", "vorname": "", "geschlecht": "x"}]})
    assert r.status_code == 200
    a, b, f = r.json()
    assert a["status"] == "moegliche_duplikate" and a["duplikate"][0]["id"] == 649
    assert b["status"] == "neu" and f["status"] == "fehler" and len(f["fehler"]) == 2
    assert geschrieben == []  # nur die Duplikatprüfung wurde aufgerufen
