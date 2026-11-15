# EduKSX-Connectors

Schnittstellen (APIs) der Sekundarschule Bülach zu Fremdsystemen. Jede API ist ein eigenständiger
Dienst in `apis/<system>/` mit eigenen Abhängigkeiten, Tests, Version und Doku. Genutzt werden sie von
IDA, CONNECT und weiteren EduKSX-Modulen über HTTP.

**Dieses Repository ist privat.** Testvorlagen enthalten echte Namen von Lehrpersonen; Zugangsdaten
gehören nie ins Repo (nur `.env.example`).

## APIs

| Ordner | System | Version | Stand | Doku |
|---|---|---|---|---|
| [`apis/escola`](apis/escola) | Escola (sekbuelach.ch) – Stammdaten, Stundenplan, Schüler:innen, Personen, Rollen, Fächer-Zuteilung, Bezugspersonen | 1.12.0 | Workflows WF-01–10 auf dem Papier vollständig, Testläufe offen | [README](apis/escola/README.md) · [Workflows](apis/escola/WORKFLOWS.md) |

Neue APIs entstehen aus [`apis/_vorlage`](apis/_vorlage).

## Aufbau

```
apis/<system>/        eine API = ein Dienst (Python/FastAPI), eigene requirements, Tests, README, WORKFLOWS
apis/_vorlage/        Gerüst für die nächste API
shared/               gemeinsame Bausteine – erst befüllen, wenn eine zweite API sie braucht
docs/                 Architektur und gemeinsame Konventionen
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

```bash
cd apis/escola
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env      # Werte eintragen
uvicorn escola_api.app:app --host 127.0.0.1 --port 8080
pytest -q
```
