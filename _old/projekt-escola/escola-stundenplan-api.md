# Escola Stundenplan – PHP-Endpunkte (sekbuelach.ch)

Mitgeschnitten am 14.11.2026 im eingeloggten Admin-Bereich. Basis: `https://www.sekbuelach.ch/`

Darauf aufbauend: **Lese-API `escola-api`** (Python/FastAPI, siehe `claude/escola-api-readme.md`).

## Authentifizierung
- **Kein API-/Bearer-Token.** Anmeldung über klassisches PHP-Session-Cookie (HttpOnly, für JS unsichtbar).
- Login-Seite `/escola/login` ist ein mehrstufiges htmx-Formular → für Automatisierung Session-Cookie einer bestehenden Anmeldung übernehmen.
- **Kein CSRF-Token** in den Stundenplan-Aufrufen gefunden.
- Aufrufe funktionieren direkt per `fetch(..., {credentials:'same-origin'})` im eingeloggten Browser (lesen und schreiben getestet).
- Antworten sind meist **HTML-Fragmente** (Prototype.js `Ajax.Updater`), kein JSON.

## Klasse wählen (Server-Session-Zustand!)
`GET admin.php?page_request=6&klassen_id=<ID>` – setzt die aktive Klasse in der Session. Danach beziehen sich `application_class.php` usw. auf diese Klasse (verifiziert: classId im Antwort-HTML stimmt jeweils). → Aufrufe mit derselben Session nie parallel; für Automatisierung eigene Anmeldung verwenden.

Test-Klasse: **TEST_A1a = klassen_id 120** (für Versuche nutzen).
Hinterbirch (H_*): IDs 92–119 · Mettmenriet (M_*): IDs 65–91 · ID 64 ohne Namen · Arbeitsgruppen Mettmenriet: `workgroup_id` 1, 2 (Stundenplan-Aufruf für Arbeitsgruppen noch unbekannt).

## Stammdaten (Skript: `claude/escola-stammdaten.js`, nur lesend)
| Liste | Quelle | Parsing |
|---|---|---|
| Klassen/Arbeitsgruppen (59) | `GET admin.php?page_request=6` | `select#unifiedClassOrWorkgroupChooser option` (value enthält `klassen_id`/`workgroup_id`, optgroup = Schulhaus) |
| Fächer (13) | Edit-HTML (type=1) einer Zelle in H_A1a | `select#tt_select_* option` → `Name (Kürzel)`; Namen in Escola gekürzt. Nur der Klasse zugeteilte Fächer (Mettmenriet-Klassen: aktuell keine) |
| Räume | Edit-HTML eines **bestehenden** Eintrags | `select#room_id_* option` → `Geschoss - Nr - Bezeichnung [Kürzel]`, optgroup = `Hibi - Trakt A/B/C/P`. **Nur Räume des eigenen Schulhauses** → Hinterbirch 96 Räume; Mettmenriet unbekannt, solange dort kein Eintrag existiert |
| Lehrpersonen (119) | `POST inc/ajax/persons/show_persons_of_group.php` mit `pageRequest=154, personCategory=lehrperson, schoolclassId=null, workgroupId=null, schoolUnitId=1|2, schoolYear=0, searchMode=0` | `li#li_<personId>`, `#name_person_*`, `#vorname_person_*` |

- `schoolUnitId` 1 = Hinterbirch (61 LP), 2 = Mettmenriet (58 LP).
- `personId` der Lehrperson = `teacherId` für type=2 im Stundenplan (verifiziert: 135 Riedhofer Marco, 643 Ulminger Remo).
- LP-Kürzel (z. B. RiMa) ist nicht als Feld vorhanden, sondern berechnet: 2 Buchstaben Nachname + 2 Vorname. Doppelt: EgDo (Eghofer/Nefmatter), PfTi (Pfishofer/Bernli). Escola entfernt Akzente, behält Umlaute (Laninger Flurina → StFe, Oberhofer → ObMa).
- Raumkürzel A105 ist doppelt vergeben (ID 13 EG-105 und ID 37 UG-005) → immer roomId verwenden.
- Die Parameter `schoolclassId`/`workgroupId` müssen als String `null` gesendet werden, sonst „Es ist ein Fehler aufgetreten.“

## Raster – je Schulhaus verschieden!
- `dayCode`: A=Mo, B=Di, C=Mi, D=Do, E=Fr
- **Hinterbirch** `lessonId` 2–12: 2=07.30–08.15, 3=08.20, 4=09.10, 5=10.15, 6=11.05, 7=12.00, 8=13.10–13.55, 9=14.00, 10=15.00, 11=15.50, 12=16.40–17.25
- **Mettmenriet** `lessonId` 24–34: 24=07.30–08.15, 25=08.20, 26=09.10, 27=10.15, 28=11.05, 29=12.00, 30=13.00–13.45, 31=13.50, 32=14.40, 33=15.35, 34=16.25–17.10
- Quelle: `.timetable-lessons` (zwei `nobr` = von/bis) in jeder Zeile von `application_class.php` mode=0
- `semester`: 1 / 2 · `schoolYear`: 0 = aktuelles. Im Editor gibt es keinen Semester-Umschalter; Einträge gelten fürs Schuljahr, Flag „nur 1. Semester“ per type=22.

## Fächer (courseId)
21 BS · 22 BG · 12 D · 15 E · 14 F · 16 Gg · 17 G · 13 M · 19 MI · 20 Mu · 18 NT · 24 RKE · 25 WAH · 99999 „- -“ · 0 leer

