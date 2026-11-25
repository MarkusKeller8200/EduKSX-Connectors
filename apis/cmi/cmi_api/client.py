"""Client für die REST-API von CMI (CM Informatik AG) – CMI Schule / CMI Cloud.

Grundlage: öffentliche Beschreibung der CMI-API im zertifizierten Power-Platform-Connector von CM Informatik
(`microsoft/PowerPlatformConnectors`, Ordner `certified-connectors/CM Informatik AG`, Swagger 2.0):

- Host `aadbridge.prod.cmicloud.ch`, Pfade unter `/api/proxy/…`, Anmeldung über Entra ID (OAuth 2.0),
  Ressource `api://cmi-proxy-aadbridge-prod-e780cbb4-ae62-8dc7-69cf-46374cd56a34`
- Mandant im Header `X-CMI-TENANT-NAME`
- Entitäten `Kontakt`, `Adresse`, `Person`, `Geschaeft` (Dossier), `Ordner`, `Dokument`:
  `GET /<E>/{guid}`, `POST /<E>` (Antwort: GUID, optional `?Vorlage=`), `PUT /<E>/{guid}`, `POST /<E>/Search`
  (Body: TentaQl-Abfrage als Text), `GET /Dokument/FileContent/{guid}`, `POST /Dokument/CheckOut|CheckIn/{guid}`

Was dort nicht beschrieben ist (Proxy-Gruppe einer eigenen Anwendung, App-only-Anmeldung, TentaQl-Syntax,
Klassenzuteilung in CMI Schule, Dateiformat beim Anlegen), ist konfigurierbar und in der README «ZU PRÜFEN».

Löschen wird nicht angeboten: der Client verweigert DELETE.
"""
from __future__ import annotations

import base64
import json
import re
import time
from dataclasses import dataclass, field
from typing import Any

import httpx

ENTRA_RESSOURCE = "api://cmi-proxy-aadbridge-prod-e780cbb4-ae62-8dc7-69cf-46374cd56a34"

# Entitäten, die gelesen bzw. gesucht werden dürfen (Schutz für /suche/{entitaet})
LESBAR = ("Kontakt", "Adresse", "Person", "Geschaeft", "AbstraktesGeschaeft", "Ordner", "Dokument",
          "Aktivitaet", "AbstrakteAktivitaet")


class SessionAbgelaufen(RuntimeError):
    """CMI bzw. Entra lehnt die Anmeldung ab (401/403)."""


class NichtGefunden(RuntimeError):
    """CMI meldet 404."""


class CMIFehler(RuntimeError):
    """CMI lehnt eine Anfrage ab (400/409/5xx) – Text aus `userMessage`/`detail`, falls vorhanden."""

    def __init__(self, status: int, text: str):
        super().__init__(text)
        self.status = status


@dataclass
class CMIConfig:
    # ZU PRÜFEN: Der Connector nutzt /api/proxy/groups/cmi-powerplattform-customconnector; für eine eigene
    # Anwendung nennt CM Informatik den Pfad (Proxy-Gruppe).
    base_url: str = "https://aadbridge.prod.cmicloud.ch/api/proxy"
    mandant: str = ""                  # X-CMI-TENANT-NAME
    token: str = ""                    # fertiges Zugriffstoken (nur für Tests/Übergang)
    entra_tenant_id: str = ""          # Entra-Mandant der Schule
    client_id: str = ""                # App-Registrierung (ZU PRÜFEN: App-only bei CMI freigeschaltet?)
    client_secret: str = ""
    scope: str = ENTRA_RESSOURCE + "/.default"
    login_url: str = "https://login.microsoftonline.com"
    timeout: float = 60.0
    # TentaQl: Vorlage für «Feld ist gleich Wert» und Verknüpfung (ZU PRÜFEN)
    tentaql_gleich: str = '{feld} = "{wert}"'
    tentaql_und: str = " AND "
    # Suchtext als JSON-String senden (Swagger: Body vom Typ string, application/json) – ZU PRÜFEN
    suche_als_json: bool = True


@dataclass
class Zaehler:
    lesen: int = 0
    schreiben: int = 0
    pfade: list[str] = field(default_factory=list)


