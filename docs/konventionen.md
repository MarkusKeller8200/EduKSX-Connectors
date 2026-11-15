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

## Tests
- Ohne Netzwerk: echte, gekürzte Antworten in `tests/fixtures/` und nachgebaute Fremdsysteme (httpx MockTransport).
- Beobachtetes Verhalten des Fremdsystems wird im Fake nachgebildet und im Test-Docstring mit Datum festgehalten.
- Zentrale Prüfung: Lesen löst keine Schreibaufrufe aus.
