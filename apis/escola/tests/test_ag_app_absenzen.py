"""Erkundung 28.11.2026 (nur lesen): Stundenplan von Arbeitsgruppen (L8, #13), App-Status (L12, #4),
Absenzen über Escolas REST-Schnittstelle (L17, #9). Antworten gekürzt bzw. erfunden; Testobjekte 649/650, AG TEST 3."""
import json
from pathlib import Path
from urllib.parse import parse_qs

import httpx

from escola_api import personen as PP
from test_personen import FakePersonen, make

FX = Path(__file__).parent / "fixtures"

MOBILE_AUS = '<div id="mobile"><br><i class="fas fa-window-close text-danger"></i> App nicht aktiviert.<hr></div>'
MOBILE_AUS_SCHALTBAR = ('<div id="mobile"><br><i class="fas fa-window-close text-danger"></i> App nicht aktiviert.<hr>'
                        '<button type="button" class="btn btn-primary btn-sm" onclick="javascript:enableDisableMobile(649,false);">'
                        'aktivieren</button><hr></div>')
MOBILE_AN = '<div id="mobile"><br><i class="fas fa-check text-success"></i> App aktiviert.<hr></div>'  # abgeleitet, nicht live
AKTIVITAET = ('<table class="niceTableNarrow" width="100%"><tr valign="top"><td width="130">Erstellung</td>'
              '<td>Sa, 14. Nov 2026, 20:50<div class="smaller-font-size">Erstellt von Keller Markus</div></td></tr>'
              '<tr valign="top"><td width="130">Anzahl Logins</td><td>{n}</td></tr>'
              '<tr valign="top"><td width="130">letzter Login</td><td>{letzt}</td></tr></table>')


# ------------------------------------------------------------------ Parser App-Status
def test_parse_app_status():
    assert PP.parse_app_status(MOBILE_AUS) == {"app_aktiviert": False, "app_schaltbar": False}
    assert PP.parse_app_status(MOBILE_AUS_SCHALTBAR) == {"app_aktiviert": False, "app_schaltbar": True}
    assert PP.parse_app_status(MOBILE_AN)["app_aktiviert"] is True
    assert PP.parse_app_status("<div>kein Reiter</div>") == {"app_aktiviert": None, "app_schaltbar": False}


def test_parse_aktivitaet():
    assert PP.parse_aktivitaet(AKTIVITAET.format(n=0, letzt="noch nie eingeloggt")) == {
        "anzahl_logins": 0, "letzter_login": None}
    assert PP.parse_aktivitaet(AKTIVITAET.format(n=12, letzt="Fr, 27. Nov 2026, 07:41")) == {
        "anzahl_logins": 12, "letzter_login": "Fr, 27. Nov 2026, 07:41"}


class FakeApp(FakePersonen):
    def __init__(self):
        super().__init__()
        self.pages["mobile"] = MOBILE_AUS
        self.pages["activity"] = AKTIVITAET.format(n=0, letzt="noch nie eingeloggt")


def test_endpunkt_person_app(monkeypatch):
    api = make(monkeypatch, FakeApp(), schreiben=False)
    assert api.get("/personen/650/app").json() == {"person_id": 650, "app_aktiviert": False, "app_schaltbar": False,
                                                    "anzahl_logins": 0, "letzter_login": None}
    assert api.get("/personen/1/app").status_code == 404


# ------------------------------------------------------------------ Stundenplan Arbeitsgruppe
class FakeAG:
    def __init__(self):
        self.posts = []

    def __call__(self, req: httpx.Request) -> httpx.Response:
        url = str(req.url)
        form = {k: v[0] for k, v in parse_qs(req.content.decode(), keep_blank_values=True).items()}
        self.posts.append((url.rsplit("/", 1)[-1], form))
        if "admin.php" in url:
            return httpx.Response(200, text="<html></html>")
        if "ajax_functions_workgroups.php" in url and form.get("type") == "7":
            return httpx.Response(200, text=json.dumps(
                [{"id": 3, "name": "TEST", "schoolName": "Hinterbirch", "count": 1}] if form["schul_id"] == "1" else []))
        if "application_workgroup.php" in url:
            assert form == {"mode": "0", "workgroupId": "3"}
            return httpx.Response(200, text=(FX / "stundenplan_92.html").read_text(encoding="utf-8"))
        if "application_class.php" in url:
            return httpx.Response(200, text="Es wurde keine Klasse gewählt")
        return httpx.Response(404)


def test_stundenplan_arbeitsgruppe(monkeypatch):
    fake = FakeAG()
    api = make(monkeypatch, fake, schreiben=False)
    rows = api.get("/arbeitsgruppen/3/stundenplan").json()
    assert rows and all(r["arbeitsgruppe_id"] == 3 for r in rows)
    assert {"tag_code", "lektion_id", "fach_kuerzel", "lehrpersonen", "raeume"} <= set(rows[0])
    assert ("admin.php?page_request=6&workgroup_id=3", {}) in fake.posts
    assert not any(n == "application_class.php" for n, _ in fake.posts)
    assert api.get("/arbeitsgruppen/99/stundenplan").status_code == 404
    csv = api.get("/arbeitsgruppen/3/stundenplan", params={"format": "csv"}).text.lstrip("﻿")
    assert csv.splitlines()[0].startswith("arbeitsgruppe_id;tag_code;lektion_id")


