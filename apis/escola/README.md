# Escola-API

REST-API für **Escola (sekbuelach.ch)** zur Weiterverwendung in anderen Projekten (z. B. IDA):

- **Anmeldung** mit Benutzername, Passwort und Zwei-Faktor-Code, plus Logout und eigene Loginseite
- **Stundenplan & Stammdaten** lesen: Klassen, Fächer, Lehrpersonen, Räume, Tage, Lektionen, Einträge
- **Arbeitsgruppen** lesen, Schüler:innen einteilen und entfernen; **Austritt** erfassen
- **Rollen** lesen und Personen zuordnen (Lehrpersonen, Schulleitung, eigene Rollen)
- **Klassenlehrpersonen** setzen und **Fächer-Zuteilung** (Klassen und Arbeitsgruppen, aktuelles und kommendes SJ) inkl. Rechte KLR/FP/SpM/Abs
- **Stundenplan schreiben**: Einträge anlegen, ändern, löschen; Lehrperson ersetzen (Nachfolge)
- **Eltern/Bezugspersonen** lesen, anlegen, verknüpfen, Sorgerecht setzen, entfernen
- **Schüler:innen & Personen** lesen, anlegen (auch ohne Klasse), einer Klasse zuordnen und (optional) schreiben
- **Schuljahr vorbereiten:** Klassenlisten, Eltern je Klasse, Vorprüfung von Importlisten auf Duplikate
- **Dokumente** als Platzhalter vorbereitet

Escola hat keine offizielle API. Diese Schnittstelle nutzt dieselben internen Aufrufe wie die
Escola-Weboberfläche und wertet deren Antworten aus.

## Übersicht aller Endpunkte

**Zugriff:** 🔓 ohne Anmeldung · 🔑 Anmeldung nötig (Header `X-Escola-Session` oder `ESCOLA_COOKIE`) ·
✏️ schreibt in Escola (nur mit `ESCOLA_SCHREIBEN=1` und `X-API-Key`) · ⏳ Platzhalter, noch nicht aktiviert.
Ist `ESCOLA_API_KEY` gesetzt, braucht zusätzlich jeder Aufruf den Header `X-API-Key`.
Listen-Endpunkte liefern mit `?format=csv` eine CSV-Tabelle.

### Testseite

`http://127.0.0.1:8080/testseite` (bzw. die Server-Adresse der API). Das Startskript öffnet
`/login?weiter=/testseite`: anmelden, danach geht es im **selben Tab** zur Testseite (das Session-Token gilt
nur pro Tab). API-Key oben rechts eintragen. Die Menügruppen links lassen sich auf- und zuklappen
(„alle auf / alle zu“); der Zustand bleibt im Tab erhalten.

**Daten lesen** (oberste Menügruppe, ändert nichts): Schüler:innen (mit/ohne Klasse, zukünftig, ehemalig),
Eltern/Bezugspersonen, Lehrpersonen, Personen nach Rolle (inkl. inaktive), Rollen, Klassen, Arbeitsgruppen,
Fächer, Lektionen/Zeiten, Schultage, Räume, Ressourcen, Stundenpläne, Zuteilungen und Klassenlehrpersonen
einer Klasse, Eltern einer Schülerin, Komplett-Export. Ergebnis als Tabelle mit Anzahl, Filter und
„Als CSV herunterladen“. Während des Ladens zählt die Seite die Einzelabfragen an Escola mit
(„läuft … 12 s · 37 Escola-Abfragen“, über `GET /fortschritt`).

**Schreib-Testfälle:**

Jeder Testfall läuft in fünf Schritten: **1 lesen → 2 schreiben/anlegen → 3 lesen → 4 rückgängig/löschen →
5 lesen**. Oben steht ein Vergleich der drei Lesestände; am Ende muss „Zurückgesetzt – Endstand entspricht dem
Anfang“ erscheinen. Schritte einzeln oder „Alle Schritte nacheinander“; Schreibschritte erst nach dem Haken
„Schreiben in Escola freigeben“, wo möglich auch als Probelauf.

| Testfall | Schreiben | Rückgängig |
|---|---|---|
| Feld einer Person / Schülerin | `PATCH /personen|schueler/{id}` Testwert | alten Wert zurückschreiben |
| Rolle zuweisen | `PATCH /personen/{id}/rollen` hinzufügen | entfernen |
| Austritt | `POST /schueler/{id}/austritt` Datum | Datum leeren |
| Klassenwechsel | `POST /schueler/{id}/klasse` Zielklasse ab heute | zurück in die bisherige Klasse (Escola-Verlauf zeigt beide Transfers) |
| Arbeitsgruppe | `POST /schueler/{id}/arbeitsgruppen` | `DELETE …/{ag}` |
| Bezugsperson | `POST /schueler/{id}/bezugspersonen` bestehende Person | `DELETE …/{beziehung_id}` |
| Klassenlehrperson | `PUT /klassen/{id}/klassenlehrpersonen` + Person | alte Belegung |
| Fach zuteilen | `PATCH /lehrpersonen/{id}/faecher` hinzu (Klasse oder Arbeitsgruppe, SJ 0/1) | weg |
| Lektion | `POST /klassen/{id}/stundenplan/{tag}/{lektion}` | `DELETE …/{eintrag_id}` |
| Mitarbeiter:in einstellen, Lehrperson ersetzen | nur Probelauf (Plan) | – |

Voreingestellt sind die Testobjekte (TEST TEST 649, SuS SuS 650, TEST_A1a 120, Arbeitsgruppe TEST 3).
Dazu ein „Freier Aufruf“ für jeden Endpunkt. Fälle, die nicht rückgängig zu machen sind (neue Person anlegen,
AHV setzen), gibt es auf der Testseite bewusst nur als Probelauf.

## Betrieb in einer Webanwendung

Die API ist ein Server-Dienst; eine Webanwendung ruft sie per HTTP auf. Direkt aus dem Browser geht es nicht
(Escola erlaubt keine fremden Seiten, Anmeldung per HttpOnly-Cookie). Varianten und Regeln:
[docs/betrieb-webanwendung.md](../../docs/betrieb-webanwendung.md). Mit Docker:

```bash
docker build -t escola-api apis/escola
docker run -p 8080:8080 --env-file apis/escola/.env escola-api
```

## Anmeldung

| Methode | Endpunkt | Zugriff | Zweck |
|---|---|---|---|
| GET | `/login` | 🔓 | Loginseite im Browser (Benutzername, Passwort, 2FA-Code, Abmelden) |
| POST | `/auth/login` | 🔓 | Mit Benutzername und Passwort bei Escola anmelden, liefert das Session-Token |
| GET | `/auth/2fa/methoden` | Session | Verfügbare Zwei-Faktor-Methoden anzeigen (App, SMS …) |
| POST | `/auth/2fa/methode` | Session | Zwei-Faktor-Methode wählen |
| POST | `/auth/2fa/erneut` | Session | Bestätigungscode erneut senden |
| POST | `/auth/2fa` | Session | Bestätigungscode eingeben und Anmeldung abschliessen |
| POST | `/auth/2fa/app` | Session | Alternative: Bestätigung in der Escola-App anfordern |
| GET | `/auth/2fa/app/{app_token}` | Session | Abfragen, ob die Bestätigung in der Escola-App erfolgt ist |
| GET | `/auth/status` | Session | Status der Session (angemeldet, 2FA offen, abgelaufen) |
| POST | `/auth/logout` | Session | Bei Escola abmelden und Session löschen |
| GET | `/status` | 🔑 | Prüfen, ob der Escola-Zugang funktioniert |
| GET | `/fortschritt` | 🔑 | Anzahl bisheriger Escola-Abfragen dieser Session (für Fortschrittsanzeige bei langen Listen) |

### Stammdaten und Raster

| Methode | Endpunkt | Zugriff | Zweck |
|---|---|---|---|
| GET | `/klassen` | 🔑 | Alle Klassen und Arbeitsgruppen mit Schulhaus und Klassenlehrperson |
| GET | `/faecher` | 🔑 | Alle Fächer mit ID, Kürzel und Namen |
| GET | `/lehrpersonen` | 🔑 | Alle Lehrpersonen mit ID, Kürzel und Schulhaus |
| GET | `/raeume` | 🔑 | Alle Räume beider Schulhäuser mit ID, Kürzel, Geschoss und Trakt (aus dem Modul Ressourcen) |
| GET | `/ressourcen` | 🔑 | Alle Ressourcen aus dem Modul Ressourcen mit Kategorie, Zeitprofil, reservierbar, Schulhaus |
| GET | `/ressourcen/kategorien` | 🔑 | Ressourcen-Kategorien (z. B. „Hibi – Trakt A“, „Mettmi – Trakt OST“) mit Anzahl |
| GET | `/ressourcen/zeiteinteilung` | 🔑 | Zeiteinteilung des Moduls Ressourcen je Profil (HIBI / METTMI) |
| GET | `/tage` | 🔑 | Wochentage mit Escola-Code (A–E) |
| GET | `/lektionen` | 🔑 | Lektionen je Schulhaus mit Escola-ID und Zeiten |

