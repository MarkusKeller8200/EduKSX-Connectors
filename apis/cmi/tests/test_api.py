"""Tests gegen ein nachgebautes CMI (httpx MockTransport), ohne Netzwerk.

Das Fake bildet die Pfade und Datenformen aus dem Swagger des Power-Platform-Connectors von CM Informatik nach
(Stand November 2026): `GET/PUT /<Entität>/{guid}`, `POST /<Entität>` → GUID, `POST /<Entität>/Search` mit
TentaQl-Text, `GET /Dokument/FileContent/{guid}`, Verweise als `{guid, displayName}`.
Nicht belegt und deshalb angenommen (ZU PRÜFEN): TentaQl-Syntax `feld = "wert" AND …`, Entität und Felder der
Klassenzuteilung, Ordner der obersten Ebene ohne Eltern, Datei Base64 in `eDokument.renditions`.
Alle Personen sind erfunden.
"""
from __future__ import annotations

import base64
import json
import re
import uuid

import httpx
import pytest
from fastapi.testclient import TestClient

from cmi_api import app as A
from cmi_api.client import CMIClient, CMIConfig

ENTITAETEN = ("Kontakt", "Adresse", "Geschaeft", "Ordner", "Dokument", "Klassenzuteilung", "Beteiligung",
              "Dossierkontakt", "Beziehung", "Zahlungsinformation", "MedizinischerInformationseintrag")


class FakeCMI:
    """In-Memory-CMI. `ignoriere_put` simuliert, dass CMI eine Änderung nicht übernimmt."""

    def __init__(self):
        self.daten: dict[str, dict[str, dict]] = {e: {} for e in ENTITAETEN}
        self.dateien: dict[str, bytes] = {}
        self.aufrufe: list[httpx.Request] = []
        self.ignoriere_put = False
        self.token_abrufe = 0

    # ---------------------------------------------------------- Testdaten
    def neu(self, entitaet: str, **felder) -> str:
        g = str(uuid.uuid4())
        self.daten[entitaet][g] = {"guid": g, "version": 1, **felder}
        self._verknuepfen(entitaet, g)
        return g

    def _verknuepfen(self, entitaet: str, g: str):
        o = self.daten[entitaet][g]
        if entitaet == "Adresse" and o.get("kontakt"):
            k = self.daten["Kontakt"][o["kontakt"]["guid"]]
            k.setdefault("adressen", []).append({"guid": g})
        if entitaet == "Ordner" and o.get("geschaeft"):
            self.daten["Geschaeft"][o["geschaeft"]["guid"]].setdefault("ordner", []).append({"guid": g})
        if entitaet == "Dokument" and o.get("geschaeft"):
            self.daten["Geschaeft"][o["geschaeft"]["guid"]].setdefault("dokumente", []).append(
                {"guid": g, "displayName": o.get("titel")})
            r = ((o.get("eDokument") or {}).get("renditions") or [{}])[0]
            if r.get("file"):
                self.dateien[g] = base64.b64decode(r["file"])
            o.pop("eDokument", None)
        if entitaet == "Klassenzuteilung":
            k = self.daten["Geschaeft"].get(o["klasse"]["guid"])
            if k:
                o["klasse"]["displayName"] = k["titel"]

    # ---------------------------------------------------------- TentaQl (angenommene Syntax)
    def _treffer(self, entitaet: str, abfrage: str) -> list[dict]:
        bed = re.findall(r'([\w.]+) = "((?:[^"\\]|\\.)*)"', abfrage)
        aus = []
        for o in self.daten[entitaet].values():
            ok = True
            for feld, wert in bed:
                v = o
                for teil in feld.split("."):
                    v = v.get(teil) if isinstance(v, dict) else None
                if str(v) != wert.replace('\\"', '"'):
                    ok = False
            if ok:
                aus.append(o)
        return aus

    # ---------------------------------------------------------- HTTP
    def __call__(self, req: httpx.Request) -> httpx.Response:
        self.aufrufe.append(req)
        if req.url.host == "login.test":
            self.token_abrufe += 1
            return httpx.Response(200, json={"access_token": "tok", "expires_in": 3600})
        if req.headers.get("Authorization") != "Bearer tok":
            return httpx.Response(401, json={"title": "Unauthorized"})
        if req.headers.get("X-CMI-TENANT-NAME") != "sekbuelach":
            return httpx.Response(400, json={"userMessage": "Mandant fehlt"})
        teile = req.url.path.split("/api/proxy/", 1)[1].split("/")
        m = req.method
        if teile == ["cmiTenants"]:
            return httpx.Response(200, json=[{"tenantName": "sekbuelach", "webClientUrl": "https://cmi.test"}])
        if teile[:2] == ["Dokument", "CheckOut"]:
            self.ausgecheckt = teile[2]
            return httpx.Response(200)
        if teile[:2] == ["Dokument", "CheckIn"]:
            if getattr(self, "ausgecheckt", None) != teile[2]:
                return httpx.Response(400, json={"userMessage": "Document is not checked out"})
            grenze = req.headers["content-type"].split("boundary=")[1].encode()
            for teil in req.content.split(b"--" + grenze):
                if b'name="file"' in teil:
                    self.dateien[teile[2]] = teil.split(b"\r\n\r\n", 1)[1].rsplit(b"\r\n", 1)[0]
            return httpx.Response(200)
        if teile[:2] == ["Dokument", "FileContent"]:
            if teile[2] not in self.dateien:
                return httpx.Response(404)
            return httpx.Response(200, content=self.dateien[teile[2]], headers={"content-type": "application/pdf"})
        e = teile[0]
        if e not in self.daten:
            return httpx.Response(404)
        if len(teile) == 2 and teile[1] == "Search" and m == "POST":
            return httpx.Response(200, json=self._treffer(e, json.loads(req.content)))
        if len(teile) == 1 and m == "POST":
            body = json.loads(req.content)
            if e == "Kontakt":
                fehlt = [b for b in A.KONTAKT_PFLICHT_BOOL if b not in body]
                if fehlt:
                    return httpx.Response(400, json={"userMessage": f"Pflichtfeld fehlt: {fehlt[0]}"})
            if e == "Geschaeft" and "Vorlage" not in req.url.params:
                return httpx.Response(400, json={"userMessage": "Pflichtfeld fehlt: laufnummer"})
            g = str(uuid.uuid4())
            self.daten[e][g] = {**body, "guid": g, "version": 1}
            self._verknuepfen(e, g)
            return httpx.Response(200, json=g)
        if len(teile) == 2 and m == "GET":
            o = self.daten[e].get(teile[1])
            return httpx.Response(200, json=o) if o else httpx.Response(404)
        if len(teile) == 2 and m == "PUT":
            if teile[1] not in self.daten[e]:
                return httpx.Response(404)
            if not self.ignoriere_put:
                alt = self.daten[e][teile[1]]
                body = json.loads(req.content)
                listen = {k: v for k, v in alt.items() if isinstance(v, list) and k not in body}
                self.daten[e][teile[1]] = {**body, **listen, "version": alt["version"] + 1}
            return httpx.Response(200)
        return httpx.Response(405)

    def schreibaufrufe(self):
        return [r for r in self.aufrufe if r.url.host != "login.test"
                and r.method != "GET" and not r.url.path.endswith("/Search")]


