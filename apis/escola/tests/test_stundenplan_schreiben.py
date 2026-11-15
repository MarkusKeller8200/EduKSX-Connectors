"""Stundenplan schreiben – Escola-Verhalten wie live am 15.11.2026 an TEST_A1a (120) beobachtet:
- Leere Zelle: new_entry=1 mit id=new_<lektion>_<tag> legt den Eintrag an.
- Belegte Zelle: addCourseField=1 legt sofort einen LEEREN Eintrag an, Fach danach mit new_entry=1&id=<eintrag>.
- Lehrperson ergibt sich aus der Fach-Zuteilung: eine Lehrperson -> nur Name (automatisch),
  mehrere -> Schalter teacher_<eintrag>_<person> (type=2 schaltet um).
"""
from urllib.parse import parse_qs

import httpx
import pytest

from escola_api.client import EscolaClient, EscolaConfig

RAEUME = {9: "A101", 10: "A102"}


class Fake:
    def __init__(self, zuteilung):
        self.zut = zuteilung            # fach -> [lehrpersonen]
        self.eintraege = {}             # rid -> dict
        self.next = 40
        self.posts = []
        self.sitzung_sj = 0

    def edit_html(self, tag, lektion):
        teile = []
        for rid, e in sorted(self.eintraege.items()):
            if (e["tag"], e["lektion"]) != (tag, lektion):
                continue
            opts = '<option value="0"></option><option value="99999">- -</option>' + "".join(
                f'<option value="{f}" {"selected" if f == e["fach"] else ""}>F{f}</option>' for f in self.zut)
            raeume = "".join(
                f'<select id="{p}{rid}"><option value="0">Raum wählen</option>' + "".join(
                    f'<option value="{r}" {"selected" if e["raeume"][i] == r else ""}>{n}</option>' for r, n in RAEUME.items())
                + "</select>" for i, p in enumerate(("room_id_", "room_2_id_", "room_3_id_")))
            lps = self.zut.get(e["fach"], [])
            if len(lps) == 1:
                lp_html = (f'<div class="tt-edit__row"><span class="tt-edit__lp-name">LP {lps[0]}</span>'
                           f'<span id="lp_warn_{rid}_{lps[0]}"></span></div>')
            else:
                lp_html = "".join(
                    f'<div class="tt-edit__row"><input id="teacher_{rid}_{p}" type="checkbox" '
                    f'{"checked" if p in e["lp"] else ""}><span class="tt-edit__lp-name">LP {p}</span>'
                    f'<span id="lp_warn_{rid}_{p}"></span></div>' for p in lps)
            teile.append(f'<select id="tt_select_{rid}">{opts}</select>{raeume}<div class="tt-edit__lp-list">{lp_html}</div>')
        if not teile:
            teile.append(f'<select id="tt_select_new_{lektion}_{tag}"><option value="0"></option></select>')
        return "<div>" + "".join(teile) + "</div>"

    def __call__(self, req):
        if req.method == "GET":
            return httpx.Response(200, text="<html></html>")
        f = {k: v[0] for k, v in parse_qs(req.content.decode(), keep_blank_values=True).items()}
        self.posts.append(f)
        p = req.url.path
        if p.endswith("lehrpersonen_faecher.php"):
            if "school_year" in f:
                self.sitzung_sj = int(f["school_year"])
            rows = "".join(
                f'<tr valign="top"><td><strong>F{f} (X)</strong></td><td><table class="normal"><tr><td>'
                f'<input class="teacher-course-assignment-cb" id="teacherCourseAssign_{f}{lp}"><span class="shrink-0">LP</span>'
                f'</td><td><a href="javascript:edit_assignment({lp},{f});"></a></td></tr></table></td></tr>'
                for f, lps in self.zut.items() for lp in lps)
            return httpx.Response(200, text=f"<table class='nice_table_narrow'>{rows}</table>")
        t = f.get("type")
        if t == "2":
            e = self.eintraege[int(f["timetableRowId"])]
            e["lp"] ^= {int(f["teacherId"])}
            return httpx.Response(200, text="")
        if t == "18":
            e = self.eintraege[int(f["timetableRowId"])]
            e["raeume"][int(f["roomType"]) - 1] = int(f["roomId"]) or None
            return httpx.Response(200, text="")
        tag, lektion = f["dayCode"], int(f["lessonId"])
        if t == "1":
            assert self.sitzung_sj == 0
            if "deleteEntry" in f:
                del self.eintraege[int(f["deleteEntry"])]
            elif "addCourseField" in f:
                self.next += 1
                self.eintraege[self.next] = {"tag": tag, "lektion": lektion, "fach": None, "raeume": [None] * 3, "lp": set()}
            elif "new_entry" in f:
                if f["id"].startswith("new_"):
                    self.next += 1
                    self.eintraege[self.next] = {"tag": tag, "lektion": lektion, "fach": int(f["courseId"]),
                                                 "raeume": [None] * 3, "lp": set()}
                else:
                    self.eintraege[int(f["id"])]["fach"] = int(f["courseId"])
        return httpx.Response(200, text=self.edit_html(tag, lektion))


def client(zut):
    fake = Fake(zut)
    return EscolaClient(EscolaConfig(base_url="https://x/"), transport=httpx.MockTransport(fake)), fake


