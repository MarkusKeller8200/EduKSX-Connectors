"""Anmeldung bei Escola (Benutzername/Passwort + Zwei-Faktor) und Session-Verwaltung.

Grundsätze:
- Benutzername, Passwort und 2FA-Code werden nur an Escola weitergereicht – nie gespeichert,
  nie geloggt, nie zurückgegeben.
- Die Escola-Session (Cookie) lebt ausschliesslich im Arbeitsspeicher dieses Prozesses.
  Der Aufrufer erhält nur ein zufälliges API-Session-Token (`X-Escola-Session`).
- Nach Logout, Ablauf oder Neustart der API ist die Session weg.

Escola-Ablauf (aus dem Escola-Frontend ermittelt, 14.11.2026):
  1. POST login.php (multipart: username, password, [loginDurationInHours]) -> JSON
  2. falls 2FA: GET  escola/api/login/two-factor/login-infos   -> verfügbare Methoden
               PATCH escola/api/login/two-factor/method        {method}
               POST escola/api/login/two-factor/verification  {code}
               POST escola/api/login/two-factor/resend
     Escola-App: POST escola/api/login/two-factor/request -> Token, GET …/state?token=…
  3. Logout:     GET admin.php?action=logout&newLogout=true
  4. Keep-alive: GET escola/api/session/keep-alive (Escola-Frontend: alle 2 Minuten)
"""
from __future__ import annotations

import logging
import secrets
import threading
import time
from dataclasses import dataclass, field

import httpx

from .client import EscolaClient, EscolaConfig

API = "escola/api/"
log = logging.getLogger("escola_api.auth")


def _log(schritt: str, r: httpx.Response) -> None:
    """Protokolliert eine Escola-Antwort ohne Inhalte, die Zugangsdaten verraten könnten."""
    try:
        ct = r.headers.get("content-type", "")
        info = f"{schritt}: {r.request.method} {r.request.url.path} -> HTTP {r.status_code}, {ct.split(';')[0] or '-'}, {len(r.content)} B"
        if r.headers.get("location"):
            info += f", weiter nach {r.headers['location']}"
        info += f", Cookies: {sorted(c for c in r.cookies.keys()) or '-'}"
        if "json" in ct:
            j = _json(r)
            sicher = {k: j[k] for k in ("success", "errorMessage", "message", "msg", "twoFactorRequired",
                                         "twoFactorSetupRequired", "passwordUpdateRequired",
                                         "emailAddressUpdateRequired") if k in j}
            info += f", JSON-Felder: {sorted(j.keys())}, Werte: {sicher}"
        elif "html" in ct:
            import re
            m = re.search(r"<title>(.*?)</title>", r.text, re.S | re.I)
            info += f", Titel: {m.group(1).strip() if m else '-'}"
            if not m and len(r.content) < 300:
                info += f", Text: {r.text.strip()!r}"
        log.info(info)
    except Exception as e:  # Logging darf den Ablauf nie stören
        log.debug("Log-Fehler: %s", e)


class LoginFehler(RuntimeError):
    pass


def _json(r: httpx.Response) -> dict:
    try:
        j = r.json()
    except ValueError:
        return {}
    return j if isinstance(j, dict) else {"data": j}


def _data(j: dict):
    return j.get("data", j)


def _ist_angemeldet(c: EscolaClient) -> bool:
    r = c._http.get("admin.php?page_request=6")
    _log("Prüfe Anmeldung", r)
    if r.status_code in (301, 302, 303) and "login" in r.headers.get("location", "").lower():
        return False
    return r.status_code == 200 and "<title>Escola - Login</title>" not in r.text and "unifiedClassOrWorkgroupChooser" in r.text


def _h2fa(c: EscolaClient) -> dict:
    h = {"Accept": "application/json"}
    ref = getattr(c, "_login_referer", None)
    if ref:
        h["Referer"] = ref
    return h


def _zwei_faktor_infos(c: EscolaClient) -> dict | None:
    r = c._http.get(API + "login/two-factor/login-infos", headers=_h2fa(c))
    _log("2FA-Infos", r)
    if r.status_code != 200:
        return None
    d = _data(_json(r))
    if isinstance(d, dict):
        log.info("2FA-Infos: Felder %s, Methoden %s", sorted(d.keys()),
                 [m.get("id") if isinstance(m, dict) else m for m in (d.get("twoFactorMethods") or d.get("methods") or [])])
    return d if isinstance(d, dict) else {"raw": d}