@pytest.fixture
def fake(monkeypatch):
    f = FakeCMI()
    cfg = CMIConfig(base_url="https://cmi.test/api/proxy", mandant="sekbuelach", entra_tenant_id="schule",
                    client_id="app", client_secret="geheim", login_url="https://login.test")
    monkeypatch.setattr(A, "_client", CMIClient(cfg, transport=httpx.MockTransport(f)))
    monkeypatch.setattr(A, "API_KEY", "key")
    monkeypatch.setattr(A, "SCHREIBEN", True)
    monkeypatch.setattr(A, "E", A.Einstellungen(
        schueler_vorlage="Vorlagen/Schuelerdossier", schueler_typ="Schuelerdossier",
        personal_vorlage="Vorlagen/Personaldossier", personal_typ="Personaldossier", klasse_typ="Klassendossier",
        kz_entitaet="Klassenzuteilung"))
    return f


@pytest.fixture
def api():
    return TestClient(A.app, headers={"X-API-Key": "key"})


# ================================================================ Grundlagen

def test_ohne_api_key_401(fake):
    assert TestClient(A.app).get("/status").status_code == 401


def test_status_und_tenants(fake, api):
    s = api.get("/status").json()
    assert s["konfiguriert"] and s["schreiben"] and s["eingerichtet"]["klassenzuteilung"]
    assert api.get("/tenants").json()[0]["tenantName"] == "sekbuelach"
    assert fake.token_abrufe == 1  # Token wird zwischengespeichert


def test_nicht_eingerichtet_501(monkeypatch, api):
    monkeypatch.setattr(A, "_client", CMIClient(CMIConfig()))
    assert api.get("/kontakte?fremdkey=1").status_code == 501


def test_schreiben_aus_403_probelauf_erlaubt(fake, api, monkeypatch):
    monkeypatch.setattr(A, "SCHREIBEN", False)
    body = {"kontakte": [{"fremdkey": "E1", "name": "Muster", "vorname": "Lea"}]}
    assert api.post("/kontakte/sync", json=body).status_code == 403
    assert api.post("/kontakte/sync?probelauf=true", json=body).status_code == 200
    assert fake.schreibaufrufe() == []


def test_freie_suche_nur_erlaubte_entitaeten(fake, api):
    fake.neu("Kontakt", fremdkey="E1", name="Muster")
    assert len(api.get("/suche/Kontakt", params={"tentaql": 'name = "Muster"'}).json()) == 1
    assert api.get("/suche/Benutzer", params={"tentaql": "x"}).status_code == 400


def test_client_loescht_nie(fake):
    with pytest.raises(RuntimeError):
        A._client._senden("DELETE", "Kontakt/123")


def test_tentaql_maskiert_anfuehrungszeichen(fake):
    assert A._client.gleich(name='O"Neil') == 'name = "O\\"Neil"'
    with pytest.raises(ValueError):
        A._client.gleich(**{"name; drop": "x"})


# ================================================================ Kontakte