### Stundenplan

| Methode | Endpunkt | Zugriff | Zweck |
|---|---|---|---|
| GET | `/eintraege` | 🔑 | Alle Stundenplan-Einträge als Tabelle (Klasse, Tag, Lektion, Fach, Lehrpersonen, Räume) |
| GET | `/export` | 🔑 | Stammdaten, Raster und alle Einträge in einem JSON |
| GET | `/klassen/{id}/stundenplan/{tag}/{lektion_id}` | 🔑 | Einträge einer Zelle mit IDs und was wählbar ist (Fächer, Räume, Lehrpersonen) |
| POST | `/klassen/{id}/stundenplan/{tag}/{lektion_id}` | 🔑 ✏️ | Eintrag anlegen (`fach_id`, optional `raum_ids`, `lehrperson_ids`) |
| PATCH | `/klassen/{id}/stundenplan/{tag}/{lektion_id}/{eintrag_id}` | 🔑 ✏️ | Fach, Räume, Lehrpersonen eines Eintrags ändern |
| DELETE | `/klassen/{id}/stundenplan/{tag}/{lektion_id}/{eintrag_id}` | 🔑 ✏️ | Einen Eintrag löschen |
| POST | `/klassen/{id}/stundenplan/abgleich` | 🔑 ✏️ | Soll-Stundenplan (z. B. aus dem Stundenplaner) abgleichen: Standard Probelauf mit Plan (neu/ändern/bleibt), dann anwenden; löschen nur mit `loeschen: true` (WF-16) |
| POST | `/lehrpersonen/{id}/ersetzen` | 🔑 ✏️ | Nachfolge: Fächer, Klassenlehrperson-Plätze und Lektionen an eine andere Lehrperson übergeben |

### Schüler:innen

| Methode | Endpunkt | Zugriff | Zweck |
|---|---|---|---|
| GET | `/schueler` | 🔑 | Alle Schüler:innen mit Klasse; mit `?ohne_klasse=true` die ohne Klasse |
| POST | `/schueler` | 🔑 ✏️ | Schüler:in anlegen, mit Klasse oder ohne Klasse zum späteren Zuordnen |
| GET | `/schueler/{id}` | 🔑 | Alle Felder einer Schülerin / eines Schülers, nach Reitern gruppiert |
| PATCH | `/schueler/{id}` | 🔑 ✏️ | Felder einer Schülerin / eines Schülers ändern |
| GET | `/schueler/{id}/klasse/optionen` | 🔑 | Wählbare Klassen für Ein-/Umteilung; `?schuljahr=1` mit den künftigen Klassennamen |
| POST | `/schueler/{id}/klasse` | 🔑 ✏️ | Klasseneinteilung und -umteilung (aktuelles SJ ab Stichtag oder kommendes SJ) |
| DELETE | `/schueler/{id}/klasse` | 🔑 ✏️ | Schüler:in aus der Klasse nehmen (aktuelles oder kommendes SJ), danach „ohne Klasse“ |
| POST | `/schueler/{id}/austritt` | 🔑 ✏️ | Austritt erfassen (Austrittsdatum, optional Wegzug; optional sofort deaktivieren) |
| GET | `/schueler/{id}/bezugspersonen` | 🔑 | Eltern/Bezugspersonen mit Funktion, Sorgerecht, abholberechtigt, gleicher Adresse |
| POST | `/schueler/{id}/bezugspersonen` | 🔑 ✏️ | Bestehende Person verknüpfen (`person_id`) oder neue Bezugsperson anlegen |
| PATCH | `/schueler/{id}/bezugspersonen/{beziehung_id}` | 🔑 ✏️ | Sorgerecht ändern (sorgeberechtigt / informationsberechtigt / keine) |
| DELETE | `/schueler/{id}/bezugspersonen/{beziehung_id}` | 🔑 ✏️ | Verknüpfung entfernen (`?deaktivieren=true`: Bezugsperson zusätzlich deaktivieren) |
| POST | `/schueler/{id}/eltern/deaktivieren` | 🔑 ✏️ | Eltern ohne weitere aktive Kinder deaktivieren (Austritt) |
| GET | `/personen/{id}/kinder` | 🔑 | Kinder, mit denen eine Bezugsperson verknüpft ist |

### Schuljahr vorbereiten

| Methode | Endpunkt | Zugriff | Zweck |
|---|---|---|---|
| GET | `/klassenlisten?schuljahr=0\|1&schulhaus=…` | 🔑 | Eine Zeile pro Schüler:in mit Klasse, Schulhaus und Klassenlehrperson(en) – für ICT-Zugänge, Drucklisten, Abgleich (WF-13, WF-17) |
| GET | `/klassen/{id}/eltern` | 🔑 | Alle Bezugspersonen der Kinder einer Klasse, Kinder ohne Eltern mit leeren Feldern – für App-Onboarding und Zuteilungsbrief (WF-14, WF-15) |
| GET | `/klassen/{id}/felder?namen=…&nur_leer=true` | 🔑 | Ausgewählte Felder aller SuS einer Klasse, z. B. Kontrollen Arzt/Zahnarzt; `nur_leer` = Liste der offenen (WF-18) |
| POST | `/import/pruefen` | 🔑 | Importliste (Schüler:innen, Eltern) mit der Escola-Duplikatprüfung vorprüfen, legt nichts an (WF-11) |

### Personen (Lehrpersonen, Mitarbeitende, weitere)

| Methode | Endpunkt | Zugriff | Zweck |
|---|---|---|---|
| GET | `/personen/rollen` | 🔑 | Alle Escola-Rollen live, inkl. eigener Rollen wie „_neu“ (Kennung `gruppe_<n>`) |
| GET | `/personen` | 🔑 | Personen einer Rolle, z. B. `?rolle=lehrperson` (Standard: alle aktiven); `?rolle=allInactive` = deaktivierte |
| POST | `/personen` | 🔑 ✏️ | Person mit einer Rolle anlegen, z. B. Lehrperson oder „_neu“ |
| GET | `/personen/{id}` | 🔑 | Alle Felder einer Person, nach Reitern gruppiert |
| PATCH | `/personen/{id}` | 🔑 ✏️ | Felder einer Person ändern |
| POST | `/personen/{id}/deaktivieren` | 🔑 ✏️ | Person deaktivieren (z. B. Austritt Mitarbeitende), umkehrbar |
| POST | `/personen/{id}/aktivieren` | 🔑 ✏️ | Deaktivierte Person wieder aktivieren |

### Arbeitsgruppen

| Methode | Endpunkt | Zugriff | Zweck |
|---|---|---|---|
| GET | `/arbeitsgruppen` | 🔑 | Alle Arbeitsgruppen mit ID, Name, Schulhaus und Anzahl Schüler:innen |
| GET | `/schueler/{id}/arbeitsgruppen` | 🔑 | Arbeitsgruppen einer Schülerin / eines Schülers |
| POST | `/schueler/{id}/arbeitsgruppen` | 🔑 ✏️ | In eine Arbeitsgruppe einteilen (`{"arbeitsgruppe_id": 3}`) |
| DELETE | `/schueler/{id}/arbeitsgruppen/{ag_id}` | 🔑 ✏️ | Aus einer Arbeitsgruppe entfernen |

### Mitarbeitende (Einstellen, AHV, Schulmail, Austritt)

