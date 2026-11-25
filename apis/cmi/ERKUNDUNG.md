# CMI – Erkundung im Mandanten der Sek Bülach

Stand: **25.11.2026**, CMI Axioma Web-Client 26.1.3. Methode: Aufzeichnung der Anfragen der Weboberfläche im eingebauten
Browser, nur lesen, angemeldet war der Projektverantwortliche. Es wurden **keine Personendaten** übernommen, nur Namen
von Typen, Feldern und Endpunkten. Grundlage für #23 und #25.

## Verbindung

| Punkt | Beobachtet |
|---|---|
| Web-Client | `https://sekbuelach.cmicloud.ch` (Angular), Konfiguration in `/config.json` |
| Mandant | `sekbuelach` (Anmeldung mit `acr_values=tenant:sekbuelach`) |
| Anmeldung Web-Client | eigener Anmeldedienst `https://sts3.prod.cmicloud.ch/sekbuelach/identity` (OpenID Connect, Client `webClient`), **nicht** Entra ID |
| Schnittstelle Web-Client | `https://proxy.cmicloud.ch/sekbuelach/webapiprivate/api` |
| weitere Dienste | `push.prod.cmicloud.ch/sekbuelach/data` (SignalR), `ki-plus.prod.cmicloud.ch/sekbuelach` |

`webapiprivate` ist die **interne** Schnittstelle der Oberfläche: Sie liefert Seiten-Layouts (`core/Layout/GetLayout`,
`GetAssocLayout`) und eine Facettensuche (`core/search/ExecuteFacetedSearch`). Sie ist nicht dokumentiert, kann sich
mit jedem Update ändern und wird von der CMI-API **nicht** benutzt. Für den Betrieb braucht es die offizielle
Schnittstelle von CM Informatik (Zugang beantragen).

## Typen (Auswahl aus 208 suchbaren Typen)

| Bereich | Typen (Anzeigename, technischer Schlüssel klein geschrieben) |
|---|---|
| Personen | Kontakt (`kontakt`, 566), Person (127), Benutzer:in, Fremdbenutzer:in, Personenkategorie, Haushalt, Haushaltsmitgliedschaft, Beziehung, Beziehungsart, Sorgerechtsinhaber:in, Kommunikationsdetail |
| Adressen | Adresse (`adresse`, 162), Adressart, Adresskategorie, Land, Gemeinde, Heimatort |
| Dossiers | Geschäft (273), Abstraktes Geschäft, **Lernendendossier** (327191), **Personaldossier** (332073), **Schulklassendossier** (330171), Fachklassendossier, Sammelklassendossier, Schuldossier, Vertragsdossier |
| Verknüpfung | **Dossierkontakt** (`dossierkontakt`: Rolle, Dossier, Laufnummer, Typ, Status, Dauer), Beteiligung (727), Rolle |
| Schule | **Klassenzuteilung Lernende** (331420), Klassenzuteilung Lehrperson (332491), Lernendezuteilung, Schullaufbahn, Schulfachzuteilung, Schuljahr, Semester, Schulhaus, Schulstandort, Klassenstufe |
| Ablage | Ordner (3096), Dokument (314), Dokumentkategorie, Registraturplan |
| Technik | **Fremdkey Mapping** (131546), Validierungsmeldung, Workflow |
| besonders schützenswert | Zahlungsinformation, Medizinischer Informationseintrag, Sonderpäd. Massnahme, Arztuntersuch, Asylstatus, Konfession |

## Kontakt

Reiter in der Oberfläche: Kontakt, Adressen, Zahlungsinformationen, Zusatzinformationen, Dossierkontakte, Schule,
Bezugspersonen, Notfallkontakte, Haushalt, Medizinische Info, Technische Details.

