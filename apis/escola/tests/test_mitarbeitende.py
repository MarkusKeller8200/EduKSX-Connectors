"""WF-01 Mitarbeiter:in einstellen / WF-02 Austritt – Regeln und Ablauf (ohne Escola, Teile ersetzt)."""
import httpx
import pytest

from escola_api import personen as PP
from escola_api.client import EscolaClient, EscolaConfig, KonfliktFehler


@pytest.mark.parametrize("vorname,nachname,mail", [
    ("Jürg", "Riedow", "juerg.riedow@sekbuelach.ch"),
    ("Félix", "Laninger", "felix.laninger@sekbuelach.ch"),
    ("Anna-Lena", "Müller-Widli", "anna.mueller@sekbuelach.ch"),
    ("Hans Peter", "Meier Huber", "hans.meier@sekbuelach.ch"),
    ("Laura", "von Arx", "laura.vonarx@sekbuelach.ch"),
    ("Ondřej", "Polisenský", "ondrej.polisensky@sekbuelach.ch"),
    ("Jörg", "Weiß", "joerg.weiss@sekbuelach.ch"),
])
def test_schulmail_regeln(vorname, nachname, mail):
    assert PP.schulmail(vorname, nachname) == mail


def test_ahv_pruefen():
    assert PP.ahv_pruefen("7561234567897") == "756.1234.5678.97"
    assert PP.ahv_pruefen(" 756.1234.5678.97 ") == "756.1234.5678.97"
    for falsch in ("7561234567890", "1234567890123", "756.1234.5678", ""):
        with pytest.raises(PP.FeldFehler):
            PP.ahv_pruefen(falsch)


@pytest.fixture
def c():
    def nie(req):
        raise AssertionError(f"Unerwarteter Escola-Aufruf {req.url}")
    return EscolaClient(EscolaConfig(base_url="https://x/"), transport=httpx.MockTransport(nie))


def test_einstellen_bricht_vor_dem_anlegen_ab(c, monkeypatch):
    angelegt = []
    monkeypatch.setattr(c, "person_anlegen", lambda *a, **k: angelegt.append(a))
    monkeypatch.setattr(c, "personen_suchen", lambda ahv=None, email=None, refresh=False:
                        {"treffer": [{"id": 77, "name": "Alt Person", "aktiv": False}] if ahv else []})
    with pytest.raises(KonfliktFehler) as e:
        c.mitarbeiter_einstellen("Muster", "Max", "m", "Hinterbirch", "lehrperson", ahv="7561234567897")
    assert e.value.personen[0]["id"] == 77 and not angelegt

    monkeypatch.setattr(c, "personen_suchen", lambda ahv=None, email=None, refresh=False:
                        {"treffer": [{"id": 5, "name": "Muster Max", "aktiv": True}] if email else []})
    with pytest.raises(KonfliktFehler, match="max.muster@sekbuelach.ch"):
        c.mitarbeiter_einstellen("Muster", "Max", "m", "Hinterbirch", "lehrperson")
    assert not angelegt
    with pytest.raises(ValueError, match="Prüfziffer"):
        c.mitarbeiter_einstellen("Muster", "Max", "m", "Hinterbirch", "lehrperson", ahv="7561234567890")


def test_einstellen_ablauf(c, monkeypatch):
    log = []
    monkeypatch.setattr(c, "personen_suchen", lambda **k: {"treffer": []})
    monkeypatch.setattr(c, "rollen", lambda refresh=False: [{"id": 13, "zuordenbar": True}])
    monkeypatch.setattr(c, "person_anlegen", lambda *a: log.append(("anlegen", a[3])) or {"angelegt": True, "id": 700})
    monkeypatch.setattr(c, "person_rollen_setzen", lambda pid, h, e: log.append(("rollen", h)) or
                        {"geaendert": True, "rollen": [{"name": "Lehrpersonen (Hinterbirch)"}]})
    monkeypatch.setattr(c, "person_schreiben", lambda pid, f: log.append(("felder", sorted(f))) or
                        {"geschrieben": True, "aenderungen": [{"feld": k} for k in f]})
    monkeypatch.setattr(c, "ahv_setzen", lambda pid, a: log.append(("ahv", a)) or {"ahv": "gesetzt"})
    monkeypatch.setattr(c, "schulmail_setzen", lambda pid, v, n: log.append(("mail", v)) or {"email": "max.muster@sekbuelach.ch"})
    r = c.mitarbeiter_einstellen("Muster", "Max", "m", "Hinterbirch", "gruppe_14", [13], "756.1234.5678.97",
                                 {"geburtstag": "01.02.1990", "natel": "079 000 00 00"})
    assert r["id"] == 700 and r["vollstaendig"]
    assert [x[0] for x in log] == ["anlegen", "rollen", "felder", "ahv", "mail"]
    assert ("ahv", "756.1234.5678.97") in log


