# CMI-API

Schnittstelle zu **CMI** (CM Informatik AG) – CMI Schule bzw. CMI Cloud, wo die Sek Bülach das zentrale Dossier
und das Archiv führt. Aufgebaut wie die Escola-API, genutzt von IDA, CONNECT und weiteren EduKSX-Modulen.

Grundfunktionen:
- **Kontakte synchronisieren bzw. anlegen** – Abgleich über den Schlüssel des Quellsystems (`fremdkey`), nur
  geänderte Felder werden geschrieben, Adresse inklusive
- **Schüler- und MA/LP-Dossier erstellen** – aus Dossiervorlage, mit Duplikatprüfung
- **SuS in Klassen einteilen und umteilen** – ab Datum, bisherige Zuteilung endet am Vortag
- **Dokumente ins Dossier hochladen** – Ordnerpfad wird angelegt, Duplikatprüfung, Kontrolle des Inhalts

Grundlage: die öffentliche REST-API des CMI-Proxys, wie sie der zertifizierte Power-Platform-Connector von
CM Informatik beschreibt (`microsoft/PowerPlatformConnectors`, Ordner `certified-connectors/CM Informatik AG`,
`apiDefinition.swagger.json`, Stand November 2026).

## Stand

Version 0.1.0 – Gerüst nach der Swagger-Beschreibung, **noch nicht live geprüft** (kein Zugang). Tests laufen gegen
ein nachgebautes CMI mit erfundenen Personen.

### ZU PRÜFEN (mit CM Informatik bzw. den CMI-Verantwortlichen der Sek Bülach)

| Punkt | Annahme in 0.1.0 | Einstellung |
|---|---|---|
| Basis-URL / Proxy-Gruppe | `https://aadbridge.prod.cmicloud.ch/api/proxy` (der Connector nutzt `…/groups/cmi-powerplattform-customconnector`) | `CMI_BASE_URL` |
| Anmeldung | Entra ID, Client-Credentials einer App-Registrierung der Schule, Scope `api://cmi-proxy-aadbridge-prod-…/.default`; der Connector meldet sich im Namen eines Benutzers an (`access_as_user`) – ob App-only erlaubt ist, klärt CMI | `CMI_ENTRA_TENANT_ID`, `CMI_CLIENT_ID`, `CMI_CLIENT_SECRET`, `CMI_SCOPE` oder `CMI_TOKEN` |
| Mandant | Header `X-CMI-TENANT-NAME` | `CMI_MANDANT` (`GET /tenants` zeigt sie) |
| TentaQl | `feld = "wert"`, verknüpft mit ` AND `; Suchtext als JSON-String | `CMI_TENTAQL_GLEICH`, `CMI_TENTAQL_UND`, `CMI_SUCHE_ALS_JSON` |
| Dossiervorlagen und Typnamen | Schüler-, Personal- und Klassendossier über Vorlage (`?Vorlage=`) und `typeName`; Vorlage setzt Laufnummer, Registraturplan und Eigner | `CMI_DOSSIER_*` |
| Verknüpfung Kontakt ↔ Dossier | über `schluesselFremdsystem` = `fremdkey`; optional zusätzlich eine Beteiligung | `CMI_BETEILIGUNG_ENTITAET`, `CMI_BETEILIGUNG_ROLLE` |
| Klassenzuteilung | eigene Entität mit Verweisen auf Schüler:in und Klasse und Datum von/bis; nicht im Swagger – über den allgemeinen Proxy-Pfad | `CMI_KLASSENZUTEILUNG_ENTITAET`, `CMI_KZ_*` |
| Ordner | Ordner der obersten Ebene haben keinen Eltern-Ordner im Dossier; Dokument kennt Feld `ordner` | – |
| Datei beim Anlegen | Base64 in `eDokument.renditions[]` (`fileName`, `file`); Alternative: anlegen, auschecken, einchecken (multipart, im Swagger belegt) | `CMI_UPLOAD_ART=rendition\|checkin` |
| Rate-Limit | Connector: 100 Aufrufe pro Minute und Verbindung | – |

Nicht jede Lizenz hat alle Endpunkte (Hinweis von CM Informatik). Mit `GET /suche/{entitaet}?tentaql=…` lässt sich
der Mandant lesend erkunden.

## Endpunkte

