# Übergabe an einen neuen Chat – EduKSX-Connectors

Stand: **2026-11-27 (23:45)** – Escolas Import-Korrekturen live nachgeprüft, alle Fehler behoben (Doku WF-11/L10, #2); Testpersonen ID 723–734 danach gelöscht. Davor **2026-11-27 (16:00)** – Testplattform 0.1.0 und Plugin-Beschreibung je API (#41–#48, Meilenstein 0.1.0) auf Branch `funktion/41-testplattform` (PR #49, baut auf PR #40 auf), Intranet-Gegenstück sek-intranet#229 (PR #230); davor **2026-11-25 (12:00)** – CMI-API 0.1.0 (#23) gebaut, nicht live; davor 2026-11-24 (13:00): Escola-API 1.16.0 auf Branch `escola-klassenbeginn-import` (Klassenbeginn L19, Importerkenntnisse WF-11); davor 2026-11-16 (14:00): #17 umgesetzt (Repo und Claude-Projekt pseudonymisiert), doppelter CI-Workflow `tests` entfernt; GitHub-Blueprint angewendet; Escola-API 1.15.0 auf `main`, Login live bestätigt,
Lesen live geprüft; Meilenstein «0.1.0 – Escola live getestet» mit #2–#15 freigegeben, noch kein Release.
[PROJEKTSTAND.md](PROJEKTSTAND.md) (aktuell), Konzepte in `docs/KONZEPT-*.md` (noch keine).
Kopien im Claude-Projekt ESCOLA: `claude/uebergabe.md` und `claude/projektstand.md` – bei jeder Übergabe beide Orte nachführen.

## Übergabe 2026-11-27 – Testplattform (Meilenstein 0.1.0)

- **Entscheid #42:** Beschreibung jeder API im Code (`summary`/Docstring, `tags`, Beispiele, `x-eduksx`), API-weit in
  `api.json` → `plugin`; `GET /plugin.json` im Format des Intranets (`shared/plugin_export.py`). `pruefen.py` prüft.
- **Testplattform** `testplattform/` (Port 8090, `start-testplattform.command`/`.bat`): Plugins aus `apis/*/api.json`,
  Tester mit Probelauf, Bestätigung (auch serverseitig, `428`), Datei-Upload, Escola-Anmeldung mit 2FA, Protokoll.
  Alte Escola-`/testseite` bleibt und ist verlinkt (Workflows).
- **Versionen:** Escola 1.17.0, CMI 0.9.0, SL-Planer 0.2.0, Vorlage 0.2.0, Testplattform 0.1.0.
- **Intranet (#48 ↔ sek-intranet#229, PR #230):** `intranet:plugin-from-openapi <name>-plugin.json --neu=…`;
  lokal nicht gegen PHP 8.5 getestet → CI des Intranets abwarten.
- **Offen:** Live-Test der Testplattform mit laufenden APIs auf dem eigenen Rechner (Testlisten in #41–#48);
  Escola-Sitzung im Intranet (nicht unterstützt); `composer ci:check` im Intranet.
- **Branch-Abhängigkeit:** `funktion/41-testplattform` enthält die Commits von PR #40 (Zeugnisse) – zuerst #40 mergen.

## Start nächster Chat (Übergabe 2026-11-15, 23:55)

**Zuerst lesen:** CLAUDE.md → AGENTS.md → dieser Abschnitt → PROJEKTSTAND.md → `apis/escola/README.md` und
`apis/escola/WORKFLOWS.md`.

**Stand Code und CI**
- `main`: Blueprint-Commit (siehe `git log`). CI: nur noch `pruefungen` (Blueprint, ruft `pruefen.py`); der alte Workflow `tests` ist entfernt (16.11.2026).
- Noch kein Release; `VERSION` = 0.1.0. Nächstes Release nur auf ausdrückliche Freigabe.
- Prüfen: `python3 pruefen.py` (Escola 89, CMI 30, SL-Planer 14, Vorlage 1 Test, wenige Sekunden).

**Offene Issues und ihr Status**

| Issue | Meilenstein | Status | Inhalt |
|---|---|---|---|
| #6 | 0.1.0 | `_1 bereit` | Stundenplan-Abgleich – **eingebaut (1.15.0)**, Live-Test mit TEST_A1a im Probelauf offen |
| #8 | 0.1.0 | `_1 bereit` | Felder pro Klasse – **eingebaut (1.15.0)**; Entscheid Escola-Feld / CMI / eigene Anwendung offen |
| #2, #3, #4, #9, #11, #13 | 0.1.0 | `_1 bereit` | brauchen Erkundung in Escola mit angemeldetem Konto (eingebauter Browser, nur lesen) |
| #5 | 0.1.0 | `_1 bereit` | Mitteilungen – Versand nur mit Freigabe und genanntem Testempfänger |
| #7, #10 | 0.1.0 | `_1 bereit` | hängen an der Antwort von Escola (Mail an Hannes/Lars) |
| #12, #14, #15 | 0.1.0 | `_1 bereit` | Testläufe – schreiben in Escola, nur zusammen mit dem Projektverantwortlichen |
| #25 | CMI-API | `_3 Beta-Test` | Kontakt vollständig lesen, Erkundung CMI (ERKUNDUNG.md) |
| #23 | CMI-API | `_3 Beta-Test` | CMI-API 0.1.0: Kontakte-Sync, Schüler-/Personaldossier, Klassen ein-/umteilen, Dokument-Upload; nach Swagger des CMI-Connectors, Annahmen in README «ZU PRÜFEN»; kein Zugang, nicht live |
| #20 | Funktionen | `_3 Beta-Test` | SL-Planer-API 0.1.0 eingecheckt (3f86271); Seiten 1–8 der Doku fehlen, Annahmen in README «ZU PRÜFEN»; kein Zugang, nicht live |
| #17 | – | `_3 Beta-Test` | Testdaten, `_old/` und Kopien im Claude-Projekt pseudonymisiert; offen: Git-Verlauf (nur auf ausdrücklichen Auftrag) |

Schliessen erst nach «getestet ok» bzw. abgehakter Testliste.

**Hinweise für die Arbeit**
- Lokal starten: `start-escola.bat` / `start-escola.command`; Login unter `/login?weiter=/testseite`.
- Testobjekte und Schreibregeln: AGENTS.md › Projektregeln.
- Von hier aus (Claude-Proxy) nicht setzbar: Repo-Einstellungen, Rulesets, Dependabot-Warnungen, Actions-Rechte →
  lokal mit eigener `gh`-Anmeldung `python3 ../my-github-blueprint/.github/blueprint/apply.py --ziel . --nur-github`.
  Rulesets bei privaten Repos nur mit bezahltem GitHub-Plan.
- Deployment-Variablen (APP_URL, DEPLOY_*) leer, Hosting noch offen.

**Arbeitsregeln** (siehe AGENTS.md)
- Jedes Thema aus dem Chat → Issue mit Testliste; Status `_1 bereit` → `_2 in Arbeit` → `_3 Beta-Test`.
- Verbesserungen aus dem Test nur als Issue anlegen; umsetzen erst nach Freigabe.
- Releases nur nach ausdrücklicher Freigabe; `VERSION`, Tags und Releases nicht anfassen.
- Löschen nur nach Rückfrage.

## Sitzungen

### Sitzung 2026-11-25 (16:00) – CMI erkundet, Kontakt lesen (#25)

- Im eingebauten Browser die CMI-Weboberfläche (sekbuelach.cmicloud.ch) beim Öffnen eines Kontakts mitgelesen:
  Mandant `sekbuelach`, Anmeldung über CMIs eigenen Anmeldedienst, interne Schnittstelle `webapiprivate` (nicht
  verwenden), Typen Lernendendossier/Personaldossier/Schulklassendossier, Klassenzuteilung Lernende, Dossierkontakt,
  Fremdkey Mapping → `apis/cmi/ERKUNDUNG.md` (ohne Personendaten).
- CMI-API 0.2.0: `/kontakte/{guid}/vollstaendig`, `/adressen`, `/dossiers`; schützenswerte Daten hinter Schalter.
- Meilensteine pro API: Escola-API (früher «0.1.0 – Escola live getestet»), SL-Planer-API, CMI-API.
- Repo vorübergehend öffentlich (Projektverantwortlicher stellt nach dem Testen wieder auf privat); Git-Verlauf vor
  dem 16.11.2026 enthält echte Namen (#17).

### Sitzung 2026-11-25 – CMI-API (#23)

- Neue API `apis/cmi` 0.1.0 nach der Swagger-Beschreibung des zertifizierten Power-Platform-Connectors von
  CM Informatik (Entitäten Kontakt, Adresse, Geschaeft, Ordner, Dokument; TentaQl-Suche; Mandant im Header
  `X-CMI-TENANT-NAME`; Entra-Anmeldung über `aadbridge.prod.cmicloud.ch`).
- Endpunkte: `/kontakte/sync`, `/dossiers/schueler|personal`, `/klassen/einteilen`, `/dossiers/{guid}/dokumente`,
  dazu Lesen und `/suche/{entitaet}` zum Erkunden. Probelauf, Prüfung vor dem Schreiben, Kontrolle danach, kein Löschen.
- Klassenzuteilung und Beteiligung sind in der öffentlichen API nicht beschrieben → konfigurierbar, bis dahin `501`.
- Nächster Schritt: Zugang bei CM Informatik beantragen (Proxy-Gruppe, App-only-Anmeldung, Mandant), TentaQl-Syntax,
  Dossiervorlagen und Modell der Klassenzuteilung in CMI Schule klären; dann Live-Test mit erfundenem Testkontakt.

### Sitzung 2026-11-24 – CMI-Import nach Escola, Klassenbeginn (L19)

- Escola-Personenimport live getestet (Testklasse TEST_A1a, erfundene Testpersonen, alle wieder gelöscht):
  Import per Zwischenablage; direkt in die Klasse möglich; **Escola-Fehler**: Spalte „Vertreter 1 Abteilung (Firma)“
  lässt den Import beim ersten Vertreter 2 abbrechen (Spalte für Spalte eingegrenzt, Mail an Lars mit Beispieldatei);
  Berechtigung der Vertreter wird ignoriert; Vertreter-Geburtstag verstümmelt; Klassenbeginn = Importtag.
- Transfer mit vergangenem Datum lehnt Escola auch serverseitig ab → Klassenbeginn nur über die Schullaufbahn
  (RPC `SchoolCareer/updateEntry`, live mitgeschnitten).
- Escola-API 1.16.0: `GET /schueler/{id}/schullaufbahn`, `PUT /schueler/{id}/klasse/beginn`,
  `POST /klassen/{id}/klassenbeginn`; 8 Tests. README (Personenimport, Klassenbeginn) und WORKFLOWS (WF-11, L10, L19).
- Messung 24.11.2026 (13:00, eingebauter Browser, dieselben RPC-Aufrufe wie die API): Klassenbeginn setzen Ø 0,76 s
  pro SuS, 6/6 Durchläufe ok, SuS 650 wieder ab 14.11.2026 in H_A1a.
- **Offen:** Issue für L19 anlegen (gh-Token in der Sitzung ungültig) und mit `Refs` verknüpfen; Branch prüfen und
  nach `main` übernehmen; Live-Test der laufenden API `PUT …/klasse/beginn` mit SuS SuS (650, aktuell H_A1a) (lesen → Probelauf → schreiben →
  zurücksetzen → lesen).
- Converter CMI → Escola (`cmi2escola.py`, ein Blatt pro Klasse) und Feldkataloge liegen im Claude-Projekt ESCOLA
  (`cmi-escola-converter.md`, `escola-import-feldtest.md`, `escola-export-alle-felder.md`).

### Sitzung 2026-11-16 (23:15) – SL-Planer-API (#20)

- Neue API `apis/slplaner` 0.1.0 nach «SL-Planer API-Dokumentation» (Seabird AG, 18.2.2026, nur Seiten 9–18 vorhanden):
  nur lesen, Personaldossier/MAB hinter `SLPLANER_PERSONALDOSSIER=1` + API-Key, 14 Tests. Workflows WF-21/22.
- Nächster Schritt: Projektverantwortlicher lädt Seiten 1–8 hoch → Annahmen bestätigen/korrigieren.

### Sitzung 2026-11-16 (00:05–) – Pseudonymisierung (#17)

- 119 Lehrpersonen in Fixtures, Tests, README-Beispiel und `_old/` (inkl. ZIP) durch erfundene Namen und Kürzel ersetzt,
  Zuordnung nur ausserhalb des Repos. Tests angepasst (Kürzel- und Schulmail-Regeln mit erfundenen Beispielen).
- Entscheid 2026-11-16: Testdaten werden pseudonymisiert (nicht gelöscht).
- Kopien im Claude-Projekt ESCOLA pseudonymisiert (`escola-api-readme.md` = aktuelle README 1.15.1, `escola-stundenplan-api.md`);
  übrige Projekt-Dokumente enthalten keine echten Personennamen.
- Workflow `tests.yml` entfernt (doppelt zu `pruefungen.yml`), Hinweis in `apis/_vorlage/README.md` angepasst.

### Sitzung 2026-11-14/15 – Escola-API bis 1.15.0, Repo, Blueprint

- Escola-API: Fächer-Zuteilung, Klassenlehrpersonen, Stundenplan schreiben, Bezugspersonen, Mitarbeitende (AHV,
  Schulmail), Austritt/Rolle «Ausgetreten», Testseite, Startdateien, Login an Escola angepasst (live bestätigt),
  Schuljahr vorbereiten (Klassenlisten, Eltern je Klasse, Import-Vorprüfung), Stundenplan-Abgleich, Felder pro Klasse.
- Workflows WF-01 bis WF-20 erhoben; Dokument «Escola-Workflows: Aufwand heute und Automatisierung» für Escola
  (claude.ai, Kopie `docs/workflows-escola.md`, PDF in `docs/`).
- Issues #2–#15 angelegt, freigegeben, Meilenstein 0.1.0; Blueprint angewendet.

## Entscheide

- Entscheid 2026-11-15: Repo privat, keine Lizenz, keine GitHub Pages (Schutzbedarf vertraulich).
- Entscheid 2026-11-15: Jede API ist ein Modul mit eigener Version (`apis/*/api.json`); Repo-Version in `VERSION`.
- Entscheid 2026-11-15: Installer = ZIP des Repos ohne `_old/` und Tests.
- Entscheide zu Escola (AHV, Schulmail, Rolle «Ausgetreten», Fachklasse = Arbeitsgruppe, Sorgerecht, Eltern):
  `apis/escola/WORKFLOWS.md` › Entscheidungen.