**Felder:** `anrede`, `briefanrede`, `titel`, `name`, `vorname`, `organisation`, `funktion`, `email`, `email2`, `natel`,
`telefonGeschaeft`, `telefonPrivat`, `faxGeschaeft`, `faxPrivat`, `homepage`, `inaktiv`, `kategorie` (→ Personenkategorie),
`kontaktschutzstufe`, `subjektart` (Natürlich/Juristisch), `unternehmensId`, `fremdkey`, `benutzerID`,
`benutzernameApps`, `googleAuthKonfiguriert`, `mediennutzungEinwilligungFotos`, `mediennutzungEinwilligungVideos`,
`createdby`, `creationdate`, `modifiedby`, `modificationdate`.

**Beziehungen (Feld → Typ):** `adressen` → Adresse · `zahlungsinformationen` → Zahlungsinformation ·
`dossierkontakte` → Dossierkontakt · `gebiete` → Gebiet (Reiter Schule) · `beziehungenA`, `beziehungenB` → Beziehung
(Bezugspersonen) · `kommunikationsDetails` → Kommunikationsdetail (Notfallkontakte) · `haushaltsmitgliedschaften` →
Haushaltsmitgliedschaft · `medizinischeInformationen` → Medizinischer Informationseintrag · `fremdKeyMappings` →
Fremdkey Mapping · `adressdatensperre` · `externeBenutzer` → Fremdbenutzer:in.

**Adresse:** `strasse`, `pLZ` (in der Weboberfläche so geschrieben; im Connector `plz`), `ort`, `adressart`,
`gueltigVonBis` (`{start:{precision,text,value}, end:{…}}`), `inaktiv`.

**Dossierkontakt:** `rolle` (z. B. Person, Partner, Verantwortlich), `computedDossier`, `dossiertitel`,
`dossierLaufnummer`, `dossierTyp` (z. B. Personaldossier, Vertragsdossier), `dossierStatus`, `dauer`.

## Folgerungen für die CMI-API

- Typnamen für `.env`: Schülerdossier = `Lernendendossier`, Personaldossier = `Personaldossier`,
  Klassendossier = `Schulklassendossier`, Klassenzuteilung = Klassenzuteilung Lernende (Entitätsname der offiziellen
  API noch ZU PRÜFEN).
- Die Verknüpfung Kontakt ↔ Dossier heisst in der Oberfläche **Dossierkontakt** (mit Rolle); der Connector nennt sie
  `beteiligungen`. Die CMI-API liest beide.
- Für die Escola-ID ist **Fremdkey Mapping** wahrscheinlich besser als das einfache Feld `fremdkey` (ZU PRÜFEN mit CMI).
- Datum in Antworten der Oberfläche als `TT.MM.JJJJ hh:mm`, in Zeiträumen als ISO-Wert (`value`).

## Schreiben (geprüft am Testkontakt «_TEST _TEST», 25.11.2026)

Alle Felder des Kontakts mit erfundenen Werten beschrieben, gespeichert, danach wieder geleert; eine Testadresse
angelegt und gelöscht. Der Kontakt ist wieder im Ausgangszustand.

| Vorgang | Aufruf der Weboberfläche | Inhalt |
|---|---|---|
| Ändern | `POST core/Save/InsertOrUpdate` | `{"<guid>": {"guid", "objVersion", "typeKey": "kontakt", <nur geänderte Felder>}}` – Antwort `{"errors": null}`; `objVersion` steigt je Speichern (Schutz gegen gleichzeitiges Ändern) |
| Feld leeren | dito | Feld mit `null` |
| Auswahlfeld | dito | `subjektart: {"value": 0, "text": "Natürlich"}`, leeren mit `{"value": null}` |
| Verweisliste | dito | `kategorie: {"added": ["<guid>"], "removed": ["<guid>"]}` |
| Neu (Adresse) | `POST core/Menu/ExecuteAction` mit `actionId: "cmi-assoc-new"`, `typeKey: "Adresse"` | Assistent: Felder `adressart` (Liste GUIDs), `adresskategorie`, `strasse`, `pLZ`, `ort`, `land`, `gueltigVonBis` als Text «01.01.2026 - »; Fortschritt über `core/Menu/GetProgressInfo` |
| Datum prüfen | `POST core/Parser/Date` | «01.01.2026» → `{value: "2026-01-01 00:00:00.000", precision: "Day"}` |
| Löschen | `POST core/Save/GetDeletability` → `POST core/Save/Delete` | `{"ids": ["<guid>"]}`; vorher Liste der mitgelöschten Objekte |

