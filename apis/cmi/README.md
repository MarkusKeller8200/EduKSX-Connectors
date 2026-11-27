# CMI-API

Schnittstelle zu **CMI** (CM Informatik AG) – CMI Schule bzw. CMI Cloud, wo die Sek Bülach das zentrale Dossier
und das Archiv führt. Aufgebaut wie die Escola-API, genutzt von IDA, CONNECT und weiteren EduKSX-Modulen.

Grundfunktionen:
- **Kontakte synchronisieren bzw. anlegen** – Abgleich über den Schlüssel des Quellsystems (`fremdkey`), nur
  geänderte Felder werden geschrieben, Adresse inklusive
- **Schüler- und MA/LP-Dossier erstellen** – aus Dossiervorlage, mit Duplikatprüfung
- **SuS in Klassen einteilen und umteilen** – ab Datum, bisherige Klassenzuteilung endet am Vortag (Schullaufbahn bleibt)
- **Zeugnisse gesammelt ablegen** – viele PDFs auf einmal, Zuordnung per `fremdkey`, Ordner Beurteilung
- **Dokumente ins Dossier hochladen** – Ordnerpfad wird angelegt, Duplikatprüfung, Kontrolle des Inhalts

Grundlage: die öffentliche REST-API des CMI-Proxys, wie sie der zertifizierte Power-Platform-Connector von
CM Informatik beschreibt (`microsoft/PowerPlatformConnectors`, Ordner `certified-connectors/CM Informatik AG`,
`apiDefinition.swagger.json`, Stand November 2026).

## Stand

Version 0.8.0 – Gerüst nach der Swagger-Beschreibung, ergänzt um die Erkundung im CMI der Sek Bülach vom 25.11.2026
([ERKUNDUNG.md](ERKUNDUNG.md)). **Noch nicht live geprüft** (kein Zugang zur offiziellen Schnittstelle). Tests laufen gegen
ein nachgebautes CMI mit erfundenen Personen.

### ZU PRÜFEN (mit CM Informatik bzw. den CMI-Verantwortlichen der Sek Bülach)

| Punkt | Annahme in 0.1.0 | Einstellung |
|---|---|---|
| Basis-URL / Proxy-Gruppe | `https://aadbridge.prod.cmicloud.ch/api/proxy` (der Connector nutzt `…/groups/cmi-powerplattform-customconnector`) | `CMI_BASE_URL` |
| Anmeldung | Entra ID, Client-Credentials einer App-Registrierung der Schule, Scope `api://cmi-proxy-aadbridge-prod-…/.default`; der Connector meldet sich im Namen eines Benutzers an (`access_as_user`) – ob App-only erlaubt ist, klärt CMI | `CMI_ENTRA_TENANT_ID`, `CMI_CLIENT_ID`, `CMI_CLIENT_SECRET`, `CMI_SCOPE` oder `CMI_TOKEN` |
| Mandant | Header `X-CMI-TENANT-NAME`; **bestätigt: `sekbuelach`** | `CMI_MANDANT` (`GET /tenants` zeigt sie) |
| TentaQl | `feld = "wert"`, verknüpft mit ` AND `; Suchtext als JSON-String | `CMI_TENTAQL_GLEICH`, `CMI_TENTAQL_UND`, `CMI_SUCHE_ALS_JSON` |
| Dossiervorlagen und Typnamen | **Typen bestätigt:** `Lernendendossier`, `Personaldossier`, `Schulklassendossier`; Vorlagen offen. Schüler-, Personal- und Klassendossier über Vorlage (`?Vorlage=`) und `typeName`; Vorlage setzt Laufnummer, Registraturplan und Eigner | `CMI_DOSSIER_*` |
| Verknüpfung Kontakt ↔ Dossier | über `schluesselFremdsystem` = `fremdkey`; optional zusätzlich eine Beteiligung | `CMI_BETEILIGUNG_ENTITAET`, `CMI_BETEILIGUNG_ROLLE` |
| Klassenzuteilung | **bestätigt (Test 25.11.2026):** Lernendendossier → Schullaufbahn (Schuljahr, von–bis, Eintrittsgrund) → Klassenzuteilung Lernende → Klassenstufe («Teilklasse») → Schulklassendossier; Entitätsnamen der offiziellen API offen | `CMI_SCHULLAUFBAHN_ENTITAET`, `CMI_KLASSENZUTEILUNG_ENTITAET`, `CMI_KLASSENSTUFE_ENTITAET` |
| Ordner | Ordner der obersten Ebene haben keinen Eltern-Ordner im Dossier; Dokument kennt Feld `ordner` | – |
| Datei beim Anlegen | Base64 in `eDokument.renditions[]` (`fileName`, `file`); Alternative: anlegen, auschecken, einchecken (multipart, im Swagger belegt) | `CMI_UPLOAD_ART=rendition\|checkin` |
| Rate-Limit | Connector: 100 Aufrufe pro Minute und Verbindung | – |

