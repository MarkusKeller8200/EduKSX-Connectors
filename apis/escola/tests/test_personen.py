"""Tests für Personen / Schüler:innen (lesen + schreiben) gegen echte, gekürzte Escola-Antworten."""
import html as _html
import re
from pathlib import Path
from urllib.parse import parse_qs

import httpx
import pytest
from fastapi.testclient import TestClient

from escola_api import personen as PP
from escola_api.client import EscolaClient, EscolaConfig

FX = Path(__file__).parent / "fixtures"
fx = lambda n: (FX / n).read_text(encoding="utf-8")


# ------------------------------------------------------------------ Parser
def test_reiter_und_bearbeitungsmodus():
    r = PP.parse_reiter(fx("person_reiter.html"))
    assert "personalien" in r and "health" in r and r[0] == "aktionen"
    assert PP.bearbeitungsmodus_an(fx("person_name.html")) is True


def test_abschnitt_name():
    f = {x.name: x for x in PP.parse_abschnitt(fx("person_name.html"), "name")}
    assert f["name"].wert == "sus" and f["name"].typ == "text"
    assert f["student_number"].typ == "zahl" and f["student_number"].wert == "999650"
    g = f["geschlecht"]  # Aufruf ohne Zusatz-Argument
    assert g.typ == "auswahl" and g.wert == "w" and g.text == "weiblich" and len(g.optionen) == 2
    assert "bild_hh" not in f  # Portrait-Upload ist kein Datenfeld


def test_abschnitt_personalien_datum_sensibel():
    fl = PP.parse_abschnitt(fx("person_personalien.html"), "personalien")
    f = {x.name: x for x in fl}
    assert f["geburtstag"].typ == "datum" and f["geburtstag"].wert == "01.01.2013"
    assert f["geburtstag"]._person.startswith("V2$utgl")
    assert f["austritt"].wert == "" and not f["austritt"].ist_schreibbar()
    assert f["nationality_id"].text == "Schweiz" and f["nationality_id"]._zusatz == ""
    assert f["bemerkungen"].typ == "mehrzeilig" and f["bemerkungen"].wert == "Zeile 1"
    ahv = f["ahv"].oeffentlich()
    assert ahv["wert"] == "***" and ahv["schreibbar"] is False
    assert f["ahv"].oeffentlich(sensibel_zeigen=True)["wert"] == "756.0000.0000.00"
    assert f["iban"].oeffentlich()["wert"] == ""


def test_abschnitt_radio_checkbox():
    f = {x.name: x for x in PP.parse_abschnitt(fx("person_bista.html"), "additional_fields_2")}
    r = f["bista_plan_stat"]
    assert r.typ == "auswahlknopf" and r.wert == "10" and r.text == "Unterricht nach Regellehrplan"
    assert [o["wert"] for o in r.optionen] == ["10", "20", "30"] and r._zusatz == "1"
    assert f["notification"].typ == "checkbox" and f["notification"].wert is True


def test_schreib_payload():
    f = {x.name: x for x in PP.parse_abschnitt(fx("person_personalien.html"), "personalien")
         + PP.parse_abschnitt(fx("person_name.html"), "name") + PP.parse_abschnitt(fx("person_bista.html"), "additional_fields_2")}
    p = PP.schreib_payload(f["geburtstag"], "2013-02-03")
    assert (p["type"], p["dd"], p["mm"], p["yyyy"]) == (7, "03", "02", "2013")
    assert PP.schreib_payload(f["geburtstag"], "3.2.2013")["dd"] == "03"
    assert PP.schreib_payload(f["nationality_id"], "deutschland")["wert"] == "3"
    assert PP.schreib_payload(f["nationality_id"], "2")["wert"] == "2"
    assert PP.schreib_payload(f["bista_plan_stat"], "20") == {"type": 2, "feld": f["bista_plan_stat"]._feld, "wert": "20",
                                                              "person_encrypted": f["bista_plan_stat"]._person, "additional_field": "1"}
    assert PP.schreib_payload(f["heimatort"], "Zürich")["prev"] == "Bülach"
    for name, val in [("ahv", "x"), ("iban", "x"), ("austritt", "01.01.2026"), ("name", " "),
                      ("geburtstag", "2013/01/01"), ("nationality_id", "Atlantis"), ("student_number", "abc")]:
        with pytest.raises(PP.FeldFehler):
            PP.schreib_payload(f[name], val)