| Methode | Endpunkt | Zugriff | Zweck |
|---|---|---|---|
| POST | `/mitarbeitende` | 🔑 ✏️ | Einstellen in einem Schritt: prüfen, anlegen, Rollen, Felder, AHV, Schulmail |
| GET | `/suche/personen?ahv=…` / `?email=…` | 🔑 | Personen (aktiv + inaktiv) mit dieser AHV-Nummer bzw. E-Mail |
| GET | `/hilfe/schulmail?vorname=…&nachname=…` | 🔑 | Schulmail nach Regel bilden (ohne Escola-Zugriff) |
| PUT | `/personen/{id}/ahv` | 🔑 ✏️ | AHV-Nummer setzen (Prüfziffer, eindeutig) |
| POST | `/personen/{id}/schulmail` | 🔑 ✏️ | Schulmail bilden, auf Doppelte prüfen, als E-Mail (Geschäft) setzen |
| POST | `/personen/{id}/austritt` | 🔑 ✏️ | Austritt erfassen (Austrittsdatum, optional Wegzug / sofort deaktivieren) |
| GET | `/lehrpersonen/{id}/einsatz` | 🔑 | Klassenlehrperson-Plätze, Fach-Zuteilungen, Stundenplan-Einträge einer Lehrperson |
| POST | `/personen/{id}/rollen/ausgetreten` | 🔑 ✏️ | Alle zuordenbaren Rollen durch die Rolle „Ausgetreten“ ersetzen |

### Rollen

| Methode | Endpunkt | Zugriff | Zweck |
|---|---|---|---|
| GET | `/rollen` | 🔑 | Alle Escola-Rollen mit ID, Name, Schulhaus; `?nur_neue=true` zeigt neu dazugekommene |
| GET | `/personen/{id}/rollen` | 🔑 | Zugewiesene Rollen einer Person (`?alle=true`: alle mit Häkchen-Status) |
| PATCH | `/personen/{id}/rollen` | 🔑 ✏️ | Einer Person eine oder mehrere Rollen zuweisen bzw. entziehen (nur freigegebene Rollen) |

### Fächer-Zuteilung (Lehrpersonen ↔ Klasse)

| Methode | Endpunkt | Zugriff | Zweck |
|---|---|---|---|
| GET | `/klassen/{id}/klassenlehrpersonen` | 🔑 | Klassenlehrpersonen A/B/C, aktuelles und kommendes Schuljahr (`?waehlbar=true`: alle wählbaren LP) |
| PUT | `/klassen/{id}/klassenlehrpersonen` | 🔑 ✏️ | Klassenlehrpersonen setzen (max. 3, aktuelles und/oder kommendes Schuljahr) |
| GET | `/klassen/{id}/lehrpersonen?schuljahr=0\|1` | 🔑 | Alle Lehrpersonen einer Klasse mit Fächern, Art und Rechten KLR/FP/SpM/Abs/Gesundheit |
| GET | `/arbeitsgruppen/{id}/lehrpersonen?schuljahr=0\|1` | 🔑 | Alle Lehrpersonen einer Arbeitsgruppe (Fachklasse) mit Fächern |
| GET | `/lehrpersonen/{id}/faecher?klasse_id=…` bzw. `?arbeitsgruppe_id=…` | 🔑 | Alle Fächer, welche die Lehrperson hat, und ihre Rechte |
| PATCH | `/lehrpersonen/{id}/faecher` | 🔑 ✏️ | Fächer zuteilen/entfernen, Rechte setzen oder Vorlage anwenden (`klassenlehrperson`, `fachlehrperson`, `sopae`); Klasse oder Arbeitsgruppe, `schuljahr` 0/1 |

### Dokumente

| Methode | Endpunkt | Zugriff | Zweck |
|---|---|---|---|
| GET | `/dokumente/struktur` | ⏳ | Ordnervorlage der Schüler:innen-Dokumente |
| GET | `/schueler/{id}/dokumente` | ⏳ | Ordner und Dateien einer Schülerin / eines Schülers |
| GET | `/schueler/{id}/dokumente/{datei_id}` | ⏳ | Einzelne Datei herunterladen |

### Dokumentation der API selbst

| Methode | Endpunkt | Zugriff | Zweck |
|---|---|---|---|
| GET | `/testseite` | 🔓 | Testseite: Fälle lesen → schreiben → lesen → rückgängig → lesen, mit Vergleich |
| GET | `/docs` | 🔓 | Interaktive Doku: alle Endpunkte mit Parametern direkt ausprobieren |
| GET | `/openapi.json` | 🔓 | Maschinenlesbare Beschreibung (OpenAPI) – z. B. für Code-Generatoren im anderen Projekt |

## Anmeldung

Benutzername, Passwort und 2FA-Code werden **nur an Escola weitergereicht** und nirgends
gespeichert oder geloggt. Die Escola-Session lebt nur im Arbeitsspeicher der API. Der Aufrufer
bekommt ein zufälliges Session-Token, das er bei jedem Aufruf als Header `X-Escola-Session` mitsendet.

### Loginseite

`http://127.0.0.1:8080/login` öffnet eine einfache Anmeldeseite:

1. Benutzername + Passwort
2. Bestätigungscode (Authentifizierungs-App oder SMS) – mit „Code erneut senden“,
   Methodenwahl und Alternative „in der Escola-App bestätigen“
3. Anzeige des Session-Tokens (kopieren) und Abmelden

Das Token liegt nur im `sessionStorage` des Browser-Tabs. Mit `?weiter=/testseite` geht es nach dem Login
im selben Tab weiter. Die Felder heissen `username`, `password`, `api-key`, `one-time-code` – Passwort-Manager
wie 1Password füllen sie aus (im Eintrag die URL `http://127.0.0.1:8080` ergänzen).

**Ablauf gegenüber Escola** (live bestätigt 15.11.2026, Details in `escola_api/auth.py`):
`POST login.php` mit Referer (sonst 403 „Referrer check failed“) → `GET escola/api/logged-in-person`
(2FA-Methoden) → `PATCH …/two-factor/method` → `POST …/two-factor/verification` → erst dann
`redirectUrl` (`admin.php?page_request=5&fromLogin=1`). Vor dem Code weder `admin.php` noch
`…/two-factor/login-infos` aufrufen – beides beendet die halbe Anmeldung.

**Protokoll:** Jeder Login-Schritt erscheint im Startfenster (Status, Cookie-Namen, Escola-Meldung) –
Passwort und Code nie, nur ihre Länge. Abgelehnte API-Keys werden mit Grund protokolliert.

### Endpunkte

| Endpunkt | Zweck |
|---|---|
| `POST /auth/login` `{benutzername, passwort, dauer_stunden?}` | Schritt 1 → `{status: "angemeldet" \| "2fa_erforderlich", session, methoden}` |
| `GET /auth/2fa/methoden` | verfügbare 2FA-Methoden |
| `POST /auth/2fa/methode` `{methode}` | Methode wählen (z. B. `totp`, `sms`) |
| `POST /auth/2fa/erneut` | Code erneut senden |
| `POST /auth/2fa` `{code}` | Schritt 2: Code bestätigen → `angemeldet` (bei falschem Code erneut versuchen) |
| `POST /auth/2fa/app` → `GET /auth/2fa/app/{token}` | Alternative: Bestätigung in der Escola-App anfordern und abfragen |
| `GET /auth/status` | `angemeldet`, `2fa_erforderlich` oder `abgelaufen` |
| `POST /auth/logout` | bei Escola abmelden, Session löschen |

```bash
# 1. Login
curl -s -X POST localhost:8080/auth/login -H 'Content-Type: application/json' \
     -d '{"benutzername":"…","passwort":"…"}'
# -> {"status":"2fa_erforderlich","session":"Xy…","methoden":[…]}

# 2. 2FA-Code
curl -s -X POST localhost:8080/auth/2fa -H 'X-Escola-Session: Xy…' -H 'Content-Type: application/json' -d '{"code":"123456"}'

# 3. Daten
curl -s localhost:8080/klassen -H 'X-Escola-Session: Xy…'

# 4. Logout
curl -s -X POST localhost:8080/auth/logout -H 'X-Escola-Session: Xy…'
```

- Die API hält angemeldete Sessions mit dem Escola-Keep-alive aktiv (alle 2 min) und verwirft
  Sessions nach 8 h ohne Aufruf (`ESCOLA_SESSION_LEERLAUF_SEK`).
- Mehrere Sessions sind voneinander getrennt (eigener Cookie-Speicher je Session).
- Konten, bei denen Escola zuerst die 2FA-Einrichtung oder eine Passwortänderung verlangt,
  bekommen `409` mit Hinweis – das einmal im Browser erledigen.
- Fallback ohne Login: `ESCOLA_COOKIE` mit dem Cookie einer Browser-Sitzung setzen; dann werden
  Aufrufe ohne `X-Escola-Session` darüber abgewickelt.

## Stundenplan & Stammdaten (lesend)