Nicht jede Lizenz hat alle Endpunkte (Hinweis von CM Informatik). Mit `GET /suche/{entitaet}?tentaql=…` lässt sich
der Mandant lesend erkunden.

## Endpunkte

🔓 lesen · 🔑 Teil nur mit eigenem Schalter und API-Key · ✏️ schreiben (`CMI_SCHREIBEN=1`, API-Key, `?probelauf=true`) · ⏳ vorbereitet, meldet `501` bis eingerichtet.
Listen mit `?format=csv` (Semikolon, UTF-8 mit BOM).

| Endpunkt | Zugriff | CMI | Inhalt |
|---|---|---|---|
| `GET /status` | 🔓 | – | Version, eingerichtet ja/nein, Schalter, Anzahl Aufrufe |
| `GET /tenants` | 🔓 | `GET /cmiTenants` | Mandanten der Anmeldung |
| `GET /suche/{entitaet}?tentaql=` | 🔓 | `POST /{E}/Search` | freie Suche (Kontakt, Adresse, Person, Geschaeft, Ordner, Dokument, Aktivitaet …) |
| `GET /kontakte` | 🔓 | `POST /Kontakt/Search` | Suche nach `fremdkey`, `name`, `vorname`, `email` oder `tentaql` |
| `GET /kontakte/{guid}` | 🔓 | `GET /Kontakt/{guid}` | ein Kontakt |
| `GET /kontakte/{guid}/vollstaendig` | 🔓 🔑 | `GET /Kontakt/{guid}` + Verweise | alles zu einem Kontakt: Adressen, Dossiers (Dossierkontakte/Beteiligungen), Schule, Bezugspersonen, Notfallkontakte, Haushalt, Fremdkey-Mappings, externe Benutzer, Adressdatensperre; Zahlungs- und Gesundheitsdaten nur mit `CMI_SCHUETZENSWERT=1` und API-Key, sonst nur Anzahl |
| `GET /kontakte/{guid}/adressen` | 🔓 | `GET /Adresse/{guid}` | Adressen mit Adressart und Gültigkeit (`?nur_aktive=true`, CSV) |
| `GET /kontakte/{guid}/dossiers` | 🔓 | Dossierkontakt / Beteiligung | Dossiers mit Rolle, Typ, Laufnummer, Status (CSV) |
| `POST /kontakte` | ✏️ | `POST /Kontakt`, `POST /Adresse` | neuen Kontakt anlegen (201); `409`, wenn der fremdkey schon existiert |
| `PATCH /kontakte/{guid}` | ✏️ | `PUT /Kontakt/{guid}`, Adresse | nur genannte Felder ändern bzw. leeren, fremdkey setzen |
| `POST /schueler` | ✏️ ⏳ | Kontakt + `POST /Geschaeft?Vorlage=` | wie Escola: Kontakt anlegen bzw. nachführen **und** Lernendendossier erstellen (201) |
| `POST /mitarbeitende` | ✏️ ⏳ | Kontakt + `POST /Geschaeft?Vorlage=` | wie Escola: Kontakt **und** Personaldossier; `standort` wählt die Vorlage (Hinterbirch/Mettmenriet) |
| `POST /kontakte/sync` | ✏️ | `Kontakt`, `Adresse` (Search, GET, POST, PUT) | bis 500 Kontakte abgleichen: anlegen, ändern, unverändert |
| `GET /dossiers` | 🔓 | `POST /Geschaeft/Search` | `?art=schueler\|personal\|klasse`, `fremdkey`, `titel` oder `tentaql` |
| `GET /dossiers/{guid}` | 🔓 | `GET /Geschaeft/{guid}` | ein Dossier |
| `GET /dossiers/{guid}/ordner` | 🔓 | `GET /Ordner/{guid}` | Ordner mit Pfad |
| `GET /dossiers/{guid}/dokumente` | 🔓 | `GET /Geschaeft/{guid}` | Dokumente des Dossiers |
| `POST /dossiers/schueler` | ✏️ ⏳ | `POST /Geschaeft?Vorlage=` | Schülerdossier zu einem Kontakt |
| `POST /dossiers/personal` | ✏️ ⏳ | `POST /Geschaeft?Vorlage=` | Personaldossier (Mitarbeitende, Lehrperson) |
| `POST /klassen` | ✏️ ⏳ | `POST /Geschaeft?Vorlage=` | Schulklassendossier (Vorlage je `standort`) oder mit `extern: true` Externes Schulklassendossier (`externe_schule`, Eigner = Schuleinheit); `409` bei gleichem Titel im Schuljahr |
| `GET /klassen` | 🔓 ⏳ | `POST /Geschaeft/Search` | Klassendossiers |
| `GET /klassen/{guid}/stufen` | 🔓 | Teilklasse | Klassenstufen einer Klasse |
| `GET /klassen/{guid}/schueler` | 🔓 ⏳ | Klassenstufe → Zuteilung → Schullaufbahn | Schüler:innen am Stichtag (`?stichtag=`, `?alle=true`) |
| `GET /schueler/{fremdkey}/klassen` | 🔓 ⏳ | Schullaufbahn, Zuteilung | Schullaufbahn mit Klasse, Klassenstufe, Eintrittsgrund, von–bis |
| `POST /klassen/einteilen` | ✏️ ⏳ | Schullaufbahn + Klassenzuteilung (POST, PUT) | in die aktuelle Klasse einteilen, umteilen, korrigieren ab Datum |
| `POST /dossiers/{guid}/dokumente` | ✏️ | `Ordner`, `Dokument`, `FileContent` | Datei hochladen (multipart) |
| `POST /zeugnisse` | ✏️ | `Dokument`, `FileContent` | Zeugnis-PDFs gesammelt in die Lernendendossiers (Ordner `CMI_ZEUGNIS_ORDNER`) |
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

