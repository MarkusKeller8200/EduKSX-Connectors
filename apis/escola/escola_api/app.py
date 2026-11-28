"""REST-API für Escola (sekbuelach.ch): Anmeldung mit 2FA, Stundenplan, Stammdaten, Personen.

Start:  uvicorn escola_api.app:app --port 8080
Doku:   http://localhost:8080/docs
"""
from __future__ import annotations

import json
import csv
import io
import os
from typing import Any, Literal

from pydantic import BaseModel, Field

from fastapi import Depends, FastAPI, Header, HTTPException, Query
from fastapi.responses import JSONResponse, Response

from pathlib import Path

import httpx
from fastapi import Request
from fastapi.responses import HTMLResponse

from . import auth as A
from .client import EscolaClient, EscolaConfig, KonfliktFehler, SessionAbgelaufen

Format = Literal["json", "csv"]



API_VERSION = json.loads((Path(__file__).resolve().parent.parent / "api.json").read_text(encoding="utf-8"))["version"]

class LoginDaten(BaseModel):
    benutzername: str
    passwort: str
    dauer_stunden: int | None = Field(None, description="optional: gewünschte Login-Dauer in Stunden")


class ImportPerson(BaseModel):
    nachname: str
    vorname: str
    geschlecht: str = Field(..., description="w, m oder d")
    art: Literal["schueler", "eltern"] = "schueler"
    schulhaus: str | None = None


class ImportListe(BaseModel):
    personen: list[ImportPerson] = Field(..., max_length=1000)


class SollEintrag(BaseModel):
    tag: str = Field(..., description="A–E (A = Montag)")
    lektion_id: int
    fach_id: int
    raum_ids: list[int] | None = None
    lehrperson_ids: list[int] | None = None


class StundenplanAbgleich(BaseModel):
    eintraege: list[SollEintrag] = Field(..., max_length=500)
    loeschen: bool = Field(False, description="überzählige Einträge löschen (sonst nur melden)")


class Code(BaseModel):
    code: str


class Methode(BaseModel):
    methode: str = Field(..., description="z. B. totp (Authentifizierungs-App), sms, escola-app")


class NeuePerson(BaseModel):
    nachname: str
    vorname: str
    geschlecht: Literal["w", "m", "d"]
    schulhaus: str = Field(..., description="Hinterbirch oder Mettmenriet")
    klasse_id: int | None = Field(None, description="nur bei Schüler:innen; leer = ohne Klasse")
    rolle: str | None = Field(None, description="nur /personen: Escola-Rolle, z. B. lehrperson, gruppe_4 (Schulverwaltung) – siehe /personen/rollen")
    kategorie: str | None = Field(None, description="veraltet, gleichbedeutend mit rolle")
    zukuenftig: bool = Field(False, description="nur /schueler ohne Klasse: als zukünftige:r Schüler:in")
    trotz_duplikat: bool = Field(False, description="auch anlegen, wenn Escola mögliche Duplikate meldet")
    felder: dict[str, Any] | None = Field(None, description="optional: weitere Felder direkt setzen (wie PATCH)")


class Transfer(BaseModel):
    klasse_id: int
    stichtag: str | None = Field(None, description="nur aktuelles Schuljahr: JJJJ-MM-TT, Standard: heute")
    schuljahr: Literal[0, 1] = Field(0, description="0 = aktuelles, 1 = kommendes Schuljahr")


class Klassenbeginn(BaseModel):
    ab: str = Field("schuljahresbeginn", description="schuljahresbeginn (1.8.), eintritt (später von 1.8. und "
                                                       "Eintrittsdatum) oder JJJJ-MM-TT")
    schuljahr: int | None = Field(None, description="Startjahr des Schuljahrs, z. B. 2026 = 2026/27; Standard: aktuelles")
    edit_id: str | None = Field(None, description="nur nötig, wenn das Schuljahr mehrere Klasseneinträge hat")


class KlassenbeginnKlasse(BaseModel):
    ab: str = Field("eintritt", description="schuljahresbeginn, eintritt oder JJJJ-MM-TT")


class RollenAenderung(BaseModel):
    hinzufuegen: list[int] = Field(default_factory=list, description="Rollen-IDs, die die Person zusätzlich bekommt")
    entfernen: list[int] = Field(default_factory=list, description="Rollen-IDs, die der Person entzogen werden")


class Austritt(BaseModel):
    datum: str = Field(..., description="Austrittsdatum TT.MM.JJJJ oder JJJJ-MM-TT")
    wegzugsdatum: str | None = Field(None, description="optional, TT.MM.JJJJ oder JJJJ-MM-TT")
    wegzugsgemeinde: str | None = None
    sofort_deaktivieren: bool = Field(False, description="zusätzlich sofort deaktivieren (sonst macht es Escola selbst)")


class ArbeitsgruppeZuteilung(BaseModel):
    arbeitsgruppe_id: int
    schuljahr: Literal[0, 1] = 0


class Rechte(BaseModel):
    klr: bool | None = Field(None, description="Klassenlehrperson (setzt SpM, Abs, Gesundheit automatisch)")
    fp: bool | None = Field(None, description="Förderplanung lesen/schreiben")
    spm: bool | None = Field(None, description="Sonderpädagogische Massnahmen")
    abs: bool | None = Field(None, description="Klassenlehrpersonen-Rechte in den Absenzen – nur für KLR")


class AhvDaten(BaseModel):
    ahv: str = Field(..., description="756.xxxx.xxxx.xx (Punkte optional)")
    ueberschreiben: bool = Field(False, description="eine vorhandene andere AHV-Nummer ersetzen")


class PersonAustritt(BaseModel):
    datum: str = Field(..., description="Austrittsdatum TT.MM.JJJJ oder JJJJ-MM-TT ('' = Austritt zurücknehmen)")
    wegzugsdatum: str | None = None
    wegzugsgemeinde: str | None = None
    sofort_deaktivieren: bool = False
    rollen_ausgetreten: bool = Field(False, description="Rollen sofort durch „Ausgetreten“ ersetzen (sonst am Stichtag "
                                                       "mit POST /personen/{id}/rollen/ausgetreten)")


class NeueMitarbeitende(BaseModel):
    nachname: str
    vorname: str
    geschlecht: Literal["w", "m", "d"]
    schulhaus: str
    rolle: str = Field(..., description="Rolle beim Anlegen, z. B. lehrperson oder gruppe_14 (_neu)")
    rollen_ids: list[int] = Field([], description="zusätzliche Rollen-IDs, z. B. 13 = Lehrpersonen (Hinterbirch)")
    ahv: str | None = None
    felder: dict[str, Any] = {}
    schulmail: bool = Field(True, description="vorname.nachname@sekbuelach.ch setzen")
    trotz_duplikat: bool = False


class NeueBezugsperson(BaseModel):
    person_id: int | None = Field(None, description="bestehende Person verknüpfen (z. B. Elternteil von Geschwistern)")
    nachname: str | None = None
    vorname: str | None = None
    geschlecht: Literal["w", "m", "d"] | None = None
    funktion: str | int | None = Field(None, description="Mutter, Vater, Vormund … oder ID (Standard nach Geschlecht)")
    sorgerecht: Literal["sorgeberechtigt", "informationsberechtigt", "keine"] = "sorgeberechtigt"
    abholberechtigt: bool = True
    felder: dict[str, Any] = Field({}, description="weitere Felder der neuen Bezugsperson (wie PATCH /personen/{id})")
    trotz_duplikat: bool = False


class Sorgerecht(BaseModel):
    sorgerecht: Literal["sorgeberechtigt", "informationsberechtigt", "keine"]


class StundenplanEintrag(BaseModel):
    fach_id: int | None = Field(None, description="Fach (muss der Klasse zugeteilt sein); beim Anlegen Pflicht")
    raum_ids: list[int] | None = Field(None, description="Soll für Raum 1–3 ([] = keine Räume)")
    lehrperson_ids: list[int] | None = Field(None, description="Soll der Lehrpersonen (nur bei mehreren mit dem Fach schaltbar)")


class Ersetzen(BaseModel):
    neu_id: int
    klassen_ids: list[int] | None = Field(None, description="nur diese Klassen (Standard: alle der bisherigen Lehrperson)")
    klassenlehrperson: bool = Field(True, description="auch Klassenlehrperson-Plätze übernehmen")


class KlassenlehrpersonenAenderung(BaseModel):
    aktuell: list[int] | None = Field(None, description="Soll für Slot A, B, C im aktuellen Schuljahr ([] = keine)")
    kommend: list[int] | None = Field(None, description="Soll für Slot A, B, C im kommenden Schuljahr ([] = keine)")


class FaecherAenderung(BaseModel):
    klasse_id: int | None = None
    arbeitsgruppe_id: int | None = Field(None, description="statt klasse_id: Arbeitsgruppe (Fachklasse)")
    schuljahr: Literal[0, 1] = Field(0, description="0 = aktuelles, 1 = kommendes Schuljahr (nur Fächer)")
    vorlage: Literal["klassenlehrperson", "fachlehrperson", "sopae"] | None = None
    faecher: list[int] | None = Field(None, description="Soll-Liste der Fach-IDs (ersetzt die Zuteilung in der Klasse)")
    faecher_hinzu: list[int] = []
    faecher_weg: list[int] = []
    rechte: Rechte | None = None


class Aenderung(BaseModel):
    felder: dict[str, Any] = Field(..., description="Interner Feldname -> neuer Wert, z. B. "
                                   '{"natel": "079 000 00 01", "geburtstag": "01.01.2013", "nationality_id": "Schweiz"}')


