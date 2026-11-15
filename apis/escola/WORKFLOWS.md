# Escola-API – Workflows (Prüfliste und spätere Testläufe)

Stand API: 1.14.0 · Liste wird laufend ergänzt (zuletzt 15.11.2026, WF-01 bis WF-20).

Jeder Workflow wird zuerst **theoretisch** gegen die vorhandene API geprüft (reichen die Endpunkte?).
Später dient er als **Testlauf** auf dem Testsystem (Testpersonen TEST TEST 649, SuS SuS 650, Testklasse TEST_A1a 120,
Test-Arbeitsgruppe TEST 3).

**Status:** ✅ mit der API vollständig möglich · ⚠️ teilweise / mit Einschränkung · ❌ fehlt noch
**Live:** 🧪 noch nicht live getestet · – kein Escola-Schreibteil · ◐ Escola-Aufrufe live geprüft, API-Ablauf noch nicht · ✔️ live getestet (Datum)

## Übersicht

| Nr | Workflow | Status | Live | Offen |
|---|---|---|---|---|
| WF-01 | Mitarbeiter:in einstellen und erfassen | ✅ | 🧪 | – (Postfach M365: IDA/CONNECT) |
| WF-02 | Mitarbeiter:in tritt auf ein Datum aus | ✅ | ◐ | Stichtag: IDA/CONNECT (L5) |
| WF-03 | Neue Lehrperson ab Datum, mit Klasse oder Fachklasse | ✅ | ◐ | Rechte fürs kommende SJ (L6) |
| WF-04 | Lehrperson verlässt die Schule | ✅ | ◐ | Stichtag (L5) |
| WF-05 | Lehrperson übernimmt zusätzliche Klasse (KLP oder Fach) | ✅ | ◐ | – |
| WF-06 | Lehrperson übernimmt eine neue Klasse (Wechsel) | ✅ | ◐ | Rechte fürs kommende SJ (L6) |
| WF-07 | Schüler:in anmelden ab Datum, Klasse, Eltern als gesetzliche Vertretung | ✅ | ◐ | neue Bezugsperson anlegen noch nicht live (L7) |
| WF-08 | Schüler:in wechselt die Klasse ab Datum | ✅ | 🧪 | – |
| WF-09 | Schüler:in verlässt die Schule zum Zeitpunkt X | ✅ | ◐ | – |
| WF-10 | Schüler:in zieht um | ✅ | ◐ | Ausführung ab Datum: IDA/CONNECT (L5) |
| WF-11 | Massenimport Schüler:innen und Eltern (Einschulung) | ⚠️ | 🧪 | Vorprüfung ✅ `POST /import/pruefen`; Importformat/Upload ([#2](https://github.com/MarkusKeller8200/EduKSX-Connectors/issues/2)) |
| WF-12 | Übertrittsformular ins Schülerdossier | ❌ | – | Dokumente ablegen ([#3](https://github.com/MarkusKeller8200/EduKSX-Connectors/issues/3)) |
| WF-13 | Klasseneinteilung durch die Schulleitung, Kontrolle | ✅ | 🧪 | Einteilung im Escola-Tool; Kontrolle `GET /klassenlisten` |
| WF-14 | App-Zugang für Eltern, Nachfassen | ⚠️ | 🧪 | Eltern je Klasse ✅ `GET /klassen/{id}/eltern`; App-Status ([#4](https://github.com/MarkusKeller8200/EduKSX-Connectors/issues/4)) |
| WF-15 | Zuteilungsbrief, Rekurs, Zuteilung definitiv | ⚠️ | 🧪 | Umteilung ✅ (WF-08); Brief ([#5](https://github.com/MarkusKeller8200/EduKSX-Connectors/issues/5)), Sichtbarkeit App ([#7](https://github.com/MarkusKeller8200/EduKSX-Connectors/issues/7)) |
| WF-16 | Stundenpläne aus dem Stundenplaner einspielen | ⚠️ | ◐ | Einzelschreiben ✅, Abgleich ✅ (nicht live) ([#6](https://github.com/MarkusKeller8200/EduKSX-Connectors/issues/6)) |
| WF-17 | ICT: Klassenlisten, Zugänge, Geräte, Nutzungsvereinbarung | ⚠️ | 🧪 | Klassenlisten ✅; Vereinbarung + Rücklauf ([#5](https://github.com/MarkusKeller8200/EduKSX-Connectors/issues/5)), Ablage ([#3](https://github.com/MarkusKeller8200/EduKSX-Connectors/issues/3)) |
| WF-18 | Arzt- und Zahnarztkontrollen | ❌ | – | Gutscheine ([#5](https://github.com/MarkusKeller8200/EduKSX-Connectors/issues/5)), Rückmeldung ablegen ([#3](https://github.com/MarkusKeller8200/EduKSX-Connectors/issues/3)), Status/Liste ([#8](https://github.com/MarkusKeller8200/EduKSX-Connectors/issues/8)) |
| WF-19 | Prüfungen mit Note an Eltern | ❌ | – | ([#10](https://github.com/MarkusKeller8200/EduKSX-Connectors/issues/10)), hängt an [#3](https://github.com/MarkusKeller8200/EduKSX-Connectors/issues/3), [#9](https://github.com/MarkusKeller8200/EduKSX-Connectors/issues/9) |
| WF-20 | Überführung nach CMI | ⚠️ | 🧪 | Stammdaten ✅; Absenzen/Verhalten/Prüfungen ([#9](https://github.com/MarkusKeller8200/EduKSX-Connectors/issues/9)), Dokumente ([#3](https://github.com/MarkusKeller8200/EduKSX-Connectors/issues/3)) |

## Lücken

| Nr | Lücke | Status |
|---|---|---|
| L1 | Stundenplan schreiben | ✅ seit 1.12 (anlegen, ändern, löschen, Lehrperson ersetzen) |
| L2 | Fächer-Zuteilung fürs kommende Schuljahr | ✅ seit 1.12 (nur Fächer, siehe L6) |
| L3 | Fächer-Zuteilung für Arbeitsgruppen (Fachklassen) | ✅ seit 1.12 |
| L4 | Bezugspersonen | ✅ seit 1.12 (lesen, verknüpfen, anlegen, Sorgerecht, entfernen, Eltern deaktivieren) |
| L5 | Stichtag – Escola-Änderungen gelten sofort | offen, ausserhalb der API: IDA/CONNECT plant und löst am Datum aus |
| L6 | Rechte (KLR/FP/SpM/Abs) fürs kommende Schuljahr | offen – Escola-Verhalten nicht live geprüft; Rechte nach dem SJ-Wechsel setzen ([#11](https://github.com/MarkusKeller8200/EduKSX-Connectors/issues/11)) |
| L7 | Neue Bezugsperson anlegen (`createNewPersonAndRelationshipRpc`) | eingebaut, nicht live getestet (legt eine nicht löschbare Person an) – im ersten Testlauf prüfen ([#12](https://github.com/MarkusKeller8200/EduKSX-Connectors/issues/12)) |
| L8 | Stundenplan von Arbeitsgruppen | offen – Escola-Aufruf unbekannt (Anzeige liefert keine Zellen) ([#13](https://github.com/MarkusKeller8200/EduKSX-Connectors/issues/13)) |
| L9 | Lehrpersonen-Schalter im Stundenplan bei mehreren Lehrpersonen pro Fach | eingebaut, live nur gelesen (H_A1a), nicht geschaltet ([#14](https://github.com/MarkusKeller8200/EduKSX-Connectors/issues/14)) |
| L10 | Escola-Importformat und Upload | offen ([#2](https://github.com/MarkusKeller8200/EduKSX-Connectors/issues/2)) |
| L11 | Dokumente im Schülerdossier lesen und ablegen | offen ([#3](https://github.com/MarkusKeller8200/EduKSX-Connectors/issues/3)) |
| L12 | Eltern-App: Aktivierungsstatus, Zugänge | offen ([#4](https://github.com/MarkusKeller8200/EduKSX-Connectors/issues/4)) |
| L13 | Mitteilungen über Escola senden, Rücklauf lesen | offen ([#5](https://github.com/MarkusKeller8200/EduKSX-Connectors/issues/5)) |
| L14 | Stundenplan-Abgleich mit dem Stundenplaner | ✅ eingebaut `POST /klassen/{id}/stundenplan/abgleich` (neutrales Format; Umwandlung des Stundenplaner-Exports in IDA/CONNECT), nicht live ([#6](https://github.com/MarkusKeller8200/EduKSX-Connectors/issues/6)) |
| L15 | Sichtbarkeit in der Eltern-App pro Phase | offen, mit Escola klären ([#7](https://github.com/MarkusKeller8200/EduKSX-Connectors/issues/7)) |
| L16 | Arzt-/Zahnarztkontrollen: Status, Liste der offenen | Lesen ✅ `GET /klassen/{id}/felder?nur_leer=true` (falls Escola-Feld); Entscheid Escola/CMI/eigene Anwendung offen ([#8](https://github.com/MarkusKeller8200/EduKSX-Connectors/issues/8)) |
| L17 | Absenzen, Verhalten, Prüfungsresultate lesen | offen ([#9](https://github.com/MarkusKeller8200/EduKSX-Connectors/issues/9)) |
| L18 | Prüfungen mit Note an Eltern | offen ([#10](https://github.com/MarkusKeller8200/EduKSX-Connectors/issues/10)) |

Testläufe der Schreib-Workflows WF-01 bis WF-10: [#15](https://github.com/MarkusKeller8200/EduKSX-Connectors/issues/15).

## Offene Fragen

Alle Fragen F-01 bis F-09 am 15.11.2026 beantwortet (siehe Entscheidungen).

## Entscheidungen (14./15.11.2026)

- **AHV-Nummer** muss geschrieben werden: in anderen Anwendungen teilweise Primärschlüssel, darf nur zu einer Person gehören → Format + Prüfziffer + Eindeutigkeit (aktive und inaktive Personen).
- **Schulmail** `vorname.nachname@sekbuelach.ch`: ä→ae, ö→oe, ü→ue, ß→ss, Akzente weg (é→e), bei Doppelnamen nur der erste Teil, Namenszusätze gehören zum Namen (von Arx → vonarx) – bestätigt (F-01).
- **Adresse schon vergeben:** melden, der/die Benutzer:in löst das Problem selbst.
- **Haupt-E-Mail = Geschäfts-E-Mail:** bei Mitarbeitenden dasselbe Escola-Feld `email` (Reiter „Geschäft“).
- **Postfach** in M365 legt später IDA oder CONNECT an, nicht die Escola-API.
- **F-02** Stundenplan schreiben → eingebaut (L1).
- **F-03** Austritt Lehrperson/Mitarbeitende: alle Rollen werden durch **„Ausgetreten“** ersetzt; die Schule legt die Rolle an, falls sie fehlt (API meldet `409`).
- **F-04** Fachklasse = Escola-**Arbeitsgruppe** (L3).
- **F-05** Informationspflicht = **informationsberechtigt**, gesetzliche Vertretung = **sorgeberechtigt** (Escola „erziehungsberechtigt“).
- **F-06** Existiert ein Elternteil schon (z. B. Geschwister), wird die bestehende Person verknüpft statt neu angelegt.
- **F-07** Tritt ein Kind aus und hat ein Elternteil keine weiteren Kinder an der Schule, wird es deaktiviert (nicht, wenn es eine andere Rolle hat, z. B. Lehrperson).
- **F-08** Umzug: neue Adresse ab Datum (IDA/CONNECT löst am Stichtag aus) oder sofort.
- **F-09** Neue Lehrperson im laufenden SJ: Sachbearbeiter:in entscheidet, ob Klasse/Fächer sofort oder am Stichtag; anlegen geht immer sofort.

## Erkenntnisse aus den Live-Prüfungen (15.11.2026)

- Fach zuteilen wirkt auf die zuletzt mit „Fächer anzeigen“ geöffnete Lehrperson → API öffnet sie jedes Mal vorher (Fehler in 1.10/1.11 behoben).
- Fächer-Matrix mit `school_year=1` stellt die **ganze Sitzung** aufs kommende SJ um (auch den Stundenplan) → API stellt immer zurück.
- Arbeitsgruppen haben eine eigene Matrix-Form und **eigene Zuteilungsnummern** → Löschen nur im Kontext der Arbeitsgruppe.
- Stundenplan: Lehrperson ergibt sich aus der Fächer-Zuteilung; Schalter nur bei mehreren Lehrpersonen mit demselben Fach.
- „Eintrag hinzufügen“ in belegter Zelle legt sofort einen leeren Eintrag an.
- Rollen-Schalter zeigt Escola nur im Bearbeitungsmodus (Fehler in der Rollen-Funktion behoben).
- Personen-Aufrufe melden nach anderen Modulen gelegentlich „Bitte laden Sie die Seite neu“ → API öffnet die Personenverwaltung neu und wiederholt.
- Bezugsperson verknüpfen gibt der Person automatisch die Rolle „Eltern/Bezugspersonen“; Entfernen nimmt sie wieder weg.
- Die Soll-Liste `faecher` wirkte bis 1.11 nur zusammen mit einer Vorlage (Fehler behoben).

---

### WF-01: Mitarbeiter:in einstellen und erfassen

- **Ziel:** Neue:r Mitarbeiter:in wird angelegt, bekommt die Tätigkeitsrolle in einem Schulhaus, alle persönlichen Daten
  (mindestens Name, Vorname, AHV-Nummer) und die Schulmail `vorname.nachname@sekbuelach.ch`.
- **Testdaten:** „Muster Max“ (neu), Hinterbirch, Rolle beim Anlegen `gruppe_14` („_neu“), Tätigkeitsrolle 13, AHV `756.1234.5678.97`.
- **Status:** ✅

**Variante A – ein Aufruf**

| Schritt | Aufruf | Erwartung / Prüfung |
|---|---|---|
| 1 | `POST /auth/login` → `POST /auth/2fa` | Session-Token |
| 2 | `GET /rollen` | ID der Tätigkeitsrolle, `zuordenbar: true` |
| 3 | `POST /mitarbeitende?probelauf=true` | Plan, Schulmail; `409` wenn AHV oder Mail vergeben |
| 4 | `POST /mitarbeitende` `{nachname, vorname, geschlecht, schulhaus, rolle, rollen_ids, ahv, felder}` | `201`, `vollstaendig: true` |
| 5 | `GET /personen/{id}` + `GET /personen/{id}/rollen` | Felder, Rolle, `email`, AHV (`***`) |

**Variante B – Einzelschritte:** `GET /hilfe/schulmail` → `GET /suche/personen?ahv=…&email=…` → `POST /personen` →
`PATCH /personen/{id}/rollen` → `PATCH /personen/{id}` → `PUT /personen/{id}/ahv` → `POST /personen/{id}/schulmail`.

- **Prüfungen im Testlauf:** zweiter Durchlauf mit gleicher AHV → `409`, nichts angelegt · Umlaut/Doppelname → richtige Adresse · ungültige AHV → `400`.
- **Aufräumen:** `POST /personen/{id}/deaktivieren`. AHV/Mail bleiben bei der inaktiven Person → für Wiederholungen andere Testdaten.

---

### WF-02: Mitarbeiter:in tritt auf ein bestimmtes Datum aus

- **Testdaten:** TEST TEST (649), vorher in TEST_A1a Klassenlehrperson A + Fach Deutsch.
- **Status:** ✅ (Stichtag-Ausführung durch IDA/CONNECT)

| Schritt | Wann | Aufruf | Erwartung |
|---|---|---|---|
| 1 | sofort | `GET /lehrpersonen/{id}/einsatz` | Klassenlehrperson-Plätze, Fächer, Lektionen |
| 2 | sofort | `POST /personen/{id}/austritt` `{"datum": "2027-07-31"}` | Austrittsdatum gesetzt |
| 3 | Stichtag | `POST /lehrpersonen/{id}/ersetzen` `{"neu_id": …}` (Lehrpersonen) | Nachfolge übernimmt Fächer/Plätze/Lektionen |
| 4 | Stichtag | `POST /personen/{id}/rollen/ausgetreten` | nur noch Rolle „Ausgetreten“ (+ nicht zuordenbare) |
| 5 | Stichtag | Escola deaktiviert die Person selbst | in `GET /personen?rolle=allInactive` – bei Mitarbeitenden im Testlauf bestätigen |
| 6 | sofort (fristlos) | `POST /personen/{id}/austritt` `{"datum": …, "rollen_ausgetreten": true, "sofort_deaktivieren": true}` | sofort inaktiv |
| 7 | Korrektur | `POST /personen/{id}/austritt` `{"datum": ""}` | Austritt zurückgenommen |

- **Aufräumen:** Schritt 7, Rollen zurück (`PATCH /personen/649/rollen`), `POST /personen/649/aktivieren`, TEST_A1a zurücksetzen.
- **Voraussetzung:** Rolle „Ausgetreten“ in Escola angelegt.

---

### WF-03: Neue Lehrperson ab Datum, mit Klasse oder Fachklasse

- **Status:** ✅ (F-09: Sachbearbeiter:in entscheidet sofort/Stichtag)

| Schritt | Wann | Aufruf |
|---|---|---|
| 1 | sofort | WF-01 `POST /mitarbeitende` mit `rolle: lehrperson`, `rollen_ids: [13]` (Hibi) bzw. `[16]` (Mettmi), `felder.eintritt` |
| 2a | SJ-Wechsel | `PUT /klassen/{k}/klassenlehrpersonen` `{"kommend": [<id>, …]}` |
| 2b | sofort/Stichtag | `PUT /klassen/{k}/klassenlehrpersonen` `{"aktuell": [<id>, …]}` |
| 3a | Fächer aktuelles SJ | `PATCH /lehrpersonen/{id}/faecher` `{"klasse_id": k, "vorlage": "fachlehrperson", "faecher": [...]}` |
| 3b | Fächer kommendes SJ | dito mit `"schuljahr": 1` (nur Fächer, L6) |
| 3c | Fachklasse | `PATCH /lehrpersonen/{id}/faecher` `{"arbeitsgruppe_id": ag, "faecher": [...]}` |
| 4 | Lektionen | `POST/PATCH /klassen/{k}/stundenplan/{tag}/{lektion}` (Lehrperson ergibt sich aus der Fächer-Zuteilung) |
| 5 | Kontrolle | `GET /lehrpersonen/{id}/einsatz` |

---

### WF-04: Lehrperson verlässt die Schule

- **Ablauf wie WF-02**, Kern ist `POST /lehrpersonen/{id}/ersetzen` (Nachfolge) am Stichtag. Ohne Nachfolge:
  `PUT /klassen/{k}/klassenlehrpersonen` (Platz leeren) und `PATCH /lehrpersonen/{id}/faecher` `{"klasse_id": k, "faecher": []}` je Klasse.
- **Status:** ✅

---

### WF-05: Lehrperson übernimmt eine zusätzliche Klasse (Klassen- oder Fachlehrperson)

- **Status:** ✅

| Schritt | Aufruf | Erwartung |
|---|---|---|
| 1 | `GET /klassen/{k}/klassenlehrpersonen` | bisherige Plätze A/B/C |
| 2a | als KLP: `PUT /klassen/{k}/klassenlehrpersonen` `{"aktuell": [<bisherige…>, <id>]}` | KLR automatisch |
| 2b | als FP: `PATCH /lehrpersonen/{id}/faecher` `{"klasse_id": k, "vorlage": "fachlehrperson", "faecher": [...]}` | Fächer, keine Rechte |
| 2c | Fachklasse: `{"arbeitsgruppe_id": ag, "faecher": [...]}` | |
| 3 | kommendes SJ: `{"kommend": …}` bzw. `"schuljahr": 1` | |
| 4 | Lektionen: `POST /klassen/{k}/stundenplan/{tag}/{lektion}` | |

---

### WF-06: Lehrperson übernimmt eine neue Klasse (gibt die bisherige ab)

- **Status:** ✅ (Rechte fürs kommende SJ: L6)

| Schritt | Aufruf |
|---|---|
| 1 | `GET /lehrpersonen/{id}/einsatz` |
| 2 | Nachfolge in der alten Klasse: `POST /lehrpersonen/{id}/ersetzen` `{"neu_id": <nachfolge>, "klassen_ids": [<alt>]}` |
| 3 | Neue Klasse: `PUT /klassen/{neu}/klassenlehrpersonen` + `PATCH /lehrpersonen/{id}/faecher` + Stundenplan |
| 4 | Zum SJ-Wechsel: `{"kommend": …}` und `"schuljahr": 1` |

---

### WF-07: Schüler:in anmelden ab Datum X, Klasse zuteilen, Eltern als gesetzliche Vertretung

- **Status:** ✅ (L7: Anlegen neuer Bezugsperson im Testlauf prüfen)

| Schritt | Aufruf | Erwartung |
|---|---|---|
| 1 | `POST /schueler` `{nachname, vorname, geschlecht, schulhaus, felder: {geburtstag, eintritt: X, …}}` | ID |
| 2a | `POST /schueler/{id}/klasse` `{"klasse_id": k, "stichtag": X}` | Transfer ab X |
| 2b | Start kommendes SJ: `{"klasse_id": k, "schuljahr": 1}` | |
| 3 | `POST /schueler/{id}/bezugspersonen` `{"nachname", "vorname", "geschlecht": "w", "sorgerecht": "sorgeberechtigt", "felder": {…}}` | Mutter; `409` mit Liste, wenn es sie schon gibt |
| 3b | bei `409` / Geschwister: `{"person_id": <id>, "sorgerecht": …}` | bestehende Person verknüpft (F-06) |
| 4 | Vater analog, z. B. `"sorgerecht": "informationsberechtigt"` | |
| 5 | `GET /schueler/{id}/bezugspersonen` | Funktion, Sorgerecht |
| 6 | Arbeitsgruppen `POST /schueler/{id}/arbeitsgruppen` | |

- **Live geprüft 15.11.2026:** Verknüpfen (TEST TEST ↔ SuS SuS), Sorgerecht ändern, Verknüpfung entfernen – alle Escola-Aufrufe ✔️.

---

### WF-08: Schüler:in wechselt die Klasse ab Datum

- **Status:** ✅

| Schritt | Aufruf |
|---|---|
| 1 | `GET /schueler/{id}/klasse/optionen` |
| 2 | `POST /schueler/{id}/klasse` `{"klasse_id": neu, "stichtag": X}` bzw. `"schuljahr": 1` |
| 3 | Arbeitsgruppen anpassen |
| 4 | Kontrolle `GET /schueler?klasse_id=neu` |

- **Testlauf:** SuS SuS (650) von H_A1a (92) nach TEST_A1a (120) und zurück.

---

### WF-09: Schüler:in verlässt die Schule zum Zeitpunkt X

- **Status:** ✅

| Schritt | Wann | Aufruf |
|---|---|---|
| 1 | sofort | `POST /schueler/{id}/austritt` `{"datum": X, "wegzugsdatum": …, "wegzugsgemeinde": …}` – Escola deaktiviert selbst |
| 2 | Stichtag | `POST /schueler/{id}/eltern/deaktivieren?probelauf=true`, dann ohne Probelauf (F-07) |
| 3 | optional | Arbeitsgruppen entfernen |
| 4 | Korrektur | `{"datum": ""}` |

---

### WF-10: Schüler:in zieht um

- **Status:** ✅ (ab Datum: IDA/CONNECT)

| Schritt | Aufruf |
|---|---|
| 1 | `GET /schueler/{id}/bezugspersonen` – `gleiche_adresse` |
| 2a | eigene Adresse: `PATCH /schueler/{id}` `{"felder": {"strasse", "private_town_id", "private_civil_commune_federal_statistical_office_code"}}` |
| 2b | Adresse der Bezugsperson: `PATCH /personen/{bezugsperson_id}` (gleiche Felder) |
| 3 | Zuzug: `arrival_timestamp`, `arrival_municipality_name` |
| 4 | Wegzug aus der Gemeinde → WF-09 |

---

## Schuljahr vorbereiten und laufendes Schuljahr (WF-11 bis WF-20)

Erhoben am 15.11.2026 aus dem Gesamtablauf (siehe `docs/workflows-escola.md`). Teile ausserhalb von Escola
(Datenaufbereitung, Rekurs, Geräte, Inventar, CMI) übernehmen IDA/CONNECT.

### WF-11: Massenimport Schüler:innen und Eltern (Einschulung)

- **Ziel:** Gelieferte Daten strukturiert einlesen; unsere Anwendung sortiert, ergänzt, bildet Mailadressen/Zugangsdaten und erzeugt eine Escola-Importdatei mit allen verfügbaren Angaben. SuS noch ohne Klasse.
- **Status:** ⚠️

| Schritt | Wer | Aufruf |
|---|---|---|
| 1 | IDA/CONNECT | Datenlieferung einlesen, aufbereiten |
| 2 | Wrapper | `POST /import/pruefen` `{"personen": [{nachname, vorname, geschlecht, art, schulhaus}]}` → `neu` / `moegliche_duplikate` / `fehler`, legt nichts an |
| 3 | IDA/CONNECT | Importdatei erzeugen (Format: L10) |
| 4 | Escola-Import | Import (manuell oder über Wrapper: L10) |
| 5 | Wrapper | Kontrolle `GET /schueler?ohne_klasse=true`, `GET /personen?rolle=guardians-all` |

### WF-12: Übertrittsformular ins Schülerdossier

- **Ziel:** Lehrpersonen der 6. Klassen reichen das Formular in Escola oder in unserer Anwendung ein; Ablage im Dossier für SL, Zuteilende und später die LP.
- **Status:** ❌ – Dokumente ablegen (L11).

### WF-13: Klasseneinteilung durch die Schulleitung

- **Ziel:** Nach der Schulhauszuteilung teilt die SL mit dem Escola-Tool ein; danach Kontrolle und Weitergabe.
- **Status:** ✅ (Einteilung selbst im Escola-Tool)

| Schritt | Aufruf |
|---|---|
| 1 | Einteilung im Escola-Tool (SL) bzw. einzeln `POST /schueler/{id}/klasse` `{"klasse_id": k, "schuljahr": 1}` |
| 2 | Kontrolle `GET /klassenlisten?schuljahr=1` (CSV) und `GET /schueler?ohne_klasse=true` (wer fehlt noch) |

### WF-14: App-Zugang für Eltern, Nachfassen

- **Ziel:** Spätestens nach der Einteilung erhalten die Eltern den App-Zugang (Escola-Funktion, unsere App oder Post Smart Send); nach einer Frist wird bei säumigen Eltern nachgefasst. Voraussetzung für den Zuteilungsbrief.
- **Status:** ⚠️

| Schritt | Aufruf |
|---|---|
| 1 | `GET /klassen/{id}/eltern?schuljahr=1` – Bezugspersonen je Kind, Kinder ohne Eltern fallen auf |
| 2 | Zugänge versenden (L12 bzw. IDA/CONNECT, Smart Send) |
| 3 | Aktivierungsstatus lesen, Liste säumiger Eltern (L12) |

### WF-15: Zuteilungsbrief, Rekurs, Zuteilung definitiv

- **Ziel:** Brief per Escola, Eltern sehen nur Klasse und KLP; Rekurs über die App oder unsere Plattform; nach Rekursfrist und Umteilungen definitiv, danach sehen Eltern ggf. die Mitschüler:innen.
- **Status:** ⚠️ – Umteilung ✅ (`POST /schueler/{id}/klasse`, WF-08); Brief versenden (L13); Sichtbarkeit (L15); Rekurs: IDA/CONNECT.

### WF-16: Stundenpläne aus dem Stundenplaner einspielen

- **Ziel:** Finaler Stundenplan als Export aus dem Stundenplaner nach Escola; ab dann sichtbar für Eltern.
- **Status:** ⚠️ – Einzelschreiben ✅; Abgleich ✅ `POST /klassen/{id}/stundenplan/abgleich` `{eintraege: [{tag, lektion_id, fach_id, raum_ids?, lehrperson_ids?}], loeschen}` – Standard Probelauf, Fehler (Fach nicht zugeteilt) → nichts geschrieben. Offen: Exportformat des Stundenplaners → IDA/CONNECT wandelt um; Live-Test mit TEST_A1a.

### WF-17: ICT – Klassenlisten, Zugänge, Geräte, Nutzungsvereinbarung

- **Ziel:** ICT lädt die Klassenlisten, erstellt fehlende Zugänge (Entra, Apple School Manager, weitere Umsysteme), meldet jedes Gerät einmal an, übergibt es mit Login-Blatt und Nutzungsvereinbarung; die Vereinbarung geht per Escola an die Eltern und muss unterschrieben zurück; Gerätedaten ins Inventar.
- **Status:** ⚠️

| Schritt | Wer | Aufruf |
|---|---|---|
| 1 | Wrapper | `GET /klassenlisten?format=csv` |
| 2 | IDA/CONNECT | Zugänge Entra/ASM, Erstanmeldung Gerät, Inventar |
| 3 | Wrapper | Klassenliste/Login-Blatt ins Dossier (L11) |
| 4 | Wrapper | Nutzungsvereinbarung senden, Rücklauf lesen (L13) |

### WF-18: Arzt- und Zahnarztkontrollen

- **Ziel:** Gutscheine einmal jährlich bzw. einmal im Sekundarschulzyklus per Escola; Rückmeldungen der Ärzt:innen über unsere Plattform ins Dossier, Erhalt markieren; Liste der offenen für die Fachstelle.
- **Status:** ❌/⚠️ – Gutscheine senden (L13), Rückmeldung ablegen (L11); Liste der offenen ✅ über `GET /klassen/{id}/felder?namen=<feld>&nur_leer=true`, sobald das Feld in Escola existiert (L16).

### WF-19: Prüfungen mit Note an Eltern

- **Ziel:** Deckblätter mit Schüler- und Prüfungscode, gesammelt scannen, unser System trennt und ordnet zu, LP kontrolliert, dann Prüfung und Note zur Bestätigung in die App; Visum kann geprüft werden.
- **Status:** ❌ – L18, hängt an L11 und L17.

### WF-20: Überführung nach CMI

- **Ziel:** Zentrales Dossier und Archiv in CMI. Überführt werden Stammdaten/Klassenzuteilung (Mutationen), Absenzen/Verhalten/Prüfungsresultate (Einzeldatensätze oder mindestens PDF pro SJ), Dokumente des Dossiers (täglich, mindestens Semesterende, v. a. Zeugnisse), Schuljahresdossier (Absenzen, Zeugnisse, Klassenlisten als PDF).
- **Status:** ⚠️ – Stammdaten ✅ (`/schueler`, `/klassenlisten`, `/schueler/{id}/bezugspersonen`); L17, L11; CMI-Seite: IDA/CONNECT.

---

## Vorlage für einen Workflow

### WF-xx: Name

- **Ziel:** …
- **Testdaten:** …
- **Status:** ✅ / ⚠️ / ❌

| Schritt | Aufruf | Erwartung / Prüfung |
|---|---|---|
| 1 | `GET …` | … |

- **Aufräumen nach dem Testlauf:** …
- **Lücken / offene Punkte:** …
