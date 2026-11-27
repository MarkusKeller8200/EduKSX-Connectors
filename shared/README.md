# shared

Bausteine, die mehrere APIs bzw. die Testplattform brauchen.

| Datei | Inhalt |
|---|---|
| `plugin_export.py` | Plugin-Beschreibung einer API aus OpenAPI + `api.json` (Format `plugin.json` des Intranets), Prüfung, `GET /plugin.json` (#42) |

Nur Standardbibliothek. Die APIs binden `plugin_export` ein, wenn der Ordner vorhanden ist (lokal, CI); im
Docker-Image einer einzelnen API fehlt er – dann erzeugt die Testplattform die Beschreibung aus `/openapi.json`.
Tests: `tests/` (läuft in `python3 pruefen.py`).
