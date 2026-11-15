"""Login / 2FA / Logout gegen einen nachgebauten Escola-Login."""
import json
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient

from escola_api.app import create_app

FX = Path(__file__).parent / "fixtures"
CHOOSER = (FX / "chooser.html").read_text(encoding="utf-8")
PW = "Sup3r-Geheim!"


class FakeLogin:
    """Bildet Escolas Login nach: Passwort -> (optional) 2FA -> Session gültig."""

    def __init__(self, zwei_faktor=True):
        self.zwei_faktor = zwei_faktor
        self.sessions = {}  # PHPSESSID -> status
        self.n = 0
        self.seen_bodies = []

    def _sid(self, req):
        c = req.headers.get("cookie", "")
        for part in c.split(";"):
            k, _, v = part.strip().partition("=")
            if k == "PHPSESSID":
                return v
        return None

    def __call__(self, req: httpx.Request) -> httpx.Response:
        url = req.url.path
        sid = self._sid(req)
        body = req.content.decode(errors="replace") if req.content else ""
        self.seen_bodies.append(body)
        if url == "/escola/login":
            self.n += 1
            sid = f"s{self.n}"
            self.sessions[sid] = "anonym"
            return httpx.Response(200, text="<title>Escola - Login</title>", headers={"set-cookie": f"PHPSESSID={sid}; path=/; HttpOnly"})
        if url == "/login.php":
            assert req.headers["content-type"].startswith("multipart/form-data")
            if 'name="username"\r\n\r\nmax' not in body or f'name="password"\r\n\r\n{PW}' not in body:
                return httpx.Response(200, json={"success": False, "errorMessage": "Benutzername oder Passwort falsch"})
            self.sessions[sid] = "2fa" if self.zwei_faktor else "ok"
            return httpx.Response(200, json={"success": True, "redirectUrl": "/admin.php", "twoFactorRequired": self.zwei_faktor})
        if url == "/admin.php":
            if "action=logout" in str(req.url):
                self.sessions[sid] = "aus"
                return httpx.Response(302, headers={"location": "/escola/login"})
            if self.sessions.get(sid) == "ok":
                return httpx.Response(200, text="<html><body>" + CHOOSER + "</body></html>")
            return httpx.Response(302, headers={"location": "/escola/login"})
        if url == "/escola/api/login/two-factor/login-infos":
            return httpx.Response(200, json={"data": {"twoFactorMethods": [{"method": "totp", "label": "Authentifizierungsapp"}, {"method": "sms", "label": "SMS"}]}})
        if url == "/escola/api/login/two-factor/method":
            return httpx.Response(200, json={})
        if url == "/escola/api/login/two-factor/resend":
            return httpx.Response(200, json={"data": True})
        if url == "/escola/api/login/two-factor/verification":
            if self.sessions.get(sid) == "2fa" and json.loads(body)["code"] == "123456":
                self.sessions[sid] = "ok"
                return httpx.Response(200, json={"data": {"success": True}})
            return httpx.Response(422, json={"message": "Der Code ist falsch."})
        if url == "/escola/api/session/keep-alive":
            return httpx.Response(200 if self.sessions.get(sid) == "ok" else 401)
        return httpx.Response(404)


@pytest.fixture
def setup(monkeypatch):
    monkeypatch.delenv("ESCOLA_COOKIE", raising=False)
    monkeypatch.delenv("ESCOLA_API_KEY", raising=False)
    monkeypatch.setenv("ESCOLA_BASE_URL", "https://x.test/")
    fake = FakeLogin()
    return fake, TestClient(create_app(transport=httpx.MockTransport(fake)))


def test_login_mit_2fa_und_logout(setup):
    fake, api = setup
    assert api.get("/klassen").status_code == 401  # ohne Anmeldung
    r = api.post("/auth/login", json={"benutzername": "max", "passwort": PW}).json()
    assert r["status"] == "2fa_erforderlich" and [m["method"] for m in r["methoden"]] == ["totp", "sms"]
    tok = r["session"]
    h = {"X-Escola-Session": tok}
    assert api.get("/klassen", headers=h).status_code == 401  # 2FA noch offen
    assert api.post("/auth/2fa/methode", headers=h, json={"methode": "sms"}).json()["methode"] == "sms"
    assert api.post("/auth/2fa/erneut", headers=h).json()["status"] == "gesendet"
    bad = api.post("/auth/2fa", headers=h, json={"code": "000000"})
    assert bad.status_code == 401 and "falsch" in bad.json()["meldung"]
    ok = api.post("/auth/2fa", headers=h, json={"code": "123456"}).json()
    assert ok["status"] == "angemeldet"
    assert len(api.get("/klassen", headers=h).json()) == 8  # Daten mit der Session
    assert api.get("/auth/status", headers=h).json()["status"] == "angemeldet"
    assert api.post("/auth/logout", headers=h).json()["status"] == "abgemeldet"
    assert api.get("/klassen", headers=h).status_code == 401
    assert "aus" in fake.sessions.values()


def test_passwort_wird_nicht_gespeichert(setup):
    fake, api = setup
    r = api.post("/auth/login", json={"benutzername": "max", "passwort": PW}).json()
    s = api.app.state.sessions.get(r["session"])
    blob = repr(vars(s)) + repr(vars(s.client)) + repr(vars(s.client.cfg)) + json.dumps(r)
    assert PW not in blob and "max" not in json.dumps(r)


def test_falsches_passwort(setup):
    fake, api = setup
    r = api.post("/auth/login", json={"benutzername": "max", "passwort": "falsch"})
    assert r.status_code == 401 and r.json()["meldung"] == "Benutzername oder Passwort falsch"
    assert api.app.state.sessions.anzahl() == 0


def test_login_ohne_2fa(monkeypatch):
    monkeypatch.delenv("ESCOLA_COOKIE", raising=False)
    monkeypatch.setenv("ESCOLA_BASE_URL", "https://x.test/")
    api = TestClient(create_app(transport=httpx.MockTransport(FakeLogin(zwei_faktor=False))))
    r = api.post("/auth/login", json={"benutzername": "max", "passwort": PW}).json()
    assert r["status"] == "angemeldet"
    assert len(api.get("/klassen", headers={"X-Escola-Session": r["session"]}).json()) == 8


def test_zwei_sessions_getrennt(setup):
    fake, api = setup
    a = api.post("/auth/login", json={"benutzername": "max", "passwort": PW}).json()["session"]
    b = api.post("/auth/login", json={"benutzername": "max", "passwort": PW}).json()["session"]
    api.post("/auth/2fa", headers={"X-Escola-Session": a}, json={"code": "123456"})
    assert api.get("/klassen", headers={"X-Escola-Session": a}).status_code == 200
    assert api.get("/klassen", headers={"X-Escola-Session": b}).status_code == 401
    assert api.get("/klassen", headers={"X-Escola-Session": "erfunden"}).status_code == 401


def test_loginseite(setup):
    _, api = setup
    r = api.get("/login")
    assert r.status_code == 200 and 'autocomplete="one-time-code"' in r.text and "/auth/2fa" in r.text
