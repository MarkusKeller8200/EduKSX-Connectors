"""2FA-Ablauf wie im Browser: nach login.php direkt redirectUrl öffnen, nicht admin.php."""
import httpx

from escola_api import auth as A
from escola_api.client import EscolaClient, EscolaConfig


def test_2fa_ablauf_ohne_admin_vor_code():
    aufrufe = []
    angemeldet = {"ok": False}

    def handler(req: httpx.Request):
        p = req.url.path
        aufrufe.append((req.method, p, req.headers.get("referer", "")))
        if p == "/escola/login":
            return httpx.Response(200, text="<title>Escola - Login</title>")
        if p == "/login.php":
            assert "escola/login" in req.headers["referer"]
            return httpx.Response(200, json={"success": True, "twoFactorRequired": True,
                                             "twoFactorSetupRequired": False, "passwordUpdateRequired": False,
                                             "redirectUrl": "admin.php?page_request=5&fromLogin=1"})
        if p.endswith("/login-infos"):
            assert req.headers["referer"].endswith("escola/login")
            return httpx.Response(200, json={"data": {"twoFactorMethods": [{"id": "totp", "label": "App"}]}})
        if p.endswith("/verification"):
            assert req.headers["referer"].endswith("escola/login")
            assert b'"123456"' in req.content
            angemeldet["ok"] = True
            return httpx.Response(200, json={"data": {"success": True}})
        if p == "/admin.php":
            assert angemeldet["ok"], "admin.php vor dem 2FA-Code aufgerufen – beendet die halbe Anmeldung"
            return httpx.Response(200, text="<div class='unifiedClassOrWorkgroupChooser'></div>")
        return httpx.Response(404)

    c = EscolaClient(EscolaConfig(cookie=""), transport=httpx.MockTransport(handler))
    r = A.login_schritt1(c, "u", "p")
    assert r["status"] == "2fa_erforderlich" and r["methoden"][0]["id"] == "totp"
    assert A.zwei_faktor_code(c, " 123 456 ")["status"] == "angemeldet"


def test_2fa_falscher_code_meldung():
    def handler(req):
        if req.url.path.endswith("/verification"):
            return httpx.Response(200, json={"data": {"success": False, "errorMessage": "Code falsch"}})
        return httpx.Response(404)
    c = EscolaClient(EscolaConfig(cookie=""), transport=httpx.MockTransport(handler))
    try:
        A.zwei_faktor_code(c, "000000")
    except A.LoginFehler as e:
        assert "Code falsch" in str(e)
    else:
        raise AssertionError("LoginFehler erwartet")