**Kontaktfelder, die schreibbar sind:** `anrede`, `briefanrede`, `titel`, `name`, `vorname`, `organisation`, `funktion`,
`kategorie` (Personenkategorien), `unternehmensIdKategorie`, `unternehmensId`, `subjektart` (Natürlich/Juristisch),
`kontaktschutzstufe`, `telefonPrivat`, `telefonGeschaeft`, `email` (geschäftlich), `email2` (privat), `faxPrivat`,
`faxGeschaeft`, `natel`, `homepage`.

**Adressarten** im Mandanten: Geschäftsadresse, Hauptadresse, Privatadresse.

Die CMI-API übernimmt daraus Feldnamen, das Leeren mit `null` und die Gültigkeit als «TT.MM.JJJJ - TT.MM.JJJJ».
Wie die offizielle Schnittstelle Auswahlfelder und Verweislisten erwartet, ist ZU PRÜFEN (angenommen: Text bzw.
Liste von `{guid}` beim `PUT` des ganzen Objekts).

## Kontakt anlegen und löschen (Test «_TEST2 _TEST2», 25.11.2026)

Kontakt mit Adresse über die Oberfläche angelegt und gleich wieder gelöscht (erfundene Werte).

| Schritt | Aufruf | Inhalt |
|---|---|---|
| Start | `POST core/Menu/ExecuteAction`, `actionId: "cmi-creation.Kontakt"`, `contextId: "global"` | Auswahl der Erstellungsoption: Vorlage **«Kontakt mit Adresse (Vorlage/Standard/Kontakt)»**, «Keine Vorlage», Ordner Standard/Global |
| Felder | dito mit `state` und `stepIndex` | Kontakt: `obj_1_anrede`, `obj_1_name`, `obj_1_vorname`, `obj_1_geburtsdatum` («TT.MM.JJJJ»), `obj_1_geschlecht`, `obj_1_organisation`, `obj_1_telefonPrivat`, `obj_1_telefonGeschaeft`, `obj_1_natel`, `obj_1_email2`, `obj_1_email` · Adresse: `obj_2_adressart`, `obj_2_adresskategorie`, `obj_2_strasse`, `obj_2_pLZ`, `obj_2_ort`, `obj_2_land`, `obj_2_gueltigVonBis` |
| Erstellen | dito, letzter Schritt mit `takenotice_step_4: true` | Antwort `progressInfoToken`; `core/Menu/GetProgressInfo` meldet `Complete` und die GUID des neuen Kontakts |
| Löschen | `core/Save/GetDeletability` → `core/Save/Delete` | Löschen des Kontakts nimmt seine Adressen mit (`willDelete`: Adresse + Kontakt) |

Weitere Erstellungsaktionen im Mandanten (Auszug): `cmi-creation.Lernendedossier` mit Vorlage
**«Lernendendossier (Vorlage/Global/Schulverwaltung)»**, `cmi-creation.Schuljahr`, `cmi-creation.Personalkategorie` u. a.
Daraus für die CMI-API: Vorlagenpfade für `CMI_KONTAKT_VORLAGE` (`Vorlage/Standard/Kontakt`) und
`CMI_DOSSIER_SCHUELER_VORLAGE` (`Vorlage/Global/Schulverwaltung`, Schreibweise in der offiziellen API ZU PRÜFEN);
der Kontakt kennt zusätzlich `geschlecht` (Verweis). Die CMI-API löscht weiterhin nicht.