# ------------------------------------------------------------------ Mock-Escola (Personen)
PERS_LIST = ('<ul><li id="li_650"><span id="name_person_650">sus</span> <span id="vorname_person_650">sus</span></li></ul>')
STAFF = ('<ul><li id="li_135"><span id="name_person_135">Schmid</span> <span id="vorname_person_135">Sibylle</span></li>'
         '<li id="li_649"><span id="name_person_649">TEST</span> <span id="vorname_person_649">TEST</span></li></ul>')


class FakePersonen:
    def __init__(self, edit_mode=True):
        self.edit_mode = edit_mode
        self.active = None
        self.writes = []
        self.edit_toggles = []
        self.zeige_inaktive = False
        self.pages = {"name": fx("person_name.html"), "personalien": fx("person_personalien.html"),
                      "additional_fields_2": fx("person_bista.html")}

    def _section(self, s):
        h = self.pages.get(s, "<div></div>")
        if not self.edit_mode:  # ohne Bearbeitungsmodus liefert Escola keine Eingabefelder
            h = re.sub(r"<(input|select|textarea)[^>]*>(.*?</select>|.*?</textarea>)?", "", h, flags=re.S)
            h = '<input type="checkbox" id="edit_mode">' + h
        return h

    def __call__(self, req: httpx.Request) -> httpx.Response:
        url = str(req.url)
        body = req.content.decode()
        form = {k: v[0] for k, v in parse_qs(body, keep_blank_values=True).items()}
        if "admin.php" in url:
            return httpx.Response(200, text="<html><body>" + fx("chooser.html") + "</body></html>")
        if "show_persons_of_group.php" in url:
            assert "&workgroupId&" in body  # Escola-Eigenheit: ohne Wert
            if form["personCategory"] == "schueler":
                return httpx.Response(200, text=PERS_LIST if form["schoolclassId"] == "92" else "Es sind keine Personen in dieser Personengruppe vorhanden.")
            if form["personCategory"] == "allInactive":
                if not self.zeige_inaktive:
                    return httpx.Response(200, text='<div>2 inaktive Personen</div><input type="checkbox" id="showHideInactivePersonsSwitch" />')
                return httpx.Response(200, text='<ul><li id="li_9"><span id="name_person_9">Alt</span> <span id="vorname_person_9">Anna</span></li></ul>'
                                                '<input type="checkbox" id="showHideInactivePersonsSwitch" checked />')
            if form["personCategory"] == "allActive":
                return httpx.Response(200, text=STAFF if form["schoolUnitId"] == "1" else "Es sind keine Personen")
            return httpx.Response(200, text="Es sind keine Personen")
        if url.endswith("/inc/ajax/ajax_functions.php") and form.get("type") == "85":
            self.zeige_inaktive = not self.zeige_inaktive
            return httpx.Response(200, text="")
        if "show_reiter.php" in url:
            self.active = int(form["active_person"])
            return httpx.Response(200, text=fx("person_reiter.html") if self.active in (650, 649) else "<ul></ul>")
        if "show_person_details.php" in url:
            return httpx.Response(200, text=self._section(form["active_section"]))
        if "ajax_functions_persons.php" in url:
            if form.get("type") == "1":
                self.edit_mode = form["edit_mode"] == "1"
                self.edit_toggles.append(form["edit_mode"])
                return httpx.Response(200, text="")
            assert self.edit_mode, "Schreiben nur im Bearbeitungsmodus"
            self.writes.append(form)
            if form.get("type") == "2":  # Textwert im "Server" aktualisieren
                tok = re.escape(form["feld"])
                for k, h in self.pages.items():
                    self.pages[k] = re.sub(rf'(id="feld_{tok}" type="(?:text|number)" value=")[^"]*"', lambda m: m.group(1) + _html.escape(form["wert"]) + '"', h)
            if form.get("type") == "7":
                for k, h in self.pages.items():
                    for part in ("dd", "mm", "yyyy"):
                        h = re.sub(rf'(id="geburtstag_{part}" type="text" value=")[^"]*"', lambda m: m.group(1) + form[part] + '"', h)
                    self.pages[k] = h
            return httpx.Response(200, text="")
        return httpx.Response(404)


def make(monkeypatch, fake, schreiben=True, key="geheim"):
    monkeypatch.setenv("ESCOLA_SCHREIBEN", "1" if schreiben else "0")
    monkeypatch.setenv("ESCOLA_API_KEY", key)
    from escola_api.app import create_app
    c = EscolaClient(EscolaConfig(base_url="https://x.test/", cookie="PHPSESSID=abc"), transport=httpx.MockTransport(fake))
    return TestClient(create_app(c), headers={"X-API-Key": key} if key else {})