**Wichtig:** Die Fach-Auswahl im Editor und die Lehrpersonen-Checkboxen hängen an der **Fächerzuteilung der Klasse**. TEST_A1a hat keine Fächer zugeteilt → Auswahl leer, keine Lehrpersonen wählbar (Speichern eines Fachs per courseId ging trotzdem).

## Endpunkt `inc/ajax/timetable/ajax_functions_timetable.php` (POST, form-urlencoded)
Gemeinsame Felder bei type=1/3: `classOrWorkgroupId, schoolYear=0, semester, dayCode, lessonId, classOrWorkgroupMode=class`

| Zweck | type | weitere Parameter |
|---|---|---|
| Zelle in Bearbeitungsmodus öffnen (liefert Edit-HTML, ändert nichts) | 1 | – |
| **Fach eintragen** ✅ getestet | 1 | `new_entry=1, id=new_<lessonId>_<dayCode>, courseId` → Antwort = Edit-HTML der neuen Zeile |
| Fach eines bestehenden Eintrags ändern | 1 | `new_entry=1, id=<timetableRowId>, courseId` |
| Zusätzlichen Eintrag hinzufügen | 1 | `addCourseField=1, entryType=0` (Fach) / `1` (Text) |
| Eintrag löschen | 1 | `deleteEntry=<timetableRowId>` |
| **Lehrperson an/abwählen** (Checkbox, Toggle) | 2 | `timetableRowId, teacherId` |
| Bearbeitung beenden (liefert Anzeige-HTML) | 3 | – |
| Fussnote hinzufügen | 4 | `rowId` |
| Fussnote löschen | 6 | `id` |
| Freitext speichern (InPlaceEditor) | 7 | `newTextValue` (+ Editor-ID) |
| Geschlecht/Teilgruppe | 8 | `gender, rowId` |
| **Raum setzen** | 18 | `timetableRowId, roomId, roomType` (1/2/3 = Raum 1–3) |
| Nur 1. Semester | 22 | `timetableId, newVal` (0/1) |
| Nur gültig wenn leer | 24 | `timetableId` |
| Fach-Platzhalter | 29 | `timetableEntryId` |

### Edit-HTML (Antwort von type=1) – was man daraus liest
- `timetableRowId`: aus `delete_entry(<rowId>,'A',2)` bzw. Select-ID `tt_select_<rowId>` (`tt_select_new_…` = leere Zelle)
- Fächer: `select#tt_select_<rowId>` (`option[selected]` = aktuelles Fach)
- Räume: `select#room_id_<rowId>` / `room_2_id_` / `room_3_id_` – `option[selected]` = gesetzter Raum
- Lehrpersonen: Checkboxen `input#teacher_<rowId>_<personId>` (`checked` = zugeteilt) mit `edit_teaching_person(rowId, personId)`

## Weitere Endpunkte
- `inc/ajax/timetable/application_class.php` POST `mode=0` → ganzer Stundenplan der aktiven Klasse (HTML); `mode=1` = **gesamten Stundenplan löschen** (Vorsicht!), `mode=9` Teilklassenlegende
- `GET escola/api/timetable/double-booking-notification?timetableId&schoolYear=0&classId[&roomId][&notifyTeacher=1]` → JSON mit Konflikten (Räume/Personen)
- `GET escola/api/timetable/download/pdf/class?schoolYear=0&useSubjectPlaceholder=0&classId=<ID>&semester=0|1|2&export=0` → PDF
- `GET inc/ajax/ajax_functions.php?klassen_id=<ID>&type=1` → „Stundenplan gespeichert“-Aktualisierung

## Stundenplan auslesen (HTML-Struktur, mode=0)
- Zelle: `div#content_<dayCode>_<lessonId>`, darin pro Eintrag `table.stundenplan_innen td`
- `span.timetable-course-name` = Fachkürzel
- `a.tipped[title]` = HTML: `<b>Fach</b><br>LP1<br />LP2<br /><i>Raum1/Raum2</i>`
- 1. `div` = LP-Kürzel (z. B. `RiMa/UlRe`), 2. `div` = Raumkürzel (z. B. `A001/A002`)
- Keine IDs in der Anzeige → IDs über Stammdaten zuordnen oder Edit-HTML (type=1) lesen

## Stand 14.11.2026
- Lesedurchlauf aller 57 Klassen: nur **H_A1a (92)** hat Einträge (34 Lektionen), alle anderen leer.
- Schreibtest: TEST_A1a Mo 07.30 Deutsch angelegt (timetableRowId 35), ohne LP/Raum.

## Ablauf für eine Lektion (schreiben)
1. `GET admin.php?page_request=6&klassen_id=<ID>`
2. type=1 `new_entry=1, id=new_<lesson>_<day>, courseId` → rowId aus Antwort
3. type=18 Raum (roomId aus Raumliste) · type=2 je Lehrperson (personId)
4. type=3 Bearbeitung beenden; optional double-booking-Check

## Noch offen
- Raum- und Lehrpersonen-Setzen live testen (braucht Klasse mit Fächerzuteilung)
- Wo die Fächerzuteilung der Klassen gepflegt wird (Voraussetzung für LP-Auswahl)
- Raumliste Mettmenriet (erst sichtbar mit einem Eintrag in einer Mettmenriet-Klasse)
- Stundenplan-Aufruf für Arbeitsgruppen
