"""Anlegen von Personen/SuS und Klassen-Transfer – Antwortformate wie live am 14.11.2026 beobachtet."""
import json
from pathlib import Path
from urllib.parse import parse_qs

import httpx
from fastapi.testclient import TestClient

from escola_api.client import EscolaClient, EscolaConfig

FX = Path(__file__).parent / "fixtures"
CHOOSER = (FX / "chooser.html").read_text(encoding="utf-8")


class FakeAnlegen:
    def __init__(self):
        self.personen = {}  # id -> dict
        self.next_id = 652
        self.rpc = []
        self.transfers = []
        self.form_offen = None

    def __call__(self, req: httpx.Request) -> httpx.Response:
        p = req.url.path
        if p == "/admin.php":
            return httpx.Response(200, text="<html><body>" + CHOOSER + "</body></html>")
        if p.startswith("/rpc/collections/CaptureNewPersonAdmin/"):
            j = json.loads(req.content)
            s, ctx = j["parameters"]["newPersonStruct"], j["rpcContext"]
            self.rpc.append((p.rsplit("/", 1)[1], ctx))
            same = [q for q in self.personen.values() if (q["vorname"], q["nachname"]) == (s["firstName"], s["lastName"])]
            if p.endswith("checkForDuplicatePersonsRpc.php"):
                if not same:
                    return httpx.Response(200, text="null")
                return httpx.Response(200, json={"__type": "DuplicatePersonStructs", "duplicatePersonStructs": [
                    {"__type": "DuplicatePersonStruct", "id": q["id"], "displayName": f"{q['nachname']} {q['vorname']}",
                     "gender": s["gender"], "listOfAllRoles": "Schüler:innen", "active": True} for q in same]})
            pid = self.next_id
            self.next_id += 1
            self.personen[pid] = {"id": pid, "vorname": s["firstName"], "nachname": s["lastName"],
                                  "kategorie": ctx["personCategoryGroup"], "klasse": ctx["schoolclassId"]}
            return httpx.Response(200, text=f'[{pid},""]')
        form = {k: v[0] for k, v in parse_qs(req.content.decode(), keep_blank_values=True).items()}
        if p == "/inc/ajax/persons/show_reiter.php":
            return httpx.Response(200, text='<ul><li id="li_aktionen">Aktionen</li></ul>')
        if p == "/inc/ajax/persons/show_persons_of_group.php":
            cat = form["personCategory"]
            hits = [q for q in self.personen.values() if q["kategorie"] == cat and form["schoolUnitId"] == "1"]
            if cat == "schueler":
                feld = "klasse_kommend" if form["schoolYear"] == "1" else "klasse"
                hits = [q for q in self.personen.values() if q.get(feld) == int(form["schoolclassId"] or 0)]
            if not hits:
                return httpx.Response(200, text="Es sind keine Personen in dieser Personengruppe vorhanden.")
            return httpx.Response(200, text="<ul>" + "".join(
                f'<li id="li_{q["id"]}"><span id="name_person_{q["id"]}">{q["nachname"]}</span> '
                f'<span id="vorname_person_{q["id"]}">{q["vorname"]}</span></li>' for q in hits) + "</ul>")
        if p == "/inc/ajax/persons/personManagement.php":
            if "mode" not in form:  # Personenverwaltung mit Gruppenauswahl
                return httpx.Response(200, text='<select id="p_rubrik"><option value="allActive">alle aktiven Personen</option>'
                                                '<option value="lehrperson">Lehrpersonen</option><option value="gruppe_14">_neu</option></select>')
            if form.get("mode") == "13":
                self.form_offen = int(form["activePersonId"])
                if form["transferSchoolyear"] == "1":
                    opts = '<option value="92">zukünftige H_A2a - Schmid Schmelzbach</option><option value="120">zukünftige TEST_A1a</option>'
                else:
                    opts = '<option value="92">H_A1a - Schmid Schmelzbach</option><option value="93">H_A1b - Schmidt</option>'
                return httpx.Response(200, text='<span id="transfer-tutorial">Bitte wähle die Klasse …</span>'
                                                f'<form id="s_form"><select name="klassen_id_transfer">{opts}</select></form>')
            if form.get("mode") == "14":
                pid = int(form["activePersonId"])
                assert self.form_offen == pid and form["Submit"] == "Transfer ausführen"
                assert ("transferDate" in form) == (form["transferSchoolyear"] == "0")
                self.transfers.append(form)
                q = self.personen[pid]
                if form["transferSchoolyear"] == "1":
                    q["klasse_kommend"] = int(form["klassen_id_transfer"])
                    return httpx.Response(200, text='<div class="alert alert-success">Test Anlegen wurde für das kommende Schuljahr '
                                                    'erfolgreich in die Klasse H_A2a transferiert</div>')
                q.update(kategorie="schueler", klasse=int(form["klassen_id_transfer"]))
                return httpx.Response(200, text='<div class="alert alert-success" role="alert">'
                                                f'{q["nachname"]} {q["vorname"]} wurde ab 14.11.2026 in die Klasse H_A1a - Schmid Schmelzbach transferiert.'
                                                '<br /><br /><a onclick="personManagementGotoMode(16);">VORGANG WIDERRUFEN</a></div>')
            if form.get("mode") == "17":
                assert form["action"] in ("1008", "1009")
                pid = int(form["element_string"].strip(":"))
                self.form_offen = (pid, form["action"])
                nxt = 1 if form["action"] == "1009" else 0
                return httpx.Response(200, text=f'<div>Möchtest du bei Test Anlegen wirklich die Klassenzuteilung entfernen?'
                                                f'<a onclick="personManagementGotoMode(29, {{ isInNextSchoolyear: {nxt},schoolclassId: {form["schoolclassId"]},schoolYear:{form["schoolYear"]}}});">JA</a></div>')
            if form.get("mode") == "29":
                pid, act = self.form_offen
                q = self.personen[pid]
                if act == "1008":
                    q.update(kategorie="students-without-schoolclass", klasse=None)
                else:
                    q.pop("klasse_kommend", None)
                return httpx.Response(200, text='<div class="alert alert-success">Die Klassenzuordnungen wurden angepasst.</div>')
            raise AssertionError(f"unerwarteter personManagement-Aufruf {form}")
        return httpx.Response(404)


