"""Tests gegen echte (gekürzte) Escola-HTML-Antworten vom 14.11.2026.
Ein Mock-Server bildet das Session-Verhalten von Escola nach (aktive Klasse)."""
import re
from pathlib import Path
from urllib.parse import parse_qs

import httpx
import pytest
from fastapi.testclient import TestClient

from escola_api import parsers as P
from escola_api.app import create_app
from escola_api.client import EscolaClient, EscolaConfig, SessionAbgelaufen

FX = Path(__file__).parent / "fixtures"
fx = lambda n: (FX / n).read_text(encoding="utf-8")


# ------------------------------------------------------------------ Parser
def test_klassen():
    k = P.parse_klassen(fx("chooser.html"))
    assert len(k) == 8
    assert k[0] == {"id": 92, "typ": "Klasse", "name": "H_A1a", "bezeichnung": "Riedhofer Ulmrist",
                    "klassenlehrperson": "Riedhofer Marco", "schulhaus": "Hinterbirch"}
    assert k[5]["klassenlehrperson"] == "Vogeck Bettina und Widmatter Bettina"
    wg = [x for x in k if x["typ"] == "Arbeitsgruppe"]
    assert [x["id"] for x in wg] == [1, 2] and wg[0]["schulhaus"] == "Mettmenriet"
    assert any(x["id"] == 64 and x["name"] == "" for x in k)


def test_lehrpersonen_und_kuerzel():
    lp = P.parse_lehrpersonen(fx("lehrpersonen.html"))
    assert lp[0] == {"id": 67, "nachname": "Gassrist", "vorname": "Ursina"}
    assert len(lp) == 3
    assert P.lp_kuerzel("Laninger", "Félix") == "LaFe"      # Akzente weg
    assert P.lp_kuerzel("Öberli", "Kai") == "ÖbKa"           # Umlaute bleiben
    assert P.lp_kuerzel("Wälbach", "Lina") == "WäLi"


def test_faecher_raeume_details():
    ed = fx("edit_cell.html")
    f = P.parse_faecher(ed)
    assert len(f) == 13 and {"id": 25, "kuerzel": "WAH", "name_kurz": "Wirtschaft, Ar"} in f
    r = P.parse_raeume(ed)
    a105 = [x for x in r if x["kuerzel"] == "A105"]
    assert len(a105) == 2 and {x["id"] for x in a105} == {13, 37}
    toepf = next(x for x in r if x["id"] == 54)
    assert toepf["bezeichnung"] == "Töpferwerkstatt H" and toepf["gruppe"] == "Hibi - Trakt B"
    d = P.parse_eintrag_details(ed)
    assert [{k: x[k] for k in ("eintrag_id", "fach_id", "raum_ids", "lehrperson_ids")} for x in d] == \
        [{"eintrag_id": 21, "fach_id": 25, "raum_ids": [33, 34], "lehrperson_ids": [632, 578]}]
    assert d[0]["raum_slots"][:2] == [33, 34] and 25 in d[0]["faecher_waehlbar"] and 9 in d[0]["raeume_waehlbar"]
    assert all(x["schaltbar"] for x in d[0]["lehrpersonen"])


def test_raster_pro_schulhaus():
    h = P.parse_raster(fx("stundenplan_92.html"))
    m = P.parse_raster(fx("stundenplan_65.html"))
    assert [t["code"] for t in h["tage"]] == list("ABCDE") and h["tage"][0]["name"] == "Montag"
    assert h["lektionen"][0] == {"id": 2, "nr": 1, "von": "07.30", "bis": "08.15"}
    assert m["lektionen"][0]["id"] == 24
    assert m["lektionen"][1] == {"id": 30, "nr": 2, "von": "13.00", "bis": "13.45"}


def test_stundenplan_eintraege():
    e = P.parse_stundenplan(fx("stundenplan_92.html"))
    assert len(e) == 6
    wah = next(x for x in e if x["fach_kuerzel"] == "WAH")
    assert wah["lehrpersonen"] == ["Bernmann Ines", "Widbach Fabian"]
    assert wah["raeume"] == ["UG - 001 - Zeichnungszimmer", "UG - 002 - Schulküche 1"]
    assert wah["raeume_kuerzel"] == ["A001", "A002"]
    bs = next(x for x in e if x["fach_kuerzel"] == "BS")
    assert bs["raeume"] == [] and bs["lehrpersonen_kuerzel"] == ["ObMa", "RiTi"]
    assert P.parse_stundenplan(fx("stundenplan_65.html")) == []


# ------------------------------------------------------------------ Mock-Escola
EMPTY_H = re.sub(r'<table width="100%" height="33" class="stundenplan_innen">.*?</table>', "", fx("stundenplan_92.html"))
NEW_CELL_H = '<div><select id="tt_select_new_2_A"><option value="0"></option>' + \
    "".join(f'<option value="{o}">{n}</option>' for o, n in re.findall(r'<option value="(\d+)"[^>]*>([^<]*\(\w+\))</option>', fx("edit_cell.html"))) + "</select></div>"
LP_H = ('<ul><li id="li_135"><span id="name_person_135">Riedhofer</span> <span id="vorname_person_135">Marco</span></li>'
        '<li id="li_632"><span id="name_person_632">Widbach</span> <span id="vorname_person_632">Fabian</span></li>'
        '<li id="li_578"><span id="name_person_578">Bernmann</span> <span id="vorname_person_578">Ines</span></li></ul>')


