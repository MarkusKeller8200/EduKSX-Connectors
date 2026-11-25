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
    personal_typ: str = ""
    klasse_typ: str = ""
    dossier_zugriff: str = "Restriktiv"   # Offen | Restriktiv – Personendossiers standardmässig restriktiv
    geschaeftseigner: str = ""            # GUID, falls die Vorlage keinen Eigner setzt
    # Verknüpfung Kontakt ↔ Dossier (optional): Entität und Feldnamen
    beteiligung_entitaet: str = ""
    beteiligung_rolle: str = ""
    # Klassenzuteilung (CMI Schule): Entität und Feldnamen; leer = nicht eingerichtet (501)
    kz_entitaet: str = ""
    kz_schueler: str = "schueler"
    kz_klasse: str = "klasse"
    kz_von: str = "von"
    kz_bis: str = "bis"
    kz_schueler_ref: Literal["kontakt", "dossier"] = "kontakt"
    # Dokumente
    upload_art: Literal["rendition", "checkin"] = "rendition"
    max_mb: float = 50.0


def einstellungen_aus_env() -> Einstellungen:
    return Einstellungen(
        kontakt_vorlage=_env("KONTAKT_VORLAGE"), kontakt_typ=_env("KONTAKT_TYP"),
        schueler_vorlage=_env("DOSSIER_SCHUELER_VORLAGE"), schueler_typ=_env("DOSSIER_SCHUELER_TYP"),
        personal_vorlage=_env("DOSSIER_PERSONAL_VORLAGE"), personal_typ=_env("DOSSIER_PERSONAL_TYP"),
        klasse_typ=_env("DOSSIER_KLASSE_TYP"), dossier_zugriff=_env("DOSSIER_ZUGRIFF", "Restriktiv"),
        geschaeftseigner=_env("DOSSIER_EIGNER"),
        beteiligung_entitaet=_env("BETEILIGUNG_ENTITAET"), beteiligung_rolle=_env("BETEILIGUNG_ROLLE"),
        kz_entitaet=_env("KLASSENZUTEILUNG_ENTITAET"), kz_schueler=_env("KZ_FELD_SCHUELER", "schueler"),
        kz_klasse=_env("KZ_FELD_KLASSE", "klasse"), kz_von=_env("KZ_FELD_VON", "von"),
        kz_bis=_env("KZ_FELD_BIS", "bis"), kz_schueler_ref=_env("KZ_SCHUELER_REF", "kontakt"),  # type: ignore[arg-type]
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
            "schreiben": SCHREIBEN, "aufrufe_cmi": {"lesen": c.zaehler.lesen, "schreiben": c.zaehler.schreiben},
            "eingerichtet": {
                "dossier_schueler": bool(E.schueler_vorlage), "dossier_personal": bool(E.personal_vorlage),
                "klassen": bool(E.klasse_typ), "klassenzuteilung": bool(E.kz_entitaet),
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

KONTAKT_FELDER = ("name", "vorname", "anrede", "email", "email2", "natel", "telefonPrivat", "telefonGeschaeft",
                  "geburtsdatum", "organisation", "mitarbeiter", "inaktiv")
KONTAKT_PFLICHT_BOOL = ("inaktiv", "mitarbeiter", "istPubliziert", "googleAuthKonfiguriert", "behindert",
                        "erhoehterBetreuungsbedarf", "aufenthaltUnbekannt")
ADRESS_FELDER = ("strasse", "plz", "ort")


class AdresseEingabe(BaseModel):
    strasse: str | None = None
    plz: str | None = None
    ort: str | None = None


class KontaktEingabe(BaseModel):
    fremdkey: str = Field(..., min_length=1, description="Schlüssel aus dem Quellsystem (z. B. Escola-ID), "
                                                         "wird in CMI als `fremdkey` geführt")
    name: str | None = None
    vorname: str | None = None
    anrede: str | None = None
    email: str | None = None
    email2: str | None = None
    natel: str | None = None
    telefonPrivat: str | None = None
    telefonGeschaeft: str | None = None
    geburtsdatum: str | None = Field(None, description="JJJJ-MM-TT")
    organisation: str | None = None
    mitarbeiter: bool | None = None
    inaktiv: bool | None = None
    adresse: AdresseEingabe | None = None


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


def _kontakt_plan(c: CMIClient, k: KontaktEingabe) -> dict:
    """Vergleicht Eingabe und CMI – ohne zu schreiben."""
    eingabe = {f: getattr(k, f) for f in KONTAKT_FELDER if getattr(k, f) is not None}
    treffer = _kontakt_per_fremdkey(c, k.fremdkey)
    plan: dict[str, Any] = {"fremdkey": k.fremdkey, "guid": None, "aktion": None, "aenderungen": {},
                            "adresse": None, "_alt": None, "_adresse_alt": None}
    if len(treffer) > 1:
        plan["aktion"] = "konflikt"
        plan["guids"] = [t.get("guid") for t in treffer]
        return plan
    if not treffer:
        plan["aktion"] = "anlegen"
        plan["aenderungen"] = {f: [None, v] for f, v in eingabe.items()}
        if k.adresse:
            plan["adresse"] = {"aktion": "anlegen", **k.adresse.model_dump(exclude_none=True)}
        return plan
    alt = c.lesen("Kontakt", treffer[0]["guid"])
    plan["guid"], plan["_alt"] = alt["guid"], alt
    plan["aenderungen"] = {f: [alt.get(f), v] for f, v in eingabe.items() if _norm(alt.get(f)) != _norm(v)}
    if k.adresse:
        neu = k.adresse.model_dump(exclude_none=True)
        adr_alt = None
        for r in alt.get("adressen") or []:
            a = c.lesen("Adresse", guid_von(r))
            if not a.get("inaktiv"):
                adr_alt = a
                break
        if adr_alt is None:
            plan["adresse"] = {"aktion": "anlegen", **neu}
        else:
            diff = {f: [adr_alt.get(f), v] for f, v in neu.items() if _norm(adr_alt.get(f)) != _norm(v)}
            plan["_adresse_alt"] = adr_alt
            plan["adresse"] = {"aktion": "aendern" if diff else "unveraendert", "guid": adr_alt["guid"],
                               "aenderungen": diff}
    adr_aktion = (plan["adresse"] or {}).get("aktion")
    plan["aktion"] = "aendern" if plan["aenderungen"] or adr_aktion in ("anlegen", "aendern") else "unveraendert"
    return plan


def _kontakt_schreiben(c: CMIClient, k: KontaktEingabe, plan: dict) -> list[dict]:
    schritte: list[dict] = []

    def schritt(name: str, fn):
        try:
            fn()
            schritte.append({"schritt": name, "ok": True})
        except (CMIFehler, NichtGefunden) as e:
            schritte.append({"schritt": name, "ok": False, "fehler": str(e)})
            raise

    neu_werte = {f: v[1] for f, v in plan["aenderungen"].items()}
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
            alt = {f: v for f, v in plan["_alt"].items() if not isinstance(v, list)}
            schritt("kontakt_aendern", lambda: c.aendern("Kontakt", plan["guid"], {**alt, **neu_werte}))
        adr = plan.get("adresse") or {}
        werte = {f: adr[f] for f in ADRESS_FELDER if f in adr}
        if adr.get("aktion") == "anlegen":
            schritt("adresse_anlegen", lambda: c.anlegen(
                "Adresse", {"inaktiv": False, "kontakt": ref(plan["guid"]), **werte}))
        elif adr.get("aktion") == "aendern":
            neu = {f: v[1] for f, v in adr["aenderungen"].items()}
            alt = {f: v for f, v in plan["_adresse_alt"].items() if not isinstance(v, list)}
            schritt("adresse_aendern", lambda: c.aendern("Adresse", adr["guid"], {**alt, **neu}))
    except (CMIFehler, NichtGefunden):
        return schritte
    # Kontrolle: neu lesen und vergleichen
    kontrolle = _kontakt_plan(c, k)
    if kontrolle["aktion"] != "unveraendert":
        schritte.append({"schritt": "kontrolle", "ok": False,
                         "fehler": "CMI hat nicht alles übernommen",
                         "abweichungen": kontrolle["aenderungen"] or kontrolle.get("adresse")})
    else:
        schritte.append({"schritt": "kontrolle", "ok": True})
    return schritte


def _sichtbar(plan: dict) -> dict:
    return {k: v for k, v in plan.items() if not k.startswith("_")}


@app.post("/kontakte/sync", tags=["Kontakte"],
          summary="Kontakte abgleichen: fehlende anlegen, geänderte Felder nachführen (Schlüssel: fremdkey)")
def kontakte_sync(body: KontaktListe, probelauf: bool = False, _=Depends(schreib_check)):
    c = client()
    doppelt = sorted({k.fremdkey for k in body.kontakte if [x.fremdkey for x in body.kontakte].count(k.fremdkey) > 1})
    if doppelt:
        raise HTTPException(400, {"meldung": "fremdkey mehrfach in der Eingabe", "betroffene": doppelt})
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


# ================================================================ Dossiers

class DossierEingabe(BaseModel):
    fremdkey: str = Field(..., min_length=1, description="Schlüssel der Person aus dem Quellsystem "
                                                         "(= fremdkey des Kontakts, in CMI `schluesselFremdsystem`)")
    kontakt_guid: str | None = Field(None, description="sonst wird der Kontakt über fremdkey gesucht")
    titel: str | None = Field(None, description="Standard: «Name Vorname» (SuS mit Jahrgang)")
    beginn: date | None = Field(None, description="Standard: heute")


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


def _dossier_anlegen(art: Literal["schueler", "personal"], body: DossierEingabe, probelauf: bool):
    c = client()
    vorlage, typ = _vorlage(art), _typ(art)
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
    if typ:
        daten["typeName"] = typ
    if E.geschaeftseigner:
        daten["geschaeftseigner"] = ref(E.geschaeftseigner)
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
                         "hinweis": f"Verknüpfung nur über schluesselFremdsystem ({PRAEFIX}BETEILIGUNG_ENTITAET leer)"})
    neu = c.lesen("Geschaeft", guid)
    abw = {f: [neu.get(f), daten[f]] for f in ("titel", "schluesselFremdsystem") if _norm(neu.get(f)) != _norm(daten[f])}
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