class CMIClient:
    def __init__(self, cfg: CMIConfig, transport: httpx.BaseTransport | None = None):
        self.cfg = cfg
        self.zaehler = Zaehler()
        self._token: str = cfg.token
        self._token_bis: float = float("inf") if cfg.token else 0.0
        headers = {"Accept": "application/json", "User-Agent": "cmi-api/0.1"}
        if cfg.mandant:
            headers["X-CMI-TENANT-NAME"] = cfg.mandant
        self._http = httpx.Client(base_url=cfg.base_url.rstrip("/") + "/", headers=headers, timeout=cfg.timeout,
                                  transport=transport, event_hooks={"request": [self._pruefen]})
        self._login = httpx.Client(timeout=cfg.timeout, transport=transport)

    # ------------------------------------------------------------ Grundlagen

    @property
    def konfiguriert(self) -> bool:
        anmeldung = bool(self.cfg.token or (self.cfg.entra_tenant_id and self.cfg.client_id and self.cfg.client_secret))
        return bool(self.cfg.base_url and self.cfg.mandant and anmeldung)

    def _pruefen(self, req: httpx.Request) -> None:
        if req.method == "DELETE":
            raise RuntimeError("Der CMI-Client löscht nie (DELETE gesperrt)")
        if req.method == "GET" or req.url.path.endswith("/Search"):
            self.zaehler.lesen += 1
        else:
            self.zaehler.schreiben += 1
            self.zaehler.pfade.append(f"{req.method} {req.url.path}")

    def _zugriffstoken(self) -> str:
        if self._token and time.time() < self._token_bis:
            return self._token
        if not (self.cfg.entra_tenant_id and self.cfg.client_id and self.cfg.client_secret):
            raise SessionAbgelaufen("Keine Anmeldung für CMI eingerichtet (Token oder Entra-App fehlt)")
        r = self._login.post(f"{self.cfg.login_url}/{self.cfg.entra_tenant_id}/oauth2/v2.0/token", data={
            "grant_type": "client_credentials", "client_id": self.cfg.client_id,
            "client_secret": self.cfg.client_secret, "scope": self.cfg.scope})
        if r.status_code != 200:
            raise SessionAbgelaufen(f"Entra-Anmeldung für CMI fehlgeschlagen ({r.status_code})")
        d = r.json()
        self._token = d["access_token"]
        self._token_bis = time.time() + int(d.get("expires_in", 3600)) - 60
        return self._token

    def _senden(self, methode: str, pfad: str, **kw) -> httpx.Response:
        kw.setdefault("headers", {})["Authorization"] = f"Bearer {self._zugriffstoken()}"
        r = self._http.request(methode, pfad.lstrip("/"), **kw)
        if r.status_code in (401, 403):
            self._token_bis = 0.0  # neues Token beim nächsten Mal
            raise SessionAbgelaufen(f"CMI lehnt den Zugang ab ({r.status_code})")
        if r.status_code == 404:
            raise NichtGefunden(pfad)
        if r.status_code >= 400:
            raise CMIFehler(r.status_code, _fehlertext(r))
        return r

    # ------------------------------------------------------------ Lesen

    def mandanten(self) -> list[dict]:
        return self._senden("GET", "cmiTenants").json()

    def lesen(self, entitaet: str, guid: str) -> dict:
        return self._senden("GET", f"{entitaet}/{guid}").json()

    def suchen(self, entitaet: str, tentaql: str) -> list[dict]:
        if self.cfg.suche_als_json:
            r = self._senden("POST", f"{entitaet}/Search", content=json.dumps(tentaql),
                             headers={"Content-Type": "application/json"})
        else:
            r = self._senden("POST", f"{entitaet}/Search", content=tentaql.encode("utf-8"),
                             headers={"Content-Type": "text/plain"})
        d = r.json() if r.content else []
        if isinstance(d, dict):  # falls CMI eine Hülle liefert
            d = d.get("items") or d.get("value") or d.get("data") or []
        return d

    def gleich(self, **bedingungen: Any) -> str:
        """TentaQl-Abfrage «feld = wert [AND …]» nach Vorlage aus der Konfiguration."""
        teile = []
        for feld, wert in bedingungen.items():
            if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_.]*", feld):
                raise ValueError(f"ungültiger Feldname {feld!r}")
            w = str(wert).replace("\\", "\\\\").replace('"', '\\"')
            teile.append(self.cfg.tentaql_gleich.format(feld=feld, wert=w))
        return self.cfg.tentaql_und.join(teile)

    def datei(self, guid: str, version: int | None = None) -> tuple[bytes, str]:
        r = self._senden("GET", f"Dokument/FileContent/{guid}", params={"Version": version} if version else None)
        return r.content, r.headers.get("content-type", "application/octet-stream")

    # ------------------------------------------------------------ Schreiben

    def anlegen(self, entitaet: str, daten: dict, vorlage: str | None = None) -> str:
        r = self._senden("POST", entitaet, json=daten, params={"Vorlage": vorlage} if vorlage else None)
        return _guid_aus(r)

    def aendern(self, entitaet: str, guid: str, daten: dict) -> None:
        self._senden("PUT", f"{entitaet}/{guid}", json={**daten, "guid": guid})

    def auschecken(self, guid: str) -> None:
        self._senden("POST", f"Dokument/CheckOut/{guid}")

    def einchecken(self, guid: str, dateiname: str, inhalt: bytes, kommentar: str = "") -> None:
        self._senden("POST", f"Dokument/CheckIn/{guid}", files={"file": (dateiname, inhalt)},
                     data={"checkInComment": kommentar} if kommentar else None)


# ---------------------------------------------------------------- Hilfen

def ref(guid: str | None) -> dict | None:
    """Verweis auf ein CMI-Objekt (Swagger: {guid, displayName, url})."""
    return {"guid": guid} if guid else None


def guid_von(verweis: Any) -> str | None:
    if isinstance(verweis, dict):
        return verweis.get("guid")
    return verweis or None


def rendition(dateiname: str, inhalt: bytes) -> dict:
    """Datei für `eDokument.renditions[]` (Swagger: `file` vom Typ string – Base64 angenommen, ZU PRÜFEN)."""
    return {"fileName": dateiname, "file": base64.b64encode(inhalt).decode("ascii")}


def _guid_aus(r: httpx.Response) -> str:
    if not r.content:
        raise CMIFehler(r.status_code, "CMI hat keine GUID zurückgegeben")
    try:
        d = r.json()
    except ValueError:
        d = r.text
    if isinstance(d, dict):
        d = d.get("guid") or d.get("uuid") or d.get("id")
    return str(d).strip().strip('"')


def _fehlertext(r: httpx.Response) -> str:
    try:
        d = r.json()
    except ValueError:
        return f"CMI meldet {r.status_code}: {r.text[:300]}"
    if isinstance(d, dict):
        return str(d.get("userMessage") or d.get("detail") or d.get("title") or d.get("developerMessage") or d)
    return str(d)
