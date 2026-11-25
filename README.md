# EduKSX-Connectors

Schnittstellen (APIs) der Sekundarschule Bülach zu Fremdsystemen. Jede API ist ein eigenständiger
Dienst in `apis/<system>/` mit eigenen Abhängigkeiten, Tests, Version und Doku. Genutzt werden sie von
IDA, CONNECT und weiteren EduKSX-Modulen über HTTP.

**Dieses Repository ist privat.** Testvorlagen enthalten echte Namen von Lehrpersonen; Zugangsdaten
gehören nie ins Repo (nur `.env.example`).

## APIs

| Ordner | System | Version | Stand | Doku |
|---|---|---|---|---|
| [`apis/escola`](apis/escola) | Escola (sekbuelach.ch) – Stammdaten, Stundenplan, Schüler:innen, Personen, Rollen, Fächer-Zuteilung, Bezugspersonen, Schuljahr vorbereiten | 1.15.0 | Login mit 2FA live bestätigt, Lesen live geprüft; Schreib-Testläufe offen | [README](apis/escola/README.md) · [Workflows](apis/escola/WORKFLOWS.md) |
| [`apis/slplaner`](apis/slplaner) | SL-Planer (Seabird AG) – Ressourcen, Einheiten, Pensenplanung, Pensen, Personaldossier/MAB (nur lesen) | 0.1.0 | nach Doku 18.2.2026 gebaut, noch nicht live geprüft | [README](apis/slplaner/README.md) · [Workflows](apis/slplaner/WORKFLOWS.md) |
| [`apis/cmi`](apis/cmi) | CMI (CM Informatik, CMI Schule) – Kontakte synchronisieren und vollständig lesen, Schüler-/Personaldossiers, Klassenzuteilung, Dokumente hochladen | 0.3.0 | nach Swagger des CMI-Connectors gebaut, noch nicht live geprüft | [README](apis/cmi/README.md) · [Workflows](apis/cmi/WORKFLOWS.md) |

Neue APIs entstehen aus [`apis/_vorlage`](apis/_vorlage).

- **Workflows aller Systeme:** [docs/workflows.md](docs/workflows.md) – erweiterbare Liste der Geschäftsfälle
- **Workflows aus Sicht Escola:** [docs/workflows-escola.md](docs/workflows-escola.md) – Aufwand heute, Automatisierung, Wünsche an Escola (zum Teilen mit dem Anbieter)
- **Testseite:** jede API bringt `/testseite` mit (Escola: lesen → schreiben → lesen → rückgängig → lesen)
- **Einsatz in Webanwendungen:** [docs/betrieb-webanwendung.md](docs/betrieb-webanwendung.md) – die APIs laufen als
  Server-Dienst (z. B. Docker), Webanwendungen rufen sie per HTTP auf
- **Archiv:** [`_old/`](_old) – Stände vor dem Umzug ins Repo (nur zum Nachschlagen)

## Aufbau

```
apis/<system>/        eine API = ein Dienst (Python/FastAPI), eigene requirements, Tests, README, WORKFLOWS
apis/_vorlage/        Gerüst für die nächste API
shared/               gemeinsame Bausteine – erst befüllen, wenn eine zweite API sie braucht
docs/                 Architektur, Konventionen, Betrieb, Workflow-Übersicht
_old/                 Archiv (frühere Kopien, nicht mehr pflegen)
.github/workflows/    Tests aller APIs bei jedem Push
```

## Gemeinsame Regeln

Siehe [docs/konventionen.md](docs/konventionen.md) – kurz:
- Lesen ist immer erlaubt, **Schreiben** nur mit Schalter (`<SYSTEM>_SCHREIBEN=1`) und API-Key.
- Jeder schreibende Aufruf kennt `?probelauf=true` und prüft nach dem Schreiben, ob das Fremdsystem übernommen hat.
- Fehler: `400` ungültige Eingabe · `403` Schreiben aus/kein Key · `404` nicht gefunden · `409` Konflikt
  (z. B. schon vergeben, Fremdsystem hat nicht übernommen) mit Liste der Betroffenen.
- Feld- und Endpunktnamen deutsch, IDs immer die des Fremdsystems.
- Tests laufen ohne Netzwerk gegen echte, gekürzte Antworten des Fremdsystems.

## Lokal starten (Beispiel Escola)

Einfachster Weg: Repo auschecken und die Startdatei doppelklicken.

| System | Datei |
|---|---|
| Windows | `start-escola.bat` |
| macOS | `start-escola.command` (beim ersten Mal: Rechtsklick → Öffnen) |
| Linux | `./start-escola.command` |

Voraussetzung ist Python 3.12 oder neuer. Beim ersten Start richtet das Skript `apis/escola/.venv`
ein, installiert die Pakete und legt `apis/escola/.env` an. Dabei fragt es, ob Schreiben erlaubt
sein soll, und nach dem Port. Es erzeugt einen API-Key und zeigt ihn an. Danach öffnen sich Login
und Testseite im Browser. Beenden mit Ctrl+C bzw. Fenster schliessen.

`.env` neu erstellen: Datei löschen und erneut starten. Ohne Browser: `start-escola.command --ohne-browser`.

Von Hand:

```bash
cd apis/escola
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python start_lokal.py        # liest .env selbst
pytest -q
```
