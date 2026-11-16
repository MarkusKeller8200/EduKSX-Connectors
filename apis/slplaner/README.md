# SL-Planer-API

Lesender Zugriff auf den **SL-Planer** (Seabird AG): Ressourcen der Schule, Einheiten, Pensenplanung
(Zuweisung der Lektionen und Aufgaben an Personen), Pensen und – geschützt – Personaldossier/MAB.
Genutzt von IDA, CONNECT und weiteren EduKSX-Modulen, z. B. um Lehrpersonen Klassen und Fächern zuzuordnen
(Abgleich mit Escola) oder Anstellungen weiterzuverarbeiten.

Grundlage: «SL-Planer API-Dokumentation», Seabird AG, 18.2.2026, Abschnitte 5.1.3–5.6.
Der SL-Planer bietet nur lesende Endpunkte an; **diese API schreibt nie** (der Client verweigert alles ausser GET).

## Stand

Version 0.1.0 – Gerüst nach Dokumentation, **noch nicht live geprüft** (kein Zugang). Tests laufen gegen einen
nachgebauten SL-Planer mit den Beispielen aus der Doku (erfundene Personen).

### ZU PRÜFEN (mit Seabird bzw. Kapitel 1–5.1.2 der Doku)

| Punkt | Annahme in 0.1.0 |
|---|---|
| Basis-URL | frei konfigurierbar (`SLPLANER_BASE_URL`) |
| Anmeldung | Header `Authorization: Bearer <Token>` (`SLPLANER_TOKEN`, `SLPLANER_AUTH_SCHEMA`) |
| Schuljahr | Abfrageparameter `sj` (z. B. `2025/26`), wird unverändert weitergegeben |
| Paginierung | reine Liste, `{data, next}`, `{data, links.next}` oder `{data, meta.current_page/last_page}` (`page`) |
| Endpunkte der Bereiche | nur `/klassenlektionen` und `/betreuung` belegt; übrige wie der `typ` im Pensum benannt |
| Personen (5.1.1) | Felder unbekannt, werden unverändert durchgereicht |
| `/pfiles_by_local_user/mab/{…}` | erwartet vermutlich die `local_user_id`, nicht die `person_id` |
| Rate-Limits, Fehlerformat | unbekannt |

## Endpunkte

🔓 lesen · 🔑 nur mit eigenem Schalter und API-Key · ⏳ vorbereitet. Listen mit `?format=csv` (Semikolon, UTF-8 mit BOM).
Wo sinnvoll `?sj=2025/26`.

| Endpunkt | Zugriff | SL-Planer | Inhalt |
|---|---|---|---|
| `GET /status` | 🔓 | – | Version, eingerichtet ja/nein, Schalter, Anzahl Aufrufe |
| `GET /ressourcentypen` | 🔓 | `/ressourcentypen` | Ressourcen der Schule mit Soll/Ist und berechnetem `einh_rest` (Soll − Ist, negativ = überplant) |
| `GET /ressourcentypen/{id}` | 🔓 | `/ressourcentypen/{id}` | einzelner Ressourcentyp |
| `GET /einheiten`, `/einheiten/{id}` | 🔓 | `/einheiten` | Einheiten (VZE, WL, Stunden …) |
| `GET /personen`, `/personen/{id}` | 🔓 | `/personen` | Personen |
| `GET /planung/{bereich}` | 🔓 | `/{bereich}` | Aufgaben inkl. `zuweisung[]`; CSV: eine Zeile pro Zuweisung |
| `GET /planung/{bereich}/{id}` | 🔓 | `/{bereich}/{id}` | einzelne Aufgabe |
| `GET /pensen` | 🔓 | `/pensen` | Pensen ab Freigabe zur Anstellung; CSV: Übersicht pro Person (BG, WL, Arbeitszeit Soll/Ist, Stunden je Gruppe) |
| `GET /pensen/{id}` | 🔓 | `/pensen/{id}` | Pensum einer Person |
| `GET /mab` | 🔑 | `/pfiles/mab` | Mitarbeiterbeurteilungen eines Schuljahres (Übersicht) |
| `GET /mab/{id}` | 🔑 | `/pfiles/mab/{id}` | eine Beurteilung, **ohne** PDF |
| `GET /mab/{id}/pdf` | 🔑 | `/pfiles/mab/{id}` | PDF der Beurteilung |
| `GET /personen/{id}/mab` | 🔑 | `/pfiles_by_person/mab/{id}` bzw. mit `alle_schuljahre=true` `/pfiles_by_local_user/mab/{id}` | Beurteilungen einer Person |
| `GET /personen/{id}/dokumente` | 🔑 | `/pfiles_by_person/{id}` | freigegebene Dokumente einer Person |
| `GET /dokumente/{id}`, `/dokumente/{id}/pdf` | 🔑 | `/pfiles/{id}` | einzelnes Dokument bzw. sein PDF |