🔓 lesen · ✏️ schreiben (`CMI_SCHREIBEN=1`, API-Key, `?probelauf=true`) · ⏳ vorbereitet, meldet `501` bis eingerichtet.
Listen mit `?format=csv` (Semikolon, UTF-8 mit BOM).

| Endpunkt | Zugriff | CMI | Inhalt |
|---|---|---|---|
| `GET /status` | 🔓 | – | Version, eingerichtet ja/nein, Schalter, Anzahl Aufrufe |
| `GET /tenants` | 🔓 | `GET /cmiTenants` | Mandanten der Anmeldung |
| `GET /suche/{entitaet}?tentaql=` | 🔓 | `POST /{E}/Search` | freie Suche (Kontakt, Adresse, Person, Geschaeft, Ordner, Dokument, Aktivitaet …) |
| `GET /kontakte` | 🔓 | `POST /Kontakt/Search` | Suche nach `fremdkey`, `name`, `vorname`, `email` oder `tentaql` |
| `GET /kontakte/{guid}` | 🔓 | `GET /Kontakt/{guid}` | ein Kontakt |
| `POST /kontakte/sync` | ✏️ | `Kontakt`, `Adresse` (Search, GET, POST, PUT) | bis 500 Kontakte abgleichen: anlegen, ändern, unverändert |
| `GET /dossiers` | 🔓 | `POST /Geschaeft/Search` | `?art=schueler\|personal\|klasse`, `fremdkey`, `titel` oder `tentaql` |
| `GET /dossiers/{guid}` | 🔓 | `GET /Geschaeft/{guid}` | ein Dossier |
| `GET /dossiers/{guid}/ordner` | 🔓 | `GET /Ordner/{guid}` | Ordner mit Pfad |
| `GET /dossiers/{guid}/dokumente` | 🔓 | `GET /Geschaeft/{guid}` | Dokumente des Dossiers |
| `POST /dossiers/schueler` | ✏️ ⏳ | `POST /Geschaeft?Vorlage=` | Schülerdossier zu einem Kontakt |
| `POST /dossiers/personal` | ✏️ ⏳ | `POST /Geschaeft?Vorlage=` | Personaldossier (Mitarbeitende, Lehrperson) |
| `GET /klassen` | 🔓 ⏳ | `POST /Geschaeft/Search` | Klassendossiers |
| `GET /klassen/{guid}/schueler` | 🔓 ⏳ | Klassenzuteilung | Zuteilungen am Stichtag (`?stichtag=`, `?alle=true`) |
| `GET /schueler/{fremdkey}/klassen` | 🔓 ⏳ | Klassenzuteilung | Schullaufbahn einer Schülerin / eines Schülers |
| `POST /klassen/einteilen` | ✏️ ⏳ | Klassenzuteilung (POST, PUT) | einteilen, umteilen, korrigieren ab Datum |
| `POST /dossiers/{guid}/dokumente` | ✏️ | `Ordner`, `Dokument`, `FileContent` | Datei hochladen (multipart) |
| `GET /dokumente/{guid}` | 🔓 | `GET /Dokument/{guid}` | Metadaten |
| `GET /dokumente/{guid}/inhalt` | 🔓 | `GET /Dokument/FileContent/{guid}` | Datei herunterladen (`?version=`) |

Nicht angeboten: Löschen jeder Art (der Client verweigert `DELETE`), Aktivitäten, Check-out/-in von Hand.

### Kontakte synchronisieren

```json
POST /kontakte/sync?probelauf=true
{"kontakte": [{"fremdkey": "escola-650", "name": "Muster", "vorname": "Lea", "geburtsdatum": "2012-03-04",
               "email": "lea@example.org", "adresse": {"strasse": "Testweg 1", "plz": "8180", "ort": "Bülach"}}]}
```

Ablauf: zuerst alle Kontakte prüfen (fremdkey doppelt in der Eingabe → `400`; mehrere CMI-Kontakte mit gleichem
fremdkey → `409`, nichts wird geschrieben). Dann je Kontakt anlegen (Pflicht-Ja/Nein-Felder von CMI auf `false`) oder
nur die abweichenden Felder ändern; Adresse: erste aktive Adresse ändern bzw. neu anlegen. Danach neu lesen und
vergleichen. Antwort je Kontakt: `aktion`, `aenderungen {feld: [alt, neu]}`, `schritte[]`; `vollstaendig`.
Übernimmt CMI etwas nicht → `409`.