class FakeEscola:
    def __init__(self, expired=False):
        self.active = None
        self.expired = expired
        self.writes = []  # alles ausser type=1/3 wäre ein Schreibzugriff

    def __call__(self, req: httpx.Request) -> httpx.Response:
        if self.expired:
            return httpx.Response(302, headers={"location": "/escola/login"})
        assert "PHPSESSID=abc" in req.headers.get("cookie", "")
        url = str(req.url)
        if "admin.php" in url:
            m = re.search(r"klassen_id=(\d+)", url)
            if m:
                self.active = int(m.group(1))
            return httpx.Response(200, text="<html><body>" + fx("chooser.html") + "</body></html>")
        form = {k: v[0] for k, v in parse_qs(req.content.decode()).items()}
        if "application_class.php" in url:
            assert form == {"mode": "0"}
            if self.active == 92:
                return httpx.Response(200, text=fx("stundenplan_92.html"))
            return httpx.Response(200, text=fx("stundenplan_65.html") if self.active in (65, 67) else EMPTY_H)
        if "ajax_functions_timetable.php" in url:
            if form.get("type") not in ("1", "3") or "new_entry" in form or "deleteEntry" in form:
                self.writes.append(form)
            if form.get("type") == "3":
                return httpx.Response(200, text="")
            cid = int(form["classOrWorkgroupId"])
            if cid == 92 and (form["dayCode"], form["lessonId"]) in (("A", "2"), ("D", "2")):
                return httpx.Response(200, text=fx("edit_cell.html"))
            return httpx.Response(200, text=NEW_CELL_H if cid in (92, 93) else '<select id="tt_select_new_x"><option value="0"></option></select>')
        if "show_persons_of_group.php" in url:
            if form["schoolUnitId"] == "1":
                return httpx.Response(200, text=LP_H + " " * 100)
            if form["schoolUnitId"] == "2":
                return httpx.Response(200, text=fx("lehrpersonen.html"))
            return httpx.Response(200, text="Es ist ein Fehler aufgetreten.")
        return httpx.Response(404)


@pytest.fixture
def fake():
    return FakeEscola()


@pytest.fixture
def api(fake):
    c = EscolaClient(EscolaConfig(base_url="https://x.test/", cookie="PHPSESSID=abc"), transport=httpx.MockTransport(fake))
    return TestClient(create_app(c))


def test_api_stammdaten(api, fake):
    assert len(api.get("/klassen").json()) == 8
    assert len(api.get("/klassen", params={"typ": "Arbeitsgruppe"}).json()) == 2
    f = api.get("/faecher").json()
    assert len(f) == 13
    assert next(x for x in f if x["kuerzel"] == "WAH")["name"] == "Wirtschaft, Arbeit, Haushalt"  # voller Name aus Tooltip
    lp = api.get("/lehrpersonen").json()
    assert len(lp) == 6 and {"Hinterbirch"} == set(next(x for x in lp if x["id"] == 135)["schulhaeuser"])
    r = api.get("/raeume").json()
    assert all(x["schulhaus"] == "Hinterbirch" for x in r) and len(r) > 5
    assert api.get("/tage").json()[4] == {"code": "E", "nr": 5, "name": "Freitag"}
    lek = api.get("/lektionen").json()
    assert {(x["schulhaus"], x["id"]) for x in lek} >= {("Hinterbirch", 2), ("Mettmenriet", 24), ("Mettmenriet", 30)}
    assert api.get("/lektionen", params={"schulhaus": "Mettmenriet"}).json()[1]["von"] == "13.00"
    assert fake.writes == []  # nichts geschrieben


def test_api_eintraege(api, fake):
    rows = api.get("/eintraege").json()
    assert len(rows) == 6 and all(r["klasse_id"] == 92 for r in rows)
    wah = next(r for r in rows if r["fach_kuerzel"] == "WAH")
    assert wah["fach_id"] == 25 and wah["tag"] == "Donnerstag" and wah["von"] == "07.30"
    assert wah["raum_ids"] == [33, 34] and wah["lehrperson_ids"] == [578, 632]
    d = next(r for r in rows if r["fach_kuerzel"] == "D")
    assert d["raum_ids"] == [75] and d["lehrperson_ids"] == [135]
    exact = api.get("/eintraege", params={"genau": True}).json()
    wah2 = next(r for r in exact if r["fach_kuerzel"] == "WAH")
    assert wah2["eintrag_id"] == 21 and wah2["lehrperson_ids"] == [632, 578]
    csv = api.get("/eintraege", params={"format": "csv"})
    assert csv.headers["content-type"].startswith("text/csv")
    lines = csv.text.lstrip("﻿").splitlines()
    assert lines[0].startswith("klasse_id;klasse;schulhaus;tag_code") and len(lines) == 7
    assert fake.writes == []


def test_session_abgelaufen():
    c = EscolaClient(EscolaConfig(base_url="https://x.test/", cookie="PHPSESSID=abc"), transport=httpx.MockTransport(FakeEscola(expired=True)))
    r = TestClient(create_app(c)).get("/klassen")
    assert r.status_code == 503 and r.json()["fehler"] == "escola_session_abgelaufen"
    with pytest.raises(SessionAbgelaufen):
        c.status()
