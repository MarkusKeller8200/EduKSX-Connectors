# CMI-API – Workflows

Stand API: 0.1.0 · erste Fassung 25.11.2026. Übersicht aller Systeme: [docs/workflows.md](../../docs/workflows.md).

**Status:** ✅ mit der API vollständig möglich · ⚠️ teilweise · ❌ fehlt noch · 💡 neu, noch nicht geprüft
**Live:** 🧪 noch nicht live getestet · ✔️ live getestet (Datum)

| Nr | Workflow | Status | Live | Offen |
|---|---|---|---|---|
| WF-20 | Überführung nach CMI (CMI-Seite) | ⚠️ | 🧪 | Zugang CMI; Absenzen/Verhalten/Prüfungen; Schuljahresdossier |
| WF-23 | Kontakte aus Escola nach CMI synchronisieren | ✅ | 🧪 | Zugang CMI, TentaQl |
| WF-24 | Schüler- bzw. Personaldossier eröffnen | ✅ | 🧪 | Dossiervorlagen, Typnamen |
| WF-25 | Klasseneinteilung und Klassenwechsel in CMI nachführen | ⚠️ | 🧪 | Modell der Klassenzuteilung in CMI Schule |
| WF-26 | Dokumente (z. B. Zeugnisse) ins Dossier ablegen | ✅ | 🧪 | Dateiformat beim Anlegen, Ordnerstruktur |

Testdaten: nur erfundene Personen (z. B. «Muster Lea», fremdkey `test-…`) und eine Testklasse; Schlüssel und
Titel mit «TEST» beginnen lassen. Die API löscht nicht – Testobjekte in CMI von Hand inaktiv setzen bzw. entfernen.

## WF-20 Überführung nach CMI (CMI-Seite)

**Ziel:** Escola-Daten ins zentrale Dossier: Stammdaten, Klassenzuteilung, Dokumente (siehe
[Escola WF-20](../escola/WORKFLOWS.md#wf-20-überführung-nach-cmi)).

**Schritte**
1. Escola lesen (`apis/escola`: `/schueler`, `/klassenlisten`, `/schueler/{id}/bezugspersonen`).
2. WF-23 Kontakte (SuS und Eltern) synchronisieren, `fremdkey` = Escola-ID.
3. WF-24 fehlende Schülerdossiers eröffnen.
4. WF-25 Klassenzuteilungen nachführen.
5. WF-26 Dokumente ablegen (mindestens Semesterende: Zeugnisse).

**Lücken:** L1 Absenzen, Verhalten, Prüfungsresultate (Escola #9) · L2 Schuljahresdossier als PDF · L3 Eltern als
Beteiligte am Schülerdossier (Beteiligungsmodell ZU PRÜFEN).

## WF-23 Kontakte aus Escola nach CMI synchronisieren

1. `POST /kontakte/sync?probelauf=true` mit den Personen (fremdkey = Escola-ID) – Plan ansehen.
2. Ohne Probelauf ausführen; `vollstaendig: true` prüfen, bei `409` die `schritte` ansehen.
3. Wiederholen ist gefahrlos: unveränderte Kontakte lösen keinen Schreibaufruf aus.

## WF-24 Schüler- bzw. Personaldossier eröffnen

1. Kontakt muss bestehen (WF-23).
2. `POST /dossiers/schueler?probelauf=true` bzw. `/dossiers/personal` mit `fremdkey` und `beginn`.
3. Ausführen; ein zweiter Versuch meldet `409` mit dem bestehenden Dossier.

## WF-25 Klasseneinteilung und Klassenwechsel in CMI nachführen

1. `GET /klassen` – Titel der Klassendossiers mit Escola vergleichen.
2. `POST /klassen/einteilen?probelauf=true` mit `ab` und den Zuteilungen; Aktionen prüfen.
3. Ausführen; Kontrolle über `GET /schueler/{fremdkey}/klassen`.

Ein Klassenwechsel im Schuljahr ändert nur die Klassenzuteilungen (wie «Klassenumteilung» in CMI); offene
Zeugnisse überträgt die API nicht.

**Lücke:** Zugriff der offiziellen API auf Schullaufbahn und Klassenzuteilung (bis dahin `501`).

## WF-26 Dokumente ins Dossier ablegen

1. Dossier finden: `GET /dossiers?art=schueler&fremdkey=…`.
2. `POST /dossiers/{guid}/dokumente?probelauf=true` mit Datei, Ordnerpfad und Schlüssel.
3. Ausführen; `vollstaendig` heisst: Titel, Dossier und Inhalt (SHA-256) stimmen.
