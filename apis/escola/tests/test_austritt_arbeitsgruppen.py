"""Austritt und Arbeitsgruppen – Abläufe wie live am 14.11.2026 getestet."""
import json
import re
from pathlib import Path
from urllib.parse import parse_qs

import httpx
from fastapi.testclient import TestClient

from escola_api.client import EscolaClient, EscolaConfig

FX = Path(__file__).parent / "fixtures"
PERS = (FX / "person_personalien.html").read_text(encoding="utf-8")
REITER = (FX / "person_reiter.html").read_text(encoding="utf-8")
WGS = [{"id": 3, "name": "TEST", "schoolId": 1, "schoolName": "Hinterbirch", "count": 0},
       {"id": 1, "name": "M_WF_GM_A1 (zuk. )", "schoolId": 2, "schoolName": "Mettmenriet", "count": 0}]


class Fake:
    def __init__(self):
        self.personalien = PERS
        self.wg = {652: set()}
        self.aktiv = True
        self.calls = []
        self.wg_kontext = False

    def __call__(self, req):
        p = req.url.path
        f = {k: v[0] for k, v in parse_qs(req.content.decode(), keep_blank_values=True).items()}
        flist = parse_qs(req.content.decode(), keep_blank_values=True)
        self.calls.append((p, f.get("type") or f.get("mode")))
        if p.endswith("show_reiter.php"):
            return httpx.Response(200, text=REITER)
        if p.endswith("show_person_details.php"):
            return httpx.Response(200, text=self.personalien if f["active_section"] == "personalien" else "<div></div>")
        if p.endswith("ajax_functions_persons.php"):
            if f.get("type") == "7":
                assert "austritt" in self.personalien
                for part in ("dd", "mm", "yyyy"):
                    self.personalien = re.sub(rf'(id="austritt_{part}" type="text" value=")[^"]*"',
                                              lambda m: m.group(1) + f[part] + '"', self.personalien)
            return httpx.Response(200, text="")
        if p.endswith("personManagement.php"):
            if f.get("mode") == "17":
                assert f["action"] == "1"
                return httpx.Response(200, text='<div>Möchtest du diese Person wirklich deaktivieren?'
                                                '<a onclick="personManagementGotoMode(36, {});">JA</a></div>')
            if f.get("mode") == "36":
                self.aktiv = False
                return httpx.Response(200, text='<div class="alert">Eine Person wurde erfolgreich deaktiviert.</div>')
        if p.endswith("ajax_functions_workgroups.php"):
            if f["type"] == "7":
                return httpx.Response(200, text=json.dumps(WGS))
            if f["type"] == "9":
                self.wg[int(f["studentId"])].discard(int(f["workgroupId"]))
                return httpx.Response(200, text="")
        if p.endswith("assignments.php"):
            if req.method == "GET":
                return httpx.Response(200, text="<div>SuS-Zuordnungen</div>")
            if f.get("mode") == "2" and f.get("updateStudent") == "1":  # wie live: setzt die Auswahl in der Sitzung
                self.wg_kontext = True
                return httpx.Response(200, json={"students": {}, "workgroups": []})
            if not self.wg_kontext:  # wie live: ohne Auswahl nur eine Fehlermeldung
                return httpx.Response(200, text="Es ist ein Fehler aufgetreten.")
            sid = int(f["student_id"])
            if f["mode"] == "2":
                return httpx.Response(200, json={"workgroups": [{"workgroup_id": w} for w in sorted(self.wg[sid])]})
            if f["mode"] == "3":
                shown = {int(x) for x in flist.get("allDisplayedWorkgroups[]", [])}
                checked = {int(x) for x in flist.get("workgroups[]", [])}
                assert shown == checked, "nur die betroffene Gruppe darf angezeigt werden"
                self.wg[sid] = (self.wg[sid] - shown) | checked
                return httpx.Response(200, text="")
        return httpx.Response(404)


def make(monkeypatch):
    monkeypatch.setenv("ESCOLA_SCHREIBEN", "1")
    monkeypatch.setenv("ESCOLA_API_KEY", "k")
    from escola_api.app import create_app
    fake = Fake()
    c = EscolaClient(EscolaConfig(base_url="https://x.test/", cookie="PHPSESSID=a"), transport=httpx.MockTransport(fake))
    return fake, TestClient(create_app(c), headers={"X-API-Key": "k"})


def test_austritt(monkeypatch):
    fake, api = make(monkeypatch)
    r = api.post("/schueler/652/austritt", json={"datum": "2027-07-09"})
    assert r.status_code == 200, r.text
    assert r.json()["austritt"] == "09.07.2027" and r.json()["deaktiviert"] is False and fake.aktiv
    r = api.post("/schueler/652/austritt", json={"datum": "14.11.2026", "sofort_deaktivieren": True})
    assert r.json()["austritt"] == "14.11.2026" and r.json()["deaktiviert"] is True and not fake.aktiv
    assert api.post("/schueler/652/austritt", json={"datum": "morgen"}).status_code == 400
    # Austritt bleibt im normalen PATCH gesperrt
    assert api.patch("/schueler/652", json={"felder": {"austritt": "01.01.2027"}}).status_code == 422


def test_arbeitsgruppen(monkeypatch):
    fake, api = make(monkeypatch)
    assert [w["id"] for w in api.get("/arbeitsgruppen").json()] == [3, 1]
    assert api.get("/schueler/652/arbeitsgruppen").json() == []
    r = api.post("/schueler/652/arbeitsgruppen", json={"arbeitsgruppe_id": 3})
    assert r.status_code == 200 and r.json()["geaendert"] is True and [w["name"] for w in r.json()["arbeitsgruppen"]] == ["TEST"]
    fake.wg[652].add(1)  # andere Gruppe bleibt bei weiterer Zuteilung unberührt
    api.post("/schueler/652/arbeitsgruppen", json={"arbeitsgruppe_id": 3})
    assert fake.wg[652] == {1, 3}
    d = api.delete("/schueler/652/arbeitsgruppen/3")
    assert d.status_code == 200 and fake.wg[652] == {1}
    assert api.post("/schueler/652/arbeitsgruppen", json={"arbeitsgruppe_id": 99}).status_code == 400


def test_arbeitsgruppen_ohne_kontext_klare_meldung(monkeypatch):
    fake, api = make(monkeypatch)
    from escola_api.client import EscolaClient
    monkeypatch.setattr(EscolaClient, "_wg_kontext", lambda self, pid, sj=0: None)
    r = api.get("/schueler/652/arbeitsgruppen")
    assert r.status_code == 502 and "nicht geliefert" in r.text