Felder: `name`, `vorname`, `anrede`, `email`, `email2`, `natel`, `telefonPrivat`, `telefonGeschaeft`,
`geburtsdatum`, `organisation`, `mitarbeiter`, `inaktiv` (Namen wie in CMI). Leere Felder ändern nichts.

### Dossier erstellen

```json
POST /dossiers/schueler   {"fremdkey": "escola-650", "beginn": "2026-08-17"}
```

Prüft vorher: Kontakt mit diesem fremdkey vorhanden und eindeutig (sonst `400`/`409`), noch kein Dossier derselben
Art mit diesem Schlüssel (sonst `409`). Titel «Name Vorname» (SuS mit Jahrgang), `zugriffsteuerung` aus
`CMI_DOSSIER_ZUGRIFF` (Standard `Restriktiv`), Status «InBearbeitung». Danach optional Beteiligung, dann Kontrolle.

### Einteilen und umteilen

```json
POST /klassen/einteilen?probelauf=true
{"ab": "2027-02-01", "zuteilungen": [{"fremdkey": "escola-650", "klasse": "2b"}]}
```

`klasse` = GUID oder Titel des Klassendossiers. Aktionen: `einteilen` (keine aktive Zuteilung), `umteilen`
(bisherige endet am Vortag, neue ab Datum), `korrigieren` (bisherige beginnt am selben Tag → Klasse ersetzen),
`unveraendert`. Unbekannte Klasse oder Schüler:in → `400`, mehrere aktive Zuteilungen → `409`, beides vor dem Schreiben.

### Dokument hochladen

```bash
curl -H "X-API-Key: $KEY" -F datei=@zeugnis.pdf -F ordner="Zeugnisse/2025-26" -F dokumentdatum=2026-07-03 \
     -F schluessel=zeugnis-650-2026-S2 "http://localhost:8082/dossiers/$GUID/dokumente?probelauf=true"
```

Felder: `datei`, `titel` (Standard: Dateiname ohne Endung), `ordner`, `dokumentdatum`, `bemerkung`, `schluessel`.
Duplikat (gleicher `schluessel` irgendwo oder gleicher Titel im Dossier) → `409`. Fehlende Ordner werden angelegt.
Kontrolle: Titel, Dossier und SHA-256 des heruntergeladenen Inhalts. Grösse bis `CMI_MAX_MB` (Standard 50).

## Schutz

- `CMI_API_KEY`: jeder Aufruf braucht den Header `X-API-Key`; ohne Key kein Schreiben.
- Schreiben nur mit `CMI_SCHREIBEN=1`; `?probelauf=true` geht immer und schreibt nie.
- Personendossiers standardmässig mit Zugriffsteuerung «Restriktiv».
- Geheimnisse nur in `.env`; Token nur im Arbeitsspeicher.

## Fehler

`400` Eingabe ungültig bzw. von CMI abgelehnt · `401` X-API-Key bzw. Anmeldung bei CMI · `403` Schreiben aus ·
`404` nicht gefunden · `409` Duplikat, mehrdeutig oder CMI hat nicht übernommen (mit `betroffene` bzw. `schritte`) ·
`501` nicht eingerichtet · `502` CMI-Serverfehler.

## Lokal starten

```bash
cd apis/cmi
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env    # Mandant, Anmeldung und Einstellungen eintragen
set -a; source .env; set +a
uvicorn cmi_api.app:app --port 8082
pytest -q
```

## Verwendete Aufrufe von CMI

`GET /cmiTenants` · `GET|PUT /{Kontakt|Adresse|Geschaeft|Ordner|Dokument}/{guid}` · `POST /{…}` (mit `?Vorlage=`) ·
`POST /{…}/Search` · `GET /Dokument/FileContent/{guid}` · `POST /Dokument/CheckOut/{guid}` ·
`POST /Dokument/CheckIn/{guid}` · konfiguriert: Klassenzuteilung und Beteiligung (`GET|POST|PUT`, `Search`).
Token: `POST https://login.microsoftonline.com/{tenant}/oauth2/v2.0/token`.

## Versionen

| Version | Datum | Änderung |
|---|---|---|
| 0.1.0 | 2026-11-25 | Erste Fassung nach Swagger des CMI-Connectors: Kontakte synchronisieren, Schüler-/Personaldossier, Klassen einteilen/umteilen, Dokumente hochladen; Probelauf, Kontrolle nach dem Schreiben; Tests gegen nachgebautes CMI (#23) |