| Endpunkt | Inhalt | Filter |
|---|---|---|
| `GET /klassen` | Klassen + Arbeitsgruppen (ID, Name, Bezeichnung, Klassenlehrperson, Schulhaus) | `schulhaus`, `typ` |
| `GET /faecher` | Fächer (ID, Kürzel, voller Name) | – |
| `GET /lehrpersonen` | Lehrpersonen (ID, Name, Kürzel, Schulhäuser) | `schulhaus` |
| `GET /raeume` | Räume je Schulhaus (ID, Kürzel, Geschoss, Nummer, Bezeichnung, Trakt) | `schulhaus` |
| `GET /tage` | Wochentage (Code A–E) | – |
| `GET /lektionen` | Lektionen **je Schulhaus** (Escola-ID, Nr, von, bis) | `schulhaus` |
| `GET /eintraege` | alle Stundenplan-Einträge, eine Zeile pro Eintrag | `klasse_id`, `schulhaus`, `genau` |
| `GET /export` | alles in einem JSON | – |

## Schüler:innen & Personen

| Endpunkt | Inhalt |
|---|---|
| `GET /schueler` | alle Schüler:innen mit Klasse (Filter `klasse_id`, `schulhaus`, `schuljahr` 0/1) |
| `GET /schueler?ohne_klasse=true` | Schüler:innen ohne Klasse und zukünftige Schüler:innen |
| `POST /schueler` | Schüler:in anlegen – mit `klasse_id` oder ohne Klasse zum späteren Zuordnen |
| `POST /schueler/{id}/klasse` | Schüler:in einer Klasse zuordnen (Transfer ab Stichtag) |
| `GET /schueler/{id}` | alle Felder einer Schülerin / eines Schülers |
| `PATCH /schueler/{id}` | Felder ändern |
| `GET /personen/rollen` | Escola-Rollen live (inkl. eigener Rollen wie „_neu“) |
| `GET /personen?rolle=…` | Personen einer Rolle (Standard: alle aktiven) |
| `POST /personen` | Person anlegen (`rolle`, z. B. `lehrperson`, `gruppe_4` = Schulverwaltung) |
| `GET /personen/{id}` | alle Felder einer Person |
| `PATCH /personen/{id}` | Felder ändern |

### Anlegen und später einer Klasse zuordnen

```bash
# 1. Schüler:in ohne Klasse vorbereiten
curl -X POST localhost:8080/schueler -H 'X-Escola-Session: …' -H 'X-API-Key: …' -H 'Content-Type: application/json' \
     -d '{"nachname":"Muster","vorname":"Lea","geschlecht":"w","schulhaus":"Hinterbirch",
          "felder":{"geburtstag":"01.01.2013","nationality_id":"Schweiz"}}'
# -> 201 {"angelegt": true, "id": 653, ...}

# 2. Später zuordnen
curl -X POST localhost:8080/schueler/653/klasse -H 'X-Escola-Session: …' -H 'X-API-Key: …' -H 'Content-Type: application/json' \
     -d '{"klasse_id": 92, "stichtag": "2027-08-16", "schuljahr": 1}'
```
- `geschlecht`: `w`, `m` oder `d`. `zukuenftig: true` legt die Person als „zukünftige:r Schüler:in“ an.
- Vor dem Anlegen fragt die API Escola nach möglichen Duplikaten. Gibt es welche, kommt `409` mit der
  Liste (ID, Name, Rollen). Mit `trotz_duplikat: true` wird trotzdem angelegt.
- `felder` setzt direkt nach dem Anlegen weitere Felder (gleiche Regeln wie `PATCH`).
- Klassenzuordnung: `schuljahr` 0 = aktuelles, 1 = kommendes; `stichtag` JJJJ-MM-TT (Standard: heute),
  nur fürs aktuelle Schuljahr.

### Klasseneinteilung, Umteilung, Entfernen

| Fall | Aufruf |
|---|---|
| Einteilung (ohne Klasse → Klasse) | `POST /schueler/{id}/klasse` `{"klasse_id": 92, "stichtag": "2026-11-14"}` |
| Umteilung (Klasse A → Klasse B) | gleicher Aufruf mit der neuen Klasse |
| Einteilung fürs kommende Schuljahr | `POST /schueler/{id}/klasse` `{"klasse_id": 92, "schuljahr": 1}` |
| Aus der Klasse nehmen | `DELETE /schueler/{id}/klasse` (`?schuljahr=1` fürs kommende SJ, `?klasse_id=` optional) |
| Welche Klassen sind wählbar? | `GET /schueler/{id}/klasse/optionen?schuljahr=0\|1` |

- Fürs **kommende Schuljahr** behalten die Klassen ihre ID, haben aber den künftigen Namen:
  92 (heute H_A1a) = „zukünftige H_A2a“. Abschliessende 3. Klassen sind dort nicht wählbar.
- Die API prüft die Klasse gegen die Auswahl, die Escola für diese Person anbietet. Die aktuelle Klasse
  selbst ist z. B. nicht wählbar.
- Nach dem Entfernen bleibt die Person bestehen und steht unter `GET /schueler?ohne_klasse=true`.
- Rückgängig machen (Escola „Vorgang widerrufen“) bietet die API nicht an – stattdessen erneut zuordnen.

### Neue Mitarbeitende

Escola legt eine Person immer mit einer **Rolle** an (Lehrperson, Schulverwaltung, Hausdienst …).
Rollen werden in Escola unter **Personen → Rollen-Konfiguration** verwaltet. Ihre technische Kennung ist
`lehrperson`, `schulleitung`, `admin` … bzw. `gruppe_<n>` für weitere und selbst angelegte Rollen.

Für Mitarbeitende, deren Rolle noch offen ist:
1. In der Rollen-Konfiguration eine Rolle „_neu“ (oder „_nicht zugeordnet“) anlegen.
2. Ihre Kennung über `GET /personen/rollen` nachschlagen, z. B. `{"rolle": "gruppe_14", "name": "_neu", "typ": "rolle"}`.
3. Anlegen mit `POST /personen` und `"rolle": "gruppe_14"`.
4. Die endgültige Rolle danach in Escola im Reiter „Rollen“ der Person setzen (über die API nicht schreibbar).

`GET /personen/rollen` liefert zusätzlich die Ansichten der Personenverwaltung (`typ: "ansicht"`, z. B.
„alle aktiven Personen“, „Schüler:innen (ohne Klasse)“). Das sind Filter, keine Rollen – damit kann
gelesen, aber keine Person angelegt werden. Der frühere Name `/personen/kategorien` bzw. das Feld
`kategorie` funktionieren weiterhin.

### Austritt erfassen

```bash
curl -X POST localhost:8080/schueler/652/austritt -H 'X-Escola-Session: …' -H 'X-API-Key: …' \
     -H 'Content-Type: application/json' \
     -d '{"datum": "2027-07-09", "wegzugsdatum": "2027-07-31", "wegzugsgemeinde": "Winterthur"}'
```
- Setzt das Austrittsdatum (und optional Wegzugsdatum/-gemeinde). Escola deaktiviert die Person danach
  selbst. Beim Speichern passiert das nicht sofort – im Test vom 14.11.2026 auch nicht bei Austritt am
  selben Tag. Mit `"sofort_deaktivieren": true` deaktiviert die API die Person zusätzlich sofort.
- Die Austritts- und Wegzugsfelder sind nur über diesen Endpunkt schreibbar, nicht über `PATCH /schueler/{id}`.

### Arbeitsgruppen

- Einteilen und Entfernen ändern nur die angegebene Arbeitsgruppe; weitere Zuteilungen bleiben bestehen.
- Funktioniert auch für Schüler:innen ohne Klasse. `schuljahr: 1` für das kommende Schuljahr.

### Aktivieren / Deaktivieren

`POST /personen/{id}/deaktivieren` bzw. `…/aktivieren` führt Escolas Aktion „Personen deaktivieren“ /
„Personen aktivieren“ aus, inklusive der Escola-Rückfrage („JA, durchführen“). Antwort z. B.
`{"id": 649, "aktiv": false, "meldung": "Eine Person wurde erfolgreich deaktiviert."}`.
Die API löst über diesen Escola-Aufruf ausschliesslich Aktivieren (2), Deaktivieren (1) und „SuS von der
Klasse entfernen“ (1008/1009) aus – „Personen definitiv löschen“ und alle anderen Sammelaktionen sind
nicht erreichbar.

Deaktivierte Personen listet `GET /personen?rolle=allInactive` (die API blendet sie dafür kurz ein, wie
der Escola-Schalter „inaktive Personen anzeigen“). Deaktivierte Schüler:innen erscheinen nicht mehr in
ihrer Klassenliste, nach dem Aktivieren wieder.