LEA = {"fremdkey": "E1", "name": "Muster", "vorname": "Lea", "email": "lea@example.org",
       "geburtsdatum": "2012-03-04", "adresse": {"strasse": "Testweg 1", "plz": "8180", "ort": "Bülach"}}


def test_kontakt_anlegen_mit_adresse_und_kontrolle(fake, api):
    r = api.post("/kontakte/sync", json={"kontakte": [LEA]})
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["vollstaendig"] and d["zusammenfassung"]["anlegen"] == 1
    assert [s["schritt"] for s in d["kontakte"][0]["schritte"]] == ["kontakt_anlegen", "adresse_anlegen", "kontrolle"]
    k = next(iter(fake.daten["Kontakt"].values()))
    assert k["fremdkey"] == "E1" and k["inaktiv"] is False and k["behindert"] is False
    a = next(iter(fake.daten["Adresse"].values()))
    assert a["kontakt"]["guid"] == k["guid"] and a["ort"] == "Bülach"


def test_kontakt_zweimal_unveraendert(fake, api):
    api.post("/kontakte/sync", json={"kontakte": [LEA]})
    vorher = len(fake.schreibaufrufe())
    # CMI liefert Datum mit Uhrzeit zurück – darf nicht als Änderung gelten
    k = next(iter(fake.daten["Kontakt"].values()))
    k["geburtsdatum"] = "2012-03-04T00:00:00"
    d = api.post("/kontakte/sync", json={"kontakte": [LEA]}).json()
    assert d["kontakte"][0]["aktion"] == "unveraendert"
    assert len(fake.schreibaufrufe()) == vorher


def test_kontakt_nur_geaenderte_felder(fake, api):
    api.post("/kontakte/sync", json={"kontakte": [LEA]})
    neu = {**LEA, "email": "lea.muster@example.org", "adresse": {**LEA["adresse"], "strasse": "Neuweg 2"}}
    p = api.post("/kontakte/sync?probelauf=true", json={"kontakte": [neu]}).json()["kontakte"][0]
    assert p["aktion"] == "aendern" and list(p["aenderungen"]) == ["email"]
    assert p["adressen"][0]["aenderungen"] == {"strasse": ["Testweg 1", "Neuweg 2"]}
    d = api.post("/kontakte/sync", json={"kontakte": [neu]}).json()
    assert d["vollstaendig"]
    k = next(iter(fake.daten["Kontakt"].values()))
    assert k["email"] == "lea.muster@example.org" and k["vorname"] == "Lea" and k["adressen"]
    assert next(iter(fake.daten["Adresse"].values()))["strasse"] == "Neuweg 2"


PRIVAT, GESCHAEFT, KAT1, KAT2 = "art-privat", "art-geschaeft", "kat-1", "kat-2"
ALLES = {"fremdkey": "T1", "anrede": "Herr", "briefanrede": "Sehr geehrter Herr Test", "titel": "Dr. TEST",
         "name": "_TEST", "vorname": "_TEST", "organisation": "TEST Organisation", "funktion": "TEST Funktion",
         "email": "test.geschaeft@example.org", "email2": "test.privat@example.org", "natel": "079 000 00 03",
         "telefonPrivat": "000 000 00 01", "telefonGeschaeft": "000 000 00 04", "faxPrivat": "000 000 00 02",
         "faxGeschaeft": "000 000 00 05", "homepage": "https://example.org", "unternehmensId": "TEST-UID",
         "subjektart": "Natürlich", "kategorien": [KAT1],
         "adressen": [{"adressart": PRIVAT, "strasse": "Testweg 99", "plz": "9999", "ort": "Testdorf",
                       "gueltig_von": "2026-01-01"},
                      {"adressart": GESCHAEFT, "strasse": "Schulweg 1", "plz": "9998", "ort": "Testdorf"}]}


def test_kontakt_alle_felder_schreiben_und_leeren(fake, api):
    # Felder wie am Testkontakt _TEST in der CMI-Oberfläche am 25.11.2026 beschrieben (erfundene Werte)
    d = api.post("/kontakte/sync", json={"kontakte": [ALLES]}).json()
    assert d["vollstaendig"], d
    k = next(iter(fake.daten["Kontakt"].values()))
    for f in ("titel", "funktion", "faxPrivat", "faxGeschaeft", "homepage", "unternehmensId", "briefanrede"):
        assert k[f] == ALLES[f], f
    assert k["subjektart"] == "Natürlich" and k["kategorie"] == [{"guid": KAT1}]
    adr = {a["strasse"]: a for a in fake.daten["Adresse"].values()}
    assert adr["Testweg 99"]["adressart"] == {"guid": PRIVAT} and adr["Testweg 99"]["gueltigVonBis"] == "01.01.2026 -"
    assert adr["Schulweg 1"]["adressart"] == {"guid": GESCHAEFT}
    # zweiter Lauf: unverändert
    assert api.post("/kontakte/sync", json={"kontakte": [ALLES]}).json()["kontakte"][0]["aktion"] == "unveraendert"
    # Kategorie wechseln, Geschäftsadresse gezielt ändern, Felder leeren
    neu = {"fremdkey": "T1", "kategorien": [KAT2], "leeren": ["titel", "funktion", "homepage", "subjektart"],
           "adressen": [{"adressart": GESCHAEFT, "strasse": "Schulweg 2", "gueltig_bis": "2026-12-31"}]}
    p = api.post("/kontakte/sync?probelauf=true", json={"kontakte": [neu]}).json()["kontakte"][0]
    assert set(p["aenderungen"]) == {"kategorie", "titel", "funktion", "homepage", "subjektart"}
    assert p["adressen"][0]["aenderungen"]["strasse"] == ["Schulweg 1", "Schulweg 2"]
    d = api.post("/kontakte/sync", json={"kontakte": [neu]}).json()
    assert d["vollstaendig"], d
    k = next(iter(fake.daten["Kontakt"].values()))
    assert k["titel"] is None and k["homepage"] is None and k["subjektart"] is None and k["kategorie"] == [{"guid": KAT2}]
    assert k["organisation"] == "TEST Organisation"  # nicht genannt → bleibt
    adr = {a["strasse"]: a for a in fake.daten["Adresse"].values()}
    assert adr["Schulweg 2"]["gueltigVonBis"] == "- 31.12.2026" and "Testweg 99" in adr