def test_anlegen_leere_zelle_mit_raum():
    c, fake = client({12: [649]})
    r = c.stundenplan_schreiben(120, "B", 3, fach_id=12, raum_ids=[9])
    e = r["eintrag"]
    assert e["fach_id"] == 12 and e["raum_ids"] == [9]
    assert e["lehrpersonen"] == [{"id": 649, "gewaehlt": True, "schaltbar": False, "name": "LP 649"}]
    assert fake.posts[-1]["type"] == "3"  # Bearbeitung beendet


def test_anlegen_in_belegter_zelle_und_loeschen():
    c, fake = client({12: [649], 15: [643]})
    erst = c.stundenplan_schreiben(120, "A", 2, fach_id=12)["eintrag"]["eintrag_id"]
    zweit = c.stundenplan_schreiben(120, "A", 2, fach_id=15)["eintrag"]
    assert zweit["eintrag_id"] != erst and zweit["fach_id"] == 15
    assert any(p.get("addCourseField") == "1" for p in fake.posts)
    r = c.stundenplan_schreiben(120, "A", 2, zweit["eintrag_id"], loeschen=True)
    assert r["geloescht"] and [e["eintrag_id"] for e in r["zelle"]] == [erst]


def test_lehrpersonen_umschalten_nur_wo_mehrere():
    c, fake = client({12: [649, 135]})
    rid = c.stundenplan_schreiben(120, "C", 4, fach_id=12, lehrperson_ids=[649])["eintrag"]["eintrag_id"]
    assert fake.eintraege[rid]["lp"] == {649}
    r = c.stundenplan_schreiben(120, "C", 4, rid, lehrperson_ids=[135])
    assert r["eintrag"]["lehrperson_ids"] == [135]
    c2, f2 = client({12: [649]})
    rid2 = c2.stundenplan_schreiben(120, "C", 4, fach_id=12)["eintrag"]["eintrag_id"]
    with pytest.raises(ValueError, match="haben dieses Fach"):
        c2.stundenplan_schreiben(120, "C", 4, rid2, lehrperson_ids=[135])


def test_pruefungen():
    c, fake = client({12: [649]})
    with pytest.raises(ValueError, match="nicht zugeteilt"):
        c.stundenplan_schreiben(120, "A", 2, fach_id=99)
    rid = c.stundenplan_schreiben(120, "A", 2, fach_id=12)["eintrag"]["eintrag_id"]
    with pytest.raises(ValueError, match="nicht wählbar"):
        c.stundenplan_schreiben(120, "A", 2, rid, raum_ids=[777])
    with pytest.raises(ValueError, match="gibt es in dieser Zelle nicht"):
        c.stundenplan_schreiben(120, "A", 2, 9999, loeschen=True)
    with pytest.raises(ValueError, match="A–E"):
        c.stundenplan_zelle(120, "F", 2)
    vorher = len(fake.posts)
    assert c.stundenplan_schreiben(120, "A", 2, rid, raum_ids=[9], probelauf=True)["probelauf"]
    assert not any(p.get("type") == "18" for p in fake.posts[vorher:])


def test_nie_ganzen_stundenplan_loeschen():
    import inspect
    from escola_api import client as mod
    assert "application_class.php" not in inspect.getsource(mod.EscolaClient.stundenplan_schreiben)


def test_ersetzen_ablauf(monkeypatch):
    c, _ = client({})
    log = []
    monkeypatch.setattr(c, "lehrperson_einsatz", lambda lp: {
        "klassenlehrperson": [{"klasse_id": 92, "schuljahr": "aktuell", "slot": "A"},
                              {"klasse_id": 92, "schuljahr": "kommend", "slot": "A"}],
        "fach_zuteilungen": [{"klasse_id": 92, "faecher": [12, 24], "klr": True, "fp": False, "spm": True, "abs": True},
                             {"klasse_id": 93, "faecher": [15], "klr": False, "fp": True, "spm": False, "abs": False}],
        "stundenplan": [{"klasse_id": 92, "tag_code": "A", "lektion_id": 2}]})
    monkeypatch.setattr(c, "lehrperson_faecher_setzen", lambda lp, k, **kw: log.append(("faecher", lp, k, kw)) or
                        {"faecher_hinzu": kw.get("faecher_hinzu"), "faecher_weg": []})
    monkeypatch.setattr(c, "klassenlehrpersonen", lambda k: {"aktuell": [{"id": 135}, {"id": 136}]})
    monkeypatch.setattr(c, "klassenlehrpersonen_setzen", lambda k, aktuell: log.append(("klp", k, aktuell)) or
                        {"nachher": {"aktuell": aktuell}})
    monkeypatch.setattr(c, "stundenplan_zelle", lambda *a: {"eintraege": []})
    r = c.lehrperson_ersetzen(135, 700)
    assert r["vollstaendig"]
    assert log[0] == ("faecher", 700, 92, {"faecher_hinzu": [12, 24], "rechte": None})   # KLR: SpM nicht kopieren
    assert log[1] == ("faecher", 700, 93, {"faecher_hinzu": [15], "rechte": {"fp": True}})
    assert ("klp", 92, [700, 136]) in log                                                # gleicher Platz A
    assert log[-2:] == [("faecher", 135, 92, {"faecher": []}), ("faecher", 135, 93, {"faecher": []})]
    assert c.lehrperson_ersetzen(135, 700, probelauf=True)["klassenlehrperson_plaetze"] == \
        [{"klasse_id": 92, "schuljahr": "aktuell", "slot": "A"}]