def _methoden(infos: dict | None) -> list:
    if not infos:
        return []
    m = infos.get("twoFactorMethods") or infos.get("methods") or []
    out = []
    for x in m:
        if isinstance(x, dict):
            out.append({k: x.get(k) for k in ("method", "type", "id", "label", "name", "isDefault", "maskedPhoneNumber") if k in x})
        else:
            out.append({"method": x})
    return out


def login_schritt1(c: EscolaClient, benutzername: str, passwort: str, dauer_stunden: int | None = None) -> dict:
    log.info("Login gestartet für Benutzer '%s' an %s (Passwort: %d Zeichen)", benutzername, c._http.base_url, len(passwort))
    r0 = c._http.get("escola/login")  # frische Escola-Session (Cookie) wie beim Öffnen der Loginseite
    _log("Loginseite", r0)
    files = {"username": (None, benutzername), "password": (None, passwort)}
    if dauer_stunden:
        files["loginDurationInHours"] = (None, str(dauer_stunden))
    r = c._http.post("login.php", files=files, headers={
        "Accept": "application/json", "Referer": str(c._http.base_url) + "escola/login"})
    _log("login.php", r)
    j = _json(r)
    if r.status_code >= 400 or j.get("success") is False:
        kurz = r.text.strip() if not j and len(r.content) < 300 else ""
        raise LoginFehler(j.get("errorMessage") or f"Login fehlgeschlagen (HTTP {r.status_code}{': ' + kurz if kurz else ''})")
    # Weitere Schritte, die Escola verlangen kann
    flags = {k: bool(j.get(k)) for k in ("twoFactorRequired", "twoFactorSetupRequired",
                                         "passwordUpdateRequired") if k in j}
    ziel = j.get("redirectUrl")
    log.info("Escola leitet weiter nach: %s", ziel or "-")
    if flags.get("twoFactorSetupRequired"):
        return {"status": "2fa_einrichtung_noetig",
                "meldung": "Für dieses Konto muss zuerst in Escola (Browser) die Zwei-Faktor-Anmeldung eingerichtet werden."}
    if flags.get("passwordUpdateRequired"):
        return {"status": "passwort_aenderung_noetig",
                "meldung": "Escola verlangt eine Passwortänderung – bitte einmal im Browser anmelden und ändern."}
    if flags.get("twoFactorRequired"):
        # Wie der Browser: zuerst die 2FA-Seite öffnen (NICHT admin.php – das verwirft den 2FA-Zustand),
        # danach laufen alle 2FA-Aufrufe mit dieser Seite als Referer.
        if ziel:
            url = ziel if "://" in ziel else str(c._http.base_url) + ziel.lstrip("/")
            c._login_referer = url
            _log("2FA-Seite", c._http.get(url, headers={"Referer": str(c._http.base_url) + "escola/login"}))
        infos = _zwei_faktor_infos(c)
        return {"status": "2fa_erforderlich", "methoden": _methoden(infos)}
    if _ist_angemeldet(c):
        return {"status": "angemeldet"}
    raise LoginFehler("Login nicht abgeschlossen – unbekannte Antwort von Escola")


def zwei_faktor_methode(c: EscolaClient, methode: str) -> None:
    r = c._http.patch(API + "login/two-factor/method", json={"method": methode}, headers=_h2fa(c))
    _log("2FA", r)
    if r.status_code >= 400:
        raise LoginFehler(_json(r).get("message") or f"Methode konnte nicht gewählt werden (HTTP {r.status_code})")


def zwei_faktor_erneut(c: EscolaClient) -> dict:
    r = c._http.post(API + "login/two-factor/resend", headers=_h2fa(c))
    _log("2FA", r)
    if r.status_code >= 400:
        raise LoginFehler(_json(r).get("message") or "Code konnte nicht erneut gesendet werden")
    return {"status": "gesendet"}


