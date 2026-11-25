# Workflows – Übersicht über alle Systeme

Geschäftsfälle der Schule und mit welchen API-Aufrufen sie umgesetzt werden. Die Details (Schritte,
Testdaten, Aufräumen) stehen in der `WORKFLOWS.md` der jeweiligen API. Diese Liste wird laufend erweitert –
neue Fälle unten anfügen, Nummer fortlaufend (`WF-xx`), auch wenn sie mehrere Systeme betreffen.

**Status:** ✅ mit den APIs vollständig möglich · ⚠️ teilweise · ❌ fehlt noch · 💡 neu, noch nicht geprüft
**Live:** 🧪 nicht live getestet · ◐ Aufrufe des Fremdsystems live geprüft · ✔️ Testlauf bestanden (Datum)

| Nr | Workflow | Systeme | Status | Live | Details |
|---|---|---|---|---|---|
| WF-01 | Mitarbeiter:in einstellen und erfassen (Rolle, Personalien, AHV, Schulmail) | Escola (+ M365-Postfach durch IDA/CONNECT) | ✅ | 🧪 | [Escola](../apis/escola/WORKFLOWS.md#wf-01-mitarbeiterin-einstellen-und-erfassen) |
| WF-02 | Mitarbeiter:in tritt auf ein Datum aus | Escola | ✅ | ◐ | [Escola](../apis/escola/WORKFLOWS.md#wf-02-mitarbeiterin-tritt-auf-ein-bestimmtes-datum-aus) |
| WF-03 | Neue Lehrperson ab Datum, mit Klasse oder Fachklasse | Escola | ✅ | ◐ | [Escola](../apis/escola/WORKFLOWS.md#wf-03-neue-lehrperson-ab-datum-mit-klasse-oder-fachklasse) |
| WF-04 | Lehrperson verlässt die Schule | Escola | ✅ | ◐ | [Escola](../apis/escola/WORKFLOWS.md#wf-04-lehrperson-verlässt-die-schule) |
| WF-05 | Lehrperson übernimmt zusätzliche Klasse (Klassen- oder Fachlehrperson) | Escola | ✅ | ◐ | [Escola](../apis/escola/WORKFLOWS.md#wf-05-lehrperson-übernimmt-eine-zusätzliche-klasse-klassen--oder-fachlehrperson) |
| WF-06 | Lehrperson übernimmt eine neue Klasse | Escola | ✅ | ◐ | [Escola](../apis/escola/WORKFLOWS.md#wf-06-lehrperson-übernimmt-eine-neue-klasse-gibt-die-bisherige-ab) |
| WF-07 | Schüler:in anmelden ab Datum, Klasse, Eltern als gesetzliche Vertretung | Escola | ✅ | ◐ | [Escola](../apis/escola/WORKFLOWS.md#wf-07-schülerin-anmelden-ab-datum-x-klasse-zuteilen-eltern-als-gesetzliche-vertretung) |
| WF-08 | Schüler:in wechselt die Klasse ab Datum | Escola | ✅ | 🧪 | [Escola](../apis/escola/WORKFLOWS.md#wf-08-schülerin-wechselt-die-klasse-ab-datum) |
| WF-09 | Schüler:in verlässt die Schule zum Zeitpunkt X | Escola | ✅ | ◐ | [Escola](../apis/escola/WORKFLOWS.md#wf-09-schülerin-verlässt-die-schule-zum-zeitpunkt-x) |
| WF-10 | Schüler:in zieht um | Escola | ✅ | ◐ | [Escola](../apis/escola/WORKFLOWS.md#wf-10-schülerin-zieht-um) |
| WF-11 | Massenimport Schüler:innen und Eltern (Einschulung) | Datenlieferung → IDA/CONNECT → Escola-Import | ⚠️ | 🧪 | [Escola](../apis/escola/WORKFLOWS.md#wf-11-massenimport-schülerinnen-und-eltern-einschulung) |
| WF-12 | Übertrittsformular ins Schülerdossier | Escola oder IDA/CONNECT | ❌ | – | [Escola](../apis/escola/WORKFLOWS.md#wf-12-übertrittsformular-ins-schülerdossier) |
| WF-13 | Klasseneinteilung durch die Schulleitung | Escola | ✅ | 🧪 | [Escola](../apis/escola/WORKFLOWS.md#wf-13-klasseneinteilung-durch-die-schulleitung) |
| WF-14 | App-Zugang für Eltern, Nachfassen | Escola, IDA/CONNECT, Post Smart Send | ⚠️ | 🧪 | [Escola](../apis/escola/WORKFLOWS.md#wf-14-app-zugang-für-eltern-nachfassen) |
| WF-15 | Zuteilungsbrief, Rekurs, Zuteilung definitiv | Escola, IDA/CONNECT | ⚠️ | 🧪 | [Escola](../apis/escola/WORKFLOWS.md#wf-15-zuteilungsbrief-rekurs-zuteilung-definitiv) |
| WF-16 | Stundenpläne aus dem Stundenplaner einspielen | Stundenplaner, Escola | ⚠️ | ◐ | [Escola](../apis/escola/WORKFLOWS.md#wf-16-stundenpläne-aus-dem-stundenplaner-einspielen) |
| WF-17 | ICT: Klassenlisten, Zugänge, Geräte, Nutzungsvereinbarung | Escola, Entra, Apple School Manager, Inventar | ⚠️ | 🧪 | [Escola](../apis/escola/WORKFLOWS.md#wf-17-ict--klassenlisten-zugänge-geräte-nutzungsvereinbarung) |
| WF-18 | Arzt- und Zahnarztkontrollen | Escola, IDA/CONNECT (oder CMI) | ❌ | – | [Escola](../apis/escola/WORKFLOWS.md#wf-18-arzt--und-zahnarztkontrollen) |
| WF-19 | Prüfungen mit Note an Eltern | IDA/CONNECT (Scan), Escola-App | ❌ | – | [Escola](../apis/escola/WORKFLOWS.md#wf-19-prüfungen-mit-note-an-eltern) |
| WF-20 | Überführung nach CMI | Escola, IDA/CONNECT, CMI | ⚠️ | 🧪 | [Escola](../apis/escola/WORKFLOWS.md#wf-20-überführung-nach-cmi) · [CMI](../apis/cmi/WORKFLOWS.md#wf-20-überführung-nach-cmi-cmi-seite) |
| WF-21 | Pensenplanung aus dem SL-Planer übernehmen (Lehrpersonen ↔ Klassen/Fächer, Abgleich mit Escola) | SL-Planer, Escola, IDA/CONNECT | ⚠️ | 🧪 | [SL-Planer](../apis/slplaner/WORKFLOWS.md#wf-21-pensenplanung-aus-dem-sl-planer-übernehmen) |
| WF-22 | Ressourcen Soll/Ist kontrollieren (überplante Ressourcentypen) | SL-Planer | ✅ | 🧪 | [SL-Planer](../apis/slplaner/WORKFLOWS.md#wf-22-ressourcen-sollist-kontrollieren) |
| WF-23 | Kontakte aus Escola nach CMI synchronisieren | Escola, CMI | ✅ | 🧪 | [CMI](../apis/cmi/WORKFLOWS.md#wf-23-kontakte-aus-escola-nach-cmi-synchronisieren) |
| WF-24 | Schüler- bzw. Personaldossier in CMI eröffnen | CMI | ✅ | 🧪 | [CMI](../apis/cmi/WORKFLOWS.md#wf-24-schüler--bzw-personaldossier-eröffnen) |
| WF-25 | Klasseneinteilung und Klassenwechsel in CMI nachführen | Escola, CMI | ⚠️ | 🧪 | [CMI](../apis/cmi/WORKFLOWS.md#wf-25-klasseneinteilung-und-klassenwechsel-in-cmi-nachführen) |
| WF-26 | Dokumente (z. B. Zeugnisse) ins CMI-Dossier ablegen | Escola/IDA, CMI | ✅ | 🧪 | [CMI](../apis/cmi/WORKFLOWS.md#wf-26-dokumente-ins-dossier-ablegen) |
| WF-27 | Zeugnisse aus Escola in die CMI-Lernendendossiers ablegen | Escola, CMI | ⚠️ | 🧪 | [CMI](../apis/cmi/WORKFLOWS.md#wf-27-zeugnisse-aus-escola-in-die-lernendendossiers-ablegen) |
| WF-28 | *(nächster Fall)* | | 💡 | | |

## Neuen Workflow aufnehmen

1. Zeile oben ergänzen (Status 💡).
2. In der `WORKFLOWS.md` jeder betroffenen API einen Abschnitt nach der dortigen Vorlage anlegen:
   Ziel, Testdaten, Schritte mit Aufrufen, Aufräumen, Lücken.
3. Fehlt etwas in einer API, als Lücke (`Lx`) dort eintragen; Status hier auf ⚠️/❌.
4. Nach dem Testlauf Spalte „Live“ auf ✔️ mit Datum setzen.

## Testläufe

Die Escola-API bringt eine Testseite mit (`/testseite`), die pro Fall **lesen → schreiben → lesen → rückgängig →
lesen** ausführt und Anfang und Ende vergleicht – siehe [apis/escola/README.md](../apis/escola/README.md#testseite).