### Rollen lesen und zuordnen

```bash
curl localhost:8080/rollen -H 'X-Escola-Session: …'
# [{"id": 13, "name": "Lehrpersonen (Hinterbirch)", "typ": "lehrperson", "schulhaus": "Hinterbirch",
#   "personengruppe": false, "neu": false, "zuordenbar": true}, …]

curl -X PATCH localhost:8080/personen/649/rollen -H 'X-Escola-Session: …' -H 'X-API-Key: …' \
     -H 'Content-Type: application/json' -d '{"hinzufuegen": [25, 41], "entfernen": [13]}'
```
- **Zuordenbar** sind nur:
  - Lehrpersonen (Hinterbirch 13, Mettmenriet 16) und Schulleitung (Hinterbirch 14, Mettmenriet 17)
  - alle eigenen Rollen, also die als Personengruppe angelegten (`personengruppe: true`, z. B. Schulverwaltung, Hausdienst, „_neu“)
- Alle anderen eingebauten Rollen (Administrator:innen, Superadministrator:innen, Ärzt:innen,
  Schüler:innen, Eltern/Bezugspersonen …) sind über die API **nur lesbar**. Schüler:innen und Eltern
  setzt Escola ohnehin selbst (über Klasse bzw. Bezugspersonen).
- Alles oder nichts: Ist eine Rolle nicht zuordenbar oder unbekannt, wird nichts geändert (`422`).
  `?probelauf=true` zeigt nur, was sich ändern würde. Die Antwort enthält die Rollen nach der Änderung.
- `neu: true` kennzeichnet Rollen, die nach dem 14.11.2026 angelegt wurden.
- Rollen **anlegen** unterstützt die API nicht. Eigene Rollen entstehen in Escola unter
  Personen → Personengruppen → „Neue Personengruppe erstellen“.

### Klassenlehrpersonen einer Klasse zuordnen

Escola: Einstellungen → Klassen → „Ändern“. Pro Klasse gibt es die Plätze A, B und C, jeweils fürs
aktuelle und fürs kommende Schuljahr.

```bash
curl localhost:8080/klassen/120/klassenlehrpersonen -H 'X-Escola-Session: …'
# {"klasse_id": 120, "name": "TEST_A1a", "aktuell": [],
#  "kommend": [{"slot": "A", "id": 576, "name": "Obereck Ursina"}], "wird_archiviert": false}

curl -X PUT localhost:8080/klassen/120/klassenlehrpersonen -H 'X-Escola-Session: …' -H 'X-API-Key: …' \
     -H 'Content-Type: application/json' -d '{"aktuell": [649, 135]}'
```
- Die Liste ist die Soll-Belegung von A, B, C in dieser Reihenfolge. `[]` = keine Klassenlehrperson,
  weggelassen = unverändert. `?probelauf=true` zeigt nur, was sich ändern würde.
- Wer Klassenlehrperson ist, bekommt von Escola **automatisch die KLR-Rechte** der Klasse (und damit SpM, Abs,
  Gesundheit). Fächer bekommt die Person dadurch nicht. Diese teilt man wie unten zu, z. B. mit `faecher_hinzu`.
- Escola speichert in diesem Formular **alle Klassen-Einstellungen auf einmal** (Name, Standort, Jahrgang,
  Bista …). Die API liest das Formular, ändert nur die Klassenlehrpersonen, schickt alles andere unverändert
  zurück und prüft danach, dass sich sonst nichts verändert hat (sonst `409`).
- Klassen, die beim Schuljahreswechsel archiviert werden, haben kein kommendes Schuljahr.
- Escola-Eigenheit: Im Formular sind bei jeder Auswahl „(keine)“ **und** die eingetragene Person als
  gewählt markiert. Massgebend ist die Person (so verhält sich auch der Browser).

### Mitarbeitende einstellen (WF-01)

```bash
curl -X POST 'localhost:8080/mitarbeitende?probelauf=true' -H 'X-Escola-Session: …' -H 'X-API-Key: …' \
     -H 'Content-Type: application/json' -d '{
  "nachname": "Muster", "vorname": "Max", "geschlecht": "m", "schulhaus": "Hinterbirch",
  "rolle": "gruppe_14", "rollen_ids": [13], "ahv": "756.1234.5678.97",
  "felder": {"geburtstag": "01.02.1990", "natel": "079 000 00 00", "eintritt": "01.08.2027"}}'
```
- **Zuerst prüfen, dann anlegen:** AHV-Format und Prüfziffer, AHV-Nummer und Schulmail noch nicht vergeben,
  Rollen zuordenbar. Ist etwas vergeben, kommt `409` mit den betroffenen Personen (ID, Name, aktiv) und es wird
  **nichts** angelegt – der Fall muss von Hand gelöst werden (z. B. ehemalige:r Mitarbeiter:in reaktivieren).
- Danach: anlegen → Rollen → Felder → AHV → Schulmail. Scheitert ein späterer Schritt, ist die Person schon
  angelegt; die Antwort zeigt pro Schritt `ok`/`fehler` und `vollstaendig: false`.
- **Schulmail** `vorname.nachname@sekbuelach.ch`: ä/ö/ü → ae/oe/ue, ß → ss, Akzente weg (é → e, ř → r),
  bei Doppelnamen nur der erste Teil (Anna-Lena Müller-Widli → `anna.mueller`). Namenszusätze gehören zum
  Namen (Laura von Arx → `laura.vonarx`). Gesetzt wird das Feld `email` im Reiter „Geschäft“ – bei Mitarbeitenden
  zugleich die Haupt-E-Mail in Escola (ein separates Feld „Haupt-E-Mail“ gibt es dort nicht).
- Das **Postfach** (M365) legt Escola nicht an – das übernimmt später IDA bzw. CONNECT.
- **AHV-Nummer:** wie im Escola-Formular geprüft (13 Ziffern, 756…, EAN-13-Prüfziffer), gespeichert als
  `756.xxxx.xxxx.xx`. Sie ist Schlüssel in anderen Anwendungen und darf nur einer Person gehören. Eine vorhandene
  andere Nummer wird nur mit `ueberschreiben: true` ersetzt. Über `PATCH /personen/{id}` bleibt das Feld gesperrt.
- **Suche nach AHV/E-Mail:** Escola hat dafür keinen Aufruf. Die API liest dazu einmal alle aktiven und inaktiven
  Personen (Reiter Personalien + Geschäft) und hält das Ergebnis `ESCOLA_CACHE_SEKUNDEN` lang. Der erste Aufruf
  dauert entsprechend; nicht lesbare Personen stehen in `nicht_gelesen`.

### Austritt Mitarbeitende (WF-02/04)

1. `GET /lehrpersonen/{id}/einsatz` – wo ist die Person Klassenlehrperson, welche Fächer, welche Lektionen?
2. `POST /personen/{id}/austritt` `{"datum": "2027-07-31"}` – Escola deaktiviert die Person am Austrittsdatum selbst.
   `{"datum": ""}` nimmt den Austritt zurück.
3. Am Austrittstag (ausgelöst von IDA/CONNECT):
   - `POST /lehrpersonen/{id}/ersetzen` `{"neu_id": …}` – Nachfolge übernimmt Fächer, Klassenlehrperson-Plätze und Lektionen,
     die bisherige Lehrperson wird ausgetragen (oder einzeln über Fächer-Zuteilung und Klassenlehrpersonen).
   - `POST /personen/{id}/rollen/ausgetreten` – alle zuordenbaren Rollen werden durch **„Ausgetreten“** ersetzt (F-03).
     Fehlt die Rolle in Escola, kommt `409` – die Schule legt sie unter Personen → Personengruppen an.
     Eingebaute, nicht zuordenbare Rollen (z. B. Admin) bleiben und stehen in `nicht_entfernt`.
   - Sofortiger Austritt: `POST /personen/{id}/austritt` mit `"rollen_ausgetreten": true, "sofort_deaktivieren": true`.

### Stundenplan schreiben