# ------------------------------------------------------------------ Absenzen (REST)
class FakeAbsenzen:
    """Antworten wie live am 28.11.2026 für H_A1a (92): keine Semester; Einträge erfunden."""
    EINTRAG = {"id": 501, "studentId": 650, "type": "E", "dateFrom": "2026-11-23", "dateTo": "2026-11-23", "lessons": 2}

    def __init__(self):
        self.gets = []

    def __call__(self, req: httpx.Request) -> httpx.Response:
        p = req.url.path
        self.gets.append((p, dict(req.url.params)))
        assert req.headers.get("accept") == "application/json"
        if p == "/escola/api/absences/selects/schoolclasses/92/absence-semesters":
            return httpx.Response(200, json={"value": None, "options": [{"text": "1. Semester 2026/27", "value": 7, "isGroup": False}]})
        if p == "/escola/api/absences/selects/schoolclasses/92/students":
            return httpx.Response(200, json={"value": 650, "options": [
                {"text": "Alle Schüler:innen einer Klasse", "value": None, "isGroup": False},
                {"text": "SUS OHNE KLASSE", "value": 651, "isGroup": False}, {"text": "Testname Testvorname", "value": 650, "isGroup": False}]})
        if p == "/escola/api/absences/selects/schoolclasses/92/types":
            return httpx.Response(200, json=[{"text": "Entschuldigt", "value": "E", "isGroup": False},
                                             {"text": "Unentschuldigt", "value": "O", "isGroup": False}])
        if p in ("/escola/api/absences/schoolclasses/92/absences", "/escola/api/absences/students/650/absences"):
            q = req.url.params
            if "semester" not in q or "sorting" not in q:
                return httpx.Response(422, json={"message": "The semester field is required. (and 1 more error)"})
            return httpx.Response(200, json=[self.EINTRAG] if q["semester"] == "7" else [])
        return httpx.Response(404, text="<html>Seite nicht gefunden</html>")


def test_absenzen_auswahl_und_eintraege(monkeypatch):
    fake = FakeAbsenzen()
    api = make(monkeypatch, fake, schreiben=False)
    a = api.get("/klassen/92/absenzen/auswahl").json()
    assert a["semester"] == [{"id": 7, "text": "1. Semester 2026/27"}]
    assert [s["id"] for s in a["schueler"]] == [651, 650]  # „Alle“ (ohne ID) fällt weg
    assert a["arten"] == [{"code": "E", "text": "Entschuldigt"}, {"code": "O", "text": "Unentschuldigt"}]
    assert api.get("/klassen/92/absenzen", params={"semester": 7}).json() == [FakeAbsenzen.EINTRAG]
    assert ("/escola/api/absences/schoolclasses/92/absences", {"semester": "7", "sorting": "date-asc"}) in fake.gets
    assert api.get("/schueler/650/absenzen", params={"semester": 1}).json() == []
    assert api.get("/schueler/650/absenzen", params={"semester": 7, "sortierung": "falsch"}).status_code == 400
    assert api.get("/klassen/92/absenzen").status_code == 422  # semester fehlt (FastAPI)
    assert api.get("/klassen/5/absenzen/auswahl").status_code == 404
    csv = api.get("/klassen/92/absenzen", params={"semester": 7, "format": "csv"}).text.lstrip("﻿").splitlines()
    assert csv[0] == "id;studentId;type;dateFrom;dateTo;lessons" and csv[1].startswith("501;650;E")


