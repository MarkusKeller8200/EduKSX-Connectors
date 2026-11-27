# Konventionen für alle APIs

Abgeleitet aus der Escola-API (Stand 1.12, November 2026). Neue APIs halten sich daran, damit IDA,
CONNECT und weitere Module alle Schnittstellen gleich ansprechen können.

## Technik
- Python 3.12+, FastAPI, httpx, pytest. Jede API hat ihr eigenes `requirements.txt`.
- Paketname `<system>_api`, App-Objekt `<system>_api.app:app`.
- Konfiguration nur über Umgebungsvariablen mit Präfix `<SYSTEM>_` (Vorlage `.env.example`).
- Ein Ordner = ein Dienst = eigener Port. Gemeinsamer Code erst nach `shared/`, wenn ihn zwei APIs brauchen.

## Anmeldung und Schutz
- Zugangsdaten des Fremdsystems werden nie gespeichert oder geloggt; Sitzungen nur im Arbeitsspeicher.
- Eigener Schutz der API über Header `X-API-Key` (`<SYSTEM>_API_KEY`).
- Schreiben ist standardmässig **aus** (`<SYSTEM>_SCHREIBEN=1`) und verlangt einen gesetzten API-Key.
- Besonders schützenswerte Daten (Gesundheit, AHV, Bank) nur mit eigenem Schalter bzw. maskiert (`***`).
- Gefährliche Aktionen des Fremdsystems (definitiv löschen, ganze Pläne löschen …) werden nicht angeboten.

## Endpunkte
- Deutsche Namen: `/schueler`, `/personen`, `/klassen/{id}/…`; IDs immer die des Fremdsystems.
- Listen-Endpunkte: optional `?format=csv`.
- Schreibende Endpunkte: `?probelauf=true` zeigt den Plan, ändert nichts.
- Nach jedem Schreiben neu lesen und vergleichen; übernimmt das Fremdsystem nicht → `409`.
- Abläufe mit mehreren Schritten melden pro Schritt `ok`/`fehler` und `vollstaendig`.
- Prüfen **bevor** etwas angelegt wird (Duplikate, Eindeutigkeit), damit keine halben Datensätze entstehen.

## Fehlercodes

| Code | Bedeutung |
|---|---|
| 400 | Eingabe ungültig (Format, unbekannte ID, Regel verletzt) |
| 401 | nicht angemeldet / Sitzung abgelaufen |
| 403 | Schreiben ausgeschaltet oder API-Key fehlt |
| 404 | Datensatz nicht gefunden |
| 409 | Konflikt: schon vergeben / Duplikat / Fremdsystem hat nicht übernommen – mit `personen` bzw. Details |
| 422 | einzelne Felder ungültig (Liste) |
| 501 | vorbereitet, noch nicht aktiviert |

## Dokumentation je API
- `README.md`: Endpunkt-Übersicht (Tabelle mit Zugriff 🔓/🔑/✏️/⏳), Beispiele, Besonderheiten des Fremdsystems,
  Tabelle „Verwendete Aufrufe des Fremdsystems“.
- `WORKFLOWS.md`: Geschäftsfälle mit Status (✅/⚠️/❌), Aufrufen, Testdaten, Aufräumen.

## Plugin-Beschreibung (Testplattform, Intranet)

Entscheid #42 (27.11.2026): Jede API beschreibt sich **im Code**; daraus entsteht `GET /plugin.json` im Format von
`plugin.json` des Intranets (sek-intranet, `PLUGINS.md`). Die Testplattform (`testplattform/`) und das Intranet
(`php artisan intranet:plugin-from-openapi`, sek-intranet#229) lesen dieselbe Beschreibung. Umwandlung:
`shared/plugin_export.py`.

- **Standard-OpenAPI:** jeder Endpunkt mit `summary="…"` oder Docstring (erste Zeile = Beschriftung), `tags=[…]`
  (Gruppe), Beispiele mit `Field(examples=[…])`, `Query(examples=[…])`, `Form(examples=[…])`. Nur erfundene Werte.
- **Eigenes nur in `x-eduksx`:** `openapi_extra={"x-eduksx": {...}}` mit `danger`, `status` (`full`/`partial`/
  `planned`), `effect` (`read`/`write`), `permission`, `use`, `note`, `label`, `body`. Vorgaben: alles ausser GET
  ist schreibend (`danger`); POST, die nur prüfen oder anmelden, mit `{"effect": "read", "danger": false}`.
- **API-weit in `api.json` → `plugin`:** `port`, `status` (Vorgabe je Endpunkt; `partial`, solange nicht live
  geprüft), `kategorie`, `beschreibung`, `data_notice`, optional `sitzung` (`header`, `feld`, `anmeldung`, `status`,
  `hinweis`) und `auth_note`.
- **Automatisch:** `?probelauf=` → `probelauf: true`; `X-API-Key` und die Sitzungs-Kopfzeile erscheinen nicht als
  Parameter; Multipart-Formulare → `form` (+ `file` fürs Intranet).
- **Prüfung:** `python3 pruefen.py` erzeugt die Beschreibung jeder API und meldet fehlende Beschriftungen,
  schreibende Endpunkte ohne `danger`, doppelte IDs und eine Version ≠ `api.json`.
- **Export:** `python3 shared/plugin_export.py apis/<name> [https://adresse] > <name>-plugin.json` (ohne laufende API).
- **Aufrufe aus dem Browser (CORS, #51):** `einbinden` erlaubt Aufrufe von `EDUKSX_CORS_ORIGINS` (Vorgabe
  `https://markuskeller8200.github.io`, die Testplattform auf GitHub Pages), inkl. Freigabe fürs lokale Netz. Auf einem
  Server die Liste bewusst setzen (leer = keine).

## Tests
- Ohne Netzwerk: echte, gekürzte Antworten in `tests/fixtures/` und nachgebaute Fremdsysteme (httpx MockTransport).
- Beobachtetes Verhalten des Fremdsystems wird im Fake nachgebildet und im Test-Docstring mit Datum festgehalten.
- Zentrale Prüfung: Lesen löst keine Schreibaufrufe aus.
