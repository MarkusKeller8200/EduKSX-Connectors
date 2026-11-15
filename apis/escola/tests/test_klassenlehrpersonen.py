"""Klassenlehrpersonen A/B/C – Verhalten wie live am 14.11.2026 an TEST_A1a (120) geprüft."""
from pathlib import Path
from urllib.parse import parse_qsl

import httpx
import pytest

from escola_api import parsers as P
from escola_api.client import EscolaClient, EscolaConfig

VORLAGE = (Path(__file__).parent / "fixtures" / "klasse_formular.html").read_text(encoding="utf-8")
LPS = {576: "Bauhuber Verena", 135: "Schmid Sibylle", 649: "TEST TEST"}


def optionen(wert: int) -> str:
    # Escola markiert immer „(keine)“ UND die gewählte Person als selected
    return '<option value="0" selected>(keine)</option>' + "".join(
        f'<option value="{i}" {"selected" if i == wert else ""}>{n}</option>' for i, n in LPS.items())


class Fake:
    def __init__(self):
        self.klp = {"klassenlehrer_id": 0, "klassenlehrer_id_2": 0, "klassenlehrer_id_3": 0,
                    "klassenlehrer_id_plan": 576, "klassenlehrer_id_2_plan": 0, "klassenlehrer_id_3_plan": 0}
        self.kontext = None
        self.posts = []

    def formular(self):
        ph = {"KLP_A": "klassenlehrer_id", "KLP_B": "klassenlehrer_id_2", "KLP_C": "klassenlehrer_id_3",
              "KLP_PA": "klassenlehrer_id_plan", "KLP_PB": "klassenlehrer_id_2_plan", "KLP_PC": "klassenlehrer_id_3_plan"}
        h = VORLAGE
        for k, n in ph.items():
            h = h.replace("{" + k + "}", optionen(self.klp[n]))
        return h

    def __call__(self, req):
        q = dict(req.url.params)
        if req.method == "GET":
            if q.get("sub_k") == "10":
                self.kontext = "klassen"
                return httpx.Response(200, text="<html>Klassen</html>")
            if q.get("mode") == "903":
                # ohne Kontext liefert Escola kein Formular (live beobachtet)
                return httpx.Response(200, text=self.formular() if self.kontext == "klassen" else "<html></html>")
            self.kontext = None
            return httpx.Response(200, text="<html></html>")
        assert q.get("mode") == "902" and self.kontext == "klassen"
        daten = parse_qsl(req.content.decode(), keep_blank_values=True)
        self.posts.append(daten)
        for n, v in daten:
            if n in self.klp:
                self.klp[n] = int(v)
        return httpx.Response(200, text="<html>gespeichert</html>")


@pytest.fixture
def env():
    fake = Fake()
    return EscolaClient(EscolaConfig(base_url="https://x/"), transport=httpx.MockTransport(fake)), fake


def test_formular_wie_browser():
    felder, info = P.klassen_formular(Fake().formular())
    d = dict(felder)
    assert "active_type" not in d and "bista_sa" not in d and "submit" not in d and "administrativeClass" not in d
    assert d["klassenlehrer_id"] == "0" and d["klassenlehrer_id_plan"] == "576"
    assert d["schoolSiteId"] == "1" and d["real_class_0"] == "9" and d["deletematchings"] == "[]"
    assert info["klassenlehrpersonen"] == {"aktuell": [], "kommend": [576]}


def test_lesen(env):
    c, fake = env
    r = c.klassenlehrpersonen(120, waehlbar=True)
    assert r["aktuell"] == [] and r["kommend"] == [{"slot": "A", "id": 576, "name": "Bauhuber Verena"}]
    assert len(r["waehlbar"]) == 3 and not fake.posts


def test_setzen_aendert_nur_klp(env):
    c, fake = env
    vorher = P.klassen_formular(fake.formular())[0]
    r = c.klassenlehrpersonen_setzen(120, aktuell=[649, 135])
    assert [x["id"] for x in r["nachher"]["aktuell"]] == [649, 135]
    assert [x["id"] for x in r["nachher"]["kommend"]] == [576]
    gesendet = fake.posts[0]
    assert gesendet[-1] == ("submit", "Abschicken")
    ohne = lambda f: [(n, v) for n, v in f if not n.startswith("klassenlehrer_id")]
    assert ohne(gesendet[:-1]) == ohne(vorher)
    c.klassenlehrpersonen_setzen(120, aktuell=[])
    assert fake.klp["klassenlehrer_id"] == 0 and fake.klp["klassenlehrer_id_2"] == 0


def test_regeln_und_probelauf(env):
    c, fake = env
    with pytest.raises(ValueError, match="Höchstens 3"):
        c.klassenlehrpersonen_setzen(120, aktuell=[576, 135, 649, 1])
    with pytest.raises(ValueError, match="wählbar"):
        c.klassenlehrpersonen_setzen(120, aktuell=[999])
    with pytest.raises(ValueError, match="Doppelte"):
        c.klassenlehrpersonen_setzen(120, kommend=[649, 649])
    r = c.klassenlehrpersonen_setzen(120, aktuell=[649], probelauf=True)
    assert r["probelauf"] and r["geaendert"] and not fake.posts
    assert not c.klassenlehrpersonen_setzen(120, kommend=[576])["geaendert"] and not fake.posts