Bereiche (`{bereich}`): `klassenlektionen`, `weitere_wl`, `sonderpaedagogik`, `klassenassistenz`, `betreuung`,
`weitere_anstellungen`, `aufgaben_klp`, `aemter`, `weiterer_berufsauftrag`.

Nicht angeboten: Pensenumfrage, Stellvertretung (keine Schnittstelle laut Seabird), Stundenplanung (in Entwicklung),
Import von Betreuungsangeboten und SuS-Zahlen Tagesstrukturen (5.5.1/5.5.2 – das sind Importformate, die der
SL-Planer bei anderen Systemen abholt; eigenes Issue, falls gewünscht).

## Schutz

- `SLPLANER_API_KEY`: jeder Aufruf braucht den Header `X-API-Key`.
- Mitarbeiterbeurteilungen und Personaldossier sind besonders schützenswert: nur mit `SLPLANER_PERSONALDOSSIER=1`
  **und** gesetztem API-Key, sonst `403` – der SL-Planer wird dann gar nicht gefragt. PDFs nur über eigene `/pdf`-Endpunkte.
- Token nur in `.env`, nie im Repo oder in Protokollen.

## Fehler

`401` Token bzw. X-API-Key falsch · `403` Personaldossier aus oder kein API-Key · `404` im SL-Planer nicht gefunden ·
`422` unbekannter Bereich · `501` SL-Planer nicht eingerichtet (Basis-URL/Token fehlen).

## Beispiele

```bash
curl -H "X-API-Key: $KEY" "http://localhost:8081/ressourcentypen?sj=2025/26"
curl -H "X-API-Key: $KEY" "http://localhost:8081/planung/klassenlektionen?sj=2025/26&format=csv" -o klassenlektionen.csv
curl -H "X-API-Key: $KEY" "http://localhost:8081/pensen?format=csv" -o pensen.csv
```

## Lokal starten

```bash
cd apis/slplaner
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env    # Basis-URL und Token eintragen
set -a; source .env; set +a
uvicorn slplaner_api.app:app --port 8081
pytest -q
```

## Verwendete Aufrufe des SL-Planers

Nur `GET`: `/ressourcentypen`, `/einheiten`, `/personen`, `/{bereich}`, `/pensen`, `/pfiles/mab`, `/pfiles/mab/{id}`,
`/pfiles_by_person/mab/{id}`, `/pfiles_by_local_user/mab/{id}`, `/pfiles_by_person/{id}`, `/pfiles/{id}` (je mit `/{id}`).

## Versionen

| Version | Datum | Änderung |
|---|---|---|
| 0.1.0 | 2026-11-16 | Erste Fassung nach SL-Planer API-Dokumentation 18.2.2026: Ressourcen, Einheiten, Personen, Pensenplanung, Pensen, Personaldossier/MAB (geschützt); CSV-Ausgabe; Tests gegen nachgebauten SL-Planer |
