"""Aktivieren/Deaktivieren – Ablauf wie live am 14.11.2026 (Rückfrage, dann mode=36)."""
from urllib.parse import parse_qs
import httpx
from fastapi.testclient import TestClient
from escola_api.client import EscolaClient, EscolaConfig


class FakeStatus:
    def __init__(self):
        self.aktiv = {649: True}
        self.offen = None
        self.modes = []

    def __call__(self, req):
        if req.url.path != "/inc/ajax/persons/personManagement.php":
            return httpx.Response(404)
        f = {k: v[0] for k, v in parse_qs(req.content.decode(), keep_blank_values=True).items()}
        self.modes.append((f.get("mode"), f.get("action")))
        if f.get("mode") == "17":
            assert f["action"] in ("1", "2"), "nur aktivieren/deaktivieren erlaubt"
            pid = int(f["element_string"].strip(":"))
            self.offen = (pid, f["action"])
            verb = "deaktivieren" if f["action"] == "1" else "aktivieren"
            return httpx.Response(200, text=f'<div class="alert">Möchtest du diese Person wirklich {verb}?'
                                            '<a onclick="personManagementGotoMode(36, {});">JA, durchführen</a></div>')
        if f.get("mode") == "36":
            pid, act = self.offen
            self.aktiv[pid] = act == "2"
            return httpx.Response(200, text=f'<div class="alert alert-success">Eine Person wurde erfolgreich '
                                            f'{"aktiviert" if act == "2" else "deaktiviert"}.<a>VORGANG WIDERRUFEN</a></div>')
        return httpx.Response(400)


def make(monkeypatch, schreiben=True):
    monkeypatch.setenv("ESCOLA_SCHREIBEN", "1" if schreiben else "0")
    monkeypatch.setenv("ESCOLA_API_KEY", "k")
    from escola_api.app import create_app
    fake = FakeStatus()
    c = EscolaClient(EscolaConfig(base_url="https://x.test/", cookie="PHPSESSID=a"), transport=httpx.MockTransport(fake))
    return fake, TestClient(create_app(c), headers={"X-API-Key": "k"})


def test_deaktivieren_aktivieren(monkeypatch):
    fake, api = make(monkeypatch)
    r = api.post("/personen/649/deaktivieren")
    assert r.status_code == 200 and r.json()["aktiv"] is False and fake.aktiv[649] is False
    assert "erfolgreich deaktiviert" in r.json()["meldung"] and "WIDERRUFEN" not in r.json()["meldung"]
    r = api.post("/personen/649/aktivieren")
    assert r.status_code == 200 and r.json()["aktiv"] is True and fake.aktiv[649] is True
    assert fake.modes == [("17", "1"), ("36", None), ("17", "2"), ("36", None)]


def test_gesperrt_ohne_schreibrecht(monkeypatch):
    fake, api = make(monkeypatch, schreiben=False)
    assert api.post("/personen/649/deaktivieren").status_code == 403
    assert fake.modes == []