Felder (Namen wie in CMI): `anrede`, `briefanrede`, `titel`, `name`, `vorname`, `organisation`, `funktion`,
`email` (geschäftlich), `email2` (privat), `natel`, `telefonPrivat`, `telefonGeschaeft`, `faxPrivat`, `faxGeschaeft`,
`homepage`, `unternehmensId`, `unternehmensIdKategorie`, `geburtsdatum`, `mitarbeiter`, `inaktiv`,
`subjektart` (`Natürlich`/`Juristisch`), `kategorien` (GUIDs der Personenkategorien, ersetzt die bisherigen).
Nicht genannte Felder bleiben unverändert; **leeren** mit `"leeren": ["titel", "homepage", …]`.

Adressen: `adresse` oder `adressen` (bis 10) mit `adressart` (GUID; bestimmt, welche aktive Adresse geändert wird –
ohne Adressart die erste aktive), `strasse`, `plz`, `ort`, `land`, `adresskategorie`, `gueltig_von`, `gueltig_bis`,
`inaktiv`. Eine Adresse beenden: `gueltig_bis` setzen oder `inaktiv: true`. Gelöscht wird nichts.

### Dossier erstellen

```json
POST /dossiers/schueler   {"fremdkey": "escola-650", "beginn": "2026-08-17"}
```

Body: `fremdkey`, optional `kontakt_guid`, `titel`, `beginn`, `bemerkung`, `standort` (Personaldossier),
`geschaeftseigner`. Die Person wird wie in der CMI-Oberfläche über das Feld `person` verknüpft.
In einem Schritt mit Kontakt: `POST /schueler` bzw. `POST /mitarbeitende` (Kontaktfelder + `beginn`, `bemerkung`,
`standort`).

Prüft vorher: Kontakt mit diesem fremdkey vorhanden und eindeutig (sonst `400`/`409`), noch kein Dossier derselben
Art mit diesem Schlüssel (sonst `409`). Titel «Name Vorname» (SuS mit Jahrgang), `zugriffsteuerung` aus
`CMI_DOSSIER_ZUGRIFF` (Standard `Restriktiv`), Status «InBearbeitung». Danach optional Beteiligung, dann Kontrolle.

### Einteilen und umteilen

```json
POST /klassen/einteilen?probelauf=true
{"ab": "2027-02-01", "zuteilungen": [{"fremdkey": "escola-650", "klasse": "2b"}]}
```

