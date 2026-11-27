"""Fächer-Zuteilung: Arbeitsgruppen, kommendes Schuljahr und Escola-Sitzungszustand (live beobachtet 15.11.2026).

Der Fake bildet zwei Escola-Eigenheiten nach:
- „Fach zuteilen“ wirkt auf die zuletzt mit „Fächer anzeigen“ geöffnete Lehrperson.
- Die Matrix mit school_year=1 stellt die ganze Sitzung aufs kommende Schuljahr um.
"""
from urllib.parse import parse_qs

import httpx
import pytest

from escola_api.client import EscolaClient, EscolaConfig

FAECHER = {12: "Deutsch (D)", 15: "Englisch (E)"}


class Fake:
    def __init__(self):
        self.ziel = None            # ("k", id) / ("ag", id)
        self.aktive_lp = None
        self.sitzung_sj = 0
        self.zut = {}               # (ziel, sj) -> {assign_id: (lp, fach)}
        self.next = {"k": 700, "ag": 4}
        self.rechte = {}            # (ziel, sj, lp) -> {prefix: 0/1}; wirkt im Sitzungs-Schuljahr

    def _tab(self, ziel, sj):
        return self.zut.setdefault((ziel, sj), {})

    def matrix(self):
        rows = self._tab(self.ziel, self.sitzung_sj)
        if self.ziel[0] == "k":
            return "<table class='nice_table_narrow'>" + "".join(
                f'<tr valign="top"><td><strong>{FAECHER[f]}</strong></td><td><table class="normal"><tr>'
                f'<td><input type="checkbox" class="teacher-course-assignment-cb" id="teacherCourseAssign_{a}">'
                f'<span class="shrink-0">LP {lp}</span></td>'
                + "".join(f'<td><input class="offscreen" id="{p}x" {"checked" if self.rechte.get((self.ziel, self.sitzung_sj, lp), {}).get(p) else ""}/></td>' for p in
                          ("edit-admin-rights", "edit-sne-rights", "edit-measures-rights", "edit-absences-rights",
                           "edit-access-to-health-data"))
                + f'<td><a href="javascript:edit_assignment({lp},{f});"></a></td></tr></table></td></tr>'
                for a, (lp, f) in sorted(rows.items())) + "</table>"
        return "<table class='nice_table_narrow'><tr class='hed'><td>Fach</td></tr>" + "".join(
            f'<tr valign="top"><td><strong>{FAECHER[f]}</strong></td><td><div><div>LP {lp}</div></div></td>'
            f'<td><div><div><input class="offscreen" id="h{a}"/></div></div></td>'
            f'<td><div><div><input class="offscreen" id="a{a}"/></div></div></td>'
            f'<td><div><div><a href="javascript:edit_assignment({lp},{f});"></a>'
            f'<a href="javascript:delete_assignment({a});"></a></div></div></td></tr>'
            for a, (lp, f) in sorted(rows.items())) + "</table>"

    def __call__(self, req):
        q = dict(req.url.params)
        if req.method == "GET":
            if "klassen_id" in q:
                self.ziel = ("k", int(q["klassen_id"]))
            elif "workgroup_id" in q:
                self.ziel = ("ag", int(q["workgroup_id"]))
            return httpx.Response(200, text="<html></html>")
        f = {k: v[0] for k, v in parse_qs(req.content.decode(), keep_blank_values=True).items()}
        p = req.url.path
        if p.endswith("zeige_faecher.php"):
            self.aktive_lp = int(f["lehrperson"])
            ziel = ("k", int(f["class_id"])) if f["class_id"] != "0" else ("ag", int(f["workgroup_id"]))
            hat = {fa for lp, fa in self._tab(ziel, int(f["schoolYear"])).values() if lp == self.aktive_lp}
            return httpx.Response(200, text="".join(
                f'<label><input type="checkbox" id="fach_{i}" {"checked" if i in hat else ""}/>{n}</label>'
                for i, n in FAECHER.items()))
        if p.endswith("ajax_functions_lehrpersonen.php"):
            assert self.aktive_lp is not None, "Escola: keine aktive Lehrperson"
            ziel = ("k", int(f["class_id"])) if f["class_id"] != "0" else ("ag", int(f["workgroup_id"]))
            art = ziel[0]
            self.next[art] += 1
            self._tab(ziel, int(f["schoolYear"]))[self.next[art]] = (self.aktive_lp, int(f["fach_id"]))
            self.aktive_lp = None  # Test: muss vor jedem Zuteilen neu geöffnet werden
            return httpx.Response(200, text="")
        mode = f["mode"]
        if mode == "0":
            if "school_year" in f:
                self.sitzung_sj = int(f["school_year"])
        elif mode in ("3", "16", "22", "23"):
            prefix = {"3": "edit-admin-rights", "16": "edit-sne-rights", "22": "edit-measures-rights",
                      "23": "edit-absences-rights"}[mode]
            self.rechte.setdefault((self.ziel, self.sitzung_sj, int(f["lehrer_id"])), {})[prefix] = int(f["new_value"])
        elif mode == "2":
            # Zuteilungsnummer gilt im aktiven Kontext + Sitzungs-Schuljahr
            for sj in (self.sitzung_sj, 0, 1):
                tab = self._tab(self.ziel, sj)
                if int(f["assignment"]) in tab:
                    del tab[int(f["assignment"])]
                    break
            else:
                raise AssertionError("Zuteilung im aktiven Kontext nicht gefunden")
        return httpx.Response(200, text=self.matrix())


