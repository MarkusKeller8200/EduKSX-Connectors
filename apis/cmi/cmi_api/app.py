"""CMI-API: verbindet IDA, CONNECT und weitere EduKSX-Module mit CMI (CM Informatik AG, CMI Schule / CMI Cloud).

Grundfunktionen (analog zur Escola-API):
- Kontakte synchronisieren bzw. anlegen
- Schüler- und Mitarbeitenden-/Lehrpersonen-Dossiers erstellen
- Schüler:innen in Klassen einteilen und umteilen
- Dokumente in ein Dossier hochladen

Lesen ist immer erlaubt. Schreiben nur mit CMI_SCHREIBEN=1 und API-Key; jeder schreibende Aufruf kennt
`?probelauf=true`, prüft vor dem Schreiben (Duplikate, Eindeutigkeit) und liest danach zur Kontrolle neu.
Löschen wird nicht angeboten. Regeln: docs/konventionen.md.

Start:  uvicorn cmi_api.app:app --port 8082
"""
from __future__ import annotations

import csv
import hashlib
import io
import json
import os
import re
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Literal

from fastapi import Depends, FastAPI, File, Form, Header, HTTPException, Query, Response, UploadFile
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from .client import (LESBAR, CMIClient, CMIConfig, CMIFehler, NichtGefunden, SessionAbgelaufen, guid_von, ref,
                     rendition)

PRAEFIX = "CMI_"
VERSION = json.loads((Path(__file__).resolve().parent.parent / "api.json").read_text(encoding="utf-8"))["version"]
API_KEY = os.environ.get(PRAEFIX + "API_KEY", "")
SCHREIBEN = os.environ.get(PRAEFIX + "SCHREIBEN", "0") == "1"

Format = Literal["json", "csv"]
DossierArt = Literal["schueler", "personal", "klasse"]


def _env(name: str, standard: str = "") -> str:
    return os.environ.get(PRAEFIX + name, standard)


@dataclass
class Einstellungen:
    """Fachliche Einstellungen des CMI-Mandanten (alle ZU PRÜFEN mit CM Informatik / CMI-Verantwortlichen)."""
    kontakt_vorlage: str = ""
    kontakt_typ: str = ""
    # Dossiers: Vorlage (Pfad, ?Vorlage=) und Typname (typeName) je Art
    schueler_vorlage: str = ""
    schueler_typ: str = ""
    personal_vorlage: str = ""
    personal_vorlagen: dict | None = None   # Standort → Vorlage, z. B. Hinterbirch/Mettmenriet
    personal_typ: str = ""
    klasse_typ: str = ""
    klasse_vorlagen: dict | None = None      # Standort → Vorlage Schulklassendossier
    klasse_extern_typ: str = ""
    klasse_extern_vorlage: str = ""
    dossier_zugriff: str = "Restriktiv"   # Offen | Restriktiv – Personendossiers standardmässig restriktiv
    geschaeftseigner: str = ""            # GUID, falls die Vorlage keinen Eigner setzt
    # Verknüpfung Kontakt ↔ Dossier (optional): Entität und Feldnamen
    beteiligung_entitaet: str = ""
    beteiligung_rolle: str = ""
    # Klassenzuteilung (CMI Schule): Entität und Feldnamen; leer = nicht eingerichtet (501)
    # Schullaufbahn (CMI Schule, Erkundung 25.11.2026): Lernendendossier → Schullaufbahn → Klassenzuteilung
    # Lernende → Klassenstufe («Teilklasse») → Schulklassendossier. Entitätsnamen der offiziellen API ZU PRÜFEN.
    lb_entitaet: str = "Schullaufbahn"
    kz_entitaet: str = "KlassenzuteilungLernende"
    stufe_entitaet: str = "Teilklasse"
    # Dokumente
    upload_art: Literal["rendition", "checkin"] = "rendition"
    max_mb: float = 50.0


def _vorlagen_map(text: str) -> dict:
    """«Hinterbirch=Pfad;Mettmenriet=Pfad» → {standort: vorlage}."""
    aus = {}
    for teil in text.split(";"):
        k, _, v = teil.partition("=")
        if k.strip() and v.strip():
            aus[k.strip().lower()] = v.strip()
    return aus


def einstellungen_aus_env() -> Einstellungen:
    return Einstellungen(
        kontakt_vorlage=_env("KONTAKT_VORLAGE"), kontakt_typ=_env("KONTAKT_TYP"),
        schueler_vorlage=_env("DOSSIER_SCHUELER_VORLAGE"), schueler_typ=_env("DOSSIER_SCHUELER_TYP"),
        personal_vorlage=_env("DOSSIER_PERSONAL_VORLAGE"), personal_typ=_env("DOSSIER_PERSONAL_TYP"),
        personal_vorlagen=_vorlagen_map(_env("DOSSIER_PERSONAL_VORLAGEN")),
        klasse_typ=_env("DOSSIER_KLASSE_TYP"), klasse_vorlagen=_vorlagen_map(_env("DOSSIER_KLASSE_VORLAGEN")),
        klasse_extern_typ=_env("DOSSIER_KLASSE_EXTERN_TYP"), klasse_extern_vorlage=_env("DOSSIER_KLASSE_EXTERN_VORLAGE"),
        dossier_zugriff=_env("DOSSIER_ZUGRIFF", "Restriktiv"),
        geschaeftseigner=_env("DOSSIER_EIGNER"),
        beteiligung_entitaet=_env("BETEILIGUNG_ENTITAET"), beteiligung_rolle=_env("BETEILIGUNG_ROLLE"),
        lb_entitaet=_env("SCHULLAUFBAHN_ENTITAET", "Schullaufbahn"),
        kz_entitaet=_env("KLASSENZUTEILUNG_ENTITAET", "KlassenzuteilungLernende"),
        stufe_entitaet=_env("KLASSENSTUFE_ENTITAET", "Teilklasse"),
        upload_art=_env("UPLOAD_ART", "rendition"), max_mb=float(_env("MAX_MB", "50")),  # type: ignore[arg-type]
    )


def config_aus_env() -> CMIConfig:
    cfg = CMIConfig(
        mandant=_env("MANDANT"), token=_env("TOKEN"), entra_tenant_id=_env("ENTRA_TENANT_ID"),
        client_id=_env("CLIENT_ID"), client_secret=_env("CLIENT_SECRET"), timeout=float(_env("TIMEOUT", "60")),
        suche_als_json=_env("SUCHE_ALS_JSON", "1") == "1")
    if _env("BASE_URL"):
        cfg.base_url = _env("BASE_URL")
    if _env("SCOPE"):
        cfg.scope = _env("SCOPE")
    if _env("TENTAQL_GLEICH"):
        cfg.tentaql_gleich = _env("TENTAQL_GLEICH")
    if _env("TENTAQL_UND"):
        cfg.tentaql_und = _env("TENTAQL_UND")
    return cfg


_client: CMIClient | None = None
E = einstellungen_aus_env()


def client() -> CMIClient:
    global _client
    if _client is None:
        _client = CMIClient(config_aus_env())
    if not _client.konfiguriert:
        raise HTTPException(501, f"CMI nicht eingerichtet ({PRAEFIX}MANDANT und Anmeldung setzen, siehe .env.example)")
    return _client


def api_key_pruefen(x_api_key: str | None = Header(None)):
    if API_KEY and x_api_key != API_KEY:
        raise HTTPException(401, "X-API-Key fehlt oder ist falsch")


def schreib_check(probelauf: bool = False):
    if probelauf:
        return
    if not SCHREIBEN:
        raise HTTPException(403, f"Schreiben ist deaktiviert ({PRAEFIX}SCHREIBEN=1 setzen)")
    if not API_KEY:
        raise HTTPException(403, f"Zum Schreiben muss {PRAEFIX}API_KEY gesetzt sein")


app = FastAPI(title="CMI-API", version=VERSION, dependencies=[Depends(api_key_pruefen)],
              description="CMI Schule / CMI Cloud: Kontakte synchronisieren, Schüler- und Personaldossiers, "
                          "Klassenzuteilung, Dokumente hochladen. Schreiben mit `?probelauf=true` testen.")


@app.exception_handler(SessionAbgelaufen)
def _abgelaufen(_, e):
    return JSONResponse({"detail": str(e)}, status_code=401)


@app.exception_handler(NichtGefunden)
def _fehlt(_, e):
    return JSONResponse({"detail": f"In CMI nicht gefunden: {e}"}, status_code=404)


@app.exception_handler(CMIFehler)
def _cmi_fehler(_, e: CMIFehler):
    status = 409 if e.status == 409 else 502 if e.status >= 500 else 400
    return JSONResponse({"detail": f"CMI: {e}", "status_cmi": e.status}, status_code=status)


# ================================================================ Hilfen

def _norm(v: Any) -> Any:
    if v in (None, ""):
        return None
    if isinstance(v, str):
        v = v.strip()
        if len(v) >= 10 and v[4] == "-" and v[7] == "-" and v[:4].isdigit():
            return v[:10]  # Datum: «2012-03-04T00:00:00» == «2012-03-04»
    return v


def _flach(d: dict, praefix: str = "") -> dict:
    aus = {}
    for k, v in d.items():
        if isinstance(v, dict):
            aus[praefix + k] = v.get("displayName") or v.get("guid")
        elif not isinstance(v, list):
            aus[praefix + k] = v
    return aus