def zwei_faktor_code(c: EscolaClient, code: str) -> dict:
    code = "".join(ch for ch in str(code) if ch.isdigit())
    log.info("2FA-Code wird gesendet (%d Ziffern)", len(code))
    r = c._http.post(API + "login/two-factor/verification", json={"code": code}, headers=_h2fa(c))
    _log("2FA", r)
    j = _json(r)
    d = _data(j)
    if r.status_code >= 400:
        raise LoginFehler(j.get("message") or j.get("msg") or "Code falsch oder abgelaufen")
    if isinstance(d, dict) and d.get("success") is False:
        raise LoginFehler(d.get("errorMessage") or "Code falsch oder abgelaufen")
    if _ist_angemeldet(c):
        return {"status": "angemeldet"}
    raise LoginFehler("Code angenommen, aber keine gültige Escola-Session – bitte neu anmelden")


def app_anfrage(c: EscolaClient) -> dict:
    """Bestätigung in der Escola-App anfordern; liefert ein Token für den Status-Abruf."""
    r = c._http.post(API + "login/two-factor/request", headers=_h2fa(c))
    if r.status_code >= 400:
        _log("App-Anfrage", r)
        raise LoginFehler(f"Anfrage an die Escola-App fehlgeschlagen (HTTP {r.status_code})")
    d = _data(_json(r))
    return {"status": "angefragt", "token": d.get("token") if isinstance(d, dict) else d}


def app_status(c: EscolaClient, token: str) -> dict:
    r = c._http.get(API + "login/two-factor/state", params={"token": token}, headers=_h2fa(c))
    d = _data(_json(r)) if r.status_code == 200 else {}
    if _ist_angemeldet(c):
        return {"status": "angemeldet"}
    return {"status": "ausstehend", "escola": d if isinstance(d, (dict, str)) else None}


def logout(c: EscolaClient) -> None:
    try:
        c._http.get("admin.php?action=logout&newLogout=true")
    finally:
        c._http.cookies.clear()


def keep_alive(c: EscolaClient) -> bool:
    try:
        r = c._http.get(API + "session/keep-alive")
        return r.status_code < 400
    except httpx.HTTPError:
        return False


# ------------------------------------------------------------------ Session-Speicher
@dataclass
class Sitzung:
    client: EscolaClient
    erstellt: float = field(default_factory=time.time)
    zuletzt: float = field(default_factory=time.time)
    status: str = "neu"  # neu | 2fa_erforderlich | angemeldet


class SessionSpeicher:
    """API-Sessions im Arbeitsspeicher. Token -> eigener EscolaClient (eigener Cookie-Speicher)."""

    def __init__(self, cfg: EscolaConfig, transport: httpx.BaseTransport | None = None,
                 max_leerlauf_sek: int = 8 * 3600, keepalive_sek: int = 120):
        self.cfg = cfg
        self.transport = transport
        self.max_leerlauf = max_leerlauf_sek
        self.keepalive_sek = keepalive_sek
        self._s: dict[str, Sitzung] = {}
        self._lock = threading.Lock()
        self._thread: threading.Thread | None = None

    def neu(self) -> tuple[str, Sitzung]:
        cfg = EscolaConfig(base_url=self.cfg.base_url, cookie="", schuleinheiten=self.cfg.schuleinheiten,
                           timeout=self.cfg.timeout, cache_sekunden=self.cfg.cache_sekunden)
        token = secrets.token_urlsafe(32)
        s = Sitzung(EscolaClient(cfg, transport=self.transport))
        with self._lock:
            self._s[token] = s
        return token, s

    def get(self, token: str | None) -> Sitzung | None:
        if not token:
            return None
        with self._lock:
            s = self._s.get(token)
        if s is None:
            return None
        if time.time() - s.zuletzt > self.max_leerlauf:
            self.entfernen(token)
            return None
        s.zuletzt = time.time()
        return s

    def entfernen(self, token: str) -> None:
        with self._lock:
            s = self._s.pop(token, None)
        if s:
            s.client.close()

    def anzahl(self) -> int:
        return len(self._s)

    def starte_keepalive(self) -> None:
        if self._thread or self.keepalive_sek <= 0:
            return

        def loop():
            while True:
                time.sleep(self.keepalive_sek)
                for tok, s in list(self._s.items()):
                    if time.time() - s.zuletzt > self.max_leerlauf:
                        self.entfernen(tok)
                    elif s.status == "angemeldet" and not keep_alive(s.client):
                        s.status = "abgelaufen"

        self._thread = threading.Thread(target=loop, name="escola-keepalive", daemon=True)
        self._thread.start()
