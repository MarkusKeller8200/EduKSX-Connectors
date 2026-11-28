"""Thematische Gruppen der Escola-API für Swagger, plugin.json und die Doku auf GitHub Pages.

Jeder Endpunkt gehört zu genau einem Thema (Test: tests/test_themen.py). Reihenfolge = Reihenfolge in der Doku.
"""
from __future__ import annotations

THEMEN: list[tuple[str, str]] = [
    ("Anmeldung und System", "Sitzung mit Benutzername, Passwort und 2FA aufbauen, Status und Fortschritt langer Aufrufe."),
    ("Stammdaten", "Klassen, Arbeitsgruppen, Fächer, Lehrpersonen, Räume, Ressourcen sowie Tage und Lektionen des Rasters."),
    ("Stundenplan", "Einträge lesen, einzeln schreiben, mit dem Stundenplaner abgleichen, Lehrperson ersetzen; "
                    "Stundenplan von Arbeitsgruppen."),
    ("Lehrpersonen und Fächer", "Fächer-Zuteilung und Rechte (KLR/FP/SpM/Abs) je Klasse oder Arbeitsgruppe, aktuelles und "
                                "kommendes Schuljahr; Klassenlehrpersonen; Einsatz einer Lehrperson."),
    ("Schüler:innen", "Schüler:innen lesen, anlegen, ändern und austreten lassen."),
    ("Klassen und Schullaufbahn", "Einteilen, umteilen, aus der Klasse entfernen, Klassenbeginn in der Schullaufbahn setzen."),
    ("Arbeitsgruppen", "Arbeitsgruppen lesen, Schüler:innen einteilen und entfernen."),
    ("Bezugspersonen und Eltern-App", "Eltern/Bezugspersonen verknüpfen, anlegen, Sorgerecht; Eltern einer Klasse mit "
                                      "App-Status; App-Status einer Person."),
    ("Schuljahr vorbereiten", "Klassenlisten, Felder pro Klasse, Vorprüfung von Importlisten."),
    ("Absenzen", "Absenz-Semester, Absenzarten und Einträge pro Klasse oder Schüler:in (Escola-REST)."),
    ("Dokumente", "Schüler:innen-Dokumente: Ordner lesen, Dateien herunterladen, hochladen, löschen (Schalter ESCOLA_DOKUMENTE)."),
    ("Zeugnisse", "Zeugnis-/Formular-Archiv lesen, Zeugnisse als PDF (Schalter ESCOLA_ZEUGNISSE)."),
    ("Mitarbeitende", "Mitarbeitende anlegen, suchen, Schul-Mail und AHV, Austritt."),
    ("Personen und Rollen", "Alle Personen lesen und ändern, aktivieren/deaktivieren, Rollen lesen und zuordnen."),
]

# (Methode, Pfad) -> Thema
ZUORDNUNG: dict[tuple[str, str], str] = {}


def _z(thema: str, *eintraege: str) -> None:
    for e in eintraege:
        m, _, pfad = e.partition(" ")
        ZUORDNUNG[(m, pfad)] = thema


_z("Anmeldung und System", "POST /auth/login", "GET /auth/2fa/methoden", "POST /auth/2fa/methode", "POST /auth/2fa/erneut",
   "POST /auth/2fa", "POST /auth/2fa/app", "GET /auth/2fa/app/{app_token}", "GET /fortschritt", "GET /auth/status",
   "POST /auth/logout", "GET /status")
_z("Stammdaten", "GET /klassen", "GET /faecher", "GET /lehrpersonen", "GET /raeume", "GET /ressourcen",
   "GET /ressourcen/kategorien", "GET /ressourcen/zeiteinteilung", "GET /tage", "GET /lektionen")
_z("Stundenplan", "GET /eintraege", "GET /klassen/{klasse_id}/stundenplan/{tag}/{lektion_id}",
   "POST /klassen/{klasse_id}/stundenplan/{tag}/{lektion_id}",
   "PATCH /klassen/{klasse_id}/stundenplan/{tag}/{lektion_id}/{eintrag_id}",
   "DELETE /klassen/{klasse_id}/stundenplan/{tag}/{lektion_id}/{eintrag_id}",
   "POST /klassen/{klasse_id}/stundenplan/abgleich", "POST /lehrpersonen/{lp_id}/ersetzen", "GET /export",
   "GET /arbeitsgruppen/{ag_id}/stundenplan")