```bash
# Zelle lesen: Einträge, wählbare Fächer/Räume/Lehrpersonen (Tag A = Montag, Lektion = Escola-ID je Schulhaus)
curl localhost:8080/klassen/120/stundenplan/A/2 -H 'X-Escola-Session: …'

# Eintrag anlegen (auch zusätzlich in einer belegten Zelle)
curl -X POST localhost:8080/klassen/120/stundenplan/B/3 … -d '{"fach_id": 12, "raum_ids": [9]}'

# Räume/Lehrpersonen ändern, löschen
curl -X PATCH localhost:8080/klassen/120/stundenplan/B/3/36 … -d '{"raum_ids": [9, 10], "lehrperson_ids": [649]}'
curl -X DELETE localhost:8080/klassen/120/stundenplan/B/3/36 …

# Nachfolge
curl -X POST 'localhost:8080/lehrpersonen/135/ersetzen?probelauf=true' … -d '{"neu_id": 700}'
```
- **Wer unterrichtet, ergibt sich aus der Fächer-Zuteilung** (live geprüft 15.11.2026): Hat nur eine Lehrperson das Fach
  in der Klasse, trägt Escola sie automatisch ein (`schaltbar: false`). Haben mehrere das Fach, gibt es pro Eintrag
  Schalter (`schaltbar: true`), die `lehrperson_ids` setzt. Eine Lehrperson ohne das Fach in der Klasse → `400`
  (zuerst Fächer-Zuteilung).
- Fach muss der Klasse zugeteilt sein; Räume nur aus dem eigenen Schulhaus; höchstens 3 Räume.
- Gilt fürs aktuelle Schuljahr (Escola-Einträge haben kein Datum). Änderungen ab Stichtag löst IDA/CONNECT aus.
- „Ganzen Stundenplan löschen“ (Escola `application_class.php mode=1`) bietet die API bewusst **nicht** an.
- `lehrperson_ersetzen`: Nachfolge bekommt dieselben Fächer (+ FP/SpM, ausser bei Klassenlehrpersonen), denselben
  Klassenlehrperson-Platz (A/B/C), in Einträgen mit Schaltern wird sie eingeschaltet; danach wird die bisherige
  Lehrperson aus den Fächern genommen. Antwort mit Schritten und `vollstaendig`.

### Eltern / Bezugspersonen (WF-07/09/10)

```bash
curl localhost:8080/schueler/650/bezugspersonen -H 'X-Escola-Session: …'
# [{"beziehung_id": 2, "person_id": 649, "name": "TEST TEST", "funktion": "Mutter", "sorgerecht": "sorgeberechtigt",
#   "abholberechtigt": true, "gleiche_adresse": true, "aktiv": true, "rollen": "Eltern/Bezugspersonen"}]

# Neue Mutter (Escola-Duplikatprüfung: gibt es die Person schon -> 409 mit Liste -> mit person_id verknüpfen)
curl -X POST localhost:8080/schueler/650/bezugspersonen … -d '{"nachname": "Muster", "vorname": "Anna", "geschlecht": "w",
     "sorgerecht": "sorgeberechtigt", "felder": {"natel": "079 000 00 00", "email_privat": "anna@example.com"}}'
# Vater schon bekannt (Geschwister): verknüpfen
curl -X POST localhost:8080/schueler/650/bezugspersonen … -d '{"person_id": 777, "sorgerecht": "informationsberechtigt"}'
```
- `sorgerecht`: `sorgeberechtigt` (Escola „erziehungsberechtigt“ = gesetzliche Vertretung), `informationsberechtigt`
  (= Informationspflicht), `keine`.
- `funktion`: Mutter, Vater, Vormund, Pflegemutter … oder ID; Standard nach Geschlecht (w = Mutter, sonst Vater).
- Bestehende Bezugspersonen werden **verknüpft, nicht neu angelegt** (F-06). Die Escola-Duplikatprüfung prüft Name/Vorname.
- Escola gibt verknüpften Personen automatisch die Rolle „Eltern/Bezugspersonen“ und nimmt sie beim Entfernen wieder weg.
- Austritt (F-07): `POST /schueler/{id}/eltern/deaktivieren` deaktiviert Bezugspersonen ohne weitere aktive Kinder
  und ohne andere Rolle (Lehrpersonen als Eltern bleiben aktiv). `?probelauf=true` zeigt nur den Plan.
- Umzug (F-08): `gleiche_adresse: true` heisst, das Kind hat die Adresse der Bezugsperson → Adresse dort mit
  `PATCH /personen/{bezugsperson_id}` ändern, sonst bei der Schülerin / dem Schüler. Ab Datum: IDA/CONNECT löst aus.

### Fächer einer Lehrperson zuordnen

Escola: Klassenverwaltung → Lehrpersonen. Wer in einer Klasse ein Fach hat, ist im Stundenplan dieser
Klasse als Lehrperson wählbar (live geprüft).

| Spalte | Escola-Bedeutung | gilt pro | API |
|---|---|---|---|
| `klr` | Klassenlehrpersonen-Rechte für die Klasse (bis 3 pro Klasse) | Lehrperson + Klasse | lesen / setzen |
| `fp` | Förderplanung der SuS lesen und schreiben | Lehrperson + Klasse | lesen / setzen |
| `spm` | Sonderpädagogische Massnahmen | Lehrperson + Klasse | lesen / setzen (bei KLR automatisch) |
| `abs` | Klassenlehrpersonen-Rechte in den Absenzen | Lehrperson + Klasse | lesen / nur über KLR |
| `gesundheit` | Gesundheitsdaten der SuS | Fach-Zuteilung | nur lesen (bei KLR automatisch) |

Regeln (wie mit der Schule vereinbart):
- **KLR** setzt Escola SpM, Abs und Gesundheit automatisch mit (gesperrt). Nimmt man KLR weg, stellt
  Escola den vorherigen Zustand wieder her. In der Antwort steht das unter `automatisch`.
- **Abs** gibt es in Escola nur für die ganze Klasse, nicht pro Fach. Für Nicht-Klassenlehrpersonen setzt die
  API Abs darum nicht (`400`), damit sie nur die Absenzen der eigenen Fächer bzw. Lektionen sehen. Ein von Hand gesetztes Abs
  bei einer Fachlehrperson nimmt die API bei der nächsten Änderung zurück.
- **Gesundheit** bleibt automatisch bei den Klassenlehrpersonen; die API setzt sie nie.
- `art` in der Antwort: `Klassenlehrperson` (KLR), `SoPä` (SpM ohne KLR), sonst `Fachlehrperson`.
  `klassenlehrperson: true` heisst: Die Person ist auf Platz A/B/C eingetragen. Dann ist KLR gesperrt und lässt sich
  nur über `PUT /klassen/{id}/klassenlehrpersonen` entfernen.
- Lehrpersonen-Kategorien (z. B. „Sportlehrer:Innen“) werden aktuell nicht unterstützt.

| Vorlage | Wirkung in der Klasse |
|---|---|
| `klassenlehrperson` | zusätzliche KLR-Rechte, ohne Klassenlehrperson-Platz (SpM, Abs, Gesundheit automatisch); Fächer optional über `faecher`. Für die echte Klassenlehrperson `PUT /klassen/{id}/klassenlehrpersonen` verwenden |
| `fachlehrperson` | nur die Fächer aus `faecher`, alle Rechte aus |
| `sopae` | alle Fächer der Klasse, SpM und FP an, KLR und Abs aus |

```bash
# Fachlehrperson: Englisch und WAH in TEST_A1a (120)
curl -X PATCH localhost:8080/lehrpersonen/649/faecher -H 'X-Escola-Session: …' -H 'X-API-Key: …' \
     -H 'Content-Type: application/json' -d '{"klasse_id": 120, "vorlage": "fachlehrperson", "faecher": [15, 25]}'

# SoPä: alle Fächer + SpM + FP (vorher ansehen mit ?probelauf=true)
curl -X PATCH 'localhost:8080/lehrpersonen/649/faecher?probelauf=true' … -d '{"klasse_id": 120, "vorlage": "sopae"}'

# Einzeln: Fach weg, FP an
curl -X PATCH localhost:8080/lehrpersonen/649/faecher … -d '{"klasse_id": 120, "faecher_weg": [25], "rechte": {"fp": true}}'
```

- `faecher` ist die Soll-Liste (ersetzt die Zuteilung in dieser Klasse), `faecher_hinzu`/`faecher_weg` ändern einzeln.
- **Arbeitsgruppen (Fachklassen, F-04):** statt `klasse_id` `arbeitsgruppe_id` angeben. Nur Fächer – Arbeitsgruppen haben
  keine KLR/FP/SpM; Abs setzt die API dort nicht. Escola führt für Arbeitsgruppen eigene Zuteilungsnummern.
