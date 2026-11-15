"""Stundenplan-Abgleich (Issue #6) und Felder pro Klasse (Issue #8)."""
import httpx
import pytest
from fastapi.testclient import TestClient

from escola_api.app import create_app
from escola_api.client import EscolaClient, EscolaConfig


def client():
    c = EscolaClient(EscolaConfig(base_url="https://x/", cookie="x"), transport=httpx.MockTransport(lambda r: httpx.Response(500)))
    ist = {("A", 2): [{"eintrag_id": 35, "fach_id": 12, "raum_ids": [], "lehrperson_ids": []}],
           ("B", 3): [{"eintrag_id": 36, "fach_id": 15, "raum_ids": [9], "lehrperson_ids": [649]}]}
    calls = []
    c._faecher_klasse = lambda k: {12, 15, 25}
    c._belegte_zellen = lambda k: set(ist)
    c.stundenplan_zelle = lambda k, t, l: {"eintraege": [dict(e) for e in ist.get((t, l), [])]}
    c.stundenplan_schreiben = lambda *a, **kw: calls.append((a, kw)) or {}
    return c, calls


SOLL = [{"tag": "A", "lektion_id": 2, "fach_id": 12, "raum_ids": [9]},          # Raum ändern
        {"tag": "C", "lektion_id": 4, "fach_id": 25, "raum_ids": [10]}]         # neu; B/3 fehlt -> bleibt/löschen


def test_probelauf_zeigt_plan_und_schreibt_nichts():
    c, calls = client()
    r = c.stundenplan_abgleich(120, SOLL)
    p = r["plan"]
    assert r["probelauf"] and not calls and not r["fehler"]
    assert p["aendern"] == [{"tag": "A", "lektion_id": 2, "eintrag_id": 35, "fach_id": 12, "raum_ids": [9]}]
    assert p["neu"][0]["fach_id"] == 25 and p["bleibt"][0]["eintrag_id"] == 36 and not p["loeschen"]


def test_anwenden_mit_loeschen():
    c, calls = client()
    r = c.stundenplan_abgleich(120, SOLL, loeschen=True, probelauf=False)
    assert r["vollstaendig"] and len(calls) == 3
    assert calls[0][0][:5] == (120, "C", 4, None, 25)          # neu
    assert calls[1][0][:4] == (120, "A", 2, 35)                # ändern
    assert calls[2][1] == {"loeschen": True}                   # löschen B/3


def test_fach_nicht_zugeteilt_blockiert_alles():
    c, calls = client()
    r = c.stundenplan_abgleich(120, [{"tag": "A", "lektion_id": 2, "fach_id": 99}], probelauf=False)
    assert r["fehler"] and r["probelauf"] and not calls


def test_unveraendert_wird_gezaehlt_und_api_standard_probelauf():
    c, calls = client()
    api = TestClient(create_app(client=c))
    body = {"eintraege": [{"tag": "A", "lektion_id": 2, "fach_id": 12}, {"tag": "B", "lektion_id": 3, "fach_id": 15, "raum_ids": [9]}]}
    r = api.post("/klassen/120/stundenplan/abgleich", json=body)
    assert r.status_code == 200 and r.json()["plan"]["unveraendert"] == 2 and not calls


def test_klasse_felder_nur_leer():
    c, _ = client()
    c.schueler = lambda refresh=False, schuljahr=0: [{"id": 650, "nachname": "SuS", "vorname": "SuS", "klasse_id": 120},
                                                     {"id": 651, "nachname": "B", "vorname": "C", "klasse_id": 120}]
    c.person = lambda pid, kat, abs_=None: {"felder": {"kontrolle_zahnarzt": "01.09.2026" if pid == 650 else ""}}
    rows = c.klasse_felder(120, ["kontrolle_zahnarzt"], nur_leer=True)
    assert [r["schueler_id"] for r in rows] == [651]
    alle = c.klasse_felder(120, ["kontrolle_zahnarzt", "gibtsnicht"])
    assert alle[0]["unbekannte_felder"] == "gibtsnicht"
    with pytest.raises(ValueError):
        c.klasse_felder(120, [])
