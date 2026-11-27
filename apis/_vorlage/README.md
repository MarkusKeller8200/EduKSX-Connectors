# Vorlage für eine neue API

1. Ordner kopieren: `cp -r apis/_vorlage apis/<system>` und `vorlage_api` in `<system>_api` umbenennen.
2. In `<system>_api/app.py` Titel, Version und Präfix der Umgebungsvariablen anpassen.
3. Aufrufe des Fremdsystems mitschneiden, echte (gekürzte) Antworten nach `tests/fixtures/`.
4. Erst lesen, dann schreiben – Schreiben hinter `<SYSTEM>_SCHREIBEN=1`, mit `?probelauf=true` und Kontrolle.
5. `README.md` und `WORKFLOWS.md` nach dem Muster von `apis/escola` führen.
6. **Plugin-Beschreibung pflegen** (Testplattform und Intranet, #42/#47): `api.json` → `plugin` (Port, Status,
   Kategorie, Beschreibung, Datenschutz-Hinweis) anpassen; jeder Endpunkt mit `summary` bzw. Docstring, `tags` und
   Beispielen, Besonderes in `openapi_extra={"x-eduksx": {...}}`. `GET /plugin.json` ist über
   `_plugin_json_einbinden(app)` am Ende von `app.py` schon eingerichtet – die API erscheint damit ohne weitere Arbeit
   in der Testplattform. Regeln: [docs/konventionen.md › Plugin-Beschreibung](../../docs/konventionen.md).
7. In der Haupt-README eintragen. Die Prüfung (`pruefungen.yml` → `pruefen.py`) findet die API über ihre `api.json`
   von selbst und prüft dabei auch die Plugin-Beschreibung.

Regeln: [docs/konventionen.md](../../docs/konventionen.md)
