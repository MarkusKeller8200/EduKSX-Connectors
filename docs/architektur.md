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

## Testplattform und Plugin-Beschreibung

Jede API beschreibt sich selbst (`GET /plugin.json`, aus OpenAPI + `api.json`, Entscheid #42). Die
**Testplattform** (`testplattform/`, Port 8090, nur lokal) liest diese Beschreibungen und baut je API eine
Testseite; Aufrufe gehen über die Plattform, die den API-Key setzt. Das **Intranet** übernimmt dieselbe Beschreibung
als Plugin (`intranet:plugin-from-openapi`, sek-intranet#229).

```
Browser ─► Testplattform :8090 ─► apis/escola :8080 · apis/slplaner :8081 · apis/cmi :8082
Intranet (Laravel) ◄── plugin.json ──┘
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