def _config_from_env() -> EscolaConfig:
    units = {}
    for part in os.getenv("ESCOLA_SCHULEINHEITEN", "1:Hinterbirch,2:Mettmenriet").split(","):
        if ":" in part:
            k, v = part.split(":", 1)
            units[int(k)] = v.strip()
    return EscolaConfig(
        base_url=os.getenv("ESCOLA_BASE_URL", "https://www.sekbuelach.ch/"),
        cookie=os.getenv("ESCOLA_COOKIE", ""),
        schuleinheiten=units,
        cache_sekunden=int(os.getenv("ESCOLA_CACHE_SEKUNDEN", "600")),
    )


def create_app(client: EscolaClient | None = None, transport: httpx.BaseTransport | None = None) -> FastAPI:
    app = FastAPI(
        title="Escola-API",
        version=API_VERSION,
        description="Liest Klassen, Fächer, Lehrpersonen, Räume, Tage, Lektionen und alle "
                    "Stundenplan-Einträge aus Escola (sekbuelach.ch). Alle Endpunkte liefern JSON "
                    "oder mit `?format=csv` eine CSV-Tabelle (Semikolon, UTF-8 mit BOM für Excel).",
    )
    state = {"client": client}
    api_key = os.getenv("ESCOLA_API_KEY", "")
    sessions = A.SessionSpeicher(_config_from_env(), transport=transport,
                                 max_leerlauf_sek=int(os.getenv("ESCOLA_SESSION_LEERLAUF_SEK", str(8 * 3600))),
                                 keepalive_sek=0 if transport else int(os.getenv("ESCOLA_KEEPALIVE_SEK", "120")))
    sessions.starte_keepalive()
    app.state.sessions = sessions

    def get_client(x_escola_session: str = Header(default="")) -> EscolaClient:
        """Escola-Zugang: per Login-Session (Header X-Escola-Session) oder – als Fallback –
        über ein fest konfiguriertes ESCOLA_COOKIE."""
        if x_escola_session:
            s = sessions.get(x_escola_session)
            if s is None:
                raise HTTPException(401, "Session unbekannt oder abgelaufen – neu anmelden (/auth/login)")
            if s.status != "angemeldet":
                raise HTTPException(401, f"Session nicht angemeldet (Status: {s.status})")
            return s.client
        if state["client"] is None:
            cfg = _config_from_env()
            if not cfg.cookie:
                raise HTTPException(401, "Nicht angemeldet: zuerst POST /auth/login (oder ESCOLA_COOKIE setzen)")
            state["client"] = EscolaClient(cfg)
        return state["client"]

    def auth(x_api_key: str = Header(default="")):
        if api_key and x_api_key != api_key:
            A.log.warning("API-Key abgelehnt: %s", "kein X-API-Key mitgeschickt" if not x_api_key
                          else f"falscher Key ({len(x_api_key)} statt {len(api_key)} Zeichen)")
            raise HTTPException(401, "X-API-Key fehlt oder ist falsch")

    @app.exception_handler(SessionAbgelaufen)
    async def _expired(_, exc):
        return JSONResponse(status_code=503, content={"fehler": "escola_session_abgelaufen", "detail": str(exc),
                                                      "loesung": "Neu anmelden (POST /auth/login) bzw. ESCOLA_COOKIE erneuern"})

    def out(rows: list[dict], fmt: Format, name: str):
        if fmt == "json":
            return rows
        buf = io.StringIO()
        if rows:
            w = csv.DictWriter(buf, fieldnames=list(rows[0].keys()), delimiter=";", extrasaction="ignore")
            w.writeheader()
            for r in rows:
                w.writerow({k: (", ".join("" if x is None else str(x) for x in v) if isinstance(v, list) else v) for k, v in r.items()})
        return Response("﻿" + buf.getvalue(), media_type="text/csv; charset=utf-8",
                        headers={"Content-Disposition": f'attachment; filename="escola_{name}.csv"'})

    deps = [Depends(auth)]
    R = Query(False, description="Cache ignorieren und neu aus Escola laden")
    F = Query("json", description="json oder csv")

    # ------------------------------------------------------------------ Anmeldung
    def _sitzung(token: str) -> A.Sitzung:
        s = sessions.get(token)
        if s is None:
            raise HTTPException(401, "Session unbekannt oder abgelaufen – neu anmelden")
        return s

    def _fehler(e: Exception, token: str | None = None, behalten=False):
        A.log.warning("Anmeldung fehlgeschlagen: %s: %s", type(e).__name__, e)
        if token and not behalten:
            sessions.entfernen(token)
        return JSONResponse(status_code=401, content={"status": "fehler", "meldung": str(e)})

    @app.get("/login", response_class=HTMLResponse, include_in_schema=False)
    def login_seite():
        return HTMLResponse((Path(__file__).parent / "login.html").read_text(encoding="utf-8"))

    @app.get("/testseite", response_class=HTMLResponse, include_in_schema=False)
    def test_seite():
        """Testseite: Endpunkte lesen, schreiben und rückgängig machen (lesen → schreiben → lesen → zurück → lesen)."""
        return HTMLResponse((Path(__file__).parent / "testseite.html").read_text(encoding="utf-8"))

    @app.post("/auth/login", dependencies=deps, tags=["Anmeldung"], openapi_extra={"x-eduksx": {"effect": "read", "danger": False}})
    def auth_login(body: LoginDaten):
        """Schritt 1: Benutzername + Passwort an Escola weiterreichen (nichts wird gespeichert).
        Antwort `status`: `angemeldet` oder `2fa_erforderlich` (dann POST /auth/2fa)."""
        token, s = sessions.neu()
        try:
            res = A.login_schritt1(s.client, body.benutzername, body.passwort, body.dauer_stunden)
        except (A.LoginFehler, httpx.HTTPError) as e:
            return _fehler(e, token)
        A.log.info("Login-Ergebnis: %s", res.get("status"))
        if res["status"] not in ("angemeldet", "2fa_erforderlich"):
            sessions.entfernen(token)
            return JSONResponse(status_code=409, content=res)
        s.status = res["status"]
        return {**res, "session": token}

    @app.get("/auth/2fa/methoden", dependencies=deps, tags=["Anmeldung"], summary="Verfügbare 2FA-Methoden der Sitzung")
    def auth_methoden(x_escola_session: str = Header(...)):
        s = _sitzung(x_escola_session)
        return {"methoden": A._methoden(A._zwei_faktor_infos(s.client))}

    @app.post("/auth/2fa/methode", dependencies=deps, tags=["Anmeldung"], summary="2FA-Methode wählen (App, SMS, Escola-App)",
               openapi_extra={"x-eduksx": {"effect": "read", "danger": False}})
    def auth_methode(body: Methode, x_escola_session: str = Header(...)):
        s = _sitzung(x_escola_session)
        try:
            A.zwei_faktor_methode(s.client, body.methode)
        except A.LoginFehler as e:
            return _fehler(e, x_escola_session, behalten=True)
        return {"status": "2fa_erforderlich", "methode": body.methode}

    @app.post("/auth/2fa/erneut", dependencies=deps, tags=["Anmeldung"], summary="2FA-Code erneut senden",
               openapi_extra={"x-eduksx": {"effect": "read", "danger": False}})
    def auth_erneut(x_escola_session: str = Header(...)):
        s = _sitzung(x_escola_session)
        try:
            return A.zwei_faktor_erneut(s.client)
        except A.LoginFehler as e:
            return _fehler(e, x_escola_session, behalten=True)

    @app.post("/auth/2fa", dependencies=deps, tags=["Anmeldung"], openapi_extra={"x-eduksx": {"effect": "read", "danger": False}})
    def auth_2fa(body: Code, x_escola_session: str = Header(...)):
        """Schritt 2: 2FA-Code (Authentifizierungs-App / SMS) bestätigen."""
        s = _sitzung(x_escola_session)
        try:
            res = A.zwei_faktor_code(s.client, body.code)
        except A.LoginFehler as e:
            return _fehler(e, x_escola_session, behalten=True)  # erneuter Versuch möglich
        s.status = res["status"]
        return {**res, "session": x_escola_session}

    @app.post("/auth/2fa/app", dependencies=deps, tags=["Anmeldung"], openapi_extra={"x-eduksx": {"effect": "read", "danger": False}})
    def auth_app(x_escola_session: str = Header(...)):
        """Alternative: Bestätigung in der Escola-App anfordern, danach GET /auth/2fa/app/{token} abfragen."""
        s = _sitzung(x_escola_session)
        try:
            return A.app_anfrage(s.client)
        except A.LoginFehler as e:
            return _fehler(e, x_escola_session, behalten=True)

    @app.get("/auth/2fa/app/{app_token}", dependencies=deps, tags=["Anmeldung"], summary="Status der Bestätigung in der Escola-App")
    def auth_app_status(app_token: str, x_escola_session: str = Header(...)):
        s = _sitzung(x_escola_session)
        try:
            res = A.app_status(s.client, app_token)
        except (A.LoginFehler, httpx.HTTPError) as e:
            return _fehler(e, x_escola_session, behalten=True)
        if res["status"] == "angemeldet":
            s.status = "angemeldet"
        return res

    @app.get("/fortschritt", dependencies=deps, tags=["Anmeldung"])
    def fortschritt(c: EscolaClient = Depends(get_client)):
        """Anzahl bisheriger Anfragen dieser Sitzung an Escola – für eine Fortschrittsanzeige
        während langer Listen (Seite fragt alle ~0.5 s ab und zeigt die Differenz)."""
        return {"aufrufe": c.zaehler, "zuletzt": c.zuletzt}

    @app.get("/auth/status", dependencies=deps, tags=["Anmeldung"], summary="Status der Anmeldesitzung")
    def auth_status(x_escola_session: str = Header(...)):
        s = _sitzung(x_escola_session)
        if s.status == "angemeldet" and not A._ist_angemeldet(s.client):
            s.status = "abgelaufen"
        return {"status": s.status, "seit": int(s.erstellt)}

    @app.post("/auth/logout", dependencies=deps, tags=["Anmeldung"], openapi_extra={"x-eduksx": {"effect": "read", "danger": False}})
    def auth_logout(x_escola_session: str = Header(...)):
        """Bei Escola abmelden und Session löschen."""
        s = sessions.get(x_escola_session)
        if s is not None:
            try:
                A.logout(s.client)
            except httpx.HTTPError:
                pass
            sessions.entfernen(x_escola_session)
        return {"status": "abgemeldet"}

    @app.get("/status", dependencies=deps, tags=["System"])
    def status(c: EscolaClient = Depends(get_client)):
        """Prüft, ob die Escola-Session gültig ist."""
        return c.status()

    @app.get("/klassen", dependencies=deps, tags=["Stammdaten"], summary="Klassen und Arbeitsgruppen (nach Schulhaus, Typ)")
    def klassen(schulhaus: str | None = None, typ: Literal["Klasse", "Arbeitsgruppe"] | None = None,
                format: Format = F, refresh: bool = R, c: EscolaClient = Depends(get_client)):
        rows = [k for k in c.klassen(refresh) if (not schulhaus or k["schulhaus"] == schulhaus) and (not typ or k["typ"] == typ)]
        return out(rows, format, "klassen")

    @app.get("/faecher", dependencies=deps, tags=["Stammdaten"], summary="Fächer")
    def faecher(format: Format = F, refresh: bool = R, c: EscolaClient = Depends(get_client)):
        return out(c.faecher(refresh), format, "faecher")

    @app.get("/lehrpersonen", dependencies=deps, tags=["Stammdaten"], summary="Lehrpersonen (nach Schulhaus)")
    def lehrpersonen(schulhaus: str | None = None, format: Format = F, refresh: bool = R, c: EscolaClient = Depends(get_client)):
        rows = [p for p in c.lehrpersonen(refresh) if not schulhaus or schulhaus in p["schulhaeuser"]]
        return out(rows, format, "lehrpersonen")

    @app.get("/raeume", dependencies=deps, tags=["Stammdaten"], summary="Räume (nach Schulhaus)")
    def raeume(schulhaus: str | None = None, format: Format = F, refresh: bool = R, c: EscolaClient = Depends(get_client)):
        data = c.raeume(refresh)
        rows = [r for sh, rs in data.items() if not schulhaus or sh == schulhaus for r in rs]
        return out(rows, format, "raeume")

    @app.get("/ressourcen", dependencies=deps, tags=["Stammdaten"])
    def ressourcen(schulhaus: str | None = None, kategorie: str | None = None, nur_reservierbar: bool = False,
                   format: Format = F, refresh: bool = R, c: EscolaClient = Depends(get_client)):
        """Alle Ressourcen aus dem Modul Ressourcen: ID (= Raum-ID im Stundenplan), Kürzel, Name, Kategorie
        (z. B. „Hibi – Trakt A“), Zeitprofil, reservierbar, Schulhaus."""
        rows = [r for r in c.ressourcen(refresh) if (not schulhaus or r["schulhaus"] == schulhaus)
                and (not kategorie or kategorie.lower() in r["kategorie"].lower()) and (not nur_reservierbar or r["reservierbar"])]
        return out(rows, format, "ressourcen")

    @app.get("/ressourcen/kategorien", dependencies=deps, tags=["Stammdaten"])
    def ressourcen_kategorien(refresh: bool = R, c: EscolaClient = Depends(get_client)):
        """Ressourcen-Kategorien mit Anzahl Ressourcen."""
        k: dict[int, dict] = {}
        for r in c.ressourcen(refresh):
            e = k.setdefault(r["kategorie_id"], {"id": r["kategorie_id"], "name": r["kategorie"], "typ": r["kategorie_typ"],
                                                 "schulhaus": r["schulhaus"], "anzahl": 0})
            e["anzahl"] += 1
        return list(k.values())

    @app.get("/ressourcen/zeiteinteilung", dependencies=deps, tags=["Stammdaten"])
    def ressourcen_zeiteinteilung(format: Format = F, refresh: bool = R, c: EscolaClient = Depends(get_client)):
        """Zeiteinteilung des Moduls Ressourcen je Profil (HIBI / METTMI) mit allen Zeitfenstern."""
        data = c.zeiteinteilung(refresh)
        if format == "csv":
            return out([{"profil_id": p["id"], "profil": p["name"], "schulhaus": p["schulhaus"], **z}
                        for p in data for z in p["zeiten"]], "csv", "zeiteinteilung")
        return data

    @app.get("/tage", dependencies=deps, tags=["Raster"], summary="Schultage des Stundenplanrasters")
    def tage(format: Format = F, refresh: bool = R, c: EscolaClient = Depends(get_client)):
        seen, rows = set(), []
        for r in c.raster(refresh).values():
            for t in r["tage"]:
                if t["code"] not in seen:
                    seen.add(t["code"]); rows.append(t)
        return out(rows, format, "tage")

    @app.get("/lektionen", dependencies=deps, tags=["Raster"])
    def lektionen(schulhaus: str | None = None, format: Format = F, refresh: bool = R, c: EscolaClient = Depends(get_client)):
        """Lektionen je Schulhaus – Hinterbirch und Mettmenriet haben eigene IDs und Zeiten."""
        rows = [{"schulhaus": sh, **l} for sh, r in c.raster(refresh).items() if not schulhaus or sh == schulhaus for l in r["lektionen"]]
        return out(rows, format, "lektionen")

    @app.get("/eintraege", dependencies=deps, tags=["Stundenplan"])
    def eintraege(klasse_id: int | None = None, schulhaus: str | None = None,
                  genau: bool = Query(False, description="exakte Escola-IDs pro Eintrag lesen (langsamer)"),
                  format: Format = F, refresh: bool = R, c: EscolaClient = Depends(get_client)):
        """Alle Stundenplan-Einträge als flache Tabelle (eine Zeile pro Eintrag)."""
        rows = [e for e in c.eintraege(refresh, genau) if (klasse_id is None or e["klasse_id"] == klasse_id)
                and (not schulhaus or e["schulhaus"] == schulhaus)]
        return out(rows, format, "eintraege")

    # ------------------------------------------------------------------ Personen / Schüler:innen
    from . import personen as PP

    flag = lambda name, default="0": os.getenv(name, default).strip().lower() in ("1", "true", "ja", "yes")
    schreiben_erlaubt = flag("ESCOLA_SCHREIBEN")
    gesundheit = flag("ESCOLA_GESUNDHEIT")
    sensibel = flag("ESCOLA_SENSIBEL_ZEIGEN")

    def _detail(c, pid, kategorie, abschnitte, optionen, format):
        try:
            d = c.person(pid, kategorie, abschnitte.split(",") if abschnitte else None, optionen, gesundheit, sensibel)
        except KeyError as e:
            raise HTTPException(404, str(e))
        if format == "csv":
            rows = [{"abschnitt": f["abschnitt"], "name": f["name"], "label": f["label"], "typ": f["typ"],
                     "wert": f.get("text", f["wert"]), "rohwert": f["wert"], "schreibbar": f["schreibbar"]}
                    for a in d["abschnitte"].values() for f in a["felder"]]
            return out(rows, "csv", f"person_{pid}")
        return d

    def _schreiben(c, pid, kategorie, body: Aenderung, probelauf: bool):
        if not schreiben_erlaubt and not probelauf:
            raise HTTPException(403, "Schreiben ist deaktiviert (ESCOLA_SCHREIBEN=1 setzen). Mit ?probelauf=true testen.")
        if schreiben_erlaubt and not api_key and not probelauf:
            raise HTTPException(403, "Zum Schreiben muss ESCOLA_API_KEY gesetzt sein")
        try:
            res = c.person_schreiben(pid, body.felder, kategorie, probelauf, gesundheit)
        except KeyError as e:
            raise HTTPException(404, str(e))
        if res.get("fehler"):
            return JSONResponse(status_code=422, content=res)
        return res

    def _schreib_check(probelauf: bool = False):
        if not schreiben_erlaubt and not probelauf:
            raise HTTPException(403, "Schreiben ist deaktiviert (ESCOLA_SCHREIBEN=1 setzen)")
        if schreiben_erlaubt and not api_key and not probelauf:
            raise HTTPException(403, "Zum Schreiben muss ESCOLA_API_KEY gesetzt sein")

    def _anlegen(c, body: NeuePerson, kategorie: str):
        _schreib_check()
        try:
            res = c.person_anlegen(body.nachname, body.vorname, body.geschlecht, kategorie, body.schulhaus,
                                   body.klasse_id, body.trotz_duplikat)
        except ValueError as e:
            raise HTTPException(400, str(e))
        if not res["angelegt"]:
            return JSONResponse(status_code=409, content=res)
        if body.felder:
            try:
                res["felder"] = c.person_schreiben(res["id"], body.felder,
                                                   "schueler" if kategorie in ("schueler", "students-without-schoolclass", "future-students") else "allActive",
                                                   False, gesundheit)
            except Exception as e:  # Person ist angelegt – ID nicht hinter einem 500 verstecken
                res["felder"] = {"id": res["id"], "geschrieben": False,
                                 "fehler": [{"feld": "*", "fehler": f"Felder nicht geschrieben: {e}"}]}
        return JSONResponse(status_code=201, content=res)

    @app.get("/schueler", dependencies=deps, tags=["Schüler:innen"])
    def schueler_liste(klasse_id: int | None = None, schulhaus: str | None = None,
                       schuljahr: int = Query(0, description="0 = aktuelles, 1 = kommendes Schuljahr"),
                       ohne_klasse: bool = Query(False, description="nur Schüler:innen ohne Klasse (inkl. zukünftige)"),
                       format: Format = F, refresh: bool = R, c: EscolaClient = Depends(get_client)):
        """Alle Schüler:innen mit Klasse (ID, Nachname, Vorname, Klasse, Schulhaus) – oder ohne Klasse."""
        quelle = c.schueler_ohne_klasse(refresh) if ohne_klasse else c.schueler(refresh, schuljahr)
        rows = [s for s in quelle if (klasse_id is None or s["klasse_id"] == klasse_id)
                and (not schulhaus or s["schulhaus"] == schulhaus)]
        return out(rows, format, "schueler")

    @app.post("/schueler", dependencies=deps, tags=["Schüler:innen"], status_code=201)
    def schueler_anlegen(body: NeuePerson, c: EscolaClient = Depends(get_client)):
        """Schüler:in anlegen – mit `klasse_id` direkt in eine Klasse, ohne `klasse_id` als
        „Schüler:in ohne Klasse“ (bzw. `zukuenftig=true`) zum späteren Zuordnen."""
        kat = "schueler" if body.klasse_id else ("future-students" if body.zukuenftig else "students-without-schoolclass")
        return _anlegen(c, body, kat)

    @app.post("/schueler/{pid}/klasse", dependencies=deps, tags=["Schüler:innen"])
    def schueler_klasse(pid: int, body: Transfer, c: EscolaClient = Depends(get_client)):
        """Schüler:in in eine Klasse transferieren (ab Stichtag, aktuelles oder kommendes Schuljahr)."""
        _schreib_check()
        import datetime as _dt
        stichtag = (body.stichtag or _dt.date.today().isoformat()) if body.schuljahr == 0 else None
        try:
            return c.schueler_transfer(pid, body.klasse_id, stichtag, body.schuljahr)
        except ValueError as e:
            raise HTTPException(400, str(e))
        except RuntimeError as e:
            raise HTTPException(409, str(e))

    @app.get("/schueler/{pid}/klasse/optionen", dependencies=deps, tags=["Schüler:innen"])
    def schueler_klasse_optionen(pid: int, schuljahr: int = Query(0, description="0 = aktuelles, 1 = kommendes"),
                                 c: EscolaClient = Depends(get_client)):
        """Klassen, in die diese:r Schüler:in transferiert werden kann – fürs kommende Schuljahr mit den
        künftigen Klassennamen (gleiche IDs, z. B. 92 = „zukünftige H_A2a“)."""
        try:
            return c.transfer_klassen(pid, schuljahr)
        except ValueError as e:
            raise HTTPException(400, str(e))
        except RuntimeError as e:
            raise HTTPException(409, str(e))

    @app.get("/schueler/{pid}/schullaufbahn", dependencies=deps, tags=["Schüler:innen"])
    def schueler_schullaufbahn(pid: int, c: EscolaClient = Depends(get_client)):
        """Schullaufbahn: Klassen je Schuljahr mit Von/Bis (z. B. „TEST_A1a 2026-08-01 – 2027-07-31“)."""
        try:
            return c.schullaufbahn(pid)
        except RuntimeError as e:
            raise HTTPException(409, str(e))

    @app.put("/schueler/{pid}/klasse/beginn", dependencies=deps, tags=["Schüler:innen"])
    def schueler_klassenbeginn(pid: int, body: Klassenbeginn,
                               probelauf: bool = Query(False, description="nur zeigen, nichts speichern"),
                               c: EscolaClient = Depends(get_client)):
        """Beginn der Klassenzuteilung in der Schullaufbahn setzen, z. B. ab Schuljahresbeginn.
        Nötig nach Import oder Transfer: Escola teilt dort immer ab heute ein."""
        _schreib_check(probelauf)
        try:
            return c.klassenbeginn_setzen(pid, body.ab, body.schuljahr, body.edit_id, probelauf)
        except KonfliktFehler as e:
            return _konflikt(e)
        except ValueError as e:
            raise HTTPException(400, str(e))
        except RuntimeError as e:
            raise HTTPException(409, str(e))

    @app.post("/klassen/{klasse_id}/klassenbeginn", dependencies=deps, tags=["Schuljahr vorbereiten"])
    def klasse_klassenbeginn(klasse_id: int, body: KlassenbeginnKlasse,
                             probelauf: bool = Query(False, description="nur zeigen, nichts speichern"),
                             c: EscolaClient = Depends(get_client)):
        """Klassenbeginn für alle SuS einer Klasse setzen (nach dem Import einer Klasse, WF-11).
        Standard `eintritt`: 1.8., bei späterem Eintritt das Eintrittsdatum. Fehler pro SuS stehen in der Liste."""
        _schreib_check(probelauf)
        return c.klasse_klassenbeginn(klasse_id, body.ab, probelauf)

    @app.delete("/schueler/{pid}/klasse", dependencies=deps, tags=["Schüler:innen"])
    def schueler_klasse_entfernen(pid: int, schuljahr: int = Query(0, description="0 = aktuelles, 1 = kommendes"),
                                  klasse_id: int | None = Query(None, description="optional; sonst wird die Klasse gesucht"),
                                  c: EscolaClient = Depends(get_client)):
        """Klassenzuteilung entfernen. Die Person bleibt bestehen und steht danach unter „ohne Klasse“."""
        _schreib_check()
        try:
            return c.schueler_aus_klasse_entfernen(pid, klasse_id, schuljahr)
        except ValueError as e:
            raise HTTPException(400, str(e))
        except RuntimeError as e:
            raise HTTPException(409, str(e))

    @app.post("/schueler/{pid}/austritt", dependencies=deps, tags=["Schüler:innen"])
    def schueler_austritt(pid: int, body: Austritt, c: EscolaClient = Depends(get_client)):
        """Austritt erfassen (Austrittsdatum, optional Wegzug). Escola deaktiviert die Person danach selbst;
        mit `sofort_deaktivieren: true` sofort."""
        _schreib_check()
        try:
            return c.schueler_austritt(pid, body.datum, body.wegzugsdatum, body.wegzugsgemeinde, body.sofort_deaktivieren)
        except KeyError as e:
            raise HTTPException(404, str(e))
        except ValueError as e:
            raise HTTPException(400, str(e))
        except RuntimeError as e:
            raise HTTPException(409, str(e))

    @app.get("/arbeitsgruppen", dependencies=deps, tags=["Arbeitsgruppen"])
    def arbeitsgruppen_liste(schuljahr: int = Query(0, description="0 = aktuelles, 1 = kommendes"),
                             format: Format = F, refresh: bool = R, c: EscolaClient = Depends(get_client)):
        """Alle Arbeitsgruppen mit ID, Name, Schulhaus und Anzahl Schüler:innen."""
        return out(c.arbeitsgruppen(schuljahr, refresh), format, "arbeitsgruppen")

    @app.get("/arbeitsgruppen/{ag_id}/stundenplan", dependencies=deps, tags=["Arbeitsgruppen"],
             summary="Stundenplan-Einträge einer Arbeitsgruppe")
    def arbeitsgruppe_stundenplan(ag_id: int, format: Format = F, c: EscolaClient = Depends(get_client)):
        """Einträge im Stundenplan einer Arbeitsgruppe (L8, #13), gleiche Felder wie bei Klassen."""
        try:
            rows = c.arbeitsgruppe_stundenplan(ag_id)
        except KeyError as e:
            raise HTTPException(404, str(e))
        return out(rows, format, f"stundenplan_ag_{ag_id}")

    @app.get("/schueler/{pid}/arbeitsgruppen", dependencies=deps, tags=["Arbeitsgruppen"])
    def schueler_arbeitsgruppen(pid: int, schuljahr: int = Query(0), c: EscolaClient = Depends(get_client)):
        """Arbeitsgruppen einer Schülerin / eines Schülers."""
        try:
            return c.schueler_arbeitsgruppen(pid, schuljahr)
        except RuntimeError as e:
            raise HTTPException(502, str(e))

    @app.post("/schueler/{pid}/arbeitsgruppen", dependencies=deps, tags=["Arbeitsgruppen"])
    def schueler_arbeitsgruppe_hinzu(pid: int, body: ArbeitsgruppeZuteilung, c: EscolaClient = Depends(get_client)):
        """Schüler:in einer Arbeitsgruppe zuteilen (andere Arbeitsgruppen bleiben unverändert)."""
        _schreib_check()
        try:
            return c.schueler_arbeitsgruppe_setzen(pid, body.arbeitsgruppe_id, True, body.schuljahr)
        except ValueError as e:
            raise HTTPException(400, str(e))
        except RuntimeError as e:
            raise HTTPException(409, str(e))

    @app.delete("/schueler/{pid}/arbeitsgruppen/{wg_id}", dependencies=deps, tags=["Arbeitsgruppen"])
    def schueler_arbeitsgruppe_weg(pid: int, wg_id: int, schuljahr: int = Query(0), c: EscolaClient = Depends(get_client)):
        """Schüler:in aus einer Arbeitsgruppe entfernen."""
        _schreib_check()
        try:
            return c.schueler_arbeitsgruppe_setzen(pid, wg_id, False, schuljahr)
        except ValueError as e:
            raise HTTPException(400, str(e))
        except RuntimeError as e:
            raise HTTPException(409, str(e))

    # Dokumente im Schülerdossier (L11, #3) – schützenswert: eigener Schalter wie Zeugnisse
    dokumente_erlaubt = flag("ESCOLA_DOKUMENTE")

    def _dok_check():
        if not dokumente_erlaubt:
            raise HTTPException(403, "Dokumente sind ausgeschaltet (ESCOLA_DOKUMENTE=1 setzen)")
        if not api_key:
            raise HTTPException(403, "Für Dokumente muss ESCOLA_API_KEY gesetzt sein")

    def _dok(fn):
        try:
            return fn()
        except KeyError as e:
            raise HTTPException(404, str(e))
        except ValueError as e:
            raise HTTPException(400, str(e))

    @app.get("/schueler/{pid}/dokumente", dependencies=deps, tags=["Dokumente"],
             summary="Ordner mit Unterordnern und Dateien (Schüler:innen-Dokumente)")
    def schueler_dokumente(pid: int, ordner_id: int | None = Query(None, description="leer = Wurzelordner"),
                           alle: bool = Query(False, description="alle Dateien aller Ordner als Liste"),
                           c: EscolaClient = Depends(get_client)):
        """Reiter „Dokumente“ einer Schülerin / eines Schülers. Dateifelder unverändert von Escola."""
        _dok_check()
        return _dok(lambda: c.dokumente_alle(pid) if alle else c.dokumente_ordner(pid, ordner_id))

    @app.get("/schueler/{pid}/dokumente/{datei_id}", dependencies=deps, tags=["Dokumente"], summary="Datei herunterladen")
    def schueler_dokument(pid: int, datei_id: int, c: EscolaClient = Depends(get_client)):
        _dok_check()
        inhalt, typ, cd = _dok(lambda: c.dokument_herunterladen(pid, datei_id))
        return Response(inhalt, media_type=typ, headers={"Content-Disposition": cd} if cd else {})

    @app.post("/schueler/{pid}/dokumente/{ordner_id}", dependencies=deps, tags=["Dokumente"],
              summary="Datei in einen Ordner hochladen")
    async def schueler_dokument_hochladen(pid: int, ordner_id: int, request: Request,
                                         dateiname: str = Query(..., description="Name der Datei in Escola"),
                                         probelauf: bool = Query(True), c: EscolaClient = Depends(get_client)):
        """Rohdaten im Body (z. B. `curl --data-binary @datei.pdf`). Zuerst Probelauf."""
        _dok_check()
        _schreib_check(probelauf)
        inhalt = await request.body()
        if not inhalt:
            raise HTTPException(400, "Leere Datei")
        typ = request.headers.get("content-type", "application/octet-stream")
        return _dok(lambda: c.dokument_hochladen(pid, ordner_id, dateiname, inhalt, typ, probelauf))

    @app.delete("/schueler/{pid}/dokumente/{datei_id}", dependencies=deps, tags=["Dokumente"], summary="Datei löschen")
    def schueler_dokument_loeschen(pid: int, datei_id: int, probelauf: bool = Query(True),
                                   c: EscolaClient = Depends(get_client)):
        """Nur für das Rückgängigmachen eines eigenen Uploads gedacht. Zuerst Probelauf."""
        _dok_check()
        _schreib_check(probelauf)
        return _dok(lambda: c.dokument_loeschen(pid, datei_id, probelauf))

    # Zeugnis-Archiv (Personenverwaltung → «Zeugnis-/Formular-Archiv»), schützenswert: eigener Schalter
    zeugnisse_erlaubt = flag("ESCOLA_ZEUGNISSE")

    def _zeugnis_check():
        if not zeugnisse_erlaubt:
            raise HTTPException(403, "Zeugnisse sind ausgeschaltet (ESCOLA_ZEUGNISSE=1 setzen)")
        if not api_key:
            raise HTTPException(403, "Für Zeugnisse muss ESCOLA_API_KEY gesetzt sein")

    @app.get("/schueler/{pid}/zeugnisse", dependencies=deps, tags=["Zeugnisse"])
    def schueler_zeugnisse(pid: int, schuljahr: str | None = Query(None, description="z. B. 2026/27"),
                           nur_definitiv: bool = Query(False, description="nur ausgedruckte (definitive) Versionen"),
                           format: Format = F, c: EscolaClient = Depends(get_client)):
        """Archivierte Zeugnisse einer Schülerin / eines Schülers (Titel, Schuljahr, definitiv, erstellt, ID)."""
        _zeugnis_check()
        try:
            rows = c.zeugnisse(pid)
        except KeyError as e:
            raise HTTPException(404, str(e))
        rows = [z for z in rows if (not schuljahr or z["schuljahr"] == schuljahr) and (not nur_definitiv or z["definitiv"])]
        return out([{k: v for k, v in z.items() if k != "url"} for z in rows], format, f"zeugnisse_{pid}")

    @app.get("/schueler/{pid}/zeugnisse/{zeugnis_id}/pdf", dependencies=deps, tags=["Zeugnisse"])
    def schueler_zeugnis_pdf(pid: int, zeugnis_id: str, c: EscolaClient = Depends(get_client)):
        """Ein archiviertes Zeugnis als PDF herunterladen."""
        _zeugnis_check()
        try:
            z, pdf = c.zeugnis_pdf(pid, zeugnis_id)
        except KeyError as e:
            raise HTTPException(404, str(e))
        except RuntimeError as e:
            raise HTTPException(502, str(e))
        name = (z["datei"] or f"Zeugnis_{pid}") + ".pdf"
        from urllib.parse import quote
        return Response(pdf, media_type="application/pdf",
                        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(name)}"})

    @app.get("/klassen/{klasse_id}/zeugnisse", dependencies=deps, tags=["Zeugnisse"])
    def klasse_zeugnisse(klasse_id: int, schuljahr: str | None = Query(None, description="z. B. 2026/27"),
                         titel: str | None = Query(None, description="z. B. «Zeugnis 1. Semester»"),
                         nur_definitiv: bool = Query(False), nur_neuestes: bool = Query(True, description="je SuS und Titel nur das neueste"),
                         format: Format = F, c: EscolaClient = Depends(get_client)):
        """Zeugnisse aller Schüler:innen einer Klasse – Grundlage für die Ablage in CMI (WF-27)."""
        _zeugnis_check()
        rows = []
        for s in [s for s in c.schueler() if s["klasse_id"] == klasse_id]:
            gesehen = set()
            for z in c.zeugnisse(s["id"]):
                if (schuljahr and z["schuljahr"] != schuljahr) or (titel and z["titel"] != titel) \
                        or (nur_definitiv and not z["definitiv"]):
                    continue
                if nur_neuestes and (z["schuljahr"], z["titel"]) in gesehen:
                    continue
                gesehen.add((z["schuljahr"], z["titel"]))
                rows.append({"schueler_id": s["id"], "nachname": s["nachname"], "vorname": s["vorname"],
                             "klasse": s["klasse"], **{k: v for k, v in z.items() if k != "url"}})
        return out(rows, format, f"zeugnisse_klasse_{klasse_id}")

    @app.get("/schueler/{pid}", dependencies=deps, tags=["Schüler:innen"])
    def schueler_detail(pid: int, abschnitte: str | None = Query(None, description="z. B. name,personalien,privat"),
                        optionen: bool = Query(False, description="Auswahlmöglichkeiten mitliefern"),
                        format: Format = F, c: EscolaClient = Depends(get_client)):
        """Alle Felder einer Schülerin / eines Schülers."""
        return _detail(c, pid, "schueler", abschnitte, optionen, format)

    @app.patch("/schueler/{pid}", dependencies=deps, tags=["Schüler:innen"])
    def schueler_schreiben(pid: int, body: Aenderung, probelauf: bool = Query(False, description="nur prüfen, nichts speichern"),
                           c: EscolaClient = Depends(get_client)):
        """Felder ändern. Gesperrt: AHV, IBAN/BIC, Austritt/Wegzug, Login/Passwort."""
        return _schreiben(c, pid, "schueler", body, probelauf)

    ANSICHTEN = {"allActive", "allInactive", "schueler", "workgroup", "students-without-schoolclass", "eltern",
                 "educatorsWorkgroup", "guardians-all", "future-students", "former-students",
                 "guardians-future", "guardians-former"}

    def _rollen(c, refresh):
        return [{"rolle": k, "name": v, "typ": "ansicht" if k in ANSICHTEN else "rolle"}
                for k, v in c.kategorien(refresh).items()]

    @app.get("/personen/rollen", dependencies=deps, tags=["Personen"])
    def personen_rollen(refresh: bool = R, c: EscolaClient = Depends(get_client)):
        """Escola-Rollen live (Personen → Rollen-Konfiguration), inkl. eigener Rollen wie „_neu“
        (Kennung `gruppe_<n>`). `typ: ansicht` = reine Filteransicht der Personenverwaltung
        (z. B. alle aktiven Personen, SuS ohne Klasse), keine Rolle."""
        return _rollen(c, refresh)

    @app.get("/personen/kategorien", dependencies=deps, tags=["Personen"], include_in_schema=False)
    def personen_kategorien(refresh: bool = R, c: EscolaClient = Depends(get_client)):
        return _rollen(c, refresh)  # veraltet, Alias für /personen/rollen

    @app.get("/personen", dependencies=deps, tags=["Personen"])
    def personen_liste(rolle: str = Query("allActive", description="Rolle oder Ansicht, siehe /personen/rollen"),
                       kategorie: str | None = Query(None, include_in_schema=False),
                       schulhaus: str | None = None, format: Format = F, refresh: bool = R,
                       c: EscolaClient = Depends(get_client)):
        """Personen einer Rolle (z. B. lehrperson, gruppe_4) oder Ansicht (Standard: alle aktiven Personen)."""
        kategorie = kategorie or rolle
        try:
            rows = c.personen(kategorie, refresh)
        except ValueError as e:
            raise HTTPException(400, str(e))
        rows = [p for p in rows if not schulhaus or schulhaus in p.get("schulhaeuser", [p.get("schulhaus")])]
        return out(rows, format, f"personen_{kategorie}")

    @app.post("/personen", dependencies=deps, tags=["Personen"], status_code=201)
    def personen_anlegen(body: NeuePerson, c: EscolaClient = Depends(get_client)):
        """Person mit einer Escola-Rolle anlegen, z. B. `rolle: "lehrperson"`, `"gruppe_4"` (Schulverwaltung)
        oder eine eigene Rolle wie „_neu“."""
        rolle = body.rolle or body.kategorie
        if not rolle:
            raise HTTPException(400, "rolle fehlt (siehe /personen/rollen)")
        return _anlegen(c, body, rolle)

    # ------------------------------------------------------------------ Fächer-Zuteilung
    @app.get("/klassen/{klasse_id}/lehrpersonen", dependencies=deps, tags=["Fächer-Zuteilung"])
    def klasse_lehrpersonen(klasse_id: int, schuljahr: int = Query(0, ge=0, le=1, description="0 = aktuelles, 1 = kommendes Schuljahr"), c: EscolaClient = Depends(get_client)):
        """Alle Lehrpersonen einer Klasse mit Fächern, Art (KLR/Fach/SoPä) und Rechten KLR/FP/SpM/Abs/Gesundheit."""
        return c.klasse_lehrpersonen(klasse_id, schuljahr)

    @app.get("/arbeitsgruppen/{ag_id}/lehrpersonen", dependencies=deps, tags=["Fächer-Zuteilung"])
    def arbeitsgruppe_lehrpersonen(ag_id: int, schuljahr: int = Query(0, ge=0, le=1, description="0 = aktuelles, 1 = kommendes Schuljahr"), c: EscolaClient = Depends(get_client)):
        """Alle Lehrpersonen einer Arbeitsgruppe (Fachklasse) mit Fächern, Abs und Gesundheit."""
        return c.klasse_lehrpersonen(None, schuljahr, arbeitsgruppe_id=ag_id)

    @app.get("/klassen/{klasse_id}/klassenlehrpersonen", dependencies=deps, tags=["Fächer-Zuteilung"])
    def klasse_klp(klasse_id: int, waehlbar: bool = Query(False, description="auch alle wählbaren Lehrpersonen"),
                   c: EscolaClient = Depends(get_client)):
        """Klassenlehrpersonen A/B/C der Klasse im aktuellen und kommenden Schuljahr."""
        try:
            return c.klassenlehrpersonen(klasse_id, waehlbar)
        except ValueError as e:
            raise HTTPException(404, str(e))

    @app.put("/klassen/{klasse_id}/klassenlehrpersonen", dependencies=deps, tags=["Fächer-Zuteilung"])
    def klasse_klp_setzen(klasse_id: int, body: KlassenlehrpersonenAenderung, probelauf: bool = Query(False),
                          c: EscolaClient = Depends(get_client)):
        """Klassenlehrpersonen setzen (max. 3). Escola vergibt damit automatisch die KLR-Rechte."""
        _schreib_check(probelauf)
        try:
            return c.klassenlehrpersonen_setzen(klasse_id, body.aktuell, body.kommend, probelauf)
        except ValueError as e:
            raise HTTPException(400, str(e))
        except RuntimeError as e:
            raise HTTPException(409, str(e))

    @app.get("/lehrpersonen/{lp_id}/faecher", dependencies=deps, tags=["Fächer-Zuteilung"])
    def lehrperson_faecher(lp_id: int, klasse_id: int | None = Query(None), arbeitsgruppe_id: int | None = Query(None),
                           schuljahr: int = Query(0, ge=0, le=1, description="0 = aktuelles, 1 = kommendes Schuljahr"), c: EscolaClient = Depends(get_client)):
        """Fächer der Klasse bzw. Arbeitsgruppe mit Zuteilung dieser Lehrperson und ihren Rechten."""
        try:
            return c.lehrperson_faecher(lp_id, klasse_id, schuljahr, arbeitsgruppe_id)
        except ValueError as e:
            raise HTTPException(400, str(e))

    @app.patch("/lehrpersonen/{lp_id}/faecher", dependencies=deps, tags=["Fächer-Zuteilung"])
    def lehrperson_faecher_setzen(lp_id: int, body: FaecherAenderung, probelauf: bool = Query(False),
                                  c: EscolaClient = Depends(get_client)):
        """Fächer zuteilen/entfernen, Rechte setzen oder eine Vorlage anwenden (klassenlehrperson, fachlehrperson, sopae)."""
        _schreib_check(probelauf)
        try:
            return c.lehrperson_faecher_setzen(lp_id, body.klasse_id, body.faecher_hinzu, body.faecher_weg,
                                               body.rechte.model_dump() if body.rechte else None,
                                               body.vorlage, body.faecher, probelauf, body.schuljahr,
                                               body.arbeitsgruppe_id)
        except ValueError as e:
            raise HTTPException(400, str(e))
        except RuntimeError as e:
            raise HTTPException(409, str(e))

    # ------------------------------------------------------------------ Stundenplan schreiben
    def _st(fn):
        try:
            return fn()
        except ValueError as e:
            raise HTTPException(400, str(e))
        except RuntimeError as e:
            raise HTTPException(409, str(e))

    @app.get("/klassen/{klasse_id}/stundenplan/{tag}/{lektion_id}", dependencies=deps, tags=["Stundenplan"])
    def stundenplan_zelle(klasse_id: int, tag: Literal["A", "B", "C", "D", "E"], lektion_id: int,
                          c: EscolaClient = Depends(get_client)):
        """Einträge einer Zelle mit Eintrags-ID, Fach, Räumen, Lehrpersonen und was wählbar ist."""
        return _st(lambda: c.stundenplan_zelle(klasse_id, tag, lektion_id))

    @app.post("/klassen/{klasse_id}/stundenplan/{tag}/{lektion_id}", dependencies=deps, tags=["Stundenplan"],
              status_code=201)
    def stundenplan_anlegen(klasse_id: int, tag: Literal["A", "B", "C", "D", "E"], lektion_id: int,
                            body: StundenplanEintrag, probelauf: bool = Query(False), c: EscolaClient = Depends(get_client)):
        """Eintrag anlegen (auch zusätzlicher Eintrag in einer belegten Zelle)."""
        _schreib_check(probelauf)
        return _st(lambda: c.stundenplan_schreiben(klasse_id, tag, lektion_id, None, body.fach_id, body.raum_ids,
                                                   body.lehrperson_ids, probelauf=probelauf))

    @app.patch("/klassen/{klasse_id}/stundenplan/{tag}/{lektion_id}/{eintrag_id}", dependencies=deps, tags=["Stundenplan"])
    def stundenplan_aendern(klasse_id: int, tag: Literal["A", "B", "C", "D", "E"], lektion_id: int, eintrag_id: int,
                            body: StundenplanEintrag, probelauf: bool = Query(False), c: EscolaClient = Depends(get_client)):
        """Fach, Räume und/oder Lehrpersonen eines Eintrags ändern."""
        _schreib_check(probelauf)
        return _st(lambda: c.stundenplan_schreiben(klasse_id, tag, lektion_id, eintrag_id, body.fach_id, body.raum_ids,
                                                   body.lehrperson_ids, probelauf=probelauf))

    @app.delete("/klassen/{klasse_id}/stundenplan/{tag}/{lektion_id}/{eintrag_id}", dependencies=deps, tags=["Stundenplan"])
    def stundenplan_loeschen(klasse_id: int, tag: Literal["A", "B", "C", "D", "E"], lektion_id: int, eintrag_id: int,
                             probelauf: bool = Query(False), c: EscolaClient = Depends(get_client)):
        """Einen Eintrag löschen (nur diesen, nie den ganzen Stundenplan)."""
        _schreib_check(probelauf)
        return _st(lambda: c.stundenplan_schreiben(klasse_id, tag, lektion_id, eintrag_id, loeschen=True,
                                                   probelauf=probelauf))

    @app.post("/klassen/{klasse_id}/stundenplan/abgleich", dependencies=deps, tags=["Stundenplan"])
    def stundenplan_abgleich(klasse_id: int, body: StundenplanAbgleich, probelauf: bool = Query(True),
                             c: EscolaClient = Depends(get_client)):
        """Soll-Stundenplan einer Klasse (z. B. aus dem Stundenplaner-Export) gegen Escola abgleichen.
        Standard ist **Probelauf** (nur Plan). Mit `probelauf=false` werden fehlende Einträge angelegt,
        abweichende geändert und – nur mit `loeschen: true` – überzählige gelöscht. Fehler → nichts geschrieben."""
        _schreib_check(probelauf)
        return _st(lambda: c.stundenplan_abgleich(klasse_id, [e.model_dump() for e in body.eintraege],
                                                  body.loeschen, probelauf))

    @app.post("/lehrpersonen/{lp_id}/ersetzen", dependencies=deps, tags=["Stundenplan"])
    def lehrperson_ersetzen(lp_id: int, body: Ersetzen, probelauf: bool = Query(False),
                            c: EscolaClient = Depends(get_client)):
        """Nachfolge: Fächer, Klassenlehrperson-Plätze und Stundenplan-Einträge an eine andere Lehrperson übergeben."""
        _schreib_check(probelauf)
        return _st(lambda: c.lehrperson_ersetzen(lp_id, body.neu_id, body.klassen_ids, body.klassenlehrperson, probelauf))

    # ------------------------------------------------------------------ Bezugspersonen / Eltern
    @app.get("/schueler/{pid}/bezugspersonen", dependencies=deps, tags=["Bezugspersonen"])
    def bezugspersonen(pid: int, c: EscolaClient = Depends(get_client)):
        """Eltern/Bezugspersonen mit Funktion, Sorgerecht, abholberechtigt, gleicher Adresse."""
        return c.bezugspersonen(pid)

    # ------------------------------------------------------------------ Schuljahr vorbereiten (WF-11 ff.)
    @app.get("/klassenlisten", dependencies=deps, tags=["Schuljahr vorbereiten"])
    def klassenlisten(schuljahr: int = Query(0, ge=0, le=1, description="0 = aktuelles, 1 = kommendes Schuljahr"),
                      schulhaus: str | None = None, format: Format = F, refresh: bool = R,
                      c: EscolaClient = Depends(get_client)):
        """Klassenlisten: eine Zeile pro Schüler:in mit Klasse, Schulhaus und Klassenlehrperson(en).
        Für ICT (Zugänge), Drucklisten und den Abgleich nach der Einteilung."""
        return out(c.klassenlisten(schuljahr, schulhaus, refresh), format, f"klassenlisten_sj{schuljahr}")

    @app.get("/klassen/{klasse_id}/felder", dependencies=deps, tags=["Schuljahr vorbereiten"])
    def klasse_felder(klasse_id: int, namen: str = Query(..., description="Feldnamen, kommagetrennt (siehe GET /schueler/{id})"),
                      abschnitte: str | None = Query(None, description="Reiter, kommagetrennt – beschleunigt das Lesen"),
                      nur_leer: bool = Query(False, description="nur SuS mit leerem Feld (Liste der offenen)"),
                      schuljahr: int = Query(0, ge=0, le=1), format: Format = F, c: EscolaClient = Depends(get_client)):
        """Ausgewählte Felder aller Schüler:innen einer Klasse, z. B. Kontrollen Arzt/Zahnarzt in
        benutzerdefinierten Feldern. Liest jede Person einzeln (Fortschritt über GET /fortschritt)."""
        felder = [f.strip() for f in namen.split(",") if f.strip()]
        abs_ = [a.strip() for a in abschnitte.split(",") if a.strip()] if abschnitte else None
        try:
            rows = c.klasse_felder(klasse_id, felder, abs_, nur_leer, schuljahr)
        except ValueError as e:
            raise HTTPException(400, str(e))
        return out(rows, format, f"felder_klasse_{klasse_id}")

    @app.get("/klassen/{klasse_id}/eltern", dependencies=deps, tags=["Schuljahr vorbereiten"])
    def klasse_eltern(klasse_id: int, schuljahr: int = Query(0, ge=0, le=1),
                      app: bool = Query(False, description="App-Status je Bezugsperson mitlesen (langsamer): "
                                                           "app_aktiviert, anzahl_logins, letzter_login"),
                      nur_ohne_app: bool = Query(False, description="nur Bezugspersonen, die die App nicht aktiviert "
                                                                    "oder sich nie angemeldet haben (setzt app=true)"),
                      format: Format = F, c: EscolaClient = Depends(get_client)):
        """Alle Bezugspersonen der Schüler:innen einer Klasse (eine Zeile pro Kind und Bezugsperson) –
        für App-Onboarding, Zuteilungsbrief und Nachfassen. Kinder ohne Bezugsperson mit leeren Feldern.
        Mit `app=true` zusätzlich der App-Status (L12, #4); `nur_ohne_app=true` liefert die Liste zum Nachfassen."""
        rows = c.eltern_der_klasse(klasse_id, schuljahr, app=app or nur_ohne_app)
        if nur_ohne_app:
            rows = [r for r in rows if r["bezugsperson_id"] is not None
                    and (r.get("app_aktiviert") is not True or not (r.get("app_eingeloggt") or r.get("anzahl_logins")))]
        return out(rows, format, f"eltern_klasse_{klasse_id}")

    # ------------------------------------------------------------------ Absenzen (L17, #9)
    def _abs(fn):
        try:
            return fn()
        except KeyError as e:
            raise HTTPException(404, str(e))
        except ValueError as e:
            raise HTTPException(400, str(e))

    @app.get("/klassen/{klasse_id}/absenzen/auswahl", dependencies=deps, tags=["Absenzen"],
             summary="Absenzen-Semester, Schüler:innen und Absenzarten einer Klasse")
    def absenzen_auswahl(klasse_id: int, c: EscolaClient = Depends(get_client)):
        """Auswahllisten des Absenzen-Moduls. `semester` liefert die IDs für die Einträge (leer = noch keine Absenzen)."""
        return _abs(lambda: c.absenzen_auswahl(klasse_id))

    @app.get("/klassen/{klasse_id}/absenzen", dependencies=deps, tags=["Absenzen"], summary="Absenzen einer Klasse")
    def klasse_absenzen(klasse_id: int, semester: int = Query(..., description="ID aus /absenzen/auswahl, z. B. 20261"),
                        sortierung: str = Query("date-asc"), roh: bool = Query(False, description="Escola-Felder unverändert"),
                        format: Format = F, c: EscolaClient = Depends(get_client)):
        """Absenz-Einträge einer Klasse in einem Absenzen-Semester (Datum, Schüler:in, Art, Dauer …)."""
        rows = _abs(lambda: c.absenzen(semester, klasse_id=klasse_id, sortierung=sortierung))
        return out(rows if roh else [c.absenz_kurz(x) for x in rows], format, f"absenzen_klasse_{klasse_id}")

    @app.get("/schueler/{pid}/absenzen", dependencies=deps, tags=["Absenzen"], summary="Absenzen einer Schülerin")
    def schueler_absenzen(pid: int, semester: int = Query(...), sortierung: str = Query("date-asc"),
                          roh: bool = Query(False), format: Format = F, c: EscolaClient = Depends(get_client)):
        """Absenz-Einträge einer Schülerin / eines Schülers in einem Absenzen-Semester."""
        rows = _abs(lambda: c.absenzen(semester, schueler_id=pid, sortierung=sortierung))
        return out(rows if roh else [c.absenz_kurz(x) for x in rows], format, f"absenzen_{pid}")

    @app.get("/personen/{pid}/app", dependencies=deps, tags=["Schuljahr vorbereiten"],
             summary="Escola-App: freigeschaltet, Anzahl Logins, letzter Login")
    def person_app(pid: int, c: EscolaClient = Depends(get_client)):
        """App-Status einer Person (Reiter „Escola App“ und „Aktivität“), nur lesen."""
        try:
            return c.app_status(pid)
        except KeyError as e:
            raise HTTPException(404, str(e))

    @app.post("/import/pruefen", dependencies=deps, tags=["Schuljahr vorbereiten"], openapi_extra={"x-eduksx": {"effect": "read", "danger": False}})
    def import_pruefen(body: ImportListe, format: Format = F, c: EscolaClient = Depends(get_client)):
        """Vorprüfung einer Importliste (Schüler:innen und Eltern) mit der Escola-Duplikatprüfung.
        Legt nichts an. `status`: `neu`, `moegliche_duplikate` (mit Liste) oder `fehler`.
        Den Import selbst macht der Escola-Import mit der von unserer Anwendung erzeugten Datei."""
        rows = c.import_pruefen([p.model_dump() for p in body.personen])
        if format == "csv":
            rows = [{**r, "fehler": "; ".join(r["fehler"]),
                     "duplikate": "; ".join(f"{d['id']} {d['name']}" for d in r["duplikate"])} for r in rows]
        return out(rows, format, "import_pruefung")

    @app.get("/personen/{pid}/kinder", dependencies=deps, tags=["Bezugspersonen"])
    def kinder(pid: int, c: EscolaClient = Depends(get_client)):
        """Alle Kinder, mit denen eine Bezugsperson verknüpft ist."""
        return c.kinder(pid)

    @app.post("/schueler/{pid}/bezugspersonen", dependencies=deps, tags=["Bezugspersonen"], status_code=201)
    def bezugsperson_neu(pid: int, body: NeueBezugsperson, c: EscolaClient = Depends(get_client)):
        """Bestehende Person verknüpfen (person_id) oder neue Bezugsperson anlegen und verknüpfen."""
        _schreib_check()
        try:
            if body.person_id:
                return c.bezugsperson_verknuepfen(pid, body.person_id, body.funktion, body.sorgerecht, body.abholberechtigt)
            if not (body.nachname and body.vorname and body.geschlecht):
                raise ValueError("person_id oder nachname, vorname, geschlecht angeben")
            res = c.bezugsperson_anlegen(pid, body.nachname, body.vorname, body.geschlecht, body.funktion,
                                         body.sorgerecht, body.abholberechtigt, body.trotz_duplikat)
            if body.felder:
                res["felder"] = c.person_schreiben(res["person_id"], body.felder)
            return res
        except KonfliktFehler as e:
            return _konflikt(e)
        except ValueError as e:
            raise HTTPException(400, str(e))
        except RuntimeError as e:
            raise HTTPException(409, str(e))

    @app.patch("/schueler/{pid}/bezugspersonen/{beziehung_id}", dependencies=deps, tags=["Bezugspersonen"])
    def bezugsperson_sorgerecht(pid: int, beziehung_id: int, body: Sorgerecht, c: EscolaClient = Depends(get_client)):
        """Sorgerecht ändern: sorgeberechtigt / informationsberechtigt / keine."""
        _schreib_check()
        return _st(lambda: c.sorgerecht_setzen(pid, beziehung_id, body.sorgerecht))

    @app.delete("/schueler/{pid}/bezugspersonen/{beziehung_id}", dependencies=deps, tags=["Bezugspersonen"])
    def bezugsperson_weg(pid: int, beziehung_id: int, deaktivieren: bool = Query(False), c: EscolaClient = Depends(get_client)):
        """Verknüpfung entfernen (Person bleibt); mit deaktivieren=true Bezugsperson zusätzlich deaktivieren."""
        _schreib_check()
        return _st(lambda: c.bezugsperson_entfernen(pid, beziehung_id, deaktivieren))

    @app.post("/schueler/{pid}/eltern/deaktivieren", dependencies=deps, tags=["Bezugspersonen"])
    def eltern_deaktivieren(pid: int, probelauf: bool = Query(False), c: EscolaClient = Depends(get_client)):
        """F-07: Eltern ohne weitere aktive Kinder (und ohne andere Rolle) deaktivieren – z. B. am Austrittstag."""
        _schreib_check(probelauf)
        return _st(lambda: c.eltern_ohne_weitere_kinder(pid, deaktivieren=not probelauf))

    # ------------------------------------------------------------------ Mitarbeitende (WF-01/02)
    def _konflikt(e):
        return JSONResponse(status_code=409, content={"detail": str(e), "personen": getattr(e, "personen", [])})

    @app.post("/mitarbeitende", dependencies=deps, tags=["Mitarbeitende"], status_code=201)
    def mitarbeitende_einstellen(body: NeueMitarbeitende, probelauf: bool = Query(False),
                                 c: EscolaClient = Depends(get_client)):
        """Einstellen in einem Schritt: prüfen (AHV, Schulmail frei), anlegen, Rollen, Felder, AHV, Schulmail."""
        _schreib_check(probelauf)
        try:
            return c.mitarbeiter_einstellen(body.nachname, body.vorname, body.geschlecht, body.schulhaus, body.rolle,
                                            body.rollen_ids, body.ahv, body.felder, body.schulmail,
                                            body.trotz_duplikat, probelauf)
        except KonfliktFehler as e:
            return _konflikt(e)
        except ValueError as e:
            raise HTTPException(400, str(e))

    @app.get("/suche/personen", dependencies=deps, tags=["Mitarbeitende"])
    def personen_suche(ahv: str | None = None, email: str | None = None, refresh: bool = Query(False),
                       c: EscolaClient = Depends(get_client)):
        """Personen (aktiv + inaktiv) mit dieser AHV-Nummer oder E-Mail. Erster Aufruf dauert (liest alle Personen)."""
        try:
            return c.personen_suchen(ahv, email, refresh)
        except ValueError as e:
            raise HTTPException(400, str(e))

    @app.get("/hilfe/schulmail", tags=["Mitarbeitende"], dependencies=deps)
    def hilfe_schulmail(vorname: str, nachname: str):
        """Schulmail nach Regel bilden (ohne Escola-Zugriff)."""
        from .personen import schulmail, FeldFehler
        try:
            return {"email": schulmail(vorname, nachname)}
        except FeldFehler as e:
            raise HTTPException(400, str(e))

    @app.put("/personen/{pid}/ahv", dependencies=deps, tags=["Mitarbeitende"])
    def person_ahv(pid: int, body: AhvDaten, probelauf: bool = Query(False), c: EscolaClient = Depends(get_client)):
        """AHV-Nummer setzen (Prüfziffer, darf keiner anderen Person gehören)."""
        _schreib_check(probelauf)
        try:
            return c.ahv_setzen(pid, body.ahv, body.ueberschreiben, probelauf=probelauf)
        except KonfliktFehler as e:
            return _konflikt(e)
        except ValueError as e:
            raise HTTPException(400, str(e))

    @app.post("/personen/{pid}/schulmail", dependencies=deps, tags=["Mitarbeitende"])
    def person_schulmail(pid: int, probelauf: bool = Query(False), c: EscolaClient = Depends(get_client)):
        """Schulmail aus Vor-/Nachname bilden, auf Doppelte prüfen und als E-Mail (Geschäft) setzen."""
        _schreib_check(probelauf)
        try:
            return c.schulmail_setzen(pid, probelauf=probelauf)
        except KonfliktFehler as e:
            return _konflikt(e)
        except ValueError as e:
            raise HTTPException(400, str(e))

    @app.post("/personen/{pid}/austritt", dependencies=deps, tags=["Mitarbeitende"])
    def person_austritt(pid: int, body: PersonAustritt, c: EscolaClient = Depends(get_client)):
        """Austritt von Mitarbeitenden erfassen (Austrittsdatum, optional Wegzug, optional sofort deaktivieren)."""
        _schreib_check()
        try:
            return c.person_austritt(pid, body.datum, body.wegzugsdatum, body.wegzugsgemeinde, body.sofort_deaktivieren,
                                     rollen_ausgetreten=body.rollen_ausgetreten)
        except KonfliktFehler as e:
            return _konflikt(e)
        except ValueError as e:
            raise HTTPException(400, str(e))

    @app.post("/personen/{pid}/rollen/ausgetreten", dependencies=deps, tags=["Mitarbeitende"])
    def person_rollen_ausgetreten(pid: int, probelauf: bool = Query(False), c: EscolaClient = Depends(get_client)):
        """Alle zuordenbaren Rollen durch die Rolle „Ausgetreten“ ersetzen (Austritt Mitarbeitende, F-03)."""
        _schreib_check(probelauf)
        try:
            return c.rollen_ausgetreten(pid, probelauf)
        except KonfliktFehler as e:
            return _konflikt(e)
        except ValueError as e:
            raise HTTPException(400, str(e))

    @app.get("/lehrpersonen/{lp_id}/einsatz", dependencies=deps, tags=["Mitarbeitende"])
    def lehrperson_einsatz(lp_id: int, c: EscolaClient = Depends(get_client)):
        """Klassenlehrperson-Plätze, Fach-Zuteilungen und Stundenplan-Einträge einer Lehrperson (für den Austritt)."""
        return c.lehrperson_einsatz(lp_id)

    @app.get("/rollen", dependencies=deps, tags=["Rollen"])
    def rollen_liste(nur_neue: bool = Query(False, description="nur Rollen, die nach dem 14.11.2026 dazugekommen sind"),
                     format: Format = F, refresh: bool = R, c: EscolaClient = Depends(get_client)):
        """Alle Escola-Rollen (ID, Name, Typ, Schulhaus). `neu: true` = nicht in der Liste vom 14.11.2026,
        `zuordenbar: true` = kann über PATCH /personen/{id}/rollen vergeben werden."""
        rows = [r for r in c.rollen(refresh) if not nur_neue or r["neu"]]
        return out(rows, format, "rollen")

    @app.get("/personen/{pid}/rollen", dependencies=deps, tags=["Rollen"])
    def person_rollen(pid: int, alle: bool = Query(False, description="auch nicht zugewiesene Rollen zeigen"),
                      c: EscolaClient = Depends(get_client)):
        """Rollen einer Person."""
        try:
            r = c.person_rollen(pid)
        except KeyError as e:
            raise HTTPException(404, str(e))
        return r if alle else [x for x in r if x["zugewiesen"]]

    @app.patch("/personen/{pid}/rollen", dependencies=deps, tags=["Rollen"])
    def person_rollen_aendern(pid: int, body: RollenAenderung, probelauf: bool = False,
                              c: EscolaClient = Depends(get_client)):
        """Einer Person eine oder mehrere Rollen zuweisen bzw. entziehen.
        Erlaubt: Lehrpersonen und Schulleitung (je Schulhaus) sowie alle eigenen Rollen (Personengruppen).
        Alle anderen eingebauten Rollen sind nur lesbar."""
        _schreib_check(probelauf)
        try:
            res = c.person_rollen_setzen(pid, body.hinzufuegen, body.entfernen, probelauf)
        except KeyError as e:
            raise HTTPException(404, str(e))
        except ValueError as e:
            raise HTTPException(400, str(e))
        if res.get("fehler"):
            return JSONResponse(status_code=422, content=res)
        return res

    def _aktiv(c, pid, aktiv):
        _schreib_check()
        try:
            return c.person_aktiv_setzen(pid, aktiv)
        except RuntimeError as e:
            raise HTTPException(409, str(e))

    @app.post("/personen/{pid}/deaktivieren", dependencies=deps, tags=["Personen"])
    def person_deaktivieren(pid: int, c: EscolaClient = Depends(get_client)):
        """Person deaktivieren (kein Login mehr, nicht mehr in den aktiven Listen). Umkehrbar mit /aktivieren."""
        return _aktiv(c, pid, False)

    @app.post("/personen/{pid}/aktivieren", dependencies=deps, tags=["Personen"])
    def person_aktivieren(pid: int, c: EscolaClient = Depends(get_client)):
        """Deaktivierte Person wieder aktivieren."""
        return _aktiv(c, pid, True)

    @app.get("/personen/{pid}", dependencies=deps, tags=["Personen"])
    def personen_detail(pid: int, abschnitte: str | None = None, optionen: bool = False,
                        format: Format = F, c: EscolaClient = Depends(get_client)):
        """Alle Felder einer beliebigen Person (Lehrperson, Mitarbeitende, Eltern …)."""
        return _detail(c, pid, "allActive", abschnitte, optionen, format)

    @app.patch("/personen/{pid}", dependencies=deps, tags=["Personen"], summary="Felder einer Person ändern (nur Genanntes)")
    def personen_schreiben(pid: int, body: Aenderung, probelauf: bool = False, c: EscolaClient = Depends(get_client)):
        return _schreiben(c, pid, "allActive", body, probelauf)

    @app.get("/export", dependencies=deps, tags=["Stundenplan"])
    def export(refresh: bool = R, c: EscolaClient = Depends(get_client)):
        """Alles in einem JSON-Dokument (für einen kompletten Import)."""
        return {
            "klassen": c.klassen(refresh), "faecher": c.faecher(refresh), "lehrpersonen": c.lehrpersonen(refresh),
            "raeume": c.raeume(refresh), "raster": c.raster(refresh), "eintraege": c.eintraege(refresh),
        }

    from .themen import anwenden as _themen_anwenden
    _themen_anwenden(app)
    _plugin_json_einbinden(app)
    return app


# Plugin-Beschreibung für Testplattform und Intranet (GET /plugin.json, #42). Fehlt shared/ (z. B. im Docker-Image),
# entfällt /plugin.json; die Testplattform erzeugt die Beschreibung dann selbst aus /openapi.json.
def _plugin_json_einbinden(app) -> None:
    import sys
    wurzel = str(Path(__file__).resolve().parents[3])
    if wurzel not in sys.path:
        sys.path.append(wurzel)
    try:
        from shared.plugin_export import einbinden
    except ImportError:
        return
    einbinden(app, Path(__file__).resolve().parents[1])


app = create_app()