def test_kontakt_leeren_unbekanntes_feld_400(fake, api):
    r = api.post("/kontakte/sync", json={"kontakte": [{"fremdkey": "T1", "name": "X", "leeren": ["fremdkey"]}]})
    assert r.status_code == 400
    zwei = [{"strasse": "A"}, {"strasse": "B"}]
    assert api.post("/kontakte/sync", json={"kontakte": [{"fremdkey": "T1", "name": "X", "adressen": zwei}]}).status_code == 400


def test_kontakt_cmi_uebernimmt_nicht_409(fake, api):
    api.post("/kontakte/sync", json={"kontakte": [LEA]})
    fake.ignoriere_put = True
    r = api.post("/kontakte/sync", json={"kontakte": [{**LEA, "natel": "079 000 00 00"}]})
    assert r.status_code == 409
    assert r.json()["kontakte"][0]["schritte"][-1]["schritt"] == "kontrolle"


def test_kontakt_doppelt_in_cmi_409_ohne_schreiben(fake, api):
    fake.neu("Kontakt", fremdkey="E1", name="A")
    fake.neu("Kontakt", fremdkey="E1", name="B")
    r = api.post("/kontakte/sync", json={"kontakte": [LEA]})
    assert r.status_code == 409 and r.json()["detail"]["betroffene"][0]["fremdkey"] == "E1"
    assert fake.schreibaufrufe() == []


def test_kontakt_eingabe_pruefen(fake, api):
    assert api.post("/kontakte/sync", json={"kontakte": [LEA, LEA]}).status_code == 400
    assert api.post("/kontakte/sync", json={"kontakte": [{"fremdkey": "X"}]}).status_code == 400
    assert fake.schreibaufrufe() == []


def test_kontakte_csv(fake, api):
    fake.neu("Kontakt", fremdkey="E1", name="Muster", vorname="Lea", geschlecht={"guid": "g", "displayName": "w"})
    r = api.get("/kontakte?name=Muster&format=csv")
    assert r.headers["content-type"].startswith("text/csv") and "Muster" in r.text and ";w" in r.text


# ================================================================ Dossiers

def _kontakt(fake, fremdkey="E1", name="Muster", vorname="Lea", geburtsdatum="2012-03-04T00:00:00"):
    return fake.neu("Kontakt", fremdkey=fremdkey, name=name, vorname=vorname, geburtsdatum=geburtsdatum)


def test_schuelerdossier_anlegen(fake, api):
    k = _kontakt(fake)
    p = api.post("/dossiers/schueler?probelauf=true", json={"fremdkey": "E1", "beginn": "2026-08-17"}).json()
    assert p["dossier"]["titel"] == "Muster Lea (2012)" and p["vorlage"] == "Vorlagen/Schuelerdossier"
    assert fake.schreibaufrufe() == []
    d = api.post("/dossiers/schueler", json={"fremdkey": "E1", "beginn": "2026-08-17"}).json()
    assert d["vollstaendig"], d
    g = fake.daten["Geschaeft"][d["guid"]]
    assert g["typeName"] == "Schuelerdossier" and g["schluesselFremdsystem"] == "E1"
    assert g["zugriffsteuerung"] == "Restriktiv" and g["beginn"] == "2026-08-17"
    assert fake.schreibaufrufe()[0].url.params["Vorlage"] == "Vorlagen/Schuelerdossier"
    assert d["schritte"][1]["uebersprungen"]  # keine Beteiligung eingerichtet
    assert k


def test_dossier_zweimal_409(fake, api):
    _kontakt(fake)
    api.post("/dossiers/schueler", json={"fremdkey": "E1"})
    r = api.post("/dossiers/schueler", json={"fremdkey": "E1"})
    assert r.status_code == 409 and r.json()["detail"]["betroffene"][0]["titel"].startswith("Muster Lea")


def test_dossier_ohne_kontakt_400(fake, api):
    assert api.post("/dossiers/personal", json={"fremdkey": "LP9"}).status_code == 400


