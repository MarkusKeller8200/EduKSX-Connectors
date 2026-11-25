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