def test_listen(monkeypatch):
    api = make(monkeypatch, FakePersonen())
    s = api.get("/schueler").json()
    assert s == [{"id": 650, "nachname": "sus", "vorname": "sus", "klasse_id": 92, "klasse": "H_A1a", "schulhaus": "Hinterbirch"}]
    p = api.get("/personen").json()
    assert [x["id"] for x in p] == [135, 649] and p[0]["schulhaeuser"] == ["Hinterbirch"]
    assert api.get("/personen", params={"rolle": "gibtsnicht"}).status_code == 400
    assert any(k["rolle"] == "lehrperson" for k in api.get("/personen/rollen").json())
    assert api.get("/personen", params={"rolle": "lehrperson"}).status_code == 200
    csv = api.get("/schueler", params={"format": "csv"}).text.lstrip("﻿").splitlines()
    assert csv[0] == "id;nachname;vorname;klasse_id;klasse;schulhaus" and csv[1].startswith("650;sus;sus;92")


def test_detail(monkeypatch):
    fake = FakePersonen(edit_mode=False)
    api = make(monkeypatch, fake)
    d = api.get("/schueler/650").json()
    assert d["felder"]["geburtstag"] == "01.01.2013" and d["felder"]["geschlecht"] == "weiblich"
    assert d["felder"]["ahv"] == "***"
    assert set(d["abschnitte"]) == {"name", "personalien", "additional_fields_2"}
    assert fake.edit_toggles == ["1", "0"]  # Bearbeitungsmodus wieder zurückgesetzt
    gs = lambda dd: next(x for x in dd["abschnitte"]["name"]["felder"] if x["name"] == "geschlecht")
    assert "optionen" not in gs(d)
    assert len(gs(api.get("/schueler/650", params={"optionen": True, "abschnitte": "name"}).json())["optionen"]) == 2
    assert "health" not in str(d["abschnitte"].keys())  # Gesundheit nur mit ESCOLA_GESUNDHEIT=1
    assert api.get("/schueler/9999").status_code == 404
    csv = api.get("/personen/649", params={"format": "csv"}).text
    assert "geburtstag" in csv and "756.0000" not in csv


def test_schreiben(monkeypatch):
    fake = FakePersonen()
    api = make(monkeypatch, fake)
    r = api.patch("/schueler/650", json={"felder": {"heimatort": "Zürich", "geburtstag": "2013-02-03", "bista_plan_stat": "20"}})
    assert r.status_code == 200, r.text
    res = r.json()
    assert res["geschrieben"] is True
    by = {a["feld"]: a for a in res["aenderungen"]}
    assert by["heimatort"]["alt"] == "Bülach" and by["heimatort"]["jetzt"] == "Zürich"
    assert by["geburtstag"]["jetzt"] == "03.02.2013"
    assert [w["type"] for w in fake.writes] == ["2", "7", "2"]


def test_schreiben_sperren_und_probelauf(monkeypatch):
    fake = FakePersonen()
    api = make(monkeypatch, fake)
    r = api.patch("/schueler/650", json={"felder": {"ahv": "756.1", "heimatort": "Zürich", "unbekannt": 1}})
    assert r.status_code == 422 and {e["feld"] for e in r.json()["fehler"]} == {"ahv", "unbekannt"}
    assert fake.writes == []  # alles oder nichts
    p = api.patch("/schueler/650", params={"probelauf": True}, json={"felder": {"heimatort": "Zürich"}}).json()
    assert p["probelauf"] is True and p["aenderungen"][0]["neu"] == "Zürich" and fake.writes == []


def test_schreiben_deaktiviert(monkeypatch):
    api = make(monkeypatch, FakePersonen(), schreiben=False)
    assert api.patch("/personen/649", json={"felder": {"heimatort": "X"}}).status_code == 403
    assert api.patch("/personen/649", params={"probelauf": True}, json={"felder": {"heimatort": "X"}}).status_code == 200
    api2 = make(monkeypatch, FakePersonen(), schreiben=True, key="")
    assert api2.patch("/personen/649", json={"felder": {"heimatort": "X"}}).status_code == 403


def test_inaktive_personen(monkeypatch):
    fake = FakePersonen()
    api = make(monkeypatch, fake)
    r = api.get("/personen", params={"rolle": "allInactive"}).json()
    assert [p["id"] for p in r] == [9]
    assert fake.zeige_inaktive is False  # Anzeige wieder wie vorher