def test_personaldossier_mit_beteiligung(fake, api, monkeypatch):
    k = _kontakt(fake, fremdkey="LP1", name="Beispiel", vorname="Tom", geburtsdatum=None)
    monkeypatch.setattr(A.E, "beteiligung_entitaet", "Beteiligung")
    monkeypatch.setattr(A.E, "beteiligung_rolle", "Mitarbeitende:r")
    d = api.post("/dossiers/personal", json={"fremdkey": "LP1"}).json()
    assert d["vollstaendig"] and d["titel"] == "Beispiel Tom"
    b = next(iter(fake.daten["Beteiligung"].values()))
    assert b["kontakt"]["guid"] == k and b["geschaeft"]["guid"] == d["guid"] and b["rolle"] == "Mitarbeitende:r"


def test_dossier_nicht_eingerichtet_501(fake, api, monkeypatch):
    monkeypatch.setattr(A, "E", A.Einstellungen())
    _kontakt(fake)
    assert api.post("/dossiers/schueler", json={"fremdkey": "E1"}).status_code == 501


# ================================================================ Erstellen wie bei Escola (POST /kontakte, /schueler, /mitarbeitende)
# Abläufe wie am 25.11.2026 in der CMI-Oberfläche mit _TEST_Schueler und _TEST_Mitarbeiter geprüft (erfundene Werte).

WEIBLICH, MAENNLICH = "geschlecht-w", "geschlecht-m"


def test_kontakt_anlegen_und_doppelt_409(fake, api):
    body = {"fremdkey": "T2", "anrede": "Herr", "name": "_TEST2", "vorname": "_TEST2", "geburtsdatum": "2000-01-01",
            "geschlecht": MAENNLICH, "email2": "test2.privat@example.org",
            "adresse": {"strasse": "Testweg 2", "plz": "9999", "ort": "Testdorf"}}
    assert api.post("/kontakte?probelauf=true", json=body).json()["aktion"] == "anlegen"
    assert fake.schreibaufrufe() == []
    r = api.post("/kontakte", json=body)
    assert r.status_code == 201 and r.json()["vollstaendig"], r.text
    k = fake.daten["Kontakt"][r.json()["guid"]]
    assert k["geschlecht"] == {"guid": MAENNLICH} and k["fremdkey"] == "T2"
    assert api.post("/kontakte", json=body).status_code == 409


def test_kontakt_patch_per_guid(fake, api):
    g = fake.neu("Kontakt", name="_TEST", vorname="_TEST", anrede="Herr", titel="Dr.", fremdkey=None)
    r = api.patch(f"/kontakte/{g}", json={"funktion": "TEST Funktion", "leeren": ["titel"], "fremdkey": "T9"})
    assert r.status_code == 200 and r.json()["vollstaendig"], r.text
    k = fake.daten["Kontakt"][g]
    assert k["funktion"] == "TEST Funktion" and k["titel"] is None and k["fremdkey"] == "T9" and k["name"] == "_TEST"
    vorher = len(fake.schreibaufrufe())
    assert api.patch(f"/kontakte/{g}", json={"funktion": "TEST Funktion"}).json()["aktion"] == "unveraendert"
    assert len(fake.schreibaufrufe()) == vorher


def test_schueler_anlegen_kontakt_und_dossier(fake, api):
    body = {"fremdkey": "escola-650", "name": "_TEST_Schueler", "vorname": "_TEST_Schueler",
            "geburtsdatum": "2012-01-01", "geschlecht": WEIBLICH, "beginn": "2026-11-25",
            "bemerkung": "TEST Schnittstelle EduKSX"}
    p = api.post("/schueler?probelauf=true", json=body).json()
    assert p["kontakt"]["aktion"] == "anlegen" and p["dossier"]["vorlage"] == "Vorlagen/Schuelerdossier"
    r = api.post("/schueler", json=body)
    assert r.status_code == 201, r.text
    d = r.json()
    g = fake.daten["Geschaeft"][d["dossier_guid"]]
    assert g["person"] == {"guid": d["kontakt_guid"]} and g["bemerkung"] == "TEST Schnittstelle EduKSX"
    assert g["typeName"] == "Schuelerdossier" and g["beginn"] == "2026-11-25"
    assert [s["teil"] for s in d["schritte"]].count("kontakt") >= 2
    assert api.post("/schueler", json=body).status_code == 409  # Dossier gibt es schon


def test_mitarbeitende_mit_standort_vorlage(fake, api, monkeypatch):
    monkeypatch.setattr(A.E, "personal_vorlagen", {"hinterbirch": "Vorlagen/Personal HB", "mettmenriet": "Vorlagen/Personal MR"})
    _kontakt(fake, fremdkey="LP7", name="_TEST_Mitarbeiter", vorname="_TEST_Mitarbeiter", geburtsdatum="1990-01-01")
    body = {"fremdkey": "LP7", "standort": "Hinterbirch"}
    assert api.post("/mitarbeitende", json={**body, "standort": "Zürich"}).status_code == 400
    r = api.post("/mitarbeitende", json=body)
    assert r.status_code == 201 and r.json()["kontakt_aktion"] == "unveraendert", r.text
    assert fake.schreibaufrufe()[0].url.params["Vorlage"] == "Vorlagen/Personal HB"


