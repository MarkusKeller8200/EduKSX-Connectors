# Vorlage für eine neue API

1. Ordner kopieren: `cp -r apis/_vorlage apis/<system>` und `vorlage_api` in `<system>_api` umbenennen.
2. In `<system>_api/app.py` Titel, Version und Präfix der Umgebungsvariablen anpassen.
3. Aufrufe des Fremdsystems mitschneiden, echte (gekürzte) Antworten nach `tests/fixtures/`.
4. Erst lesen, dann schreiben – Schreiben hinter `<SYSTEM>_SCHREIBEN=1`, mit `?probelauf=true` und Kontrolle.
5. `README.md` und `WORKFLOWS.md` nach dem Muster von `apis/escola` führen.
6. In der Haupt-README und in `.github/workflows/tests.yml` eintragen.

Regeln: [docs/konventionen.md](../../docs/konventionen.md)
