"""Fächer-Zuteilung Lehrperson ↔ Klasse – Verhalten wie live am 14.11.2026 an TEST TEST (649) in TEST_A1a (120)."""
from pathlib import Path
from urllib.parse import parse_qs

import httpx
import pytest

from escola_api import parsers as P
from escola_api.client import EscolaClient, EscolaConfig

FX = (Path(__file__).parent / "fixtures" / "lehrpersonen_faecher.html").read_text(encoding="utf-8")
FAECHER = {21: "Bewegung und Sport (BS)", 12: "Deutsch (D)", 15: "Englisch (E)", 25: "Wirtschaft, Arbeit, Haushalt (WAH)"}


def test_parser_echte_matrix():
    z = P.parse_lehrpersonen_faecher(FX)
    assert [(r["assign_id"], r["fach_id"], r["lehrperson_id"]) for r in z] == [(707, 12, 649), (702, 15, 643)]
    t = z[0]
    assert t["fach"] == "Deutsch" and t["fach_kurz"] == "D" and t["lehrperson"] == "TEST TEST"
    assert (t["klr"], t["fp"], t["spm"], t["abs"], t["gesundheit"]) == (True, True, True, True, True)
    assert t["spm_automatisch"] and t["abs_automatisch"] and not t["klr_automatisch"]
    assert not any(z[1][k] for k in ("klr", "fp", "spm", "abs", "gesundheit"))


class Fake:
    """Bildet Escola nach: Rechte pro Lehrperson, KLR setzt SpM/Abs/Gesundheit automatisch."""

    def __init__(self):
        self.klasse = None
        self.zut = {}          # assign_id -> (lp, fach)
        self.rechte = {}       # lp -> {klr, fp, spm, abs}
        self.next = 800
        self.calls = []

    def matrix(self):
        rows = []
        for aid, (lp, fid) in sorted(self.zut.items()):
            r = self.rechte.setdefault(lp, dict(klr=False, fp=False, spm=False, abs=False))
            def cell(prefix, an, auto=False):
                return (f'<td><input type="checkbox" class="offscreen" id="{prefix}x{aid}" '
                        f'{"disabled " if auto else ""}{"checked" if an else ""} /></td>')
            k = r["klr"]
            rows.append(f'<tr valign="top"><td><strong>{FAECHER[fid]}</strong></td><td><table class="normal"><tr>'
                        f'<td><input type="checkbox" class="teacher-course-assignment-cb" id="teacherCourseAssign_{aid}">'
                        f'<span class="shrink-0">LP {lp}</span></td>'
                        + cell("edit-admin-rights", k) + cell("edit-sne-rights", r["fp"])
                        + cell("edit-measures-rights", k or r["spm"], k) + cell("edit-absences-rights", k or r["abs"], k)
                        + cell("edit-access-to-health-data", k, k)
                        + f'<td><a href="javascript:edit_assignment({lp},{fid});"></a></td></tr></table></td></tr>')
        return '<table class="nice_table_narrow"><tr class="hed"><td>Fach</td></tr>' + "".join(rows) + "</table>"

    def __call__(self, req):
        p = req.url.path
        f = {k: v[0] for k, v in parse_qs(req.content.decode(), keep_blank_values=True).items()}
        if req.method == "GET":
            self.klasse = int(req.url.params.get("klassen_id", 0)) or self.klasse
            return httpx.Response(200, text="<html></html>")
        self.calls.append((p.rsplit("/", 1)[1], f.get("mode") or f.get("type")))
        assert self.klasse == 120
        if p.endswith("zeige_faecher.php"):
            hat = {fid for lp, fid in self.zut.values() if lp == int(f["lehrperson"])}
            return httpx.Response(200, text="".join(
                f'<div><label><input type="checkbox" id="fach_{i}" {"checked" if i in hat else ""} />{n} </label></div>'
                for i, n in FAECHER.items()))
        if p.endswith("ajax_functions_lehrpersonen.php"):
            assert f["type"] == "1" and f["wert"] == "1"
            self.next += 1
            self.zut[self.next] = (649, int(f["fach_id"]))
            return httpx.Response(200, text="")
        mode = f["mode"]
        if mode == "2":
            del self.zut[int(f["assignment"])]
        elif mode in ("3", "16", "22", "23"):
            key = {"3": "klr", "16": "fp", "22": "spm", "23": "abs"}[mode]
            self.rechte.setdefault(int(f["lehrer_id"]), dict(klr=False, fp=False, spm=False, abs=False))[key] = f["new_value"] == "1"
        return httpx.Response(200, text=self.matrix())


@pytest.fixture
def env():
    fake = Fake()
    c = EscolaClient(EscolaConfig(base_url="https://x/"), transport=httpx.MockTransport(fake))
    return c, fake


def test_lesen_schreibt_nichts(env):
    c, fake = env
    fake.zut[700] = (649, 12)
    r = c.lehrperson_faecher(649, 120)
    assert [f["id"] for f in r["faecher"]] == [12] and r["art"] == "Fachlehrperson"
    assert {f["id"] for f in r["faecher_der_klasse"] if f["zugeteilt"]} == {12}
    assert all(m == "0" or n == "zeige_faecher.php" for n, m in fake.calls)


def test_fachlehrperson_und_wieder_weg(env):
    c, fake = env
    r = c.lehrperson_faecher_setzen(649, 120, vorlage="fachlehrperson", faecher=[15, 25])
    assert {f["id"] for f in r["nachher"]["faecher"]} == {15, 25}
    assert not any(r["nachher"][k] for k in ("klr", "fp", "spm", "abs"))
    r = c.lehrperson_faecher_setzen(649, 120, faecher_weg=[15, 25])
    assert r["nachher"]["faecher"] == [] and not fake.zut


def test_sopae_alle_faecher_spm_fp(env):
    c, fake = env
    r = c.lehrperson_faecher_setzen(649, 120, vorlage="sopae")
    n = r["nachher"]
    assert {f["id"] for f in n["faecher"]} == set(FAECHER) and n["spm"] and n["fp"] and not n["abs"]
    assert n["art"] == "SoPä"


def test_klassenlehrperson_automatik(env):
    c, fake = env
    r = c.lehrperson_faecher_setzen(649, 120, vorlage="klassenlehrperson", faecher=[12])
    n = r["nachher"]
    assert n["klr"] and n["spm"] and n["abs"] and n["faecher"][0]["gesundheit"]
    assert set(n["automatisch"]) == {"spm", "abs"} and r["rechte"] == {"klr": True}


def test_regeln(env):
    c, fake = env
    with pytest.raises(ValueError, match="Abs"):
        c.lehrperson_faecher_setzen(649, 120, faecher_hinzu=[12], rechte={"abs": True})
    with pytest.raises(ValueError, match="Gesundheit"):
        c.lehrperson_faecher_setzen(649, 120, faecher_hinzu=[12], rechte={"gesundheit": True})
    with pytest.raises(ValueError, match="nicht"):
        c.lehrperson_faecher_setzen(649, 120, faecher_hinzu=[99])
    with pytest.raises(ValueError, match="mindestens einem Fach"):
        c.lehrperson_faecher_setzen(649, 120, rechte={"fp": True})
    assert not fake.zut


def test_probelauf(env):
    c, fake = env
    r = c.lehrperson_faecher_setzen(649, 120, vorlage="sopae", probelauf=True)
    assert r["probelauf"] and r["faecher_hinzu"] == sorted(FAECHER) and not fake.zut