## Dossiers anlegen (Test «_TEST_Schueler» und «_TEST_Mitarbeiter», 25.11.2026)

Zuerst je ein Kontakt (Vorlage «Kontakt mit Adresse», Geschlecht über Stammdaten «Geschlecht»: männlich/weiblich,
im Assistenten `obj_1_geschlecht: ["<guid>"]`), dann das Dossier über «+» der Hauptmaske. Beide bleiben als
Testobjekte bestehen.

| Dossier | Aktion | Vorlagen im Mandanten | Felder im Assistenten |
|---|---|---|---|
| Lernendendossier | `cmi-creation.Lernendedossier` | «Lernendendossier (Vorlage/Global/Schulverwaltung)» | `obj_1_beginn` (Pflicht, Vorgabe heute), `obj_1_person` (Pflicht, Kontakt), `obj_1_bemerkung`, `obj_1_geschaeftseigner` (Pflicht, Vorgabe «Sekundarschule Bülach; Sekbülach») |
| Personaldossier | `cmi-creation.Personaldossier` | «Personaldossier Hinterbirch (Vorlage/Global/Schulverwaltung)», «Personaldossier Mettmenriet (…)» | `obj_1_beginn` (Pflicht), `obj_1_person` (Pflicht), `obj_1_bemerkung`, `obj_1_geschaeftseigner` (Vorgabe aus Vorlage, z. B. «HR Hinterbirch; HRH») |

- Beim Erstellen legt CMI die Ordnerstruktur der Vorlage mit an (Lernendendossier 16 Ordner, Personaldossier 22).
- Die Person hängt am Dossier im Feld **`person`**; der Titel wird aus dem Namen gebildet.
- Personaldossier: Felder `person`, `geschaeftsstatus`, `customEffektiverEintritt`, `customFiktiverEintritt`; Reiter
  Übersicht, Personalanstellungen, Personalentwicklung, Zuteilungen, Absenzen, Dokumente, Aufgaben, Notizen,
  Explizite Berechtigung, Dossierdetails.
- Lernendendossier: Übersicht mit aktueller Schulklasse, Schulklassendossier, Klassenlehrperson und
  **Schullaufbahneinträgen** («Neue Schullaufbahn») – dort hängt die Klassenzuteilung (nächster Schritt).
- Kontakt (zusätzlich gesehen): `rufname`, `geschlecht`, `heimatorte`, `nationalitaeten`, `korrespondenzsprache`,
  `aufenthaltsbewilligungen`, `sozialversNr` (AHV – besonders schützenswert, von der CMI-API nicht bearbeitet).

## Dokumente in Ordner und Unterordner ablegen (Test, 25.11.2026)

Am Personaldossier «_TEST_Mitarbeiter» und am Lernendendossier «_TEST_Schueler» geprüft, mit erfundenen Testdateien.
Die drei Testdokumente bleiben bestehen.

**Ordner der Vorlagen**

| Dossier | Ordner (Unterordner) |
|---|---|
| Personaldossier (Vorlage Hinterbirch) | a_Grunddaten (01_Bewerbungsunterlagen, 02_Personalausweis, 03_Adressen, 04_Familienverhältnis) · b_Verfügungen · c_Entwicklung · d_Administratives · e_Korrespondenz (je mit Unterordnern) |
| Lernendendossier | a_Akten Verwaltung (01_Laufbahn, 02_Schulgeld, 03_Korrespondenz, 04_Gesuche) · b_Dossier Schule (05_Schulbesuche, 06_Kommunikation, 07_Unterricht, 08_Beurteilung, 09_Weiteres) · c_Sonderpädagogik · d_Diverses |

**Drei Wege in der Oberfläche**