# ================================================================ Klassen und Klassenzuteilung

def _kz_check():
    if not E.kz_entitaet:
        raise HTTPException(501, f"Klassenzuteilung nicht eingerichtet ({PRAEFIX}KLASSENZUTEILUNG_ENTITAET; "
                                 "Modell in CMI Schule ZU PRÜFEN)")


def _klassen(c: CMIClient) -> list[dict]:
    if not E.klasse_typ:
        raise HTTPException(501, f"Typname der Klassendossiers nicht eingerichtet ({PRAEFIX}DOSSIER_KLASSE_TYP)")
    return _suche(c, "Geschaeft", typeName=E.klasse_typ)


@app.get("/klassen", tags=["Klassen"], summary="Klassen (Klassendossiers)")
def klassen(format: Format = "json"):
    return _antwort(_klassen(client()), format, "klassen")


def _aktiv(z: dict, stichtag: date) -> bool:
    von, bis = _norm(z.get(E.kz_von)), _norm(z.get(E.kz_bis))
    return (not von or von <= stichtag.isoformat()) and (not bis or bis >= stichtag.isoformat())


def _zuteilung_aus(z: dict) -> dict:
    return {"guid": z.get("guid"), "schueler": guid_von(z.get(E.kz_schueler)), "klasse": guid_von(z.get(E.kz_klasse)),
            "klasse_name": (z.get(E.kz_klasse) or {}).get("displayName") if isinstance(z.get(E.kz_klasse), dict) else None,
            "von": _norm(z.get(E.kz_von)), "bis": _norm(z.get(E.kz_bis))}