def make(monkeypatch, schreiben=True):
    monkeypatch.setenv("ESCOLA_SCHREIBEN", "1" if schreiben else "0")
    monkeypatch.setenv("ESCOLA_API_KEY", "k")
    from escola_api.app import create_app
    fake = FakeAnlegen()
    c = EscolaClient(EscolaConfig(base_url="https://x.test/", cookie="PHPSESSID=abc"), transport=httpx.MockTransport(fake))
    return fake, TestClient(create_app(c), headers={"X-API-Key": "k"})


def test_sus_ohne_klasse_anlegen_und_zuordnen(monkeypatch):
    fake, api = make(monkeypatch)
    r = api.post("/schueler", json={"nachname": "Test", "vorname": "Anlegen", "geschlecht": "w", "schulhaus": "Hinterbirch"})
    assert r.status_code == 201 and r.json()["id"] == 652
    assert fake.rpc[-1] == ("captureNewPersonRpc.php", {"personCategoryGroup": "students-without-schoolclass", "schoolclassId": None, "schoolUnitId": 1})
    ohne = api.get("/schueler", params={"ohne_klasse": True}).json()
    assert ohne == [{"id": 652, "nachname": "Test", "vorname": "Anlegen", "klasse_id": None, "klasse": None,
                     "schulhaus": "Hinterbirch", "status": "ohne Klasse"}]
    t = api.post("/schueler/652/klasse", json={"klasse_id": 92, "stichtag": "2026-11-14"})
    assert t.status_code == 200 and t.json()["transferiert"] is True and "transferiert" in t.json()["meldung"]
    assert "WIDERRUFEN" not in t.json()["meldung"]
    assert fake.transfers[0]["klassen_id_transfer"] == "92" and fake.transfers[0]["transferSchoolyear"] == "0"
    assert api.get("/schueler", params={"ohne_klasse": True}).json() == []
    assert [s["id"] for s in api.get("/schueler", params={"klasse_id": 92}).json()] == [652]


def test_duplikat_und_direkt_in_klasse(monkeypatch):
    fake, api = make(monkeypatch)
    api.post("/schueler", json={"nachname": "Test", "vorname": "Anlegen", "geschlecht": "w", "schulhaus": "Hinterbirch"})
    d = api.post("/schueler", json={"nachname": "Test", "vorname": "Anlegen", "geschlecht": "w", "schulhaus": "Hinterbirch"})
    assert d.status_code == 409 and d.json()["duplikate"][0] == {"id": 652, "name": "Test Anlegen", "rollen": "Schüler:innen", "aktiv": True}
    k = api.post("/schueler", json={"nachname": "Test", "vorname": "Anlegen", "geschlecht": "w", "schulhaus": "Hinterbirch",
                                    "klasse_id": 92, "trotz_duplikat": True})
    assert k.status_code == 201 and fake.rpc[-1][1] == {"personCategoryGroup": "schueler", "schoolclassId": 92, "schoolUnitId": 1}
    z = api.post("/schueler", json={"nachname": "Neu", "vorname": "Zukunft", "geschlecht": "m", "schulhaus": "Mettmenriet", "zukuenftig": True})
    assert z.status_code == 201 and fake.rpc[-1][1] == {"personCategoryGroup": "future-students", "schoolclassId": None, "schoolUnitId": 2}