def test_einstellen_teilfehler_wird_gemeldet(c, monkeypatch):
    monkeypatch.setattr(c, "personen_suchen", lambda **k: {"treffer": []})
    monkeypatch.setattr(c, "person_anlegen", lambda *a: {"angelegt": True, "id": 701})
    monkeypatch.setattr(c, "schulmail_setzen", lambda *a: (_ for _ in ()).throw(RuntimeError("Escola hat die E-Mail nicht übernommen")))
    r = c.mitarbeiter_einstellen("Muster", "Max", "m", "Hinterbirch", "lehrperson")
    assert r["id"] == 701 and not r["vollstaendig"]
    assert r["schritte"][-1] == {"schritt": "schulmail", "ok": False, "fehler": "Escola hat die E-Mail nicht übernommen"}


def test_rollen_vorab_geprueft(c, monkeypatch):
    monkeypatch.setattr(c, "rollen", lambda refresh=False: [{"id": 13, "zuordenbar": True}, {"id": 1, "zuordenbar": False}])
    monkeypatch.setattr(c, "person_anlegen", lambda *a: pytest.fail("darf nicht anlegen"))
    with pytest.raises(ValueError, match="nicht zuordenbar"):
        c.mitarbeiter_einstellen("Muster", "Max", "m", "Hinterbirch", "lehrperson", [1], schulmail=False)


def test_rollen_ausgetreten(c, monkeypatch):
    monkeypatch.setattr(c, "rollen", lambda refresh=False: [
        {"id": 13, "name": "Lehrpersonen (Hinterbirch)", "personengruppe": False, "zuordenbar": True},
        {"id": 2, "name": "Administrator:innen", "personengruppe": False, "zuordenbar": False},
        {"id": 41, "name": "Hausdienst", "personengruppe": True, "zuordenbar": True}])
    with pytest.raises(KonfliktFehler, match="fehlt"):
        c.rollen_ausgetreten(649)
    monkeypatch.setattr(c, "rollen", lambda refresh=False: [
        {"id": 13, "name": "Lehrpersonen (Hinterbirch)", "personengruppe": False, "zuordenbar": True},
        {"id": 2, "name": "Administrator:innen", "personengruppe": False, "zuordenbar": False},
        {"id": 41, "name": "Hausdienst", "personengruppe": True, "zuordenbar": True},
        {"id": 50, "name": "Ausgetreten", "personengruppe": True, "zuordenbar": True}])
    monkeypatch.setattr(c, "person_rollen", lambda pid: [
        {"id": 13, "name": "Lehrpersonen (Hinterbirch)", "zugewiesen": True, "aenderbar": True},
        {"id": 2, "name": "Administrator:innen", "zugewiesen": True, "aenderbar": True},
        {"id": 41, "name": "Hausdienst", "zugewiesen": True, "aenderbar": True},
        {"id": 50, "name": "Ausgetreten", "zugewiesen": False, "aenderbar": True}])
    aufruf = {}
    monkeypatch.setattr(c, "person_rollen_setzen", lambda pid, h, e, p=False: aufruf.update(h=h, e=e) or {"geaendert": True})
    r = c.rollen_ausgetreten(649)
    assert aufruf == {"h": [50], "e": [13, 41]} and r["nicht_entfernt"] == ["Administrator:innen"]
