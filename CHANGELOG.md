# Changelog – EduKSX-Connectors

Format angelehnt an [Keep a Changelog](https://keepachangelog.com/de/), Versionen nach
[Semantic Versioning](https://semver.org/lang/de/) (MAJOR.MINOR.PATCH). Neue Einträge kommen laufend unter
**Unveröffentlicht**; `python3 .github/blueprint/release.py set X.Y.Z --commit` macht daraus eine Version.

## [Unveröffentlicht]

### Hinzugefügt
- CMI-API 0.1.0 (`apis/cmi`, #23): Kontakte synchronisieren bzw. anlegen, Schüler- und Personaldossier
  erstellen, SuS in Klassen einteilen/umteilen, Dokumente ins Dossier hochladen; Probelauf, Kontrolle nach dem
  Schreiben, keine Lösch-Endpunkte; nach Swagger des CMI-Connectors, Tests gegen nachgebautes CMI; Workflows WF-23–26
- SL-Planer-API 0.1.0 (`apis/slplaner`, nur lesen): Ressourcen Soll/Ist, Einheiten, Personen, Pensenplanung aller
  Bereiche, Pensen, Personaldossier/MAB hinter eigenem Schalter; CSV-Ausgabe; Tests gegen nachgebauten SL-Planer
- GitHub-Blueprint angewendet: Labels, Meilensteine, Formulare, Workflows (Prüfungen, Release, Installer-ZIP,
  Fremdkomponenten), CLAUDE.md/AGENTS.md, Übergabe und Projektstand, Steckbrief `docs/PROJEKTSTART.md`
- `pruefen.py`: Tests aller APIs und gültige Modul-Versionen; `VERSION` (Repo 0.1.0); `apis/*/api.json` (Modul-Versionen)
- Escola-API 1.15.0: Stundenplan-Abgleich (#6), Felder pro Klasse (#8); 1.14.0: Klassenlisten, Eltern einer Klasse,
  Import-Vorprüfung; 1.13.0: Startdateien, Login an Escola angepasst und live bestätigt, Testseite «Daten lesen»

### Entfernt
- Workflow `tests.yml`: doppelte Prüfung, `pruefungen.yml` führt dieselben Tests über `pruefen.py` aus

### Sicherheit
- Testdaten (`apis/escola/tests/`) und Archiv `_old/` pseudonymisiert: erfundene Namen und Kürzel statt echter
  Lehrpersonen, auch im ZIP unter `_old/pakete/`; Escola-IDs bleiben (#17);
  ebenso die Kopien im Claude-Projekt ESCOLA
