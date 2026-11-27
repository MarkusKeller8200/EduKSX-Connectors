# Testplattform

Webseite zum Testen aller APIs in `apis/` (#41, #43). Jede API ist ein **Plugin** mit eigener Testseite; die
Testseite entsteht aus der Plugin-Beschreibung der API (Entscheid #42) – neue APIs erscheinen ohne Änderung an der
Plattform.

```
Browser ──► Testplattform (127.0.0.1:8090) ──X-API-Key──► Escola-API :8080 · SL-Planer-API :8081 · CMI-API :8082
            Beschreibung: GET <api>/plugin.json (sonst aus /openapi.json erzeugt)
```

## Starten

1. Die APIs starten, die getestet werden sollen – z. B. `start-escola.command` / `.bat`, oder
   `cd apis/cmi && uvicorn cmi_api.app:app --port 8082`.
2. `start-testplattform.command` (macOS/Linux) bzw. `start-testplattform.bat` (Windows) – richtet beim ersten Start
   die Python-Umgebung ein und öffnet `http://127.0.0.1:8090`.

Von Hand: `cd testplattform && pip install -r requirements.txt && python3 start_lokal.py`.

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

## Versionen

| Version | Datum | Änderung |
|---|---|---|
| 0.1.0 | 2026-11-27 | Erste Fassung: Plugins aus `apis/*/api.json`, Beschreibung aus `/plugin.json` bzw. `/openapi.json`, Tester mit Probelauf, Bestätigung, Datei-Upload, Escola-Anmeldung mit 2FA, Protokoll (#41, #43, #44–#46) |