def test_schueler_ohne_einrichtung_501_ohne_schreiben(fake, api, monkeypatch):
    monkeypatch.setattr(A, "E", A.Einstellungen())
    r = api.post("/schueler", json={"fremdkey": "X1", "name": "_TEST"})
    assert r.status_code == 501 and fake.schreibaufrufe() == []


# ================================================================ Klassen

def _klassen_setup(fake):
    a = fake.neu("Geschaeft", titel="1a", typeName="Klassendossier")
    b = fake.neu("Geschaeft", titel="1b", typeName="Klassendossier")
    s = _kontakt(fake)
    return a, b, s


def test_einteilen_umteilen(fake, api):
    a, b, s = _klassen_setup(fake)
    d = api.post("/klassen/einteilen", json={"ab": "2026-08-17", "zuteilungen": [{"fremdkey": "E1", "klasse": "1A"}]}).json()
    assert d["vollstaendig"] and d["zuteilungen"][0]["aktion"] == "einteilen"
    assert [z["fremdkey"] if "fremdkey" in z else z["schueler"] for z in api.get(f"/klassen/{a}/schueler?stichtag=2026-09-01").json()] == [s]
    # Umteilen ab 1.2.2027: bisherige endet am Vortag
    p = api.post("/klassen/einteilen?probelauf=true",
                 json={"ab": "2027-02-01", "zuteilungen": [{"fremdkey": "E1", "klasse": b}]}).json()
    assert p["zuteilungen"][0]["aktion"] == "umteilen" and p["zuteilungen"][0]["bisher_bis"] == "2027-01-31"
    d = api.post("/klassen/einteilen", json={"ab": "2027-02-01", "zuteilungen": [{"fremdkey": "E1", "klasse": b}]}).json()
    assert d["vollstaendig"], d
    laufbahn = api.get("/schueler/E1/klassen").json()
    assert [(z["klasse_name"], z["von"], z["bis"]) for z in laufbahn] == [
        ("1a", "2026-08-17", "2027-01-31"), ("1b", "2027-02-01", None)]
    # nochmals: unverändert, kein Schreiben
    vorher = len(fake.schreibaufrufe())
    d = api.post("/klassen/einteilen", json={"ab": "2027-03-01", "zuteilungen": [{"fremdkey": "E1", "klasse": "1b"}]}).json()
    assert d["zuteilungen"][0]["aktion"] == "unveraendert" and len(fake.schreibaufrufe()) == vorher


def test_einteilen_am_selben_tag_korrigiert(fake, api):
    a, b, s = _klassen_setup(fake)
    api.post("/klassen/einteilen", json={"ab": "2026-08-17", "zuteilungen": [{"fremdkey": "E1", "klasse": "1a"}]})
    d = api.post("/klassen/einteilen", json={"ab": "2026-08-17", "zuteilungen": [{"fremdkey": "E1", "klasse": "1b"}]}).json()
    assert d["vollstaendig"] and d["zuteilungen"][0]["aktion"] == "korrigieren"
    assert len(fake.daten["Klassenzuteilung"]) == 1


def test_einteilen_prueft_vorher(fake, api):
    _klassen_setup(fake)
    r = api.post("/klassen/einteilen", json={"zuteilungen": [{"fremdkey": "E1", "klasse": "9z"},
                                                             {"fremdkey": "E404", "klasse": "1a"}]})
    assert r.status_code == 400 and len(r.json()["detail"]["betroffene"]) == 2
    assert fake.schreibaufrufe() == []


def test_einteilen_kontrolle_409(fake, api):
    a, b, s = _klassen_setup(fake)
    api.post("/klassen/einteilen", json={"ab": "2026-08-17", "zuteilungen": [{"fremdkey": "E1", "klasse": "1a"}]})
    fake.ignoriere_put = True
    r = api.post("/klassen/einteilen", json={"ab": "2027-02-01", "zuteilungen": [{"fremdkey": "E1", "klasse": "1b"}]})
    assert r.status_code == 409  # alte Zuteilung nicht beendet → zwei aktive


def test_klassenzuteilung_nicht_eingerichtet_501(fake, api, monkeypatch):
    monkeypatch.setattr(A.E, "kz_entitaet", "")
    assert api.post("/klassen/einteilen", json={"zuteilungen": [{"fremdkey": "E1", "klasse": "1a"}]}).status_code == 501


# ================================================================ Dokumente

PDF = b"%PDF-1.4 erfundenes Zeugnis"


def _dossier(fake):
    g = fake.neu("Geschaeft", titel="Muster Lea (2012)", typeName="Schuelerdossier", schluesselFremdsystem="E1")
    return g