@app.get("/klassen/{guid}/schueler", tags=["Klassen"], dependencies=[Depends(_kz_check)],
         summary="Zuteilungen einer Klasse (aktiv am Stichtag, Standard heute)")
def klasse_schueler(guid: str, stichtag: date | None = None, alle: bool = False, format: Format = "json"):
    c = client()
    tag = stichtag or date.today()
    zs = [z for z in _suche(c, E.kz_entitaet, **{f"{E.kz_klasse}.guid": guid}) if alle or _aktiv(z, tag)]
    return _antwort([_zuteilung_aus(z) for z in zs], format, "klasse")


def _schueler_ref(c: CMIClient, fremdkey: str) -> str:
    if E.kz_schueler_ref == "dossier":
        treffer = _dossiers_per_fremdkey(c, "schueler", fremdkey)
    else:
        treffer = _kontakt_per_fremdkey(c, fremdkey)
    if len(treffer) != 1:
        raise LookupError("nicht gefunden" if not treffer else "mehrdeutig")
    return treffer[0]["guid"]


@app.get("/schueler/{fremdkey}/klassen", tags=["Klassen"], dependencies=[Depends(_kz_check)],
         summary="Klassenzuteilungen einer Schülerin / eines Schülers (Schullaufbahn)")
def schueler_klassen(fremdkey: str):
    c = client()
    try:
        s = _schueler_ref(c, fremdkey)
    except LookupError as e:
        raise HTTPException(404, f"Schüler:in {fremdkey}: {e}")
    zs = _suche(c, E.kz_entitaet, **{f"{E.kz_schueler}.guid": s})
    return sorted((_zuteilung_aus(z) for z in zs), key=lambda z: z["von"] or "")