Wie «Klasseneinteilung → Direkte Schulklasseneinteilung» in CMI: pro Schüler:in ein **Schullaufbahneintrag**
(Schuljahr der Klasse, von–bis, Eintrittsgrund) mit **Klassenzuteilung** auf eine **Klassenstufe** der Klasse.
`klasse` = GUID oder Titel (mit oder ohne Schuljahr, z. B. «2b» oder «2b 2026/27»); `klassenstufe` nur nötig, wenn
die Klasse mehrere hat; `eintrittsgrund` = `schuleintritt` (Standard beim Einteilen), `zuzug`, `klassenwechsel`
(Standard beim Umteilen), `umteilung`, `kindergarteneintritt`, `primareintritt`, `sekundareintritt`; `bis` Standard
Ende der Klasse bzw. 31.7. Voraussetzung: Lernendendossier mit `fremdkey` (`POST /schueler`).

Aktionen: `einteilen` (keine aktive Zuteilung; Schullaufbahn des Schuljahrs wird verwendet oder angelegt),
`umteilen` (wie «Klassenumteilung» in CMI: bisherige Klassenzuteilung endet am Vortag, neue Zuteilung ab Datum in
derselben Schullaufbahn; nur beim Wechsel in ein anderes Schuljahr endet auch die Schullaufbahn),
`korrigieren` (bisherige Zuteilung beginnt am selben Tag → Klassenstufe ersetzen), `unveraendert`.
`GET /schueler/{fremdkey}/klassen` liefert eine Zeile pro Klassenzuteilung (mit `schullaufbahn`, `von`, `bis`).
Nicht nachgebildet: Übertragung offener Zeugnisse («Bestehende Leistungen übertragen» im CMI-Assistenten). Unbekannte Klasse,
Klasse ohne Klassenstufe oder fehlendes Lernendendossier → `400`, mehrere aktive Einträge → `409`, alles vor dem
Schreiben. Klassen ohne Klassenstufe: beim Anlegen `klassenlehrplan` mitgeben (`POST /klassen`).

Noch nicht in der API: «In Planung für Schuljahreswechsel aufnehmen» (Sammelklassendossier).

### Dokument hochladen

```bash
curl -H "X-API-Key: $KEY" -F datei=@zeugnis.pdf -F ordner="b_Dossier Schule/08_Beurteilung" \
     -F dokumentdatum=2026-07-03 -F schluessel=zeugnis-650-2026-S2 "http://localhost:8082/dossiers/$GUID/dokumente?probelauf=true"
```

Felder: `datei`, `titel` (Standard: Dateiname ohne Endung), Zielordner als Pfad `ordner` (z. B.
`b_Dossier Schule/08_Beurteilung`, Gross-/Kleinschreibung egal) oder direkt `ordner_guid` (aus
`GET /dossiers/{guid}/ordner`), `dokumentdatum`, `eingangsdatum`, `ausgangsdatum`, `bemerkung`, `autor`, `thema`,
`schluessel`. Duplikat (gleicher `schluessel` irgendwo oder gleicher Titel im Dossier) → `409`. Fehlt ein Ordner,
kommt `400` mit den fehlenden Teilen; anlegen nur mit `ordner_anlegen=true` (die Vorlagen geben die Ordner vor).
Kontrolle: Titel, Dossier und SHA-256 des heruntergeladenen Inhalts. Grösse bis `CMI_MAX_MB` (Standard 50).

### Zeugnisse gesammelt ablegen

```bash
curl -H "X-API-Key: $KEY" -F dateien=@lea.pdf -F dateien=@tim.pdf \
     -F 'zuordnung=[{"datei":"lea.pdf","fremdkey":"escola-650"},{"datei":"tim.pdf","fremdkey":"escola-651"}]' \
     -F schuljahr=2026/27 -F semester=1 -F dokumentdatum=2027-01-29 "http://localhost:8082/zeugnisse?probelauf=true"
```