| Weg | Aufrufe | Ergebnis |
|---|---|---|
| Datei in den Ordner ziehen | **ein** Aufruf: `POST core/Dokument/AddNew?atGuid=<Ordner-GUID>&fieldKey=children`, multipart mit Feld `file` | Dokument mit Datei im Ordner, Titel = Dateiname ohne Endung, Art aus der Endung (Pdf, Text) |
| «Neues Dokument» (ohne Vorlage) | Assistent `cmi-assoc-new`, `typeKey: "Dokument"`, Felder `titel` (Pflicht), `bemerkung`, `kategorie`, `autor`, `thema`, `standort`, `dokumentdatum`, `eingangsdatum`, `ausgangsdatum` | Dokument nur mit Metadaten, ohne Datei |
| Datei nachreichen | Menü «Neue Version hochladen»: `POST core/Dokument/AddNewVersion?objGuid=<Dokument-GUID>`, multipart `file` | neue Version mit Datei |

- Der Ordnerbaum kommt über `core/CustomTree/GetChildren` mit `treeKey: "DokumenteExplorerTree.<Dossier-GUID>"`
  und `parentKey` (Antwort: `guid`, `displayName`, `childrenCount`, `parentGuid`).
- «Neues Dokument» bietet auch Vorlagen an (z. B. «Antrag Personal Anstellung», «Antrag SuS IBR»); die erzeugen
  ein Dokument aus einer Word-Vorlage, nicht aus einer Datei.
- Dokumentfelder in Listen: `titel`, `art`, `fileSize`, `lastCheckInDate`, `dokumentVersion`, `downloadUrl`.

**Für die CMI-API:** Upload mit Zielordner per Pfad (`b_Dossier Schule/08_Beurteilung`) oder per `ordner_guid`;
Ordner aus der Vorlage werden nicht neu angelegt (nur mit `ordner_anlegen=true`). Offiziell entspricht das
`POST /Dokument` mit Verweis auf Dossier und Ordner und der Datei (Format ZU PRÜFEN) bzw. Check-in.

## Klasseneinteilung und Planung (Lernendendossier «_TEST_Schueler», 25.11.2026 – nicht abgeschlossen)

Menü «⋮» oben rechts im Lernendendossier → **Klasseneinteilung**. Ein Assistent
(`actionId: "workspaces.cmiaxioma.schulverwaltung.menucommands.einschulung.klasseneinteilungcommand"`,
`actionArguments: "<Dossier-GUID>"`) mit zwei Optionen. Bis zur Klassenwahl durchgespielt, **nicht gespeichert**:
im Mandanten gibt es keine Testklasse.

| Option (`klasseneinteilungsoptionWizardOptionChoice`) | Schritt 2 | Schritt 3 |
|---|---|---|
| `direkteKlasseneinteilung` – aktuelle Klasse | `schuljahr` (Verweis «Schuljahr», Vorgabe 2026/27), `eintrittsgrund` (Pflicht), `vonBis` («01.08.2026 - 31.07.2027», Vorgabe = Schuljahr) | `einteilungSchulklassendossier` (Verweis «AbstraktesSchulklassendossier»: Schulklassendossier oder Externes Schulklassendossier) |
| `planungSchuljahreswechsel` – künftige Klasse («In Planung aufnehmen») | `schuljahr`, `vonBis` (kein Eintrittsgrund) | `planungSammelklassendossier` (Verweis «Sammelklassendossier») |

**Eintrittsgründe** (`key` → Anzeige): `schuleintritt` Schuleintritt · `zuzug` Zuzug · `klassenwechsel` Klassenwechsel ·
`umteilung` Umteilung · `kindergarteneintritt` · `primareintritt` · `sekundareintritt`.

- Die Planung teilt also nicht in eine Schulklasse ein, sondern in ein **Sammelklassendossier** des künftigen
  Schuljahres (Planungsprozess Schuljahreswechsel); die definitive Klasse entsteht später.
- Das Ergebnis erscheint im Lernendendossier unter **Schullaufbahneinträge**; Aufbau des Eintrags (Typ
  «Klassenzuteilung Lernende» / «Schullaufbahn») noch offen.
