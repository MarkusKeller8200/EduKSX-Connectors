"""Zeugnis-Archiv (Personenverwaltung → «Zeugnis-/Formular-Archiv»), aufgezeichnet 26.11.2026 an SUS OHNE KLASSE."""
from pathlib import Path

import httpx

from escola_api import personen as PP
from test_personen import FakePersonen, make

FX = Path(__file__).parent / "fixtures"
PDF = b"%PDF-1.7 erfundenes Testzeugnis"


def test_parser_zeugnis_archiv():
    z = PP.parse_zeugnis_archiv((FX / "person_zeugnisse.html").read_text(encoding="utf-8"))
    assert [(x["schuljahr"], x["titel"], x["definitiv"], x["erstellt"]) for x in z] == [
        ("2026/27", "Zeugnis 1. Semester", True, "2026-11-26T07:55"),
        ("2026/27", "Zeugnis 1. Semester", False, "2026-11-26T07:54"),
        ("2025/26", "Zeugnis 2. Semester", True, "2026-07-03T14:05")]
    assert z[0]["id"] == "wIFFAEmaM5hnZJA72oBxMKnaBxxhGbkg_5_2" and z[0]["erstellt_von"] == "M. Keller"
    assert z[0]["datei"] == "Zeugnis_2026-27_1.-Semester_SUS-OHNE-KLASSE_ID651"
    assert PP.parse_zeugnis_archiv("<h5>Zeugnisse</h5> Es sind noch keine Archiv-Zeugnisse vorhanden") == []


class FakeZeugnisse(FakePersonen):
    def __init__(self):
        super().__init__()
        self.pages["certificates"] = (FX / "person_zeugnisse.html").read_text(encoding="utf-8")
        self.downloads = []

    def __call__(self, req: httpx.Request) -> httpx.Response:
        if "/MediaServer/Download/" in str(req.url):
            self.downloads.append(req.url.path)
            if "Kaputt" in req.url.path:
                return httpx.Response(200, content=b"<html>Fehler</html>")
            return httpx.Response(200, content=PDF, headers={"content-type": "application/pdf"})
        return super().__call__(req)


def _api(monkeypatch, fake, an=True, key="geheim"):
    monkeypatch.setenv("ESCOLA_ZEUGNISSE", "1" if an else "0")
    return make(monkeypatch, fake, schreiben=False, key=key)


def test_zeugnisse_schalter(monkeypatch):
    assert _api(monkeypatch, FakeZeugnisse(), an=False).get("/schueler/650/zeugnisse").status_code == 403
    assert _api(monkeypatch, FakeZeugnisse(), key="").get("/schueler/650/zeugnisse").status_code == 403


def test_zeugnisse_liste_und_pdf(monkeypatch):
    fake = FakeZeugnisse()
    api = _api(monkeypatch, fake)
    z = api.get("/schueler/650/zeugnisse").json()
    assert len(z) == 3 and z[0]["erstellt"] == "2026-11-26T07:55" and "url" not in z[0]
    assert [x["id"] for x in api.get("/schueler/650/zeugnisse", params={"schuljahr": "2026/27", "nur_definitiv": True}).json()] == [
        "wIFFAEmaM5hnZJA72oBxMKnaBxxhGbkg_5_2"]
    r = api.get(f"/schueler/650/zeugnisse/{z[0]['id']}/pdf")
    assert r.status_code == 200 and r.content == PDF and r.headers["content-type"] == "application/pdf"
    assert "Zeugnis_2026-27_1.-Semester_SUS-OHNE-KLASSE_ID651.pdf" in r.headers["content-disposition"]
    assert fake.downloads == [f"/api/0/de/MediaServer/Download/{z[0]['id']}/Zeugnis_2026-27_1.-Semester_SUS-OHNE-KLASSE_ID651."]
    assert api.get("/schueler/650/zeugnisse/fremd/pdf").status_code == 404
    assert api.get("/schueler/999/zeugnisse").status_code == 404


def test_zeugnis_kein_pdf_502(monkeypatch):
    fake = FakeZeugnisse()
    fake.pages["certificates"] = fake.pages["certificates"].replace("wIFFAEmaM5hnZJA72oBxMKnaBxxhGbkg_5_2", "Kaputt_5_2")
    assert _api(monkeypatch, fake).get("/schueler/650/zeugnisse/Kaputt_5_2/pdf").status_code == 502


def test_klasse_zeugnisse(monkeypatch):
    api = _api(monkeypatch, FakeZeugnisse())
    rows = api.get("/klassen/92/zeugnisse", params={"schuljahr": "2026/27"}).json()
    assert [(r["schueler_id"], r["titel"], r["definitiv"]) for r in rows] == [(650, "Zeugnis 1. Semester", True)]
    alle = api.get("/klassen/92/zeugnisse", params={"nur_neuestes": False}).json()
    assert len(alle) == 3
    assert api.get("/klassen/93/zeugnisse").json() == []
