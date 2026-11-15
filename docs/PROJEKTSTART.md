# Projektstart – EduKSX-Connectors

Stand: 2026-11-15 · Status: **OFFEN** – Grundgerüst erst nach Bestätigung durch Projektverantwortliche:r

Steckbrief aus der Start-Checkliste (`start.py --ziel …` im GitHub-Blueprint). Er ist die Grundlage für das Grundgerüst
und für die Konfiguration in `.github/blueprint.toml`. Änderungen hier festhalten und `start.py` erneut ausführen.

## Ziel

Schnittstellen (APIs) zu den Fremdsystemen der Sek Bülach, zuerst Escola, damit IDA und CONNECT Verwaltungsabläufe automatisieren können.

**Nichtziele:**

- (keine genannt)

## Datenschutz

- Zielgruppe: öffentliche Organe
- Anwendbares Recht: IDG (Kanton Zürich)
- Daten: Personendaten · Schutzbedarf: **vertraulich**

Die Zuordnung ist eine Arbeitshilfe, keine Rechtsberatung; bei öffentlichen Organen die zuständige
Datenschutzstelle einbeziehen (z. B. Vorabkontrolle bzw. Datenschutz-Folgenabschätzung).

## Antworten

| Frage | Antwort |
|---|---|
| Wie heisst das Projekt (voller Name)? | EduKSX-Connectors |
| Was soll das Projekt leisten, und für wen? (ein bis zwei Sätze) | Schnittstellen (APIs) zu den Fremdsystemen der Sek Bülach, zuerst Escola, damit IDA und CONNECT Verwaltungsabläufe automatisieren können. |
| Was gehört ausdrücklich nicht dazu (Nichtziele)? | – |
| Welcher Kurzname soll in den Release-Titeln stehen? | EduKSX-Connectors |
| Ist es eine Web-Anwendung, eine Desktop-Anwendung oder beides? | web |
| Wer nutzt die Anwendung? | öffentliche Organe |
| Welche öffentlichen Organe? | Kanton Zürich |
| Ist das Repository neu oder gibt es es schon? | bestehend |
| Wer gibt Issues und Releases frei (Rolle genügt)? | Projektverantwortliche:r |
| Arbeitest du allein oder im Team? | allein |
| Ist das Repository öffentlich oder privat? | privat |
| Unter welcher Lizenz steht der Code? | keine |
| In welchen Programmiersprachen wird entwickelt? | Python |
| Welcher Grundsatz gilt für Abhängigkeiten? | geprüfte Pakete |
| Wo läuft die Web-Anwendung? | offen |
| Wie kommt die Anwendung zu den Nutzer:innen? | Server, Installer (GitHub-Releases); GitHub Pages nicht (Schutzbedarf vertraulich, Entscheid 15.11.2026) |
| Welches Framework bzw. welche Grundlage? | FastAPI |
| Welche Daten verarbeitet die Anwendung? | Personendaten |
| Welcher Schutzbedarf gilt für die Daten (Klassifizierung)? | vertraulich |
| Welche Anmeldungen und Zugänge braucht es? | externe Dienste (API), Entra ID / SSO, eigene Benutzerkonten |
| In welchen Sprachen wird die Oberfläche ausgeliefert? | de-CH |
| Gibt es Plugins oder Module mit eigener Version? | ja |
| Mit welchem Befehl laufen alle Prüfungen? | python3 pruefen.py |
| In welcher Datei steht die Versionsnummer? | VERSION |
| Mit welcher Version startet das Projekt? | 0.1.0 |
| Mit welchen KI-Agenten wird gearbeitet? | Claude |
| Wie heisst der erste Meilenstein? | 0.1.0 – Escola live getestet |
| Übergabe und Projektstand auch als Kopie im Claude-Projekt führen? | ja |
| Welche ersten Funktionen gehören in diesen Meilenstein? | – |

## Grundgerüst

Vorschlag für Aufbau, Ordner und erste Dateien – wird vor dem Anlegen mit Projektverantwortliche:r
abgestimmt (Status je Punkt: BESCHLOSSEN, EMPFOHLEN, OFFEN, ZU PRÜFEN):

| Punkt | Vorschlag | Status |
|---|---|---|
| Technik | Python · FastAPI | OFFEN |
| Ordner | Quellcode, `tests/`, `docs/` | OFFEN |
| Prüfungen | `python3 pruefen.py` (Workflow «pruefungen») | OFFEN |
| Version | `VERSION` mit 0.1.0 | OFFEN |
| Auslieferung | Server, Installer (ZIP ohne _old und Tests); keine GitHub Pages – Workflow «installer» lädt Artefakte «installer-*» hoch | OFFEN |

## Erster Meilenstein: 0.1.0 – Escola live getestet

- (noch keine)

Diese Punkte werden nach Bestätigung als Issues mit Testliste angelegt.
