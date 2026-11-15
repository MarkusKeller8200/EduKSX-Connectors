# Changelog – EduKSX-Connectors

Format angelehnt an [Keep a Changelog](https://keepachangelog.com/de/), Versionen nach
[Semantic Versioning](https://semver.org/lang/de/) (MAJOR.MINOR.PATCH). Neue Einträge kommen laufend unter
**Unveröffentlicht**; `python3 .github/blueprint/release.py set X.Y.Z --commit` macht daraus eine Version.

## [Unveröffentlicht]

### Hinzugefügt
- GitHub-Blueprint angewendet: Labels, Meilensteine, Formulare, Workflows (Prüfungen, Release, Installer-ZIP,
  Fremdkomponenten), CLAUDE.md/AGENTS.md, Übergabe und Projektstand, Steckbrief `docs/PROJEKTSTART.md`
- `pruefen.py`: Tests aller APIs und gültige Modul-Versionen; `VERSION` (Repo 0.1.0); `apis/*/api.json` (Modul-Versionen)
- Escola-API 1.15.0: Stundenplan-Abgleich (#6), Felder pro Klasse (#8); 1.14.0: Klassenlisten, Eltern einer Klasse,
  Import-Vorprüfung; 1.13.0: Startdateien, Login an Escola angepasst und live bestätigt, Testseite «Daten lesen»

### Sicherheit
- Echte Personendaten in Fixtures und `_old/` sind erfasst, Bereinigung offen (#17)