- Für den letzten Schritt braucht es eine **Testklasse** (Schulklassendossier) und eine **Test-Sammelklasse**.

## Klassendossiers anlegen (Testklassen, 25.11.2026)

Anwendung «Schule» → Klassen → «+» bietet: Externes Schulklassendossier, Fachklassendossier, Sammelklassendossier,
Schulklassendossier (verwendet werden Schul- und Externes Schulklassendossier). Angelegt als Testobjekte, bleiben bestehen:

| Testklasse | Typ | Vorlage | Geschäftseigner |
|---|---|---|---|
| TEST_A1a 2026/27 | Schulklassendossier | «Schulklassendossier Hinterbirch (Vorlage/Global/Schulverwaltung)» | Klassen Hinterbirch; KLH |
| TEST_A1b 2026/27 | Schulklassendossier | «Schulklassendossier Mettmenriet (…)» | Klassen Mettmenriet; KLM |
| TEST_Extern 2026/27 | Externes Schulklassendossier | «Externes Schulklassendossier (Vorlage/Global/Schulverwaltung)» | Klassen weitere; KLW |

| Aktion | Felder (`obj_1_*`) |
|---|---|
| `cmi-creation.Schulklassendossier` | `titel` (Pflicht), `schuljahr` (Verweis Schuljahr), `beginn` (Pflicht), `ende`, `geschaeftseigner` (Pflicht; Organisationseinheit, Schulträger, Schulkreis, Schuleinheit, Benutzer oder Kontakt) |
| `cmi-creation.ExternesSchulklassendossier` | dieselben plus `externeSchule` (Pflicht, Stammdaten «Externe Schule», z. B. «Extern», «Gymnasium») |

- CMI hängt das Schuljahr an den Titel: «TEST_A1a» → «TEST_A1a 2026/27».
- **Regel SCV102:** ein Externes Schulklassendossier muss einer **Schuleinheit** gehören; die Vorgabe der Vorlage
  («Sekundarschule Bülach», ein Schulträger) wird abgelehnt. «Klassen weitere» geht.
- Nach dem Anlegen warnt CMI «Es sind noch keine Schulstufen zugewiesen» (Schulstufe separat).
- Schuljahre im Mandanten: 2021/22 bis 2026/27.

## Klasseneinteilung ausgeführt (_TEST_Schueler → TEST_A1a, 25.11.2026)

1. **Klassenstufe nötig:** Eine neue Klasse hat keine Klassenstufe; die Einteilung fragt danach («Klassenstufe»,
   Pflicht) und findet sonst nichts. Anlegen im Klassendossier unter Dossierdetails → Klassenstufen → «Neue
   Klassenstufe»: Assistent `cmi-assoc-new` mit `typeKey: "Teilklasse"`, einziges Feld `klassenlehrplan`
   (Stammdaten «Klassenlehrplan», z. B. «1. Sekundarschule», «2. Sekundarschule Abteilung B»). Ergebnis «1. SST».
2. **Einteilung:** Assistent `…einschulung.klasseneinteilungcommand` mit
   `direkteKlasseneinteilung`, `schuljahr`, `eintrittsgrund: "schuleintritt"`, `vonBis: "01.08.2026 - 31.07.2027"`,
   `einteilungSchulklassendossier`, `einteilungTeilklasse` (bei nur einer Stufe automatisch), Zusammenfassung mit
   `einschulungSummaryTakeNotice: true`. Meldung «Einschulung ausgeführt.»

**Datenmodell danach**