def _antwort(daten: list[dict], format: Format, name: str):
    if format != "csv":
        return daten
    buf = io.StringIO()
    zeilen = [_flach(d) for d in daten]
    if zeilen:
        spalten: list[str] = []
        for z in zeilen:
            spalten += [k for k in z if k not in spalten]
        w = csv.DictWriter(buf, fieldnames=spalten, delimiter=";", extrasaction="ignore")
        w.writeheader()
        w.writerows(zeilen)
    return Response("﻿" + buf.getvalue(), media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition": f'attachment; filename="cmi_{name}.csv"'})


def _konflikt(meldung: str, betroffene: list) -> HTTPException:
    return HTTPException(409, {"meldung": meldung, "betroffene": betroffene})


def _typ(art: str) -> str:
    return {"schueler": E.schueler_typ, "personal": E.personal_typ, "klasse": E.klasse_typ}[art]


def _vorlage(art: str) -> str:
    return {"schueler": E.schueler_vorlage, "personal": E.personal_vorlage}.get(art, "")


def _suche(c: CMIClient, entitaet: str, **bedingungen) -> list[dict]:
    bed = {k: v for k, v in bedingungen.items() if v not in (None, "")}
    if not bed:
        raise HTTPException(400, "Suche braucht mindestens eine Bedingung")
    return c.suchen(entitaet, c.gleich(**bed))


def _kontakt_per_fremdkey(c: CMIClient, fremdkey: str) -> list[dict]:
    return _suche(c, "Kontakt", fremdkey=fremdkey, typeName=E.kontakt_typ or None)


def _dossiers_per_fremdkey(c: CMIClient, art: str, fremdkey: str) -> list[dict]:
    return _suche(c, "Geschaeft", schluesselFremdsystem=fremdkey, typeName=_typ(art) or None)


# ================================================================ Status, Mandanten, freie Suche

@app.get("/status", tags=["Status"])
def status():
    c = _client or CMIClient(config_aus_env())
    return {"ok": True, "version": VERSION, "konfiguriert": c.konfiguriert, "mandant": c.cfg.mandant or None,
            "schreiben": SCHREIBEN, "schuetzenswert": SCHUETZENSWERT and bool(API_KEY), "aufrufe_cmi": {"lesen": c.zaehler.lesen, "schreiben": c.zaehler.schreiben},
            "eingerichtet": {
                "dossier_schueler": bool(E.schueler_vorlage), "dossier_personal": bool(E.personal_vorlage),
                "klassen": bool(E.klasse_typ), "klassenzuteilung": bool(E.klasse_typ and E.schueler_typ),
                "beteiligung": bool(E.beteiligung_entitaet), "upload_art": E.upload_art}}


@app.get("/tenants", tags=["Status"], summary="CMI-Mandanten, auf die die Anmeldung Zugriff hat")
def tenants():
    return client().mandanten()


@app.get("/suche/{entitaet}", tags=["Status"],
         summary="Freie Suche mit TentaQl (nur lesen) – zum Erkunden des Mandanten")
def suche(entitaet: str, tentaql: str = Query(..., min_length=1), format: Format = "json"):
    if entitaet not in LESBAR:
        raise HTTPException(400, f"Entität nicht erlaubt; möglich: {', '.join(LESBAR)}")
    return _antwort(client().suchen(entitaet, tentaql), format, entitaet.lower())


# ================================================================ Kontakte

# Felder wie in der CMI-Weboberfläche (Erkundung 25.11.2026, Schreiben am Testkontakt _TEST geprüft)
KONTAKT_TEXT = ("anrede", "briefanrede", "titel", "name", "vorname", "organisation", "funktion", "email", "email2",
                "natel", "telefonPrivat", "telefonGeschaeft", "faxPrivat", "faxGeschaeft", "homepage",
                "unternehmensId", "unternehmensIdKategorie", "geburtsdatum", "rufname")
KONTAKT_BOOL = ("mitarbeiter", "inaktiv")
KONTAKT_FELDER = KONTAKT_TEXT + KONTAKT_BOOL + ("subjektart", "kategorie", "geschlecht")
KONTAKT_LEERBAR = KONTAKT_TEXT + ("subjektart", "kategorie", "geschlecht")
KONTAKT_PFLICHT_BOOL = ("inaktiv", "mitarbeiter", "istPubliziert", "googleAuthKonfiguriert", "behindert",
                        "erhoehterBetreuungsbedarf", "aufenthaltUnbekannt")
ADRESS_TEXT = ("strasse", "plz", "ort")
ADRESS_VERWEISE = ("adressart", "adresskategorie", "land")


class AdresseEingabe(BaseModel):
    adressart: str | None = Field(None, description="GUID der Adressart (z. B. Privat-, Geschäfts-, Hauptadresse); "
                                                    "bestimmt, welche bestehende Adresse geändert wird")
    strasse: str | None = None
    plz: str | None = None
    ort: str | None = None
    land: str | None = Field(None, description="GUID des Landes")
    adresskategorie: str | None = Field(None, description="GUID der Adresskategorie")
    gueltig_von: date | None = None
    gueltig_bis: date | None = None
    inaktiv: bool | None = None


class KontaktEingabe(BaseModel):
    fremdkey: str = Field(..., min_length=1, description="Schlüssel aus dem Quellsystem (z. B. Escola-ID), "
                                                         "wird in CMI als `fremdkey` geführt")
    anrede: str | None = None
    briefanrede: str | None = None
    titel: str | None = None
    name: str | None = None
    vorname: str | None = None
    organisation: str | None = None
    funktion: str | None = None
    email: str | None = Field(None, description="E-Mail geschäftlich")
    email2: str | None = Field(None, description="E-Mail privat")
    natel: str | None = None
    telefonPrivat: str | None = None
    telefonGeschaeft: str | None = None
    faxPrivat: str | None = None
    faxGeschaeft: str | None = None
    homepage: str | None = None
    unternehmensId: str | None = None
    unternehmensIdKategorie: str | None = None
    geburtsdatum: str | None = Field(None, description="JJJJ-MM-TT")
    rufname: str | None = None
    geschlecht: str | None = Field(None, description="GUID des Geschlechts (Stammdaten «Geschlecht»: männlich, weiblich)")
    mitarbeiter: bool | None = None
    inaktiv: bool | None = None
    subjektart: Literal["Natürlich", "Juristisch"] | None = None
    kategorien: list[str] | None = Field(None, description="GUIDs der Personenkategorien (ersetzt die bisherigen)")
    leeren: list[str] = Field([], description=f"Felder, die geleert werden: {', '.join(KONTAKT_LEERBAR)}")
    adresse: AdresseEingabe | None = None
    adressen: list[AdresseEingabe] = Field([], max_length=10)


class KontaktListe(BaseModel):
    kontakte: list[KontaktEingabe] = Field(..., min_length=1, max_length=500)


@app.get("/kontakte", tags=["Kontakte"], summary="Kontakte suchen (fremdkey, name, email oder TentaQl)")
def kontakte(fremdkey: str | None = None, name: str | None = None, vorname: str | None = None,
             email: str | None = None, tentaql: str | None = None, format: Format = "json"):
    c = client()
    daten = c.suchen("Kontakt", tentaql) if tentaql else _suche(c, "Kontakt", fremdkey=fremdkey, name=name,
                                                                 vorname=vorname, email=email)
    return _antwort(daten, format, "kontakte")


@app.get("/kontakte/{guid}", tags=["Kontakte"])
def kontakt(guid: str):
    return client().lesen("Kontakt", guid)


# ---------------------------------------------------------------- Kontakt vollständig lesen
# Beziehungen eines Kontakts, wie sie die CMI-Weboberfläche zeigt (Erkundung 25.11.2026, apis/cmi/ERKUNDUNG.md).
# Feld im Kontakt → (Entität für GET /<Entität>/{guid}, Bereich in der Antwort, besonders schützenswert).
# Entitätsnamen der offiziellen API ZU PRÜFEN; enthält ein Verweis eine `url` auf denselben Server, gilt diese.
KONTAKT_BEZIEHUNGEN: dict[str, tuple[str, str, bool]] = {
    "adressen": ("Adresse", "adressen", False),
    "dossierkontakte": ("Dossierkontakt", "dossiers", False),
    "beteiligungen": ("Beteiligung", "dossiers", False),
    "gebiete": ("Gebiet", "schule", False),
    "beziehungenA": ("Beziehung", "bezugspersonen", False),
    "beziehungenB": ("Beziehung", "bezugspersonen", False),
    "kommunikationsDetails": ("Kommunikationsdetail", "notfallkontakte", False),
    "haushaltsmitgliedschaften": ("Haushaltsmitgliedschaft", "haushalt", False),
    "fremdKeyMappings": ("FremdkeyMapping", "fremdkey_mappings", False),
    "externeBenutzer": ("Fremdbenutzer", "externe_benutzer", False),
    "adressdatensperre": ("Adressdatensperre", "adressdatensperre", False),
    "zahlungsinformationen": ("Zahlungsinformation", "zahlungsinformationen", True),
    "medizinischeInformationen": ("MedizinischerInformationseintrag", "medizinische_informationen", True),
}
SCHUETZENSWERT = os.environ.get(PRAEFIX + "SCHUETZENSWERT", "0") == "1"
_INTERN = {"access", "metas", "iconId", "checkOutInfo_MF", "previewUrl", "editUrl", "downloadUrl"}


def _verweise(wert: Any) -> list[str]:
    """Verweisliste aus CMI: [{guid,…}], ["guid"] oder «g1;g2» (Weboberfläche)."""
    if not wert:
        return []
    if isinstance(wert, str):
        return [g for g in wert.split(";") if g.strip()]
    if isinstance(wert, dict):
        wert = [wert]
    return [g for g in (guid_von(v) for v in wert) if g]


def _anzeige(v: Any) -> Any:
    """Verweis bzw. Auswahlwert lesbar machen: {displayName}/{text} → Text."""
    if isinstance(v, dict):
        if "displayName" in v or "text" in v:
            return v.get("displayName") or v.get("text")
        if set(v) <= {"start", "end"}:
            return _zeitraum(v)
    return v


def _zeitraum(v: Any) -> dict:
    """gueltigVonBis/dauer: {start:{value}, end:{value}} oder «von - bis» → {von, bis} (Datum)."""
    if isinstance(v, dict):
        def tag(x):
            x = x.get("value") if isinstance(x, dict) else x
            return _norm(x)
        return {"von": tag(v.get("start")), "bis": tag(v.get("end"))}
    m = re.fullmatch(r"\s*(\d\d\.\d\d\.\d{4})?\s*-\s*(\d\d\.\d\d\.\d{4})?\s*", v) if isinstance(v, str) else None
    if m:
        return {"von": _iso(m.group(1)), "bis": _iso(m.group(2))}
    return {"von": _iso(v) if isinstance(v, str) else _norm(v), "bis": None}


def _iso(t: str | None) -> str | None:
    """«01.01.2026» bzw. «2026-01-01T…» → «2026-01-01»."""
    t = (t or "").strip()
    if len(t) >= 10 and t[2] == "." and t[5] == ".":
        return f"{t[6:10]}-{t[3:5]}-{t[0:2]}"
    return _norm(t)


def _bereinigt(o: dict) -> dict:
    return {k: (_anzeige(v) if not isinstance(v, list) else v) for k, v in o.items() if k not in _INTERN}


def _adresse_aus(a: dict) -> dict:
    zr = _zeitraum(a.get("gueltigVonBis"))
    return {"guid": a.get("guid"), "adressart": _anzeige(a.get("adressart")), "strasse": a.get("strasse"),
            "plz": a.get("plz") or a.get("pLZ"), "ort": a.get("ort"), "land": _anzeige(a.get("land")),
            "gueltig_von": zr["von"], "gueltig_bis": zr["bis"], "inaktiv": a.get("inaktiv")}


def _dossier_aus(d: dict) -> dict:
    dossier = d.get("computedDossier") or d.get("geschaeft") or d.get("dossier")
    zr = _zeitraum(d.get("dauer"))
    return {"guid": d.get("guid"), "rolle": _anzeige(d.get("rolle")),
            "dossier_guid": guid_von(dossier), "dossiertitel": d.get("dossiertitel") or _anzeige(dossier),
            "laufnummer": d.get("dossierLaufnummer"), "dossiertyp": _anzeige(d.get("dossierTyp")),
            "status": _anzeige(d.get("dossierStatus")), "von": zr["von"], "bis": zr["bis"]}


def _verweis_lesen(c: CMIClient, entitaet: str, verweis: Any) -> dict:
    url = verweis.get("url") if isinstance(verweis, dict) else None
    basis = c.cfg.base_url.rstrip("/") + "/"
    if url and url.startswith(basis):
        return c._senden("GET", url[len(basis):]).json()
    return c.lesen(entitaet, guid_von(verweis) or str(verweis))


def kontakt_vollstaendig_lesen(c: CMIClient, guid: str, schuetzenswert: bool) -> dict:
    k = c.lesen("Kontakt", guid)
    aus: dict[str, Any] = {
        "kontakt": {f: _anzeige(v) for f, v in k.items()
                    if f not in KONTAKT_BEZIEHUNGEN and f not in _INTERN and not isinstance(v, list)},
        "adressen": [], "dossiers": [], "schule": [], "bezugspersonen": [], "notfallkontakte": [], "haushalt": [],
        "fremdkey_mappings": [], "externe_benutzer": [], "adressdatensperre": [],
        "geschuetzt": {}, "nicht_lesbar": [], "weitere_beziehungen": {}}
    for feld, wert in k.items():
        if feld in KONTAKT_BEZIEHUNGEN:
            entitaet, bereich, heikel = KONTAKT_BEZIEHUNGEN[feld]
            verweise = wert if isinstance(wert, list) else _verweise(wert)
            if heikel:
                aus["geschuetzt"][bereich] = {"anzahl": len(verweise)}
                if not schuetzenswert:
                    continue
                aus["geschuetzt"][bereich]["eintraege"] = []
            for v in verweise:
                try:
                    o = _verweis_lesen(c, entitaet, v)
                except (CMIFehler, NichtGefunden) as e:
                    aus["nicht_lesbar"].append({"beziehung": feld, "guid": guid_von(v) or v, "fehler": str(e)})
                    continue
                eintrag = (_adresse_aus(o) if bereich == "adressen" else
                           _dossier_aus(o) if bereich == "dossiers" else _bereinigt(o))
                if heikel:
                    aus["geschuetzt"][bereich]["eintraege"].append(eintrag)
                else:
                    aus[bereich].append(eintrag)
        elif isinstance(wert, list) and wert and all(isinstance(x, dict) and "guid" in x for x in wert):
            # unbekannte Beziehung: nur Verweise zeigen, nicht nachladen
            aus["weitere_beziehungen"][feld] = [{"guid": x.get("guid"), "name": x.get("displayName")} for x in wert]
    aus["adressen"].sort(key=lambda a: (bool(a["inaktiv"]), a["adressart"] or ""))
    return aus


@app.get("/kontakte/{guid}/vollstaendig", tags=["Kontakte"],
         summary="Kontakt mit Adressen, Dossiers, Schule, Bezugspersonen, Notfallkontakten, Haushalt, techn. Details")
def kontakt_vollstaendig(guid: str):
    return kontakt_vollstaendig_lesen(client(), guid, SCHUETZENSWERT and bool(API_KEY))


@app.get("/kontakte/{guid}/adressen", tags=["Kontakte"], summary="Adressen eines Kontakts (aktive zuerst)")
def kontakt_adressen(guid: str, nur_aktive: bool = False, format: Format = "json"):
    adr = kontakt_vollstaendig_lesen(client(), guid, False)["adressen"]
    return _antwort([a for a in adr if not (nur_aktive and a["inaktiv"])], format, "adressen")


@app.get("/kontakte/{guid}/dossiers", tags=["Kontakte"],
         summary="Dossiers, an denen der Kontakt beteiligt ist (Rolle, Dossiertyp, Status)")
def kontakt_dossiers(guid: str, format: Format = "json"):
    return _antwort(kontakt_vollstaendig_lesen(client(), guid, False)["dossiers"], format, "dossiers")


def _adressen_eingabe(k: KontaktEingabe) -> list[AdresseEingabe]:
    return ([k.adresse] if k.adresse else []) + list(k.adressen)


def _kontakt_eingabe(k: KontaktEingabe) -> dict:
    eingabe: dict[str, Any] = {f: getattr(k, f) for f in KONTAKT_TEXT + KONTAKT_BOOL + ("subjektart", "geschlecht")
                               if getattr(k, f) is not None}
    if k.kategorien is not None:
        eingabe["kategorie"] = sorted(k.kategorien)
    for f in k.leeren:
        eingabe[f] = [] if f == "kategorie" else None
    return eingabe


def _kontakt_vergleich(alt: dict, f: str) -> Any:
    v = alt.get(f)
    if f == "kategorie":
        return sorted(_verweise(v))
    if f == "subjektart":
        return _anzeige(v) or None
    if f == "geschlecht":
        return guid_von(v)
    return _norm(v)


def _adress_ist(a: dict) -> dict:
    zr = _zeitraum(a.get("gueltigVonBis"))
    return {"strasse": a.get("strasse"), "plz": a.get("plz") or a.get("pLZ"), "ort": a.get("ort"),
            "adressart": guid_von(a.get("adressart")), "adresskategorie": guid_von(a.get("adresskategorie")),
            "land": guid_von(a.get("land")), "gueltig_von": zr["von"], "gueltig_bis": zr["bis"],
            "inaktiv": a.get("inaktiv")}


def _adress_plan(neu: AdresseEingabe, bestehende: list[dict], vergeben: set) -> dict:
    soll = {f: (v.isoformat() if isinstance(v, date) else v) for f, v in neu.model_dump(exclude_none=True).items()}
    kandidaten = [a for a in bestehende if not a.get("inaktiv") and a["guid"] not in vergeben
                  and (neu.adressart is None or guid_von(a.get("adressart")) == neu.adressart)]
    if not kandidaten:
        return {"aktion": "anlegen", "soll": soll}
    alt = kandidaten[0]
    vergeben.add(alt["guid"])
    ist = _adress_ist(alt)
    diff = {f: [ist.get(f), v] for f, v in soll.items() if _norm(ist.get(f)) != _norm(v)}
    return {"aktion": "aendern" if diff else "unveraendert", "guid": alt["guid"], "aenderungen": diff,
            "soll": soll, "_alt": alt}


def _adress_daten(soll: dict, alt: dict | None = None) -> dict:
    """Werte für CMI: Verweise als {guid}, Gültigkeit als «TT.MM.JJJJ - TT.MM.JJJJ» (Swagger: Text; ZU PRÜFEN)."""
    d: dict[str, Any] = {f: soll[f] for f in ADRESS_TEXT + ("inaktiv",) if f in soll}
    d.update({f: ref(soll[f]) for f in ADRESS_VERWEISE if f in soll})
    if "gueltig_von" in soll or "gueltig_bis" in soll:
        ist = _adress_ist(alt) if alt else {}
        von, bis = soll.get("gueltig_von", ist.get("gueltig_von")), soll.get("gueltig_bis", ist.get("gueltig_bis"))
        d["gueltigVonBis"] = f"{_ch_datum(von)} - {_ch_datum(bis)}".strip()
    return d


def _ch_datum(iso: str | None) -> str:
    return f"{iso[8:10]}.{iso[5:7]}.{iso[:4]}" if iso else ""


def _kontakt_plan(c: CMIClient, k: KontaktEingabe, guid: str | None = None) -> dict:
    """Vergleicht Eingabe und CMI – ohne zu schreiben. Mit guid: genau dieser Kontakt."""
    eingabe = _kontakt_eingabe(k)
    treffer = [{"guid": guid}] if guid else _kontakt_per_fremdkey(c, k.fremdkey)
    plan: dict[str, Any] = {"fremdkey": k.fremdkey, "guid": None, "aktion": None, "aenderungen": {},
                            "adressen": [], "_alt": None}
    if len(treffer) > 1:
        plan["aktion"] = "konflikt"
        plan["guids"] = [t.get("guid") for t in treffer]
        return plan
    if not treffer:
        plan["aktion"] = "anlegen"
        plan["aenderungen"] = {f: [None, v] for f, v in eingabe.items() if v not in (None, [])}
        plan["adressen"] = [{"aktion": "anlegen", "soll": {f: (v.isoformat() if isinstance(v, date) else v)
                                                           for f, v in a.model_dump(exclude_none=True).items()}}
                            for a in _adressen_eingabe(k)]
        return plan
    alt = c.lesen("Kontakt", treffer[0]["guid"])
    plan["guid"], plan["_alt"] = alt["guid"], alt
    plan["aenderungen"] = {f: [_kontakt_vergleich(alt, f), v] for f, v in eingabe.items()
                           if _kontakt_vergleich(alt, f) != (_norm(v) if not isinstance(v, list) else v)}
    if _adressen_eingabe(k):
        bestehende = [c.lesen("Adresse", g) for g in _verweise(alt.get("adressen"))]
        vergeben: set = set()
        plan["adressen"] = [_adress_plan(a, bestehende, vergeben) for a in _adressen_eingabe(k)]
    adr_geaendert = any(a["aktion"] in ("anlegen", "aendern") for a in plan["adressen"])
    plan["aktion"] = "aendern" if plan["aenderungen"] or adr_geaendert else "unveraendert"
    return plan


def _kontakt_werte(neu_werte: dict) -> dict:
    d = dict(neu_werte)
    if "kategorie" in d:
        d["kategorie"] = [ref(g) for g in d["kategorie"] or []]
    if "geschlecht" in d:
        d["geschlecht"] = ref(d["geschlecht"])
    return d


def _kontakt_schreiben(c: CMIClient, k: KontaktEingabe, plan: dict, guid: str | None = None) -> list[dict]:
    schritte: list[dict] = []

    def schritt(name: str, fn):
        try:
            fn()
            schritte.append({"schritt": name, "ok": True})
        except (CMIFehler, NichtGefunden) as e:
            schritte.append({"schritt": name, "ok": False, "fehler": str(e)})
            raise

    neu_werte = _kontakt_werte({f: v[1] for f, v in plan["aenderungen"].items()})
    try:
        if plan["aktion"] == "anlegen":
            daten = {b: False for b in KONTAKT_PFLICHT_BOOL}
            daten.update(fremdkey=k.fremdkey, **neu_werte)
            if E.kontakt_typ:
                daten["typeName"] = E.kontakt_typ

            def anlegen():
                plan["guid"] = c.anlegen("Kontakt", daten, E.kontakt_vorlage or None)
            schritt("kontakt_anlegen", anlegen)
        elif neu_werte:
            alt = {f: v for f, v in plan["_alt"].items() if not isinstance(v, list) or f in neu_werte}
            schritt("kontakt_aendern", lambda: c.aendern("Kontakt", plan["guid"], {**alt, **neu_werte}))
        for adr in plan["adressen"]:
            if adr["aktion"] == "anlegen":
                daten_a = {"inaktiv": False, "kontakt": ref(plan["guid"]), **_adress_daten(adr["soll"])}
                schritt("adresse_anlegen", lambda d=daten_a: c.anlegen("Adresse", d))
            elif adr["aktion"] == "aendern":
                neu = _adress_daten({f: v[1] for f, v in adr["aenderungen"].items()}, adr["_alt"])
                alt = {f: v for f, v in adr["_alt"].items() if not isinstance(v, list)}
                schritt("adresse_aendern", lambda g=adr["guid"], d={**alt, **neu}: c.aendern("Adresse", g, d))
    except (CMIFehler, NichtGefunden):
        return schritte
    # Kontrolle: neu lesen und vergleichen
    kontrolle = _kontakt_plan(c, k, guid or plan["guid"])
    if kontrolle["aktion"] != "unveraendert":
        schritte.append({"schritt": "kontrolle", "ok": False, "fehler": "CMI hat nicht alles übernommen",
                         "abweichungen": kontrolle["aenderungen"] or [_sichtbar(a) for a in kontrolle["adressen"]]})
    else:
        schritte.append({"schritt": "kontrolle", "ok": True})
    return schritte


def _kontakt_pruefen(k: KontaktEingabe) -> None:
    falsch = [f for f in k.leeren if f not in KONTAKT_LEERBAR]
    ohne_art = [a for a in _adressen_eingabe(k) if not a.adressart]
    if falsch or len(ohne_art) > 1:
        raise HTTPException(400, {"meldung": f"leeren: unbekannte Felder {falsch}" if falsch else
                                  "Mehrere Adressen brauchen je eine adressart", "betroffene": [k.fremdkey]})


def _sichtbar(plan: dict) -> dict:
    aus = {k: v for k, v in plan.items() if not k.startswith("_")}
    if "adressen" in aus:
        aus["adressen"] = [{k: v for k, v in a.items() if not k.startswith("_")} for a in aus["adressen"]]
    return aus


@app.post("/kontakte/sync", tags=["Kontakte"],
          summary="Kontakte abgleichen: fehlende anlegen, geänderte Felder nachführen (Schlüssel: fremdkey)")
def kontakte_sync(body: KontaktListe, probelauf: bool = False, _=Depends(schreib_check)):
    c = client()
    doppelt = sorted({k.fremdkey for k in body.kontakte if [x.fremdkey for x in body.kontakte].count(k.fremdkey) > 1})
    if doppelt:
        raise HTTPException(400, {"meldung": "fremdkey mehrfach in der Eingabe", "betroffene": doppelt})
    for k in body.kontakte:
        _kontakt_pruefen(k)
    plaene = [_kontakt_plan(c, k) for k in body.kontakte]
    for p, k in zip(plaene, body.kontakte):
        if p["aktion"] == "anlegen" and not (k.name or k.organisation):
            raise HTTPException(400, {"meldung": "Neuer Kontakt braucht name oder organisation",
                                      "betroffene": [k.fremdkey]})
    konflikte = [{"fremdkey": p["fremdkey"], "guids": p["guids"]} for p in plaene if p["aktion"] == "konflikt"]
    if konflikte:
        raise _konflikt("Mehrere CMI-Kontakte mit demselben fremdkey – bitte in CMI bereinigen", konflikte)
    zusammenfassung = {a: sum(p["aktion"] == a for p in plaene) for a in ("anlegen", "aendern", "unveraendert")}
    if probelauf:
        return {"probelauf": True, "zusammenfassung": zusammenfassung, "kontakte": [_sichtbar(p) for p in plaene]}
    ergebnisse = []
    for p, k in zip(plaene, body.kontakte):
        if p["aktion"] == "unveraendert":
            ergebnisse.append({**_sichtbar(p), "schritte": []})
            continue
        ergebnisse.append({**_sichtbar(p), "schritte": _kontakt_schreiben(c, k, p)})
    vollstaendig = all(s["ok"] for e in ergebnisse for s in e["schritte"])
    antwort = {"probelauf": False, "vollstaendig": vollstaendig, "zusammenfassung": zusammenfassung,
               "kontakte": ergebnisse}
    if not vollstaendig:
        return JSONResponse(antwort, status_code=409)
    return antwort


def _einzel_antwort(plan: dict, schritte: list[dict], status_ok: int = 200):
    antwort = {"probelauf": False, "vollstaendig": all(s["ok"] for s in schritte), **_sichtbar(plan),
               "schritte": schritte}
    return JSONResponse(antwort, status_code=status_ok if antwort["vollstaendig"] else 409)


@app.post("/kontakte", tags=["Kontakte"], status_code=201,
          summary="Neuen Kontakt anlegen (mit Adressen); 409, wenn es den fremdkey schon gibt")
def kontakt_anlegen(body: KontaktEingabe, probelauf: bool = False, _=Depends(schreib_check)):
    c = client()
    _kontakt_pruefen(body)
    if not (body.name or body.organisation):
        raise HTTPException(400, "Neuer Kontakt braucht name oder organisation")
    plan = _kontakt_plan(c, body)
    if plan["aktion"] == "konflikt":
        raise _konflikt("Mehrere CMI-Kontakte mit diesem fremdkey", plan["guids"])
    if plan["aktion"] != "anlegen":
        raise _konflikt("Kontakt mit diesem fremdkey gibt es schon – ändern mit PATCH /kontakte/{guid}",
                        [plan["guid"]])
    if probelauf:
        return {"probelauf": True, **_sichtbar(plan)}
    return _einzel_antwort(plan, _kontakt_schreiben(c, body, plan), 201)


class KontaktAenderung(KontaktEingabe):
    fremdkey: str | None = Field(None, description="optional: fremdkey setzen bzw. ändern")


@app.patch("/kontakte/{guid}", tags=["Kontakte"],
           summary="Felder eines Kontakts ändern bzw. leeren, Adressen nachführen (nur Genanntes)")
def kontakt_aendern(guid: str, body: KontaktAenderung, probelauf: bool = False, _=Depends(schreib_check)):
    c = client()
    _kontakt_pruefen(body)
    k = KontaktEingabe(**{**body.model_dump(exclude={"fremdkey"}), "fremdkey": body.fremdkey or "-"})
    plan = _kontakt_plan(c, k, guid)
    if body.fremdkey and _norm(plan["_alt"].get("fremdkey")) != body.fremdkey:
        plan["aenderungen"]["fremdkey"] = [plan["_alt"].get("fremdkey"), body.fremdkey]
        plan["aktion"] = "aendern"
    if probelauf or plan["aktion"] == "unveraendert":
        return {"probelauf": probelauf, **_sichtbar(plan), "schritte": []}
    return _einzel_antwort(plan, _kontakt_schreiben(c, k, plan, guid))


# ================================================================ Dossiers

class DossierEingabe(BaseModel):
    fremdkey: str = Field(..., min_length=1, description="Schlüssel der Person aus dem Quellsystem "
                                                         "(= fremdkey des Kontakts, in CMI `schluesselFremdsystem`)")
    kontakt_guid: str | None = Field(None, description="sonst wird der Kontakt über fremdkey gesucht")
    titel: str | None = Field(None, description="Standard: «Name Vorname» (SuS mit Jahrgang)")
    beginn: date | None = Field(None, description="Standard: heute")
    bemerkung: str | None = None
    standort: str | None = Field(None, description="Personaldossier: Standort der Vorlage, z. B. Hinterbirch, "
                                                   "Mettmenriet (CMI_DOSSIER_PERSONAL_VORLAGEN)")
    geschaeftseigner: str | None = Field(None, description="GUID, sonst setzt ihn die Vorlage")


@app.get("/dossiers", tags=["Dossiers"], summary="Dossiers einer Art suchen (fremdkey oder TentaQl)")
def dossiers(art: DossierArt | None = None, fremdkey: str | None = None, titel: str | None = None,
             tentaql: str | None = None, format: Format = "json"):
    c = client()
    if tentaql:
        daten = c.suchen("Geschaeft", tentaql)
    else:
        typ = _typ(art) if art else None
        if art and not typ:
            raise HTTPException(501, f"Typname für {art}-Dossiers nicht eingerichtet "
                                     f"({PRAEFIX}DOSSIER_{art.upper()}_TYP)")
        daten = _suche(c, "Geschaeft", schluesselFremdsystem=fremdkey, titel=titel, typeName=typ)
    return _antwort(daten, format, "dossiers")


@app.get("/dossiers/{guid}", tags=["Dossiers"])
def dossier(guid: str):
    return client().lesen("Geschaeft", guid)


def _ordnerbaum(c: CMIClient, dossier_guid: str) -> list[dict]:
    g = c.lesen("Geschaeft", dossier_guid)
    alle = {guid_von(r): c.lesen("Ordner", guid_von(r)) for r in g.get("ordner") or []}
    return list(alle.values())


@app.get("/dossiers/{guid}/ordner", tags=["Dossiers"], summary="Ordner eines Dossiers mit Pfad")
def dossier_ordner(guid: str):
    ordner = _ordnerbaum(client(), guid)
    nach_guid = {o["guid"]: o for o in ordner}

    def pfad(o: dict) -> str:
        teile, seen = [o.get("titel", "")], {o["guid"]}
        p = guid_von(o.get("parent"))
        while p and p in nach_guid and p not in seen:
            seen.add(p)
            teile.insert(0, nach_guid[p].get("titel", ""))
            p = guid_von(nach_guid[p].get("parent"))
        return "/".join(teile)
    return [{"guid": o["guid"], "titel": o.get("titel"), "pfad": pfad(o)} for o in ordner]


@app.get("/dossiers/{guid}/dokumente", tags=["Dossiers"])
def dossier_dokumente(guid: str):
    return client().lesen("Geschaeft", guid).get("dokumente") or []


def _dossier_vorlage(art: str, standort: str | None) -> str:
    if art == "personal" and E.personal_vorlagen:
        if standort and standort.lower() in E.personal_vorlagen:
            return E.personal_vorlagen[standort.lower()]
        if standort or not E.personal_vorlage:
            raise HTTPException(400, f"standort muss einer sein von: {', '.join(E.personal_vorlagen)}")
    return _vorlage(art)


def _dossier_anlegen(art: Literal["schueler", "personal"], body: DossierEingabe, probelauf: bool):
    c = client()
    vorlage, typ = _dossier_vorlage(art, body.standort), _typ(art)
    if not vorlage and not typ:
        raise HTTPException(501, f"{art}-Dossier nicht eingerichtet ({PRAEFIX}DOSSIER_{art.upper()}_VORLAGE "
                                 f"bzw. _TYP setzen)")
    # Prüfen vor dem Anlegen: Kontakt vorhanden und eindeutig, noch kein Dossier
    if body.kontakt_guid:
        kontakt_daten = c.lesen("Kontakt", body.kontakt_guid)
    else:
        treffer = _kontakt_per_fremdkey(c, body.fremdkey)
        if not treffer:
            raise HTTPException(400, f"Kein CMI-Kontakt mit fremdkey {body.fremdkey} – zuerst /kontakte/sync")
        if len(treffer) > 1:
            raise _konflikt("Mehrere Kontakte mit diesem fremdkey", [t.get("guid") for t in treffer])
        kontakt_daten = c.lesen("Kontakt", treffer[0]["guid"])
    vorhanden = _dossiers_per_fremdkey(c, art, body.fremdkey)
    if vorhanden:
        raise _konflikt(f"Es gibt schon ein {art}-Dossier für diese Person",
                        [{"guid": d.get("guid"), "titel": d.get("titel")} for d in vorhanden])
    titel = body.titel or " ".join(x for x in (kontakt_daten.get("name"), kontakt_daten.get("vorname")) if x)
    if not body.titel and art == "schueler" and _norm(kontakt_daten.get("geburtsdatum")):
        titel += f" ({_norm(kontakt_daten['geburtsdatum'])[:4]})"
    daten: dict[str, Any] = {
        "titel": titel, "beginn": (body.beginn or date.today()).isoformat(),
        "schluesselFremdsystem": body.fremdkey, "zugriffsteuerung": E.dossier_zugriff,
        "geschaeftsstatus": "InBearbeitung", "lifecycleStatus": "InBearbeitung"}
    # Die CMI-Oberfläche verknüpft die Person direkt über das Feld «person» (Erkundung 25.11.2026)
    daten["person"] = ref(kontakt_daten["guid"])
    if typ:
        daten["typeName"] = typ
    if body.bemerkung:
        daten["bemerkung"] = body.bemerkung
    if body.geschaeftseigner or E.geschaeftseigner:
        daten["geschaeftseigner"] = ref(body.geschaeftseigner or E.geschaeftseigner)
    plan = {"art": art, "kontakt_guid": kontakt_daten["guid"], "vorlage": vorlage or None, "dossier": daten,
            "beteiligung": bool(E.beteiligung_entitaet)}
    if probelauf:
        return {"probelauf": True, **plan}
    schritte: list[dict] = []
    guid = None
    try:
        guid = c.anlegen("Geschaeft", daten, vorlage or None)
        schritte.append({"schritt": "dossier_anlegen", "ok": True, "guid": guid})
    except CMIFehler as e:
        schritte.append({"schritt": "dossier_anlegen", "ok": False, "fehler": str(e)})
        return JSONResponse({"probelauf": False, "vollstaendig": False, "schritte": schritte}, status_code=409)
    if E.beteiligung_entitaet:
        bet = {"kontakt": ref(kontakt_daten["guid"]), "geschaeft": ref(guid)}
        if E.beteiligung_rolle:
            bet["rolle"] = E.beteiligung_rolle
        try:
            schritte.append({"schritt": "beteiligung", "ok": True,
                             "guid": c.anlegen(E.beteiligung_entitaet, bet)})
        except (CMIFehler, NichtGefunden) as e:
            schritte.append({"schritt": "beteiligung", "ok": False, "fehler": str(e)})
    else:
        schritte.append({"schritt": "beteiligung", "ok": True, "uebersprungen": True,
                         "hinweis": "Person über das Feld «person» verknüpft"})
    neu = c.lesen("Geschaeft", guid)
    abw = {f: [neu.get(f), daten[f]] for f in ("titel", "schluesselFremdsystem") if _norm(neu.get(f)) != _norm(daten[f])}
    if guid_von(neu.get("person")) not in (None, kontakt_daten["guid"]):
        abw["person"] = [guid_von(neu.get("person")), kontakt_daten["guid"]]
    schritte.append({"schritt": "kontrolle", "ok": not abw, **({"abweichungen": abw} if abw else {})})
    antwort = {"probelauf": False, "vollstaendig": all(s["ok"] for s in schritte), "guid": guid,
               "titel": neu.get("titel"), "schritte": schritte}
    return antwort if antwort["vollstaendig"] else JSONResponse(antwort, status_code=409)


@app.post("/dossiers/schueler", tags=["Dossiers"], summary="Schülerdossier für einen Kontakt erstellen")
def schuelerdossier(body: DossierEingabe, probelauf: bool = False, _=Depends(schreib_check)):
    return _dossier_anlegen("schueler", body, probelauf)


@app.post("/dossiers/personal", tags=["Dossiers"],
          summary="Personaldossier (Mitarbeitende/Lehrperson) für einen Kontakt erstellen")
def personaldossier(body: DossierEingabe, probelauf: bool = False, _=Depends(schreib_check)):
    return _dossier_anlegen("personal", body, probelauf)


class PersonMitDossier(KontaktEingabe):
    beginn: date | None = Field(None, description="Beginn des Dossiers, Standard heute")
    bemerkung: str | None = Field(None, description="Bemerkung im Dossier")
    standort: str | None = Field(None, description="nur Mitarbeitende: Standort der Personaldossier-Vorlage")


def _person_mit_dossier(art: Literal["schueler", "personal"], body: PersonMitDossier, probelauf: bool):
    """Wie Escola POST /schueler bzw. /mitarbeitende: Kontakt anlegen (oder vorhandenen nehmen) und Dossier dazu."""
    c = client()
    k = KontaktEingabe(**body.model_dump(exclude={"beginn", "bemerkung", "standort"}))
    _kontakt_pruefen(k)
    plan = _kontakt_plan(c, k)
    if plan["aktion"] == "konflikt":
        raise _konflikt("Mehrere CMI-Kontakte mit diesem fremdkey", plan["guids"])
    if plan["aktion"] == "anlegen" and not (k.name or k.organisation):
        raise HTTPException(400, "Neuer Kontakt braucht name oder organisation")
    if not _dossier_vorlage(art, body.standort) and not _typ(art):
        raise HTTPException(501, f"{art}-Dossier nicht eingerichtet ({PRAEFIX}DOSSIER_{art.upper()}_VORLAGE bzw. _TYP)")
    vorhanden = _dossiers_per_fremdkey(c, art, k.fremdkey)
    if vorhanden:
        raise _konflikt(f"Es gibt schon ein {art}-Dossier für diese Person",
                        [{"guid": d.get("guid"), "titel": d.get("titel")} for d in vorhanden])
    dossier = DossierEingabe(fremdkey=k.fremdkey, beginn=body.beginn, bemerkung=body.bemerkung,
                             standort=body.standort, kontakt_guid=plan["guid"])
    if probelauf:
        vorlage = _dossier_vorlage(art, body.standort)
        return {"probelauf": True, "kontakt": _sichtbar(plan), "dossier": {"art": art, "vorlage": vorlage or None}}
    schritte = [] if plan["aktion"] == "unveraendert" else _kontakt_schreiben(c, k, plan)
    if not all(s["ok"] for s in schritte):
        return JSONResponse({"probelauf": False, "vollstaendig": False, "kontakt": _sichtbar(plan),
                             "schritte": schritte}, status_code=409)
    dossier.kontakt_guid = plan["guid"]
    d = _dossier_anlegen(art, dossier, False)
    d = json.loads(d.body) if isinstance(d, JSONResponse) else d
    alle = [{**s, "teil": "kontakt"} for s in schritte] + [{**s, "teil": "dossier"} for s in d.get("schritte", [])]
    antwort = {"probelauf": False, "vollstaendig": all(s["ok"] for s in alle), "kontakt_guid": plan["guid"],
               "kontakt_aktion": plan["aktion"], "dossier_guid": d.get("guid"), "titel": d.get("titel"),
               "schritte": alle}
    return JSONResponse(antwort, status_code=201 if antwort["vollstaendig"] else 409)


@app.post("/schueler", tags=["Dossiers"], status_code=201,
          summary="Schüler:in erfassen: Kontakt anlegen bzw. nachführen und Lernendendossier erstellen")
def schueler_anlegen(body: PersonMitDossier, probelauf: bool = False, _=Depends(schreib_check)):
    return _person_mit_dossier("schueler", body, probelauf)


@app.post("/mitarbeitende", tags=["Dossiers"], status_code=201,
          summary="Mitarbeitende/Lehrperson erfassen: Kontakt anlegen bzw. nachführen und Personaldossier erstellen")
def mitarbeitende_anlegen(body: PersonMitDossier, probelauf: bool = False, _=Depends(schreib_check)):
    return _person_mit_dossier("personal", body, probelauf)


# ================================================================ Klassen und Klassenzuteilung

def _kz_check():
    if not (E.klasse_typ and E.schueler_typ):
        raise HTTPException(501, f"Klassenzuteilung braucht {PRAEFIX}DOSSIER_KLASSE_TYP und "
                                 f"{PRAEFIX}DOSSIER_SCHUELER_TYP")


def _klassen(c: CMIClient) -> list[dict]:
    if not E.klasse_typ:
        raise HTTPException(501, f"Typname der Klassendossiers nicht eingerichtet ({PRAEFIX}DOSSIER_KLASSE_TYP)")
    return _suche(c, "Geschaeft", typeName=E.klasse_typ)


class KlasseEingabe(BaseModel):
    titel: str = Field(..., min_length=1, description="z. B. «2a» – CMI hängt das Schuljahr an («2a 2026/27»)")
    schuljahr: str = Field(..., description="GUID des Schuljahres (Stammdaten «Schuljahr»)")
    beginn: date
    ende: date | None = None
    extern: bool = Field(False, description="Externes Schulklassendossier (andere Schule)")
    standort: str | None = Field(None, description="Vorlage je Standort, z. B. Hinterbirch, Mettmenriet")
    geschaeftseigner: str | None = Field(None, description="GUID; extern: muss eine Schuleinheit sein "
                                                           "(z. B. «Klassen weitere»), sonst setzt ihn die Vorlage")
    externe_schule: str | None = Field(None, description="GUID der externen Schule – Pflicht bei extern")
    klassenlehrplan: str | None = Field(None, description="GUID des Klassenlehrplans (z. B. «1. Sekundarschule»): "
                                                          "legt die Klassenstufe an – ohne sie kann CMI nicht einteilen")


@app.post("/klassen", tags=["Klassen"], status_code=201,
          summary="Schulklassendossier bzw. Externes Schulklassendossier anlegen")
def klasse_anlegen(body: KlasseEingabe, probelauf: bool = False, _=Depends(schreib_check)):
    c = client()
    if body.extern:
        typ, vorlage = E.klasse_extern_typ, E.klasse_extern_vorlage
        if not body.externe_schule:
            raise HTTPException(400, "Externes Schulklassendossier braucht externe_schule")
    else:
        typ = E.klasse_typ
        karte = E.klasse_vorlagen or {}
        if karte and (not body.standort or body.standort.lower() not in karte):
            raise HTTPException(400, f"standort muss einer sein von: {', '.join(karte)}")
        vorlage = karte.get((body.standort or "").lower(), "")
    if not typ and not vorlage:
        raise HTTPException(501, f"Klassendossier nicht eingerichtet ({PRAEFIX}DOSSIER_KLASSE"
                                 f"{'_EXTERN' if body.extern else ''}_TYP bzw. Vorlage)")
    if body.ende and body.ende < body.beginn:
        raise HTTPException(400, "ende liegt vor beginn")
    # Duplikat: gleicher Titel im gleichen Schuljahr (CMI hängt das Schuljahr an den Titel)
    vorhanden = [k for k in _suche(c, "Geschaeft", typeName=typ or None, **{"schuljahr.guid": body.schuljahr})
                 if (k.get("titel") or "").strip().lower().split(" ")[0] == body.titel.strip().lower()]
    if vorhanden:
        raise _konflikt("Klasse gibt es in diesem Schuljahr schon",
                        [{"guid": k.get("guid"), "titel": k.get("titel")} for k in vorhanden])
    daten: dict[str, Any] = {"titel": body.titel, "beginn": body.beginn.isoformat(), "schuljahr": ref(body.schuljahr),
                             "zugriffsteuerung": "Offen", "geschaeftsstatus": "InBearbeitung",
                             "lifecycleStatus": "InBearbeitung"}
    if body.ende:
        daten["ende"] = body.ende.isoformat()
    if typ:
        daten["typeName"] = typ
    if body.geschaeftseigner:
        daten["geschaeftseigner"] = ref(body.geschaeftseigner)
    if body.extern:
        daten["externeSchule"] = ref(body.externe_schule)
    if probelauf:
        return {"probelauf": True, "vorlage": vorlage or None, "klasse": daten}
    schritte: list[dict] = []
    try:
        guid = c.anlegen("Geschaeft", daten, vorlage or None)
        schritte.append({"schritt": "klasse_anlegen", "ok": True, "guid": guid})
    except CMIFehler as e:
        # z. B. SCV102: Geschäftseigner muss eine Schuleinheit sein
        return JSONResponse({"probelauf": False, "vollstaendig": False,
                             "schritte": [{"schritt": "klasse_anlegen", "ok": False, "fehler": str(e)}]}, status_code=409)
    if body.klassenlehrplan:
        try:
            st = c.anlegen(E.stufe_entitaet, {"schulklassendossier": ref(guid), "klassenlehrplan": ref(body.klassenlehrplan)})
            schritte.append({"schritt": "klassenstufe_anlegen", "ok": True, "guid": st})
        except (CMIFehler, NichtGefunden) as e:
            schritte.append({"schritt": "klassenstufe_anlegen", "ok": False, "fehler": str(e)})
    neu = c.lesen("Geschaeft", guid)
    ok = (neu.get("titel") or "").lower().startswith(body.titel.lower())
    schritte.append({"schritt": "kontrolle", "ok": ok, **({} if ok else {"titel_cmi": neu.get("titel")})})
    ok = all(x["ok"] for x in schritte)
    return JSONResponse({"probelauf": False, "vollstaendig": ok, "guid": guid, "titel": neu.get("titel"),
                         "schritte": schritte}, status_code=201 if ok else 409)


@app.get("/klassen", tags=["Klassen"], summary="Klassen (Klassendossiers)")
def klassen(format: Format = "json"):
    return _antwort(_klassen(client()), format, "klassen")


EINTRITTSGRUENDE = ("schuleintritt", "zuzug", "klassenwechsel", "umteilung", "kindergarteneintritt",
                    "primareintritt", "sekundareintritt")
Eintrittsgrund = Literal[EINTRITTSGRUENDE]  # type: ignore[valid-type]


def _klassenstufen(c: CMIClient, klasse_guid: str) -> list[dict]:
    return _suche(c, E.stufe_entitaet, **{"schulklassendossier.guid": klasse_guid})


def _lernendendossier(c: CMIClient, fremdkey: str) -> dict:
    treffer = _dossiers_per_fremdkey(c, "schueler", fremdkey)
    if len(treffer) != 1:
        raise LookupError("kein Lernendendossier" if not treffer else "mehrere Lernendendossiers")
    return treffer[0]


def _laufbahn(c: CMIClient, dossier_guid: str) -> list[dict]:
    """Klassenzuteilungen der Schullaufbahn, je mit eigener Dauer (wie in CMI «Zuteilungen»).

    CMI führt pro Schuljahr eine Schullaufbahn; ein Klassenwechsel beendet nur die Klassenzuteilung
    (Dauer bis Vortag) und legt eine neue Zuteilung in derselben Schullaufbahn an."""
    aus = []
    for lb in _suche(c, E.lb_entitaet, **{"lernendedossier.guid": dossier_guid}):
        lb_zr = _zeitraum(lb.get("vonBis"))
        basis = {"schullaufbahn": lb["guid"], "titel": lb.get("titel"), "schuljahr": _anzeige(lb.get("schuljahr")),
                 "schuljahr_guid": guid_von(lb.get("schuljahr")), "status": _anzeige(lb.get("status")),
                 "eintrittsgrund": _anzeige(lb.get("eintrittsgrund")),
                 "laufbahn_von": lb_zr["von"], "laufbahn_bis": lb_zr["bis"], "_lb": lb}
        zuteilungen = _suche(c, E.kz_entitaet, **{"schullaufbahn.guid": lb["guid"]})
        if not zuteilungen:
            aus.append({**basis, "zuteilung": None, "von": lb_zr["von"], "bis": lb_zr["bis"], "klassenstufe": None,
                        "klassenstufe_titel": None, "klasse": None, "klasse_titel": None, "_kz": None})
        for kz in zuteilungen:
            kz_zr = _zeitraum(kz.get("vonBis"))
            stufe_guid = guid_von(kz.get("teilklasse"))
            stufe = c.lesen(E.stufe_entitaet, stufe_guid) if stufe_guid else {}
            aus.append({**basis, "zuteilung": kz["guid"], "von": kz_zr["von"] or lb_zr["von"],
                        "bis": kz_zr["bis"] or lb_zr["bis"], "klassenstufe": stufe_guid,
                        "klassenstufe_titel": stufe.get("titel"), "klasse": guid_von(stufe.get("schulklassendossier")),
                        "klasse_titel": _anzeige(stufe.get("schulklassendossier")), "_kz": kz})
    return sorted(aus, key=lambda x: (x["von"] or "", x["bis"] or ""))


def _aktiv_am(eintraege: list[dict], tag: str) -> list[dict]:
    return [x for x in eintraege if x["von"] and x["von"] <= tag and (not x["bis"] or x["bis"] >= tag)]


def _ohne_intern(x: dict) -> dict:
    return {k: v for k, v in x.items() if not k.startswith("_")}


@app.get("/schueler/{fremdkey}/klassen", tags=["Klassen"], dependencies=[Depends(_kz_check)],
         summary="Schullaufbahn einer Schülerin / eines Schülers: Einträge mit Klasse und Klassenstufe")
def schueler_klassen(fremdkey: str):
    c = client()
    try:
        d = _lernendendossier(c, fremdkey)
    except LookupError as e:
        raise HTTPException(404, f"Schüler:in {fremdkey}: {e}")
    return [_ohne_intern(x) for x in _laufbahn(c, d["guid"])]


@app.get("/klassen/{guid}/stufen", tags=["Klassen"], summary="Klassenstufen einer Klasse (CMI «Teilklasse»)")
def klasse_stufen(guid: str):
    return [{"guid": s.get("guid"), "titel": s.get("titel"), "klassenlehrplan": _anzeige(s.get("klassenlehrplan"))}
            for s in _klassenstufen(client(), guid)]


@app.get("/klassen/{guid}/schueler", tags=["Klassen"], dependencies=[Depends(_kz_check)],
         summary="Schüler:innen einer Klasse am Stichtag (Standard heute)")
def klasse_schueler(guid: str, stichtag: date | None = None, alle: bool = False, format: Format = "json"):
    c = client()
    tag = stichtag or date.today()
    aus = []
    for st in _klassenstufen(c, guid):
        for kz in _suche(c, E.kz_entitaet, **{"teilklasse.guid": st["guid"]}):
            lb = c.lesen(E.lb_entitaet, guid_von(kz.get("schullaufbahn")))
            zr = _zeitraum(kz.get("vonBis") or lb.get("vonBis"))
            if not alle and not _aktiv_am([zr], tag.isoformat()):
                continue
            aus.append({"zuteilung": kz.get("guid"), "lernendendossier": guid_von(lb.get("lernendedossier")),
                        "name": kz.get("computedPersonName"), "vorname": kz.get("computedPersonVorname"),
                        "klassenstufe": st.get("titel"), "von": zr["von"], "bis": zr["bis"]})
    return _antwort(aus, format, "klasse")


class Einteilung(BaseModel):
    fremdkey: str = Field(..., min_length=1, description="Schlüssel der Schülerin / des Schülers (Lernendendossier)")
    klasse: str = Field(..., min_length=1, description="GUID oder Titel des Klassendossiers (z. B. «2a 2026/27»)")
    klassenstufe: str | None = Field(None, description="GUID der Klassenstufe; nötig, wenn die Klasse mehrere hat")
    eintrittsgrund: Eintrittsgrund | None = Field(None, description="Standard: schuleintritt bzw. klassenwechsel")


class EinteilungListe(BaseModel):
    ab: date | None = Field(None, description="gilt ab (Standard heute); bisheriger Eintrag endet am Vortag")
    bis: date | None = Field(None, description="Ende des Eintrags; Standard Ende der Klasse bzw. 31.7.")
    zuteilungen: list[Einteilung] = Field(..., min_length=1, max_length=1000)


def _ende_standard(klasse: dict, ab: date) -> str:
    ende = _norm(klasse.get("ende"))
    return ende or date(ab.year + (1 if ab.month >= 8 else 0), 7, 31).isoformat()


@app.post("/klassen/einteilen", tags=["Klassen"], dependencies=[Depends(_kz_check)],
          summary="SuS in die aktuelle Klasse einteilen bzw. umteilen (Schullaufbahn wie «Klasseneinteilung» in CMI)")
def klassen_einteilen(body: EinteilungListe, probelauf: bool = False, _=Depends(schreib_check)):
    c = client()
    ab = body.ab or date.today()
    alle_klassen = _klassen(c) + (_suche(c, "Geschaeft", typeName=E.klasse_extern_typ) if E.klasse_extern_typ else [])
    nach_titel: dict[str, list[dict]] = {}
    for k in alle_klassen:
        t = (k.get("titel") or "").strip().lower()
        nach_titel.setdefault(t, []).append(k)
        nach_titel.setdefault(t.split(" ")[0], []).append(k)
    nach_guid = {k["guid"]: k for k in alle_klassen}

    fehler, konflikte, plaene = [], [], []
    for e in body.zuteilungen:
        klasse = nach_guid.get(e.klasse)
        if not klasse:
            kand = {k["guid"]: k for k in nach_titel.get(e.klasse.strip().lower(), [])}
            if len(kand) != 1:
                fehler.append({"fremdkey": e.fremdkey, "fehler": f"Klasse {e.klasse!r} "
                               + ("nicht gefunden" if not kand else "mehrdeutig")})
                continue
            klasse = next(iter(kand.values()))
        stufen = _klassenstufen(c, klasse["guid"])
        if e.klassenstufe:
            stufen = [s for s in stufen if s["guid"] == e.klassenstufe]
        if len(stufen) != 1:
            fehler.append({"fremdkey": e.fremdkey, "fehler": "Klasse hat keine Klassenstufe" if not stufen else
                           "Klasse hat mehrere Klassenstufen – klassenstufe angeben"})
            continue
        try:
            dossier = _lernendendossier(c, e.fremdkey)
        except LookupError as ex:
            fehler.append({"fremdkey": e.fremdkey, "fehler": str(ex)})
            continue
        laufbahn = _laufbahn(c, dossier["guid"])
        tag = ab.isoformat()
        aktiv = _aktiv_am([x for x in laufbahn if x["zuteilung"]], tag)
        if len(aktiv) > 1:
            konflikte.append({"fremdkey": e.fremdkey, "eintraege": [_ohne_intern(x) for x in aktiv]})
            continue
        schuljahr = guid_von(klasse.get("schuljahr"))
        plan: dict[str, Any] = {"fremdkey": e.fremdkey, "lernendendossier": dossier["guid"], "klasse": klasse["guid"],
                                "klasse_titel": klasse.get("titel"), "klassenstufe": stufen[0]["guid"],
                                "schuljahr": schuljahr, "ab": tag,
                                "bis": (body.bis.isoformat() if body.bis else _ende_standard(klasse, ab))}
        # Schullaufbahn des Schuljahrs, die am Stichtag läuft (in CMI eine pro Schuljahr)
        lb_jahr = [x for x in _aktiv_am([{**x, "von": x["laufbahn_von"], "bis": x["laufbahn_bis"]} for x in laufbahn], tag)
                   if x["schuljahr_guid"] == schuljahr]
        lb_guids = {x["schullaufbahn"] for x in lb_jahr}
        if len(lb_guids) > 1:
            konflikte.append({"fremdkey": e.fremdkey, "fehler": "mehrere Schullaufbahnen im Schuljahr",
                              "eintraege": [_ohne_intern(x) for x in lb_jahr]})
            continue
        if lb_guids:
            plan["schullaufbahn"] = lb_jahr[0]["schullaufbahn"]
            if not body.bis and lb_jahr[0]["laufbahn_bis"]:
                plan["bis"] = lb_jahr[0]["laufbahn_bis"]
        if aktiv and aktiv[0]["klassenstufe"] == stufen[0]["guid"]:
            plan["aktion"] = "unveraendert"
        elif aktiv and aktiv[0]["von"] == tag:
            plan["aktion"] = "korrigieren"  # Zuteilung beginnt am selben Tag: Klassenstufe ersetzen
        elif aktiv:
            plan["aktion"] = "umteilen"
            plan["eintrittsgrund"] = e.eintrittsgrund or "klassenwechsel"
            plan["bisher_bis"] = (ab - timedelta(days=1)).isoformat()
            if aktiv[0]["schullaufbahn"] != plan.get("schullaufbahn"):
                plan["neues_schuljahr"] = True  # Wechsel über das Schuljahr: alte Schullaufbahn endet ebenfalls
        else:
            plan["aktion"] = "einteilen"
            plan["eintrittsgrund"] = e.eintrittsgrund or "schuleintritt"
        if aktiv:
            plan["bisher"] = _ohne_intern(aktiv[0])
            plan["_alt"] = aktiv[0]
        plaene.append(plan)
    if fehler:
        raise HTTPException(400, {"meldung": "Eingabe ungültig", "betroffene": fehler})
    if konflikte:
        raise _konflikt("Mehrere aktive Klassenzuteilungen bzw. Schullaufbahnen am Stichtag – bitte in CMI bereinigen",
                        konflikte)
    zusammenfassung = {a: sum(p["aktion"] == a for p in plaene)
                       for a in ("einteilen", "umteilen", "korrigieren", "unveraendert")}
    if probelauf:
        return {"probelauf": True, "zusammenfassung": zusammenfassung, "zuteilungen": [_sichtbar(p) for p in plaene]}

    def ohne_listen(d: dict) -> dict:
        return {k: v for k, v in d.items() if not isinstance(v, list)}

    def dauer(von: str | None, bis: str | None) -> str:
        return f"{_ch_datum(von)} - {_ch_datum(bis)}"

    ergebnisse = []
    for p in plaene:
        schritte: list[dict] = []
        try:
            if p["aktion"] == "korrigieren":
                kz = p["_alt"]["_kz"]
                c.aendern(E.kz_entitaet, kz["guid"], {**ohne_listen(kz), "teilklasse": ref(p["klassenstufe"])})
                schritte.append({"schritt": "zuteilung_korrigieren", "ok": True})
            if p["aktion"] == "umteilen":
                alt = p["_alt"]
                kz = alt["_kz"]
                c.aendern(E.kz_entitaet, kz["guid"], {**ohne_listen(kz), "vonBis": dauer(alt["von"], p["bisher_bis"])})
                schritte.append({"schritt": "bisherige_zuteilung_beenden", "ok": True})
                if p.get("neues_schuljahr"):
                    lb = alt["_lb"]
                    c.aendern(E.lb_entitaet, lb["guid"], {**ohne_listen(lb),
                              "vonBis": dauer(alt["laufbahn_von"], p["bisher_bis"])})
                    schritte.append({"schritt": "bisherige_schullaufbahn_beenden", "ok": True})
            if p["aktion"] in ("einteilen", "umteilen"):
                lb_guid = p.get("schullaufbahn")
                if not lb_guid:
                    lb_guid = c.anlegen(E.lb_entitaet, {
                        "lernendedossier": ref(p["lernendendossier"]), "schuljahr": ref(p["schuljahr"]),
                        "vonBis": dauer(p["ab"], p["bis"]), "eintrittsgrund": p["eintrittsgrund"]})
                    schritte.append({"schritt": "schullaufbahn_anlegen", "ok": True, "guid": lb_guid})
                kz_guid = c.anlegen(E.kz_entitaet, {"schullaufbahn": ref(lb_guid), "teilklasse": ref(p["klassenstufe"]),
                                                    "vonBis": dauer(p["ab"], p["bis"])})
                schritte.append({"schritt": "zuteilung_anlegen", "ok": True, "guid": kz_guid})
        except (CMIFehler, NichtGefunden) as ex:
            schritte.append({"schritt": p["aktion"], "ok": False, "fehler": str(ex)})
        if p["aktion"] != "unveraendert" and all(s["ok"] for s in schritte):
            aktiv = _aktiv_am([x for x in _laufbahn(c, p["lernendendossier"]) if x["zuteilung"]], p["ab"])
            ok = len(aktiv) == 1 and aktiv[0]["klassenstufe"] == p["klassenstufe"]
            schritte.append({"schritt": "kontrolle", "ok": ok,
                             **({} if ok else {"fehler": "CMI zeigt am Stichtag nicht die neue Klasse",
                                               "aktiv": [_ohne_intern(x) for x in aktiv]})})
        ergebnisse.append({**_sichtbar(p), "schritte": schritte})
    vollstaendig = all(s["ok"] for e in ergebnisse for s in e["schritte"])
    antwort = {"probelauf": False, "vollstaendig": vollstaendig, "zusammenfassung": zusammenfassung,
               "zuteilungen": ergebnisse}
    return antwort if vollstaendig else JSONResponse(antwort, status_code=409)


# ================================================================ Dokumente

@app.get("/dokumente/{guid}", tags=["Dokumente"])
def dokument(guid: str):
    return client().lesen("Dokument", guid)


@app.get("/dokumente/{guid}/inhalt", tags=["Dokumente"], summary="Datei herunterladen")
def dokument_inhalt(guid: str, version: int | None = None):
    inhalt, typ = client().datei(guid, version)
    return Response(inhalt, media_type=typ, headers={"Content-Disposition": f'attachment; filename="{guid}"'})


def _ordner_finden(c: CMIClient, dossier_guid: str, pfad: str) -> tuple[str | None, list[str]]:
    """Sucht den Ordnerpfad im Dossier. Gibt (GUID des tiefsten vorhandenen Ordners, fehlende Teile) zurück."""
    teile = [t.strip() for t in pfad.replace("\\", "/").split("/") if t.strip()]
    if not teile:
        return None, []
    ordner = _ordnerbaum(c, dossier_guid)
    im_dossier = {o["guid"] for o in ordner}

    def eltern_von(o: dict) -> str | None:
        p = guid_von(o.get("parent"))
        return p if p in im_dossier else None  # oberste Ebene: kein Eltern-Ordner im Dossier (ZU PRÜFEN)

    eltern: str | None = None
    for i, t in enumerate(teile):
        passend = [o for o in ordner if (o.get("titel") or "").strip().lower() == t.lower()
                   and eltern_von(o) == eltern]
        if not passend:
            return eltern, teile[i:]
        eltern = passend[0]["guid"]
    return eltern, []


@app.post("/dossiers/{guid}/dokumente", tags=["Dokumente"],
          summary="Datei als Dokument ins Dossier hochladen (Ordnerpfad wird bei Bedarf angelegt)")
def dokument_hochladen(guid: str, datei: UploadFile = File(...), titel: str | None = Form(None),
                       ordner: str | None = Form(None, description="Pfad, z. B. «b_Dossier Schule/08_Beurteilung»"),
                       ordner_guid: str | None = Form(None, description="Zielordner direkt (statt Pfad)"),
                       ordner_anlegen: bool = Form(False, description="fehlende Ordner anlegen (sonst 400)"),
                       dokumentdatum: date | None = Form(None), eingangsdatum: date | None = Form(None),
                       ausgangsdatum: date | None = Form(None), bemerkung: str | None = Form(None),
                       autor: str | None = Form(None), thema: str | None = Form(None),
                       schluessel: str | None = Form(None, description="Schlüssel im Quellsystem gegen Duplikate"),
                       probelauf: bool = False, _=Depends(schreib_check)):
    c = client()
    inhalt = datei.file.read()
    if not inhalt:
        raise HTTPException(400, "Datei ist leer")
    if len(inhalt) > E.max_mb * 1024 * 1024:
        raise HTTPException(400, f"Datei grösser als {E.max_mb:g} MB")
    name = datei.filename or "dokument"
    titel = (titel or Path(name).stem).strip()
    g = c.lesen("Geschaeft", guid)  # 404, wenn das Dossier fehlt
    # Prüfen vor dem Anlegen: Duplikat über Schlüssel oder gleichen Titel im Dossier
    if schluessel:
        gleich = _suche(c, "Dokument", schluesselFremdsystem=schluessel)
        if gleich:
            raise _konflikt("Dokument mit diesem Schlüssel gibt es schon", [d.get("guid") for d in gleich])
    gleicher_titel = [d for d in g.get("dokumente") or [] if (d.get("displayName") or "").strip() == titel]
    if gleicher_titel:
        raise _konflikt("Im Dossier gibt es schon ein Dokument mit diesem Titel",
                        [guid_von(d) for d in gleicher_titel])
    if ordner_guid:
        if ordner_guid not in {o["guid"] for o in _ordnerbaum(c, guid)}:
            raise HTTPException(400, "ordner_guid gehört nicht zu diesem Dossier")
        fehlend: list[str] = []
    else:
        ordner_guid, fehlend = _ordner_finden(c, guid, ordner or "")
        if fehlend and not ordner_anlegen:
            raise HTTPException(400, {"meldung": "Ordner nicht im Dossier (ordner_anlegen=true zum Anlegen)",
                                      "fehlend": fehlend})
    sha = hashlib.sha256(inhalt).hexdigest()
    plan = {"dossier": guid, "dossier_titel": g.get("titel"), "titel": titel, "dateiname": name,
            "bytes": len(inhalt), "sha256": sha, "ordner": ordner, "ordner_anlegen": fehlend,
            "upload_art": E.upload_art}
    if probelauf:
        return {"probelauf": True, **plan}

    schritte: list[dict] = []
    dok_guid = None
    try:
        for t in fehlend:
            ordner_guid = c.anlegen("Ordner", {"titel": t, "parent": ref(ordner_guid), "geschaeft": ref(guid)})
            schritte.append({"schritt": f"ordner_anlegen:{t}", "ok": True, "guid": ordner_guid})
        daten: dict[str, Any] = {"titel": titel, "beschuss": False, "beschlussvorhanden": False,
                                 "istPubliziert": False, "vip": False, "geschaeft": ref(guid)}
        if ordner_guid:
            daten["ordner"] = ref(ordner_guid)
        for feld, wert in (("dokumentdatum", dokumentdatum), ("eingangsdatum", eingangsdatum),
                           ("ausgangsdatum", ausgangsdatum)):
            if wert:
                daten[feld] = wert.isoformat()
        for feld, wert in (("bemerkung", bemerkung), ("autor", autor), ("thema", thema)):
            if wert:
                daten[feld] = wert
        if schluessel:
            daten["schluesselFremdsystem"] = schluessel
        if E.upload_art == "rendition":
            daten["eDokument"] = {"renditions": [rendition(name, inhalt)]}
        dok_guid = c.anlegen("Dokument", daten)
        schritte.append({"schritt": "dokument_anlegen", "ok": True, "guid": dok_guid})
        if E.upload_art == "checkin":
            c.auschecken(dok_guid)
            c.einchecken(dok_guid, name, inhalt, "Upload EduKSX")
            schritte.append({"schritt": "datei_einchecken", "ok": True})
    except (CMIFehler, NichtGefunden) as e:
        schritte.append({"schritt": "hochladen", "ok": False, "fehler": str(e)})
    if dok_guid and all(s["ok"] for s in schritte):
        try:
            d = c.lesen("Dokument", dok_guid)
            zurueck, _typ_ = c.datei(dok_guid)
            abw = []
            if (d.get("titel") or "").strip() != titel:
                abw.append("titel")
            if guid_von(d.get("geschaeft")) not in (None, guid):
                abw.append("dossier")
            if hashlib.sha256(zurueck).hexdigest() != sha:
                abw.append("inhalt")
            schritte.append({"schritt": "kontrolle", "ok": not abw, **({"abweichungen": abw} if abw else {})})
        except (CMIFehler, NichtGefunden) as e:
            schritte.append({"schritt": "kontrolle", "ok": False, "fehler": str(e)})
    antwort = {"probelauf": False, "vollstaendig": all(s["ok"] for s in schritte), "guid": dok_guid,
               **{k: plan[k] for k in ("titel", "bytes", "sha256", "ordner")}, "schritte": schritte}
    return antwort if antwort["vollstaendig"] else JSONResponse(antwort, status_code=409)