def test_person_anlegen_und_pruefungen(monkeypatch):
    fake, api = make(monkeypatch)
    lp = api.post("/personen", json={"nachname": "Muster", "vorname": "Lea", "geschlecht": "w", "schulhaus": "Hinterbirch", "kategorie": "lehrperson"})
    assert lp.status_code == 201 and fake.personen[lp.json()["id"]]["kategorie"] == "lehrperson"
    assert api.post("/personen", json={"nachname": "A", "vorname": "B", "geschlecht": "w", "schulhaus": "Hinterbirch"}).status_code == 400
    assert api.post("/personen", json={"nachname": "A", "vorname": "B", "geschlecht": "w", "schulhaus": "Hinterbirch", "kategorie": "allActive"}).status_code == 400
    assert api.post("/schueler", json={"nachname": "A", "vorname": "B", "geschlecht": "w", "schulhaus": "Atlantis"}).status_code == 400
    assert api.post("/schueler", json={"nachname": " ", "vorname": "B", "geschlecht": "w", "schulhaus": "Hinterbirch"}).status_code == 400
    assert api.post("/schueler/652/klasse", json={"klasse_id": 9999}).status_code == 400
    assert api.post("/schueler/652/klasse", json={"klasse_id": 92, "stichtag": "14.11.2026"}).status_code == 400


def test_schreiben_aus_und_dokumente_platzhalter(monkeypatch):
    fake, api = make(monkeypatch, schreiben=False)
    assert api.post("/schueler", json={"nachname": "A", "vorname": "B", "geschlecht": "w", "schulhaus": "Hinterbirch"}).status_code == 403
    assert api.post("/schueler/652/klasse", json={"klasse_id": 92}).status_code == 403
    assert fake.rpc == [] and fake.transfers == []
    for url in ("/schueler/650/dokumente", "/schueler/650/dokumente/1", "/dokumente/struktur"):
        r = api.get(url)
        assert r.status_code == 501 and "noch nicht aktiviert" in r.json()["detail"]


def test_eigene_gruppe_neu(monkeypatch):
    fake, api = make(monkeypatch)
    k = api.get("/personen/rollen").json()
    assert {"rolle": "gruppe_14", "name": "_neu", "typ": "rolle"} in k
    assert {"rolle": "allActive", "name": "alle aktiven Personen", "typ": "ansicht"} in k
    assert api.get("/personen/kategorien").json() == k  # alter Name bleibt als Alias
    r = api.post("/personen", json={"nachname": "Neu", "vorname": "Mitarbeiterin", "geschlecht": "w",
                                    "schulhaus": "Hinterbirch", "rolle": "gruppe_14"})
    assert r.status_code == 201 and fake.rpc[-1] == ("captureNewPersonRpc.php", {"personCategoryGroup": "gruppe_14", "schoolclassId": None, "schoolUnitId": 1})
    assert api.post("/personen", json={"nachname": "A", "vorname": "B", "geschlecht": "w", "schulhaus": "Hinterbirch",
                                       "kategorie": "gruppe_99"}).status_code == 400


def test_umteilen_entfernen_kommendes_sj(monkeypatch):
    fake, api = make(monkeypatch)
    pid = api.post("/schueler", json={"nachname": "Test", "vorname": "Anlegen", "geschlecht": "w", "schulhaus": "Hinterbirch",
                                      "klasse_id": 92}).json()["id"]
    # Umteilung 92 -> 93 (aktuelles SJ)
    r = api.post(f"/schueler/{pid}/klasse", json={"klasse_id": 93, "stichtag": "2026-11-14"})
    assert r.status_code == 200 and fake.personen[pid]["klasse"] == 93
    # nicht angebotene Klasse wird abgewiesen, ohne Transfer
    n = len(fake.transfers)
    assert api.post(f"/schueler/{pid}/klasse", json={"klasse_id": 120}).status_code == 400 and len(fake.transfers) == n
    # Optionen fürs kommende SJ mit künftigen Namen
    o = api.get(f"/schueler/{pid}/klasse/optionen", params={"schuljahr": 1}).json()
    assert o[0] == {"id": 92, "name": "zukünftige H_A2a - Schmid Schmelzbach"}
    # Einteilung kommendes SJ (ohne Stichtag)
    k = api.post(f"/schueler/{pid}/klasse", json={"klasse_id": 92, "schuljahr": 1}).json()
    assert k["schuljahr"] == 1 and k["stichtag"] is None and "transferDate" not in fake.transfers[-1]
    # Entfernen kommendes SJ, dann aktuelles SJ (Klasse wird gesucht)
    e1 = api.delete(f"/schueler/{pid}/klasse", params={"schuljahr": 1})
    assert e1.status_code == 200 and "klasse_kommend" not in fake.personen[pid]
    e0 = api.delete(f"/schueler/{pid}/klasse")
    assert e0.status_code == 200 and e0.json()["klasse_id"] == 93
    assert fake.personen[pid]["kategorie"] == "students-without-schoolclass"
    assert api.delete(f"/schueler/{pid}/klasse").status_code == 400  # keine Klasse mehr