- **Kommendes Schuljahr:** `"schuljahr": 1` (Fächer; Rechte erst nach dem Schuljahreswechsel setzen).
- Rechte gibt es nur, solange die Lehrperson mindestens ein Fach in der Klasse hat. Entfernt man alle
  Fächer, ist die Lehrperson nicht mehr in der Klasse.
- Die Antwort enthält den Plan (`faecher_hinzu`, `faecher_weg`, `rechte`) und den Zustand `nachher`;
  übernimmt Escola etwas nicht, kommt `409`.

### Dokumente (Platzhalter)

`GET /schueler/{id}/dokumente`, `GET /schueler/{id}/dokumente/{datei_id}` und `GET /dokumente/struktur`
sind vorbereitet, antworten aber mit `501 – noch nicht aktiviert`, bis die Escola-Berechtigung
„Schüler:innen-Dokumente“ freigeschaltet und der Zugriff geprüft ist.

### Lesen

`GET /schueler/650` liefert
```json
{
  "id": 650,
  "reiter": ["aktionen", "name", "personalien", "privat", "..."],
  "abschnitte": {
    "personalien": {"titel": "Personalien", "felder": [
      {"name": "geburtstag", "label": "Geburtsdatum", "typ": "datum", "wert": "01.01.2013", "schreibbar": true},
      {"name": "nationality_id", "label": "Nationalität", "typ": "auswahl", "wert": "2", "text": "Schweiz", "schreibbar": true}
    ]}
  },
  "felder": {"geburtstag": "01.01.2013", "nationality_id": "Schweiz", "natel": "079 000 00 01", "...": "..."}
}
```
- `?optionen=true` liefert bei Auswahlfeldern alle möglichen Werte mit.
- `?abschnitte=name,personalien` begrenzt auf einzelne Reiter.
- `?format=csv` liefert eine Tabelle (Abschnitt, Feld, Label, Typ, Wert).
- Feldtypen: `text`, `zahl`, `mehrzeilig`, `auswahl`, `auswahlknopf`, `checkbox`, `datum`.
- Alle Felder einer Schülerin sind in `escola-schueler-felder.md` (ESCOLA-Projekt) beschrieben.

### Schreiben

```bash
curl -X PATCH localhost:8080/schueler/650 -H 'X-Escola-Session: …' -H 'X-API-Key: …' \
     -H 'Content-Type: application/json' \
     -d '{"felder": {"natel": "079 000 00 01", "geburtstag": "01.01.2013", "nationality_id": "Schweiz", "bista_plan_stat": "10"}}'
```
- Schlüssel sind die internen Feldnamen aus `GET …/{id}` (`name`).
- Datum: `TT.MM.JJJJ` oder `JJJJ-MM-TT`, leer = löschen.
- Auswahl / Auswahlknopf: Wert oder angezeigter Text (`"Schweiz"`, `"2"`).
- Checkbox: `true` / `false`.
- **Alles oder nichts:** Ist ein Feld unbekannt, gesperrt oder ungültig, wird nichts gespeichert (`422`
  mit Fehlerliste).
- `?probelauf=true` zeigt nur, was geändert würde.
- Die Antwort enthält pro Feld `alt`, `neu` und den nach dem Speichern neu gelesenen Wert `jetzt`.

**Sicherheit beim Schreiben**
- Schreiben ist standardmässig **aus** (`ESCOLA_SCHREIBEN=1` zum Aktivieren) und verlangt dann einen
  gesetzten `ESCOLA_API_KEY`.
- Über `PATCH` nie schreibbar: AHV-Nummer (nur über `PUT /personen/{id}/ahv`), IBAN/BIC, Austritts- und Wegzugsdatum (nur über `…/austritt`), Reiter „Login“
  (Benutzername, Passwort, Login-Einstellungen). Rollen und Bezugspersonen laufen über eigene Endpunkte
  (`/personen/{id}/rollen`, `/schueler/{id}/bezugspersonen`).
- AHV-Nummer, IBAN und BIC werden beim Lesen nur als `***` ausgegeben (`ESCOLA_SENSIBEL_ZEIGEN=1` für Klartext).
- Der Reiter „Gesundheit & Ernährung“ (Krankenkasse, Allergien, Medikamente …) ist nur mit
  `ESCOLA_GESUNDHEIT=1` erreichbar.

## Besonderheiten Escola

- **Lektionen:** Hinterbirch (IDs 2–12) und Mettmenriet (IDs 24–34) haben eigene Lektions-IDs und
  Nachmittagszeiten → immer `schulhaus` + `lektion_id` verwenden.
- **Räume / Ressourcen** kommen aus dem Escola-Modul **Ressourcen** (`admin.php?page_request=160`):
  162 Ressourcen in 8 Kategorien (Stand 14.11.2026: Hinterbirch 96, Mettmenriet 66). Die IDs sind dieselben
  wie die Raum-IDs im Stundenplan (z. B. 9 = A101). `/raeume` liefert die Kategorien vom Typ „Räume“,
  `/ressourcen` alles inkl. Zeitprofil und „reservierbar“.
- **Zeiteinteilung:** Das Modul Ressourcen hat eigene Zeitprofile („HIBI – Lektionen“, „METTMI – Lektionen“)
  mit eigenen IDs. Für den Stundenplan gelten die Lektions-IDs aus `/lektionen`.
- **Fächer** zeigt Escola nur, wenn sie der Klasse zugeteilt sind.
- **Kürzel sind nicht eindeutig** (Raum A105, LP EgDo/PfTi) → immer IDs verwenden.
- **Session-Zustand:** Escola merkt sich in der Sitzung die „aktive Klasse“ und die „aktive Person“.
  Die API arbeitet pro Session strikt nacheinander. Wer mit derselben Escola-Sitzung gleichzeitig im
  Browser arbeitet, sieht dort u. U. andere Klassen/Personen.
- **Personenfelder** haben verschlüsselte, pro Sitzung neue Feldschlüssel. Die API liest vor jedem
  Speichern den Reiter neu und verwendet nach aussen nur die stabilen internen Feldnamen.
- **Kommendes Schuljahr ist Sitzungszustand:** Die Fächer-Matrix mit `school_year=1` stellt die ganze Escola-Sitzung aufs
  kommende Schuljahr um – auch die Stundenplan-Anzeige. Die API stellt danach immer auf das aktuelle Schuljahr zurück.
- **Fach zuteilen** wirkt auf die zuletzt mit „Fächer anzeigen“ geöffnete Lehrperson; die API öffnet sie vor jedem Zuteilen.
- **Personen-Sitzung:** Nach anderen Modulen meldet Escola bei Personen gelegentlich „Bitte laden Sie die Seite neu“.
  Die API öffnet dann die Personenverwaltung neu und wiederholt den Aufruf einmal.
- **Rollen-Schalter** zeigt Escola nur im Bearbeitungsmodus; die API schaltet ihn dafür kurz ein.
- Personenfelder sind nur im **Bearbeitungsmodus** sichtbar. Die API schaltet ihn bei Bedarf kurz ein und
  stellt den vorherigen Zustand wieder her.

## Installation & Start

Am einfachsten mit `start-escola.bat` (Windows) bzw. `start-escola.command` (macOS/Linux) im
Repo-Hauptordner, siehe Haupt-README. Von Hand:

```bash
python -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env    # Werte eintragen
set -a && source .env && set +a                         # Windows: Variablen manuell setzen
uvicorn escola_api.app:app --host 127.0.0.1 --port 8080
```

Dann `http://127.0.0.1:8080/login` öffnen oder direkt `/docs` (interaktive Doku).

`start_lokal.py` (von den Startdateien aufgerufen) legt beim ersten Start `.env` mit API-Key an, lädt `.env`
selbst, zeigt den geladenen Key maskiert an und öffnet die Anmeldung. Zusätzliche Variablen:
`ESCOLA_PORT` (Standard 8080), `ESCOLA_LOG` (`INFO` oder `DEBUG`).

Die API verarbeitet Personendaten von Schüler:innen und Mitarbeitenden. Nur lokal bzw. im internen
Netz betreiben, `ESCOLA_API_KEY` setzen und für Produktivbetrieb hinter HTTPS stellen.

## Tests

```bash
pytest -q
```

Die Tests laufen ohne Netzwerk gegen echte, gekürzte Escola-Antworten (`tests/fixtures/`) und einen
nachgebauten Escola-Login. Sie prüfen u. a., dass beim Lesen nichts geschrieben wird, dass gesperrte
Felder abgewiesen werden und dass das Passwort nirgends gespeichert wird.

## Verwendete Escola-Aufrufe

