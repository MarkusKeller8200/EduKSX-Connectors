"""Lesender Client für die SL-Planer-API (Seabird AG).

Grundlage: «SL-Planer API-Dokumentation», Seabird AG, 18.2.2026, Abschnitte 5.1.3–5.6 (Seiten 9–18).
Die Abschnitte davor (Basis-URL, Anmeldung, Personen 5.1.1, Paginierung, Schuljahr) lagen nicht vor –
alles, was daraus stammen müsste, ist konfigurierbar und in der README als «ZU PRÜFEN» markiert.

Der SL-Planer stellt nur GET-Endpunkte bereit. Diese API liest deshalb ausschliesslich.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from urllib.parse import urlsplit

import httpx

# Bereiche der Pensenplanung (Doku 5.1.5): Schlüssel = `typ` im Pensum (5.1.6.2), Wert = Endpunkt im SL-Planer.
# Belegt sind nur /klassenlektionen und /betreuung; die übrigen «folgen dem Muster» – Namen ZU PRÜFEN.
BEREICHE: dict[str, str] = {
    "klassenlektionen": "klassenlektionen",
    "weitere_wl": "weitere_wl",
    "sonderpaedagogik": "sonderpaedagogik",
    "klassenassistenz": "klassenassistenz",
    "betreuung": "betreuung",
    "weitere_anstellungen": "weitere_anstellungen",
    "aufgaben_klp": "aufgaben_klp",
    "aemter": "aemter",
    "weiterer_berufsauftrag": "weiterer_berufsauftrag",
}


class SessionAbgelaufen(RuntimeError):
    """SL-Planer lehnt den Zugang ab (401/403) – Token prüfen."""


class NichtGefunden(RuntimeError):
    """SL-Planer meldet 404."""


@dataclass
class SLPlanerConfig:
    base_url: str = ""          # ZU PRÜFEN: Basis-URL laut Seabird (Abschnitt 1–4 der Doku)
    token: str = ""             # API-Token von Seabird, nur aus .env
    auth_schema: str = "Bearer"  # Header «Authorization: <schema> <token>»; ZU PRÜFEN
    timeout: float = 30.0
    max_seiten: int = 200       # Schutz gegen endlose Paginierung


class SLPlanerClient:
    def __init__(self, cfg: SLPlanerConfig, transport: httpx.BaseTransport | None = None):
        self.cfg = cfg
        headers = {"Accept": "application/json", "User-Agent": "slplaner-api/0.1"}
        if cfg.token:
            headers["Authorization"] = f"{cfg.auth_schema} {cfg.token}".strip()
        self.zaehler = 0
        self._http = httpx.Client(base_url=cfg.base_url, headers=headers, timeout=cfg.timeout,
                                  transport=transport, event_hooks={"request": [self._zaehlen]})

    def _zaehlen(self, req: httpx.Request) -> None:
        if req.method != "GET":  # Schutz: dieser Client darf nur lesen
            raise RuntimeError(f"SL-Planer-Client liest nur, nicht {req.method}")
        self.zaehler += 1

    @property
    def konfiguriert(self) -> bool:
        return bool(self.cfg.base_url and self.cfg.token)

    def _get(self, pfad: str, params: dict | None = None) -> Any:
        params = {k: v for k, v in (params or {}).items() if v not in (None, "")}
        # Leere params nicht mitgeben: httpx würde sonst die Abfrage eines «next»-Links verwerfen
        r = self._http.get(pfad, params=params or None)
        if r.status_code in (401, 403):
            raise SessionAbgelaufen(f"SL-Planer lehnt den Zugang ab ({r.status_code})")
        if r.status_code == 404:
            raise NichtGefunden(pfad)
        r.raise_for_status()
        return r.json()

    def liste(self, pfad: str, params: dict | None = None) -> list[dict]:
        """Liest alle Seiten einer Liste.

        Doku 5.3.2: «paginierte Liste, jedes Element im data-Array». Wie die nächste Seite angegeben wird,
        ist nicht beschrieben (ZU PRÜFEN). Unterstützt: reine Liste, {data, next}, {data, links: {next}},
        {data, meta: {current_page, last_page}}.
        """
        params = dict(params or {})
        daten: list[dict] = []
        naechste: str | None = pfad
        for _ in range(self.cfg.max_seiten):
            if naechste is None:
                break
            antwort = self._get(naechste, params)
            if isinstance(antwort, list):
                return daten + antwort
            daten += antwort.get("data") or []
            naechste = None
            nxt = antwort.get("next") or (antwort.get("links") or {}).get("next")
            meta = antwort.get("meta") or {}
            if nxt:
                # Link der nächsten Seite enthält die Parameter schon; nur Links auf denselben Server folgen
                if urlsplit(nxt).netloc and urlsplit(nxt).netloc != urlsplit(self.cfg.base_url).netloc:
                    raise RuntimeError(f"SL-Planer verweist auf fremden Server: {nxt}")
                naechste, params = nxt, {}
            elif meta.get("current_page") and meta.get("last_page") and meta["current_page"] < meta["last_page"]:
                params = {**params, "page": meta["current_page"] + 1}
                naechste = pfad
        return daten

    def einzeln(self, pfad: str, params: dict | None = None) -> dict:
        antwort = self._get(pfad, params)
        if isinstance(antwort, dict) and set(antwort) == {"data"}:
            return antwort["data"]
        return antwort