# ------------------------------------------------------------------ Dokumente im Schülerdossier (L11, #3)
class FakeDocs:
    """Antworten wie live am 28.11.2026 für SuS SuS 650 (Wurzel 63, Unterordner 65 leer); Datei erfunden."""
    def __init__(self):
        self.dateien = {65: [self._datei(900, "alt", "pdf")]}
        self.calls = []

    @staticmethod
    def _datei(fid, name, ext):  # Felder wie live am 28.11.2026 (Upload einer Testdatei bei 650)
        return {"id": fid - 70, "folderFileId": fid, "folderId": 65, "name": name, "extension": ext,
                "mimeType": "application/pdf", "size": 10, "createdByName": "Keller Markus", "isUnseen": False}

    def __call__(self, req: httpx.Request) -> httpx.Response:
        p = req.url.path
        self.calls.append((req.method, p))
        base = "/escola/api/docs/root/global/students/650"
        if not p.startswith(base):
            return httpx.Response(404)
        rest = p[len(base):]
        if rest == "" and req.method == "GET":
            return httpx.Response(200, json={"status": 200, "data": {"id": 1, "rootFolderId": 63, "filesUnseenCount": 0}})
        if rest == "/folders/63":
            return httpx.Response(200, json={"status": 200, "data": {
                "id": 63, "rootId": 1, "parentFolderId": None, "name": "Schüler:innen-Dokumente", "accessLevel": "read",
                "isReachableForGuardians": True, "isReachableForStudents": True, "path": [{"id": 63, "name": "Schüler:innen-Dokumente"}],
                "folders": [{"id": 65, "name": "10_Schülergrunddaten", "filesCount": len(self.dateien[65]),
                             "isVisibleForGuardians": False, "isVisibleForStudents": False}], "files": []}})
        if rest == "/folders/65":
            return httpx.Response(200, json={"status": 200, "data": {
                "id": 65, "name": "10_Schülergrunddaten", "path": [{"id": 63, "name": "Schüler:innen-Dokumente"},
                                                                    {"id": 65, "name": "10_Schülergrunddaten"}],
                "folders": [], "files": self.dateien[65]}})
        if rest == "/folders/65/files" and req.method == "POST":
            assert b'name="file"; filename="neu.pdf"' in req.content
            self.dateien[65].append(self._datei(901, "neu", "pdf"))
            return httpx.Response(200, json={"status": 200, "data": self._datei(901, "neu", "pdf")})
        if rest == "/folder-files/900" and req.method == "GET":
            return httpx.Response(200, content=b"%PDF erfunden", headers={"content-type": "application/pdf",
                                                                         "content-disposition": 'attachment; filename="alt.pdf"'})
        if rest == "/folder-files/901" and req.method == "DELETE":
            self.dateien[65] = [d for d in self.dateien[65] if d["folderFileId"] != 901]
            return httpx.Response(200, json={"status": 200, "msg": "File deleted."})
        return httpx.Response(404, json={"status": 404})


def _docs_api(monkeypatch, fake, schreiben=True):
    monkeypatch.setenv("ESCOLA_DOKUMENTE", "1")
    return make(monkeypatch, fake, schreiben=schreiben)


def test_dokumente_lesen(monkeypatch):
    api = _docs_api(monkeypatch, FakeDocs())
    w = api.get("/schueler/650/dokumente").json()
    assert w["id"] == 63 and w["pfad"] == ["Schüler:innen-Dokumente"] and w["sichtbar_eltern"] is True
    assert w["unterordner"] == [{"id": 65, "name": "10_Schülergrunddaten", "anzahl_dateien": 1,
                                 "sichtbar_eltern": False, "sichtbar_schueler": False}]
    alle = api.get("/schueler/650/dokumente", params={"alle": True}).json()
    assert len(alle) == 1 and alle[0]["ordner"] == "Schüler:innen-Dokumente / 10_Schülergrunddaten"
    assert (alle[0]["folderFileId"], alle[0]["name"], alle[0]["extension"]) == (900, "alt", "pdf")
    r = api.get("/schueler/650/dokumente/900")
    assert r.content == b"%PDF erfunden" and r.headers["content-type"] == "application/pdf"
    assert api.get("/schueler/650/dokumente/777").status_code == 404
    assert api.get("/schueler/651/dokumente").status_code == 404


def test_dokument_hochladen_und_zuruecksetzen(monkeypatch):
    fake = FakeDocs()
    api = _docs_api(monkeypatch, fake)
    probe = api.post("/schueler/650/dokumente/65", params={"dateiname": "neu.pdf"}, content=b"%PDF neu").json()
    assert probe["probelauf"] is True and probe["ordner"] == "Schüler:innen-Dokumente / 10_Schülergrunddaten"
    assert not any(m == "POST" for m, _ in fake.calls)
    assert api.post("/schueler/650/dokumente/65", params={"dateiname": "ALT.pdf", "probelauf": False}, content=b"x").status_code == 400
    neu = api.post("/schueler/650/dokumente/65", params={"dateiname": "neu.pdf", "probelauf": False}, content=b"%PDF neu",
                   headers={"content-type": "application/pdf"}).json()
    assert neu["datei_id"] == 901 and neu["escola"]["name"] == "neu" and len(fake.dateien[65]) == 2
    assert api.delete("/schueler/650/dokumente/901").json()["probelauf"] is True and len(fake.dateien[65]) == 2
    assert api.delete("/schueler/650/dokumente/901", params={"probelauf": False}).json()["geloescht"] is True
    assert [d["folderFileId"] for d in fake.dateien[65]] == [900]


def test_dokumente_schreiben_gesperrt(monkeypatch):
    api = _docs_api(monkeypatch, FakeDocs(), schreiben=False)
    assert api.post("/schueler/650/dokumente/65", params={"dateiname": "neu.pdf", "probelauf": False}, content=b"x").status_code == 403
    assert api.post("/schueler/650/dokumente/65", params={"dateiname": "neu.pdf"}, content=b"x").status_code == 200
