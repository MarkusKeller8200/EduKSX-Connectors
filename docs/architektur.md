# Architektur

```
            ┌──────────┐   ┌──────────┐   ┌────────────────┐
            │   IDA    │   │ CONNECT  │   │ weitere Module │
            └────┬─────┘   └────┬─────┘   └───────┬────────┘
                 │  HTTP (X-API-Key, Sitzung)      │
     ┌───────────┼──────────────┼──────────────────┼──────────┐
     │  EduKSX-Connectors                                      │
     │   apis/escola  (Port 8080)   apis/<nächstes> (Port …)   │
     └───────────┬──────────────────────────────────┬─────────┘
                 │ interne Aufrufe wie die Weboberfläche
          ┌──────┴──────┐                       ┌───┴───┐
          │   Escola    │                       │  …    │
          └─────────────┘                       └───────┘
```

## Aufgabenteilung
- **APIs (dieses Repo):** einzelne, geprüfte Schritte im Fremdsystem – lesen, anlegen, ändern, mit Probelauf
  und Kontrolle. Keine Planung, keine Daten anderer Systeme.
- **IDA / CONNECT:** Geschäftsfälle steuern (Workflows), Stichtage planen und am Datum auslösen, Daten
  zwischen Systemen abgleichen (z. B. Schulmail aus Escola → Postfach in M365).

## Stichtage
Fremdsysteme wie Escola übernehmen Änderungen sofort. Alles mit „ab Datum“ (Austritt am Stichtag,
Nachfolge, Umzug, Klassenwechsel mitten im Jahr) plant IDA/CONNECT und ruft die API am Datum auf.
Ausnahme: Escola-Klassenzuteilung und Austrittsdatum kennen selbst ein Datum.

## Sitzungen
Escola merkt sich Zustand in der Sitzung (aktive Klasse, aktive Person, Schuljahr). Darum pro Sitzung
strikt nacheinander; für parallele Arbeit mehrere Sitzungen (eigene Anmeldungen) verwenden.