def test_dokument_hochladen_mit_ordnerpfad(fake, api):
    g = _dossier(fake)
    oben = fake.neu("Ordner", titel="Zeugnisse", parent=None, geschaeft={"guid": g})
    files = {"datei": ("zeugnis.pdf", PDF, "application/pdf")}
    form = {"ordner": "Zeugnisse/2025-26", "ordner_anlegen": "true", "dokumentdatum": "2026-07-03",
            "schluessel": "zeugnis-E1-2026-S2"}
    p = api.post(f"/dossiers/{g}/dokumente?probelauf=true", files=files, data=form).json()
    assert p["ordner_anlegen"] == ["2025-26"] and p["titel"] == "zeugnis" and fake.schreibaufrufe() == []
    r = api.post(f"/dossiers/{g}/dokumente", files=files, data=form)
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["vollstaendig"] and fake.dateien[d["guid"]] == PDF
    unter = [o for o in fake.daten["Ordner"].values() if o["titel"] == "2025-26"][0]
    assert unter["parent"]["guid"] == oben
    dok = fake.daten["Dokument"][d["guid"]]
    assert dok["ordner"]["guid"] == unter["guid"] and dok["schluesselFremdsystem"] == "zeugnis-E1-2026-S2"
    pfade = {o["pfad"] for o in api.get(f"/dossiers/{g}/ordner").json()}
    assert pfade == {"Zeugnisse", "Zeugnisse/2025-26"}
    assert api.get(f"/dokumente/{d['guid']}/inhalt").content == PDF
    # gleicher Schlüssel nochmals → 409
    r2 = api.post(f"/dossiers/{g}/dokumente", files=files, data={**form, "titel": "anders"})
    assert r2.status_code == 409


def test_dokument_in_vorhandenen_unterordner(fake, api):
    # Ordner wie im Lernendendossier der Sek Bülach (Erkundung 25.11.2026)
    g = _dossier(fake)
    b = fake.neu("Ordner", titel="b_Dossier Schule", parent=None, geschaeft={"guid": g})
    beurteilung = fake.neu("Ordner", titel="08_Beurteilung", parent={"guid": b}, geschaeft={"guid": g})
    files = {"datei": ("TEST_Zeugnis.pdf", PDF, "application/pdf")}
    # fehlender Ordner ohne ordner_anlegen → 400, nichts geschrieben
    r = api.post(f"/dossiers/{g}/dokumente", files=files, data={"ordner": "b_Dossier Schule/99_Neu"})
    assert r.status_code == 400 and r.json()["detail"]["fehlend"] == ["99_Neu"] and fake.schreibaufrufe() == []
    d = api.post(f"/dossiers/{g}/dokumente", files=files,
                 data={"ordner": "b_dossier schule/08_Beurteilung", "autor": "TEST Autor", "thema": "Zeugnis"}).json()
    assert d["vollstaendig"], d
    dok = fake.daten["Dokument"][d["guid"]]
    assert dok["ordner"] == {"guid": beurteilung} and dok["autor"] == "TEST Autor" and dok["titel"] == "TEST_Zeugnis"
    # direkt per ordner_guid; fremde GUID → 400
    assert api.post(f"/dossiers/{g}/dokumente", files={"datei": ("b.pdf", PDF)}, data={"ordner_guid": "fremd"}).status_code == 400
    d2 = api.post(f"/dossiers/{g}/dokumente", files={"datei": ("b.pdf", PDF)}, data={"ordner_guid": b}).json()
    assert fake.daten["Dokument"][d2["guid"]]["ordner"] == {"guid": b}


def test_dokument_gleicher_titel_409(fake, api):
    g = _dossier(fake)
    api.post(f"/dossiers/{g}/dokumente", files={"datei": ("a.pdf", PDF)})
    assert api.post(f"/dossiers/{g}/dokumente", files={"datei": ("a.pdf", PDF)}).status_code == 409


def test_dokument_leer_oder_dossier_fehlt(fake, api):
    g = _dossier(fake)
    assert api.post(f"/dossiers/{g}/dokumente", files={"datei": ("a.pdf", b"")}).status_code == 400
    assert api.post("/dossiers/unbekannt/dokumente", files={"datei": ("a.pdf", PDF)}).status_code == 404


def test_dokument_inhalt_nicht_uebernommen_409(fake, api, monkeypatch):
    g = _dossier(fake)
    monkeypatch.setattr(fake, "_verknuepfen", lambda e, guid: None)  # CMI verwirft die Datei
    r = api.post(f"/dossiers/{g}/dokumente", files={"datei": ("a.pdf", PDF)})
    assert r.status_code == 409 and r.json()["schritte"][-1]["schritt"] == "kontrolle"


def test_dokument_hochladen_per_checkin(fake, api, monkeypatch):
    monkeypatch.setattr(A.E, "upload_art", "checkin")
    g = _dossier(fake)
    d = api.post(f"/dossiers/{g}/dokumente", files={"datei": ("brief.pdf", PDF)}, data={"titel": "Brief"}).json()
    assert d["vollstaendig"], d
    assert [s["schritt"] for s in d["schritte"]] == ["dokument_anlegen", "datei_einchecken", "kontrolle"]
    assert fake.dateien[d["guid"]] == PDF


# ================================================================ Kontakt vollständig lesen
# Aufbau wie in der Erkundung vom 25.11.2026 (ERKUNDUNG.md), Person und Adressen erfunden.

