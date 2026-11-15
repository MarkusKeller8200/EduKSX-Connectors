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
| WF-11 | *(nächster Fall)* | | 💡 | | |

## Neuen Workflow aufnehmen

1. Zeile oben ergänzen (Status 💡).
2. In der `WORKFLOWS.md` jeder betroffenen API einen Abschnitt nach der dortigen Vorlage anlegen:
   Ziel, Testdaten, Schritte mit Aufrufen, Aufräumen, Lücken.
3. Fehlt etwas in einer API, als Lücke (`Lx`) dort eintragen; Status hier auf ⚠️/❌.
4. Nach dem Testlauf Spalte „Live“ auf ✔️ mit Datum setzen.

## Testläufe

Die Escola-API bringt eine Testseite mit (`/testseite`), die pro Fall **lesen → schreiben → lesen → rückgängig →
lesen** ausführt und Anfang und Ende vergleicht – siehe [apis/escola/README.md](../apis/escola/README.md#testseite).