Je Datei: `datei` (Dateiname), `fremdkey` (Lernendendossier), optional `schuljahr`, `semester`, `titel`
(sonst die gemeinsamen Werte). Abgelegt in `CMI_ZEUGNIS_ORDNER` (Standard `b_Dossier Schule/08_Beurteilung`,
bestätigt 26.11.2026 – mit `ordner` übersteuerbar; der Ordner wird nicht angelegt). Titel «Zeugnis 2026/27 1. Semester», Thema
«Zeugnis», Schlüssel `zeugnis-<fremdkey>-2026-27-S1`. Schon abgelegte Zeugnisse (gleicher Schlüssel) meldet die
API als `vorhanden`, ein erneuter Lauf schreibt also nichts doppelt. Vor dem Schreiben wird alles geprüft (kein
PDF, Datei ohne Zuordnung, unbekannter fremdkey, Ordner fehlt, doppelt in der Eingabe, gleicher Titel ohne
Schlüssel) → `400`, nichts abgelegt. Nach dem Ablegen Kontrolle wie beim Einzel-Upload (SHA-256).

## Schutz

- `CMI_API_KEY`: jeder Aufruf braucht den Header `X-API-Key`; ohne Key kein Schreiben.
- Schreiben nur mit `CMI_SCHREIBEN=1`; `?probelauf=true` geht immer und schreibt nie.
- Personendossiers standardmässig mit Zugriffsteuerung «Restriktiv».
- Zahlungsinformationen und medizinische Informationen nur mit `CMI_SCHUETZENSWERT=1` **und** API-Key; sonst
  meldet `/kontakte/{guid}/vollstaendig` nur die Anzahl, CMI wird dafür gar nicht gefragt.
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
| 0.8.0 | 2026-11-25 | `POST /zeugnisse`: Zeugnis-PDFs gesammelt ins Lernendendossier (Ordner Beurteilung), Duplikate über Schlüssel, alles vor dem Schreiben geprüft (#38) |
| 0.7.1 | 2026-11-25 | Klassenwechsel wie «Klassenumteilung» in CMI: Schullaufbahn bleibt, bisherige Klassenzuteilung endet am Vortag, neue Zuteilung mit eigener Dauer; Wechsel _TEST_Schueler TEST_A1a → TEST_A1b aufgezeichnet (#36) |
| 0.7.0 | 2026-11-25 | Klasseneinteilung nach dem Modell von CMI Schule (Schullaufbahn → Klassenzuteilung → Klassenstufe), Eintrittsgrund, `GET /klassen/{guid}/stufen`, Klassenstufe beim Anlegen einer Klasse (`klassenlehrplan`); Einteilung von _TEST_Schueler in TEST_A1a aufgezeichnet (#36) |
| 0.6.0 | 2026-11-25 | `POST /klassen`: Schul- und Externes Schulklassendossier anlegen (Vorlage je Standort, Schuljahr, Beginn/Ende, externe Schule); Klassendossiers und Klasseneinteilung in CMI erkundet (#36) |
| 0.5.0 | 2026-11-25 | Dokument-Upload in beliebigen Ordner/Unterordner: Zielordner per Pfad oder `ordner_guid`, fehlende Ordner nur mit `ordner_anlegen=true`, Felder Autor, Thema, Eingangs-/Ausgangsdatum; Ablage in CMI erkundet (#32) |
| 0.4.0 | 2026-11-25 | Erstellen wie bei Escola: `POST /kontakte`, `PATCH /kontakte/{guid}`, `POST /schueler`, `POST /mitarbeitende`; Dossier verknüpft die Person über `person`, Bemerkung, Personaldossier-Vorlage je Standort; Kontakt mit `geschlecht`, `rufname` (#30) |
| 0.3.0 | 2026-11-25 | Kontakt-Sync mit allen Feldern der CMI-Oberfläche (Titel, Briefanrede, Funktion, Fax, Homepage, Unternehmens-ID, Subjektart, Kategorien), Felder leeren, mehrere Adressen nach Adressart mit Land, Kategorie und Gültigkeit; Schreibweise aus Test am Kontakt _TEST (#27) |
| 0.2.0 | 2026-11-25 | Kontakt vollständig lesen (`/kontakte/{guid}/vollstaendig`, `/adressen`, `/dossiers`), Schalter `CMI_SCHUETZENSWERT`; Erkundung im CMI der Sek Bülach (`ERKUNDUNG.md`) (#25) |
| 0.1.0 | 2026-11-25 | Erste Fassung nach Swagger des CMI-Connectors: Kontakte synchronisieren, Schüler-/Personaldossier, Klassen einteilen/umteilen, Dokumente hochladen; Probelauf, Kontrolle nach dem Schreiben; Tests gegen nachgebautes CMI (#23) |