| Zweck | Aufruf |
|---|---|
| Login | `GET escola/login`, `POST login.php` (multipart `username`, `password`, Header `Referer`) |
| 2FA | `GET escola/api/logged-in-person` (Methoden), `PATCH escola/api/login/two-factor/method`, `POST …/verification` `{code}`, `POST …/resend`, `POST …/request` + `GET …/state` (Escola-App); danach `redirectUrl` |
| Logout / Keep-alive | `GET admin.php?action=logout&newLogout=true` / `GET escola/api/session/keep-alive` |
| Klassenliste | `GET admin.php?page_request=6` → `#unifiedClassOrWorkgroupChooser` |
| Stundenplan | `GET admin.php?page_request=6&klassen_id=<ID>`, `POST inc/ajax/timetable/application_class.php` `mode=0` |
| Zelle ansehen | `POST inc/ajax/timetable/ajax_functions_timetable.php` `type=1` / `type=3` |
| Personenliste | `POST inc/ajax/persons/show_persons_of_group.php` `personCategory=…&schoolclassId[=<Klasse>]&workgroupId&schoolUnitId=1\|2&schoolYear=0&searchMode=false` |
| Person / Reiter | `POST inc/ajax/persons/show_reiter.php` `active_person=<id>`, `POST …/show_person_details.php` `active_section=<reiter>` |
| Bearbeitungsmodus | `POST inc/ajax/persons/ajax_functions_persons.php` `type=1&edit_mode=0\|1` |
| Feld speichern | `POST …/ajax_functions_persons.php` `type=2` (Text/Auswahl/Knopf) bzw. `type=7` (Datum) |
| Person anlegen | `POST rpc/collections/CaptureNewPersonAdmin/checkForDuplicatePersonsRpc.php` + `…/captureNewPersonRpc.php` (JSON) |
| Klasse zuordnen | `POST inc/ajax/persons/personManagement.php` `mode=13` (Formular), dann `mode=14&klassen_id_transfer&transferDate&transferSchoolyear&activePersonId` |
| Rollen lesen | `POST rpc/collections/RoleAssignmentConfigurationAdmin/getAllPlainRoles.php` (JSON) |
| Deaktivieren / Aktivieren | `POST inc/ajax/persons/personManagement.php` `mode=17&action=1\|2&element_string=:<id>:` (Rückfrage), dann `mode=36` |
| Aus Klasse entfernen | `mode=17&action=1008\|1009&element_string=:<id>:&schoolclassId&schoolYear` (Rückfrage), dann `mode=29&isInNextSchoolyear&schoolclassId&schoolYear` |
| Inaktive anzeigen | `POST inc/ajax/ajax_functions.php` `type=85` (Umschalter) |
| Ressourcen | `POST inc/ajax/raumverwaltung/rooms.php` (Kategorien `tr.head_2`, Ressourcen `li#item_<id>`) |
| Zeiteinteilung | `POST inc/ajax/raumverwaltung/stundeneinteilung.php` (`select#profileChooser`; Profil wechseln `mode=0&selectedProfile=<id>`) |
| Arbeitsgruppen | Liste `POST inc/ajax/workgroups/ajax_functions_workgroups.php` `type=7`; Zuteilung lesen `POST …/assignments.php` `mode=2`; einteilen `mode=3&workgroups[]&allDisplayedWorkgroups[]`; entfernen `…/ajax_functions_workgroups.php` `type=9` |
| Rollen einer Person | Reiter `active_section=rollen` im Bearbeitungsmodus (Häkchen `role_<id>`); ändern: `POST …/ajax_functions_persons.php` `type=24&role=<id>&new_value=1\|0` |
| Fächer-Matrix einer Klasse | `GET admin.php?page_request=6&klassen_id=<ID>`, dann `POST inc/ajax/lehrpersonen/lehrpersonen_faecher.php` `mode=0` |
| Fächer einer Lehrperson | `POST inc/ajax/lehrpersonen/zeige_faecher.php` `type=1&lehrperson&fach_id=0&class_id&workgroup_id=0&schoolYear=0` (Häkchen `fach_<id>`) |
| Fach zuteilen | `POST inc/ajax/lehrpersonen/ajax_functions_lehrpersonen.php` `type=1&fach_id&wert=1&class_id&workgroup_id=0&schoolYear=0` |
| Fach-Zuteilung löschen | `POST …/lehrpersonen_faecher.php` `mode=2&assignment=<assignId>` |
| Rechte (aktive Klasse) | `POST …/lehrpersonen_faecher.php` `lehrer_id&new_value=0\|1` mit `mode=3` KLR (`allowed=1`), `16` FP, `22` SpM, `23` Abs; Gesundheit `mode=20&assignId&newValue` (API: nur lesen) |
| Klassenlehrpersonen | erst `GET admin.php?page_request=6&sub_k=10` (Kontext Einstellungen → Klassen, sonst kein Formular und Speichern wird ignoriert), dann Formular `GET …&mode=903&id=<Klasse>`, speichern `POST …&mode=902&id=<Klasse>` mit **allen** Formularfeldern (`klassenlehrer_id`, `_2`, `_3`, `…_plan`) + `submit=Abschicken` |
| Stundenplan schreiben | `POST inc/ajax/timetable/ajax_functions_timetable.php` (Kontext `classOrWorkgroupId, schoolYear=0, semester=1, dayCode, lessonId, classOrWorkgroupMode=class`): `type=1&new_entry=1&id=new_<lektion>_<tag>&courseId` (leere Zelle), `type=1&addCourseField=1&entryType=0` (legt sofort leeren Eintrag an), `type=1&new_entry=1&id=<eintrag>&courseId` (Fach), `type=1&deleteEntry=<eintrag>`, `type=3` (Bearbeitung beenden); `type=18&timetableRowId&roomId&roomType=1..3` (Raum); `type=2&timetableRowId&teacherId` (Lehrperson umschalten) |
| Fächer-Zuteilung Arbeitsgruppe / kommendes SJ | aktivieren `admin.php?page_request=6&workgroup_id=<id>`; Matrix `lehrpersonen_faecher.php mode=0&school_year=0\|1`; `zeige_faecher.php`/`ajax_functions_lehrpersonen.php` mit `class_id=0&workgroup_id=<id>` bzw. `schoolYear=1` |
| Bezugspersonen | `POST rpc/collections/PersonReferenceAdministrationAdmin/<methode>.php` JSON `{parameters, rpcContext: {otherPersonId}}`: `getGuardianReferenceStructsRpc`, `getGuardianReferenceStructsAtGuardianSideRpc`, `getConfigRpc`, `getContextPersonRpc`, `createGuardianRelationshipRpc {guardRelStruct, sideOfRel: "Student"}`, `createNewPersonAndRelationshipRpc {newGuardAndRelStruct: {newPerson, guardianRelationship}}`, `editCustodianTypeRpc {relationshipId, newCustodianType, typeOfRelationship: "guardian_relationship", sideOfRel}`, `deleteGuardianRelationshipRpc {id, deleteOption: delete_only_relationship\|delete_relationship_deactivate_guardian}` |
| Personenverwaltung öffnen | `GET admin.php?page_request=154`, `POST inc/ajax/persons/personManagement.php?pageRequest=154`, `show_persons_of_group.php` |

## Versionen

| Version | Datum | Änderungen |
|---|---|---|
| 1.15.1 | 16.11.2026 | Testdaten pseudonymisiert (#17): erfundene Namen und Kürzel statt echter Lehrpersonen |
| 1.15.0 | 15.11.2026 | `POST /klassen/{id}/stundenplan/abgleich` (Issue #6), `GET /klassen/{id}/felder` (Issue #8) |
| 1.14.0 | 15.11.2026 | Schuljahr vorbereiten: `/klassenlisten`, `/klassen/{id}/eltern`, `/import/pruefen`; Workflows WF-11 bis WF-20 aufgenommen |
| 1.13.0 | 15.11.2026 | Startdateien (`start-escola.bat`/`.command`), Login an Escola angepasst (Referer, 2FA-Ablauf wie Escola-Loginseite) und live bestätigt, Login-Protokoll, Loginseite für Passwort-Manager, Testseite: „Daten lesen“ mit Tabelle/Filter/CSV und Abfragezähler (`GET /fortschritt`), Menügruppen ein-/ausklappbar, alles im selben Tab |
| 1.12.0 | 15.11.2026 | Testseite (lesen → schreiben → lesen → zurück → lesen), Repo EduKSX-Connectors |
