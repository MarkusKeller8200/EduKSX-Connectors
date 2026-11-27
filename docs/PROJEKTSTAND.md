# EduKSX-Connectors – Projektstand

> Stand 2026-11-27 (23:45): Escolas Korrekturen am Personenimport live nachgeprüft (TEST_A1a, ERGÄNZEN und
> ÜBERSCHREIBEN) – alle gemeldeten Fehler behoben; README › Personenimport und WORKFLOWS WF-11/L10 nachgeführt (#2).
> Testpersonen ID 723–734 (TEST/TESTV) danach gelöscht. Weiterhin offen: Branch übernehmen, Upload über die API.
>
> Stand 2026-11-27 (16:00): Testplattform 0.1.0 und Plugin-Beschreibung je API (#41–#48) auf Branch, nicht gemergt.
>
> Stand 2026-11-25: CMI-API 0.1.0 eingecheckt (#23, nicht live). Davor 2026-11-16 (14:00): Escola-API 1.15.1 deckt WF-01 bis WF-10 ab und Teile von WF-11 bis WF-20; Login und
> Lesen sind live geprüft, die Schreibabläufe noch nicht. Als Nächstes: Erkundung in Escola für die offenen Issues
> und Testläufe mit den Testobjekten (Meilenstein «0.1.0 – Escola live getestet»).
>
> Stand 2026-11-24 (13:00): Escola-API 1.16.0 (Branch, noch nicht auf `main`): Klassenbeginn über die Schullaufbahn
> (L19) und Erkenntnisse zum Escola-Personenimport (WF-11, #2). Importtests auf dem Testsystem live durchgeführt.
> Als Nächstes: Branch prüfen und übernehmen, Klassenbeginn mit TEST_A1a live testen, Issue anlegen (gh hier nicht verfügbar).

## Umgesetzt

| Bereich | Stand | Seit Version | Doku |
|---|---|---|---|
| Escola: Anmeldung mit 2FA, Session, Protokoll | live bestätigt | Escola 1.13.0 | `apis/escola/README.md` › Anmeldung |
| Escola: Stammdaten, Stundenplan, SuS, Personen, Rollen lesen | live geprüft | Escola ≤ 1.12.0 | `apis/escola/README.md` |
| Escola: Fächer-Zuteilung, Klassenlehrpersonen, Stundenplan schreiben, Bezugspersonen, Mitarbeitende | eingebaut, teilweise live | Escola 1.12.0 | `apis/escola/WORKFLOWS.md` WF-01–10 |
| Escola: Schuljahr vorbereiten (Klassenlisten, Eltern je Klasse, Import-Vorprüfung) | eingebaut, nicht live | Escola 1.14.0 | WF-11–20 |
| Escola: Stundenplan-Abgleich, Felder pro Klasse | eingebaut, nicht live | Escola 1.15.0 | #6, #8 |
| Escola: Schullaufbahn, Klassenbeginn pro SuS und pro Klasse (L19) | eingebaut, Escola-Aufrufe live mitgeschnitten, API nicht live | Escola 1.16.0 | README › Klassenbeginn, WF-11 |
| Escola-Personenimport (in Escola, nicht API): Ablauf, Feldliste, Werte; Escola-Fehler behoben | live getestet 24.11.2026, nachgeprüft 27.11.2026 | – | README › Personenimport, #2 |
| Testseite, Startdateien | fertig | Escola 1.13.0 | `README.md` › Lokal starten |
| SL-Planer: Ressourcen, Einheiten, Pensenplanung, Pensen, Personaldossier/MAB (nur lesen) | nach Doku gebaut, nicht live; Annahmen ZU PRÜFEN | SL-Planer 0.1.0 | `apis/slplaner/README.md`, #20 |
| CMI: Kontakte synchronisieren, Schüler-/Personaldossier, Klassen ein-/umteilen, Dokumente hochladen | nach Swagger des CMI-Connectors gebaut, nicht live; Annahmen ZU PRÜFEN | CMI 0.1.0 | `apis/cmi/README.md`, #23 |
| Testplattform: Webseite für alle APIs, je API eine Testseite aus `GET /plugin.json` | gebaut, Tests ohne Netzwerk, lokal im Browser geprüft (ohne Fremdsysteme) | Testplattform 0.1.0 | `testplattform/README.md`, #41, #43 |
| Plugin-Beschreibung je API (OpenAPI + `x-eduksx` + `api.json`), Export fürs Intranet | gebaut, in `pruefen.py` | Escola 1.18.0, CMI 0.9.0, SL-Planer 0.2.0 | `docs/konventionen.md`, #42, #48 |
| GitHub-Blueprint | angewendet (Rest von Hand) | Repo 0.1.0 | `docs/GITHUB-ABLAUF.md` |

## Offen bzw. geplant

- Meilenstein «0.1.0 – Escola live getestet»: #2–#15 (`_1 bereit`), davon #6 und #8 eingebaut
- #17 Pseudonymisierung umgesetzt, auch im Claude-Projekt (`_3 Beta-Test`); offen: Git-Verlauf (nur auf Auftrag)
- #20 SL-Planer-API (`_3 Beta-Test`): Seiten 1–8 der Seabird-Doku einarbeiten (Basis-URL, Anmeldung, Paginierung, Personen), dann Live-Test
- #23 CMI-API (`_3 Beta-Test`): Zugang bei CM Informatik, ZU PRÜFEN-Punkte klären (Anmeldung, TentaQl, Vorlagen, Klassenzuteilung, Upload-Format), dann Live-Test
- Meilenstein «0.1.0» (Testplattform): #41–#48 umgesetzt (`_3 Beta-Test`), Testlisten abhaken; Intranet sek-intranet#229 (PR #230)
- Sammlungen Fehler / Verbesserungen / Funktionen: nur nach Freigabe

## Technik

- Python 3.12, FastAPI, httpx, BeautifulSoup/lxml; Tests mit pytest gegen gekürzte Escola-Antworten und MockTransport.
- `apis/escola/escola_api/`: `client.py` (Escola-Aufrufe), `parsers.py`, `personen.py`, `auth.py` (Login),
  `app.py` (Endpunkte), `login.html`, `testseite.html`. Version in `apis/escola/api.json`.
- Konfiguration nur über Umgebungsvariablen bzw. `apis/escola/.env` (nie im Repo); `start_lokal.py` legt sie an.
- Prüfen: `python3 pruefen.py`
