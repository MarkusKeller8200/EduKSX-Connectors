# Testplattform

Webseite zum Testen aller APIs in `apis/` (#41, #43). Jede API ist ein **Plugin** mit eigener Testseite; die
Testseite entsteht aus der Plugin-Beschreibung der API (Entscheid #42) – neue APIs erscheinen ohne Änderung an der
Plattform.

```
Browser ──► Testplattform (127.0.0.1:8090) ──X-API-Key──► Escola-API :8080 · SL-Planer-API :8081 · CMI-API :8082
            Beschreibung: GET <api>/plugin.json (sonst aus /openapi.json erzeugt)
```

## Starten (lokal, alles mit einem Doppelklick – #50)

`start-testplattform.command` (macOS/Linux) bzw. `start-testplattform.bat` (Windows) doppelklicken. Das Skript
- richtet beim ersten Start `testplattform/.venv` ein und installiert die Pakete **aller** APIs (erneut, sobald sich
  eine `requirements.txt` ändert),
- legt fehlende `apis/<name>/.env` aus `.env.example` an – mit neuem API-Key und **Schreiben aus**
  (`<NAME>_SCHREIBEN=0`; zum Schreiben in der `.env` auf `1` setzen und neu starten),
- startet alle APIs (Escola 8080, SL-Planer 8081, CMI 8082) und die Plattform (8090), alles nur auf 127.0.0.1;
  läuft eine API schon, wird sie nicht doppelt gestartet,
- öffnet `http://127.0.0.1:8090`. **Ctrl+C** (bzw. Fenster schliessen) beendet alles.

Optionen: `--nur-plattform` (APIs selbst starten), `--ohne-browser`.
Von Hand: `cd testplattform && pip install -r requirements.txt && python3 start_lokal.py`.

## GitHub Pages (nur Oberfläche – #51)

Die Oberfläche gibt es auch auf GitHub Pages: **https://markuskeller8200.github.io/EduKSX-Connectors/**.
**Die APIs müssen trotzdem lokal laufen** (Doppelklick wie oben); die Seite ruft sie direkt aus dem Browser auf.

- Auf der Startseite je API Adresse prüfen und API-Key eintragen (`<NAME>_API_KEY` aus `apis/<name>/.env`). Der Key
  bleibt nur im Browser-Tab (sessionStorage), die Adresse im Browser (localStorage).
- Die Daten gehen direkt vom Browser an die API auf dem eigenen Rechner – nicht über GitHub. GitHub liefert nur
  HTML, JavaScript und `plugins.json` (Namen, Versionen, Ports aus `apis/*/api.json`).
- Die APIs erlauben Aufrufe von der Pages-Adresse (CORS inkl. Freigabe fürs lokale Netz, `shared/plugin_export.py`):
  `EDUKSX_CORS_ORIGINS` (Komma-Liste), Vorgabe `https://markuskeller8200.github.io`; leer = keine.
- Unterschiede zur lokalen Plattform: Bestätigung vor dem Schreiben nur im Browser; Protokoll nur im Tab; die API
  muss `/plugin.json` anbieten (aus dem Repo gestartet: ja).
- Browser: Chrome, Edge, Firefox (evtl. Rückfrage «Zugriff auf lokales Netzwerk» – erlauben). Safari blockiert
  Aufrufe von https-Seiten an `http://127.0.0.1`.
- Veröffentlicht vom Workflow `.github/workflows/pages.yml` bei Änderungen auf `main`; einmalig in den
  Repo-Einstellungen Pages → Source «GitHub Actions» wählen. **Privates Repo: Pages nur mit bezahltem GitHub-Plan.**
- Lokal ansehen: `python3 testplattform/pages_bauen.py _site` erzeugt die Seite in `_site/`.

## Einstellungen

Ohne Einstellungen findet die Plattform alle `apis/*/api.json` und ruft sie unter `http://127.0.0.1:<port>` auf
(Port aus `api.json` → `plugin.port` bzw. `<NAME>_PORT`). Der API-Key kommt aus der Umgebung oder aus
`apis/<name>/.env` (`<NAME>_API_KEY`, dieselbe Datei, die die API selbst liest).

| Variable | Bedeutung |
|---|---|
| `<NAME>_URL` | Adresse einer API, z. B. `CMI_URL=http://127.0.0.1:8082` |
| `<NAME>_API_KEY` | API-Key der API; bleibt auf dem Server, der Browser sieht ihn nie |
| `TESTPLATTFORM_PORT` | Port der Plattform (Standard 8090); sie lauscht nur auf 127.0.0.1 |
| `TESTPLATTFORM_TOKEN` | optional: Zugangsschlüssel (Kopfzeile `X-Testplattform-Token`), falls die Plattform nicht nur lokal läuft |
| `TESTPLATTFORM_VORLAGE` | `1` = auch `apis/_vorlage` anzeigen |
| `EDUKSX_CORS_ORIGINS` | für die APIs: erlaubte Herkunft für Aufrufe aus dem Browser (Vorgabe GitHub Pages, siehe unten) |

Vorlage: `.env.example` (als `.env` kopieren, nie einchecken).

## Funktionen

- **Startseite:** alle APIs mit Version, Adresse, API-Key hinterlegt ja/nein und Ergebnis von `GET /status`
  (erreichbar · nicht eingerichtet · nicht angemeldet · nicht erreichbar).
- **Testseite je API:** Endpunkte nach Gruppe (`tags`), Filter, Status (bestätigt / teilweise / geplant),
  ✏️ für schreibende Endpunkte; Datenschutz-Hinweis der API.
- **Tester:** Pfad-, Abfrage- und Kopfzeilen-Parameter mit Beispielwerten, JSON-Body mit Prüfung, «Beispiel
  einsetzen», «Felder löschen», «Formatieren», «Mögliche Werte»; Formulare mit Datei-Upload (auch mehrere Dateien);
  IDs aus der letzten Antwort (`id`, `guid`, `…_id`, `fremdkey`) werden in Pfadparameter übernommen; Antwort mit
  Status, Dauer, JSON oder Download (CSV, PDF).
- **Schutz:** Aufrufe nur für Endpunkte aus der Beschreibung; `planned` ist nicht aufrufbar. Schreibende Endpunkte
  starten mit **Probelauf** (`?probelauf=true`); ohne Probelauf fragt die Seite nach, und die Plattform verlangt die
  Bestätigung auch serverseitig (sonst `428`). Das gilt auch für `DELETE` (z. B. Escola: Zuteilung entfernen).
  Ob eine API überhaupt schreibt, entscheidet weiterhin die API selbst (`<NAME>_SCHREIBEN=1`).
- **Anmeldung (Escola):** Benutzername, Passwort und 2FA-Code; die Sitzung (`X-Escola-Session`) liegt nur im
  Browser-Tab (sessionStorage) und wird an die API weitergereicht. Für die Workflow-Tests (lesen → schreiben → lesen
  → zurück) bleibt die bisherige **Escola-Testseite** (`/testseite` der Escola-API) verlinkt.
- **Protokoll:** letzte 300 Aufrufe im Arbeitsspeicher – Zeit, API, Endpunkt, Status, Probelauf, Dauer; ohne
  Parameterwerte, Bodys und Zugangsdaten.
- **plugin.json herunterladen:** die Beschreibung im Format des Intranets (#48, sek-intranet#229).

## Plugin-Beschreibung einer API

Siehe [docs/konventionen.md › Plugin-Beschreibung](../docs/konventionen.md#plugin-beschreibung-testplattform-intranet)
und `shared/plugin_export.py`. Kurz: `summary`, `tags`, Beispiele und `openapi_extra={"x-eduksx": {...}}` im Code,
API-weite Angaben in `api.json` → `plugin`. `python3 pruefen.py` prüft jede API.

## Aufbau

| Pfad | Inhalt |
|---|---|
| `testplattform/app.py` | FastAPI: Plugins finden, Beschreibung holen, Proxy mit Prüfung, Protokoll |
| `testplattform/static/` | `index.html`, `plattform.js`, `plattform.css` (ohne Fremdbibliotheken, WCAG 2.1 AA) |
| `tests/` | Tests gegen nachgebaute APIs (ohne Netzwerk) |
| `testplattform.json` | Version der Testplattform |
| `start_lokal.py` | Start aller APIs und der Plattform (#50) |
| `pages_bauen.py` | statische Seite für GitHub Pages (#51) |

## Versionen

| Version | Datum | Änderung |
|---|---|---|
| 0.2.0 | 2026-11-27 | Ein Doppelklick startet alle APIs und die Plattform (#50); Oberfläche auch auf GitHub Pages mit direktem Aufruf der lokal laufenden APIs (#51) |
| 0.1.0 | 2026-11-27 | Erste Fassung: Plugins aus `apis/*/api.json`, Beschreibung aus `/plugin.json` bzw. `/openapi.json`, Tester mit Probelauf, Bestätigung, Datei-Upload, Escola-Anmeldung mit 2FA, Protokoll (#41, #43, #44–#46) |