_z("Lehrpersonen und Fächer", "GET /klassen/{klasse_id}/lehrpersonen", "GET /arbeitsgruppen/{ag_id}/lehrpersonen",
   "GET /klassen/{klasse_id}/klassenlehrpersonen", "PUT /klassen/{klasse_id}/klassenlehrpersonen",
   "GET /lehrpersonen/{lp_id}/faecher", "PATCH /lehrpersonen/{lp_id}/faecher", "GET /lehrpersonen/{lp_id}/einsatz")
_z("Schüler:innen", "GET /schueler", "POST /schueler", "GET /schueler/{pid}", "PATCH /schueler/{pid}",
   "POST /schueler/{pid}/austritt")
_z("Klassen und Schullaufbahn", "POST /schueler/{pid}/klasse", "DELETE /schueler/{pid}/klasse",
   "GET /schueler/{pid}/klasse/optionen", "GET /schueler/{pid}/schullaufbahn", "PUT /schueler/{pid}/klasse/beginn",
   "POST /klassen/{klasse_id}/klassenbeginn")
_z("Arbeitsgruppen", "GET /arbeitsgruppen", "GET /schueler/{pid}/arbeitsgruppen", "POST /schueler/{pid}/arbeitsgruppen",
   "DELETE /schueler/{pid}/arbeitsgruppen/{wg_id}")
_z("Bezugspersonen und Eltern-App", "GET /schueler/{pid}/bezugspersonen", "POST /schueler/{pid}/bezugspersonen",
   "GET /personen/{pid}/kinder", "PATCH /schueler/{pid}/bezugspersonen/{beziehung_id}",
   "DELETE /schueler/{pid}/bezugspersonen/{beziehung_id}", "POST /schueler/{pid}/eltern/deaktivieren",
   "GET /klassen/{klasse_id}/eltern", "GET /personen/{pid}/app")
_z("Schuljahr vorbereiten", "GET /klassenlisten", "GET /klassen/{klasse_id}/felder", "POST /import/pruefen")
_z("Absenzen", "GET /klassen/{klasse_id}/absenzen/auswahl", "GET /klassen/{klasse_id}/absenzen", "GET /schueler/{pid}/absenzen")
_z("Dokumente", "GET /schueler/{pid}/dokumente", "GET /schueler/{pid}/dokumente/{datei_id}",
   "POST /schueler/{pid}/dokumente/{ordner_id}", "DELETE /schueler/{pid}/dokumente/{datei_id}")
_z("Zeugnisse", "GET /schueler/{pid}/zeugnisse", "GET /schueler/{pid}/zeugnisse/{zeugnis_id}/pdf",
   "GET /klassen/{klasse_id}/zeugnisse")
_z("Mitarbeitende", "POST /mitarbeitende", "GET /suche/personen", "GET /hilfe/schulmail", "PUT /personen/{pid}/ahv",
   "POST /personen/{pid}/schulmail", "POST /personen/{pid}/austritt", "POST /personen/{pid}/rollen/ausgetreten")
_z("Personen und Rollen", "GET /personen/rollen", "GET /personen", "POST /personen", "POST /personen/{pid}/deaktivieren",
   "POST /personen/{pid}/aktivieren", "GET /personen/{pid}", "PATCH /personen/{pid}", "GET /rollen",
   "GET /personen/{pid}/rollen", "PATCH /personen/{pid}/rollen")


def anwenden(app) -> list[str]:
    """Tags der Routen auf das Thema setzen und die Themen-Reihenfolge in OpenAPI hinterlegen.
    Gibt Routen ohne Thema zurück (sollte leer sein)."""
    from fastapi.routing import APIRoute
    namen = [t for t, _ in THEMEN]
    ohne = []
    for r in app.routes:
        if not isinstance(r, APIRoute) or not r.include_in_schema:
            continue
        for m in sorted(r.methods - {"HEAD", "OPTIONS"}):
            thema = ZUORDNUNG.get((m, r.path))
            if thema is None:
                ohne.append(f"{m} {r.path}")
            elif thema not in namen:
                raise ValueError(f"Unbekanntes Thema {thema!r}")
            else:
                r.tags = [thema]
    app.openapi_tags = [{"name": t, "description": b} for t, b in THEMEN]
    app.openapi_schema = None
    return ohne
