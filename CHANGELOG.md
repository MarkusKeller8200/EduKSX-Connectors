# Changelog – EduKSX-Connectors

Format angelehnt an [Keep a Changelog](https://keepachangelog.com/de/), Versionen nach
[Semantic Versioning](https://semver.org/lang/de/) (MAJOR.MINOR.PATCH). Neue Einträge kommen laufend unter
**Unveröffentlicht**; `python3 .github/blueprint/release.py set X.Y.Z --commit` macht daraus eine Version.

## [Unveröffentlicht]

### Geändert
- Escola-API 1.19.1 (#4, #13): mit Testdaten live geprüft – App-Status erkennt «App (manuell) aktiviert» (das
  Symbol der Gerätezeile ist auch dann rot), neu `app_manuell` und `app_eingeloggt`; Zellen im Stundenplan von
  Arbeitsgruppen trennen `arbeitsgruppe`, LP-Kürzel und Zusatz richtig
- Escola-API 1.19.0 (#3, #4, #9, #11, #13): Erkundung 28.11.2026 an den Testobjekten – Dokumente im
  Schülerdossier über Escolas REST lesen, hochladen und löschen (Schalter `ESCOLA_DOKUMENTE`, ersetzt die
  501-Platzhalter; `/dokumente/struktur` entfällt), Absenzen über `/escola/api/absences` (`/klassen/{id}/absenzen…`,
  `/schueler/{id}/absenzen`), App-Status `/personen/{id}/app` und `/klassen/{id}/eltern?app=true|nur_ohne_app=true`,
  Stundenplan von Arbeitsgruppen `/arbeitsgruppen/{id}/stundenplan`, Rechte auch fürs kommende Schuljahr (#11);
  Hochladen/Löschen von Dokumenten und Rechte kommendes SJ live in Escola geprüft; Befund: in Escola sind ausser H_A1a noch
  keine Schüler:innen erfasst, Absenzen/Dossier/Noten ohne Daten
- Escola-Doku (README › Personenimport, WORKFLOWS WF-11/L10, #2): Escolas Import-Korrekturen am 27.11.2026 live
  nachgeprüft – Abteilung (Firma), PLZ Geschäft, Berechtigung (EB/IB/Keine, mit ÜBERSCHREIBEN auch bei verknüpften
  Vertreter:innen), Vertreter-Geburtstag, Ja/Nein-Felder inkl. Jod, Auto-Matching, eigene Adresse neuer SuS;
  Umgehungen (Spalte weglassen, Berechtigung nachträglich per API) entfallen
- CMI-API 0.7.1 (#36): Klassenwechsel wie «Klassenumteilung» in CMI – Schullaufbahn bleibt, bisherige
  Klassenzuteilung endet am Vortag, neue Zuteilung mit eigener Dauer

### Hinzugefügt
- Testplattform 0.1.0 (#41, #43): Webseite zum Testen aller APIs (`testplattform/`, Port 8090,
  `start-testplattform.command`/`.bat`); jede API ist ein Plugin mit eigener Testseite, Tester mit Beispielwerten,
  Probelauf, Bestätigung für schreibende Aufrufe, Datei-Upload, Escola-Anmeldung mit 2FA und Protokoll
- Testplattform 0.2.0: ein Doppelklick startet alle APIs und die Plattform, fehlende `.env` mit Schreiben aus (#50);
  Oberfläche auch auf GitHub Pages (`pages.yml`), ruft die lokal laufenden APIs direkt auf; APIs erlauben dafür
  Aufrufe von der Pages-Adresse (CORS, `EDUKSX_CORS_ORIGINS`) (#51)
- Plugin-Beschreibung je API (#42): `GET /plugin.json` aus OpenAPI + `api.json` im Format des Intranets
  (`shared/plugin_export.py`), Prüfung in `pruefen.py`, Export für das Intranet (#48)
- Escola-API 1.18.0 (#44), CMI-API 0.9.0 (#45), SL-Planer-API 0.2.0 (#46), Vorlage 0.2.0 (#47): Beschreibungen
  für alle Endpunkte, `api.json` → `plugin`
- CMI-API 0.8.0 (#38): `POST /zeugnisse` – Zeugnis-PDFs gesammelt in die Lernendendossiers ablegen
- Escola-API 1.17.0 (#39): Zeugnisse aus dem Zeugnis-/Formular-Archiv lesen und als PDF herunterladen
  (`/schueler/{id}/zeugnisse`, `/klassen/{id}/zeugnisse`), Schalter `ESCOLA_ZEUGNISSE`
- Escola-API 1.16.0: Schullaufbahn lesen, Klassenbeginn setzen (pro SuS und pro Klasse, z. B. ab 1.8.), weil
  Import und Transfer in Escola nur ab heute einteilen (L19); Erkenntnisse zum Escola-Personenimport in README und
  WORKFLOWS (WF-11, #2), u. a. Abbruch durch die Spalte „Vertreter 1 Abteilung (Firma)“
- CMI-API 0.7.0 (#36): Klasseneinteilung nach dem Modell von CMI Schule (Schullaufbahn, Klassenzuteilung,
  Klassenstufe, Eintrittsgrund); Klassenstufe beim Anlegen einer Klasse
- CMI-API 0.6.0 (#36): Schul- und Externes Schulklassendossier anlegen (`POST /klassen`); Testklassen in CMI
- CMI-API 0.5.0 (#32): Dokumente in beliebigen Ordner/Unterordner eines Dossiers ablegen (Pfad oder GUID),
  Ordner der Vorlagen werden nicht neu angelegt; Ablage in CMI erkundet (`ERKUNDUNG.md`)
- CMI-API 0.4.0 (#30): `POST /kontakte`, `PATCH /kontakte/{guid}`, `POST /schueler` (Kontakt + Lernendendossier),
  `POST /mitarbeitende` (Kontakt + Personaldossier, Vorlage je Standort); Erstellen der Dossiers in CMI erkundet
- CMI-API 0.3.0 (#27): Kontakt-Sync mit allen Feldern der CMI-Oberfläche, Felder leeren, mehrere Adressen nach
  Adressart mit Gültigkeit; Schreibweise der CMI-Oberfläche in `apis/cmi/ERKUNDUNG.md` (Test am Kontakt _TEST)
- CMI-API 0.2.0 (#25): Kontakt vollständig lesen (Adressen, Dossiers, Schule, Bezugspersonen, Notfallkontakte,
  Haushalt, technische Details; Zahlungs- und Gesundheitsdaten nur mit `CMI_SCHUETZENSWERT=1`); Erkundung des
  CMI-Mandanten in `apis/cmi/ERKUNDUNG.md` (nur Typen und Felder, keine Personendaten)
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