@pytest.fixture
def env():
    fake = Fake()
    return EscolaClient(EscolaConfig(base_url="https://x/"), transport=httpx.MockTransport(fake)), fake


def test_mehrere_faecher_je_mit_geoeffneter_lehrperson(env):
    c, fake = env
    r = c.lehrperson_faecher_setzen(649, 120, vorlage="fachlehrperson", faecher=[12, 15])
    assert {f["id"] for f in r["nachher"]["faecher"]} == {12, 15}
    assert set(fake._tab(("k", 120), 0).values()) == {(649, 12), (649, 15)}


def test_kommendes_schuljahr_und_sitzung_zurueck(env):
    c, fake = env
    r = c.lehrperson_faecher_setzen(649, 120, faecher_hinzu=[12], schuljahr=1)
    assert r["schuljahr"] == 1 and [f["id"] for f in r["nachher"]["faecher"]] == [12]
    assert fake._tab(("k", 120), 1) and not fake._tab(("k", 120), 0)
    assert fake.sitzung_sj == 0, "Sitzung muss wieder aufs aktuelle Schuljahr stehen"
    r = c.lehrperson_faecher_setzen(649, 120, rechte={"fp": True}, schuljahr=1)  # live geprüft 28.11.2026
    assert r["nachher"]["fp"] is True and fake.sitzung_sj == 0
    assert fake.rechte[(("k", 120), 1, 649)]["edit-sne-rights"] == 1 and (("k", 120), 0, 649) not in fake.rechte
    c.lehrperson_faecher_setzen(649, 120, rechte={"fp": False}, schuljahr=1)
    assert fake.rechte[(("k", 120), 1, 649)]["edit-sne-rights"] == 0 and fake.sitzung_sj == 0
    c.lehrperson_faecher_setzen(649, 120, faecher_weg=[12], schuljahr=1)
    assert not fake._tab(("k", 120), 1) and fake.sitzung_sj == 0


def test_arbeitsgruppe(env):
    c, fake = env
    r = c.lehrperson_faecher_setzen(649, arbeitsgruppe_id=3, faecher_hinzu=[12])
    assert r["arbeitsgruppe_id"] == 3 and [f["id"] for f in r["nachher"]["faecher"]] == [12]
    assert c.klasse_lehrpersonen(arbeitsgruppe_id=3)["lehrpersonen"][0]["faecher"][0]["assign_id"] == 5
    with pytest.raises(ValueError, match="keine Rechte"):
        c.lehrperson_faecher_setzen(649, arbeitsgruppe_id=3, rechte={"fp": True})
    with pytest.raises(ValueError, match="keine Klassenlehrperson"):
        c.lehrperson_faecher_setzen(649, arbeitsgruppe_id=3, vorlage="klassenlehrperson")
    c.lehrperson_faecher_setzen(649, arbeitsgruppe_id=3, faecher=[])
    assert not fake._tab(("ag", 3), 0)


def test_genau_ein_ziel(env):
    c, _ = env
    with pytest.raises(ValueError, match="Genau eines"):
        c.lehrperson_faecher(649)
    with pytest.raises(ValueError, match="Genau eines"):
        c.lehrperson_faecher(649, 120, arbeitsgruppe_id=3)


def test_schuljahr_als_query_parameter(monkeypatch):
    """Regression 15.11.2026: ?schuljahr=0 wurde mit 422 abgelehnt (Literal im Query-Parameter)."""
    from fastapi.testclient import TestClient
    from escola_api.app import create_app
    fake = Fake()
    c = EscolaClient(EscolaConfig(base_url="https://x/"), transport=httpx.MockTransport(fake))
    tc = TestClient(create_app(client=c))
    for url in ("/lehrpersonen/649/faecher?klasse_id=120&schuljahr=0", "/lehrpersonen/649/faecher?klasse_id=120&schuljahr=1",
                "/klassen/120/lehrpersonen?schuljahr=1", "/arbeitsgruppen/3/lehrpersonen?schuljahr=0"):
        assert tc.get(url).status_code == 200, url
    assert tc.get("/klassen/120/lehrpersonen?schuljahr=2").status_code == 422
