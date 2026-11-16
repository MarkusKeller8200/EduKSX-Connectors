# SL-Planer-API – Workflows

Stand API: 0.1.0 · erste Fassung 16.11.2026. Übersicht aller Systeme: [docs/workflows.md](../../docs/workflows.md).

**Status:** ✅ mit der API vollständig möglich · ⚠️ teilweise · ❌ fehlt noch · 💡 neu, noch nicht geprüft
**Live:** 🧪 noch nicht live getestet · ✔️ live getestet (Datum)

| Nr | Workflow | Status | Live | Offen |
|---|---|---|---|---|
| WF-21 | Pensenplanung aus dem SL-Planer übernehmen (Lehrpersonen ↔ Klassen/Fächer, Abgleich mit Escola) | ⚠️ | 🧪 | Zugang SL-Planer; Abgleich-Logik in IDA/CONNECT |
| WF-22 | Ressourcen Soll/Ist kontrollieren (überplante Ressourcentypen) | ✅ | 🧪 | Zugang SL-Planer |

## WF-21 Pensenplanung aus dem SL-Planer übernehmen

**Ziel:** Wer unterrichtet welches Fach in welcher Klasse – aus dem SL-Planer lesen und mit Escola abgleichen
(Fächer-Zuteilung, Klassenlehrpersonen).

**Schritte**
1. `GET /planung/klassenlektionen?sj=…` und `GET /planung/weitere_wl?sj=…` – Fach, Klasse, `zuweisung[]` mit Person und Zeitraum.
2. Personen über Name/Vorname/Geburtsdatum bzw. `local_user_id` den Escola-Personen zuordnen (Regel offen).
3. Vergleich mit Escola (`apis/escola`, Fächer-Zuteilung) – Abweichungen anzeigen, Schreiben in Escola nur dort mit Probelauf.

**Lücken:** L1 Zuordnung Person SL-Planer ↔ Escola (kein gemeinsamer Schlüssel bekannt) · L2 Kürzel der Fächer und Klassen beider Systeme abgleichen.

## WF-22 Ressourcen Soll/Ist kontrollieren

`GET /ressourcentypen?sj=…` (oder `?format=csv`): `einh_rest` < 0 = mehr zugewiesen als der Schule zusteht,
> 0 = noch offen.