| Objekt (`typeKey`) | Wichtige Felder |
|---|---|
| Lernendendossier (`lernendedossier`) | `person`, `schullaufbahneintraege` |
| Schullaufbahn (`schullaufbahn`) | `titel` (= Klassenlehrplan, z. B. «1. Sekundarschule»), `schuljahr`, `status` (InBearbeitung), `vonBis` |
| Klassenzuteilung Lernende (`klassenzuteilungLernende`) | `teilklasse` (Klassenstufe), `schullaufbahn`, `schulklassendossier` (abgeleitet, schreibgeschützt), **`vonBis`** (eigene Dauer), `computedIstPerHeuteZugeteilt`, `computedPersonName`, `computedPersonVorname` |
| Klassenstufe (`teilklasse`) | `titel` («1. SST»), `klassenlehrplan`, `klassenzuteilungenLernende`, gehört zum Schulklassendossier |

Im Lernendendossier zeigt die Übersicht danach «Aktuelle Schullaufbahn: 1. Sekundarschule», «Aktuelles
Schulklassendossier: TEST_A1a 2026/27», «Anzahl Schuljahre: 1». Die CMI-API bildet das so nach (`/klassen/einteilen`).

## Klassenwechsel ausgeführt (_TEST_Schueler: TEST_A1a → TEST_A1b, 25.11.2026)

Nach der ersten Einteilung bietet das Menü des Lernendendossiers keine «Klasseneinteilung» mehr an. Der Wechsel
läuft über das **Menü des Schullaufbahneintrags** (Übersicht → Schullaufbahneinträge → «⋮») → **Klassenumteilung**.
Vorher in TEST_A1b die Klassenstufe «1. SST» angelegt (wie oben).

| Schritt | Felder |
|---|---|
| 1 Option | `klasseneinteilungsoptionWizardOptionChoice`: `direkteKlasseneinteilung` oder `planungSchuljahreswechsel` |
| 2 Umteilung | `umteilungPer` (Pflicht, Vorgabe morgen, z. B. «26.11.2026»), `schulklassendossier` (Pflicht), `eintrittsgrund` (Vorgabe `umteilung`, gewählt `klassenwechsel`), `bestehendeLeistungenUebertragen` (Vorgabe ja) |
| 3 Zusammenfassung | `klassenumteilungSummaryTakeNotice: true`; Hinweis «Bestehende offene Zeugnisse werden in den neuen Schulklassenkontext weitergeführt» |

`actionId: "workspaces.cmiaxioma.schulverwaltung.klassenumteilung.klassenumteilunglernendecommand"`,
`actionArguments: "<Schullaufbahn-GUID>"`, `contextId: "assocentry.<id>;schullaufbahneintraege"`.

**Ergebnis**

- Die **Schullaufbahn bleibt** (gleiche GUID, Dauer unverändert, weiterhin ein Eintrag «1. Sekundarschule 2026/27»).
- Die **bisherige Klassenzuteilung** (TEST_A1a) endet am **Vortag** des Stichtags: Dauer «25.11.2026 - 25.11.2026».
- Eine **neue Klassenzuteilung** (TEST_A1b, Klassenstufe «1. SST») in derselben Schullaufbahn ab Stichtag:
  «26.11.2026 - 31.07.2027».
- Übersicht danach: «Aktuelles Schulklassendossier: TEST_A1b 2026/27». Die Schullaufbahn zeigt unter
  «Klassenzuteilungen» beide Zuteilungen.
- Wo `eintrittsgrund` und `bestehendeLeistungenUebertragen` landen, zeigt die Oberfläche nicht (ZU PRÜFEN).

**Für die CMI-API (0.7.1):** `umteilen` im selben Schuljahr = PUT `KlassenzuteilungLernende.vonBis` (Ende Vortag)
und POST neue `KlassenzuteilungLernende` mit `schullaufbahn`, `teilklasse`, `vonBis`. Nur beim Wechsel in ein
anderes Schuljahr endet auch die Schullaufbahn und eine neue wird angelegt. Die Übertragung offener Zeugnisse macht
nur der Assistent; über das Objektmodell ist sie nicht nachgebildet (ZU PRÜFEN).

Offen: «In Planung aufnehmen» (Sammelklassendossier) live aufzeichnen.