def _kontakt_mit_allem(fake):
    k = fake.neu("Kontakt", name="Muster", vorname="Lea", anrede="Frau", email="lea@example.org", inaktiv=False,
                 fremdkey=None, kategorie={"guid": "kat1", "displayName": "Fachstelle Test"},
                 subjektart={"iconId": None, "text": None, "value": None})
    a1 = fake.neu("Adresse", strasse="Testweg 1", pLZ="8180", ort="Bülach", inaktiv=False,
                  adressart={"guid": "aa1", "displayName": "Privatadresse"},
                  gueltigVonBis={"start": {"precision": "Day", "value": "2024-10-21T00:00:00"},
                                 "end": {"precision": None, "value": None}})
    a2 = fake.neu("Adresse", strasse="Altweg 3", plz="8180", ort="Bülach", inaktiv=True,
                  adressart={"guid": "aa2", "displayName": "Geschäftsadresse"},
                  gueltigVonBis={"start": {"value": "2020-08-01T00:00:00"}, "end": {"value": "2026-01-31T23:59:59"}})
    d1 = fake.neu("Dossierkontakt", rolle="Person", computedDossier={"guid": "pd1", "displayName": "Lea Muster"},
                  dossierLaufnummer="2024-0001", dossierStatus="InBearbeitung", dossiertitel="Lea Muster",
                  dossierTyp="Personaldossier", dauer={"start": None, "end": None})
    z1 = fake.neu("Zahlungsinformation", iban="CH00 0000 0000 0000 0000 0")
    o = fake.daten["Kontakt"][k]
    o.update(adressen=f"{a1};{a2}", dossierkontakte=[{"guid": d1}], zahlungsinformationen=[{"guid": z1}],
             medizinischeInformationen="", beziehungenA="", gebiete=[{"guid": "fehlt"}],
             notizen=[{"guid": "n1", "displayName": "Notiz"}])
    return k


def test_kontakt_vollstaendig(fake, api):
    k = _kontakt_mit_allem(fake)
    d = api.get(f"/kontakte/{k}/vollstaendig").json()
    assert d["kontakt"]["name"] == "Muster" and d["kontakt"]["kategorie"] == "Fachstelle Test"
    assert [(a["strasse"], a["plz"], a["adressart"], a["gueltig_von"], a["gueltig_bis"]) for a in d["adressen"]] == [
        ("Testweg 1", "8180", "Privatadresse", "2024-10-21", None),
        ("Altweg 3", "8180", "Geschäftsadresse", "2020-08-01", "2026-01-31")]
    assert d["dossiers"] == [{"guid": d["dossiers"][0]["guid"], "rolle": "Person", "dossier_guid": "pd1",
                              "dossiertitel": "Lea Muster", "laufnummer": "2024-0001", "dossiertyp": "Personaldossier",
                              "status": "InBearbeitung", "von": None, "bis": None}]
    # schützenswert: ohne Schalter nur Anzahl, keine IBAN
    assert d["geschuetzt"]["zahlungsinformationen"] == {"anzahl": 1}
    assert "CH00" not in json.dumps(d)
    # nicht lesbare Beziehung wird gemeldet, unbekannte nur als Verweis
    assert d["nicht_lesbar"][0]["beziehung"] == "gebiete"
    assert d["weitere_beziehungen"] == {"notizen": [{"guid": "n1", "name": "Notiz"}]}
    assert fake.schreibaufrufe() == []


def test_kontakt_vollstaendig_schuetzenswert(fake, api, monkeypatch):
    k = _kontakt_mit_allem(fake)
    monkeypatch.setattr(A, "SCHUETZENSWERT", True)
    d = api.get(f"/kontakte/{k}/vollstaendig").json()
    assert d["geschuetzt"]["zahlungsinformationen"]["eintraege"][0]["iban"].startswith("CH00")
    monkeypatch.setattr(A, "API_KEY", "")  # ohne API-Key nie
    d = TestClient(A.app).get(f"/kontakte/{k}/vollstaendig").json()
    assert "eintraege" not in d["geschuetzt"]["zahlungsinformationen"]


def test_kontakt_adressen_und_dossiers(fake, api):
    k = _kontakt_mit_allem(fake)
    assert [a["strasse"] for a in api.get(f"/kontakte/{k}/adressen?nur_aktive=true").json()] == ["Testweg 1"]
    assert api.get(f"/kontakte/{k}/dossiers").json()[0]["dossiertyp"] == "Personaldossier"
    assert "Testweg 1" in api.get(f"/kontakte/{k}/adressen?format=csv").text


# ================================================================ Lesen schreibt nie

def test_lesen_loest_keine_schreibaufrufe_aus(fake, api):
    a, b, s = _klassen_setup(fake)
    g = _dossier(fake)
    for pfad in ("/status", "/tenants", "/kontakte?fremdkey=E1", "/klassen", f"/klassen/{a}/schueler",
                 "/schueler/E1/klassen", "/dossiers?art=schueler&fremdkey=E1", f"/dossiers/{g}",
                 f"/dossiers/{g}/ordner", f"/dossiers/{g}/dokumente"):
        assert api.get(pfad).status_code == 200, pfad
    assert fake.schreibaufrufe() == []
    assert A._client.zaehler.schreiben == 0