class Einteilung(BaseModel):
    fremdkey: str = Field(..., min_length=1, description="Schlüssel der Schülerin / des Schülers")
    klasse: str = Field(..., min_length=1, description="GUID oder Titel des Klassendossiers")


class EinteilungListe(BaseModel):
    ab: date | None = Field(None, description="gilt ab (Standard heute); bisherige Zuteilung endet am Vortag")
    zuteilungen: list[Einteilung] = Field(..., min_length=1, max_length=1000)


@app.post("/klassen/einteilen", tags=["Klassen"], dependencies=[Depends(_kz_check)],
          summary="SuS in Klassen einteilen bzw. umteilen (ab Datum; bisherige Zuteilung wird beendet)")
def klassen_einteilen(body: EinteilungListe, probelauf: bool = False, _=Depends(schreib_check)):
    c = client()
    ab = body.ab or date.today()
    klassen_liste = _klassen(c)
    nach_titel: dict[str, list[str]] = {}
    for k in klassen_liste:
        nach_titel.setdefault((k.get("titel") or "").strip().lower(), []).append(k["guid"])
    guids = {k["guid"] for k in klassen_liste}

    fehler, konflikte, plaene = [], [], []
    for e in body.zuteilungen:
        if e.klasse in guids:
            ziel = e.klasse
        else:
            kandidaten = nach_titel.get(e.klasse.strip().lower(), [])
            if len(kandidaten) != 1:
                fehler.append({"fremdkey": e.fremdkey, "fehler": f"Klasse {e.klasse!r} "
                               + ("nicht gefunden" if not kandidaten else "mehrdeutig")})
                continue
            ziel = kandidaten[0]
        try:
            s = _schueler_ref(c, e.fremdkey)
        except LookupError as ex:
            fehler.append({"fremdkey": e.fremdkey, "fehler": f"Schüler:in {ex}"})
            continue
        zs = _suche(c, E.kz_entitaet, **{f"{E.kz_schueler}.guid": s})
        aktiv = [z for z in zs if _aktiv(z, ab)]
        if len(aktiv) > 1:
            konflikte.append({"fremdkey": e.fremdkey, "zuteilungen": [_zuteilung_aus(z) for z in aktiv]})
            continue
        plan: dict[str, Any] = {"fremdkey": e.fremdkey, "schueler": s, "klasse": ziel, "ab": ab.isoformat()}
        if not aktiv:
            plan["aktion"] = "einteilen"
        elif guid_von(aktiv[0].get(E.kz_klasse)) == ziel:
            plan["aktion"] = "unveraendert"
        elif _norm(aktiv[0].get(E.kz_von)) == ab.isoformat():
            plan["aktion"] = "korrigieren"  # Zuteilung beginnt am selben Tag: Klasse ersetzen statt Nulltag
        else:
            plan["aktion"] = "umteilen"
            plan["bisher_bis"] = (ab - timedelta(days=1)).isoformat()
        if aktiv:
            plan["bisher"] = _zuteilung_aus(aktiv[0])
            plan["_alt"] = aktiv[0]
        plaene.append(plan)
    if fehler:
        raise HTTPException(400, {"meldung": "Eingabe ungültig", "betroffene": fehler})
    if konflikte:
        raise _konflikt("Mehrere aktive Zuteilungen am Stichtag – bitte in CMI bereinigen", konflikte)
    zusammenfassung = {a: sum(p["aktion"] == a for p in plaene)
                       for a in ("einteilen", "umteilen", "korrigieren", "unveraendert")}
    sichtbar = [_sichtbar(p) for p in plaene]
    if probelauf:
        return {"probelauf": True, "zusammenfassung": zusammenfassung, "zuteilungen": sichtbar}

    def ohne_listen(d: dict) -> dict:
        return {k: v for k, v in d.items() if not isinstance(v, list)}

    ergebnisse = []
    for p, aus in zip(plaene, sichtbar):
        schritte: list[dict] = []
        try:
            if p["aktion"] == "korrigieren":
                c.aendern(E.kz_entitaet, p["_alt"]["guid"], {**ohne_listen(p["_alt"]), E.kz_klasse: ref(p["klasse"])})
                schritte.append({"schritt": "zuteilung_korrigieren", "ok": True})
            if p["aktion"] == "umteilen":
                c.aendern(E.kz_entitaet, p["_alt"]["guid"], {**ohne_listen(p["_alt"]), E.kz_bis: p["bisher_bis"]})
                schritte.append({"schritt": "bisherige_beenden", "ok": True})
            if p["aktion"] in ("einteilen", "umteilen"):
                g = c.anlegen(E.kz_entitaet, {E.kz_schueler: ref(p["schueler"]), E.kz_klasse: ref(p["klasse"]),
                                              E.kz_von: p["ab"]})
                schritte.append({"schritt": "zuteilung_anlegen", "ok": True, "guid": g})
        except (CMIFehler, NichtGefunden) as ex:
            schritte.append({"schritt": p["aktion"], "ok": False, "fehler": str(ex)})
        if p["aktion"] != "unveraendert" and all(s["ok"] for s in schritte):
            zs = _suche(c, E.kz_entitaet, **{f"{E.kz_schueler}.guid": p["schueler"]})
            aktiv = [z for z in zs if _aktiv(z, ab)]
            ok = len(aktiv) == 1 and guid_von(aktiv[0].get(E.kz_klasse)) == p["klasse"]
            schritte.append({"schritt": "kontrolle", "ok": ok,
                             **({} if ok else {"fehler": "CMI zeigt am Stichtag nicht die neue Klasse",
                                               "aktiv": [_zuteilung_aus(z) for z in aktiv]})})
        ergebnisse.append({**aus, "schritte": schritte})
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
                       ordner: str | None = Form(None, description="z. B. «Zeugnisse/2025-26»"),
                       dokumentdatum: date | None = Form(None), bemerkung: str | None = Form(None),
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
    ordner_guid, fehlend = _ordner_finden(c, guid, ordner or "")
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
        if dokumentdatum:
            daten["dokumentdatum"] = dokumentdatum.isoformat()
        if bemerkung:
            daten["bemerkung"] = bemerkung
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
