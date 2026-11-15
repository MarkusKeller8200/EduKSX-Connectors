# Escola – Schüler:innen & Dokumente (Analyse 14.11.2026)

## Befund
- **Keine Schüler:innen erfasst:** `personCategory=schueler` liefert für alle 57 Klassen (aktuelles und kommendes Schuljahr) „Es sind keine Personen in dieser Personengruppe vorhanden“. Auch „ohne Klasse“, „zukünftige“, „ehemalige“ SuS und alle Eltern-Kategorien sind leer. Die Personenverwaltung im Browser zeigt dasselbe.
- „alle aktiven Personen“ = 169 (Mitarbeitende), 2 inaktive.
- **Globale Dokumentenvorlage leer:** Root „Schüler:innen-Dokumente“ (Folder 63) hat keine Unterordner, keine Dateien. Keine Konfigurator:innen zugeordnet.

## Personenliste – korrekte Parameter
`POST inc/ajax/persons/show_persons_of_group.php` (form-urlencoded, Prototype-Serialisierung):
`pageRequest=154&personCategory=schueler&schoolclassId=<klassen_id>&workgroupId&schoolUnitId=<1|2>&schoolYear=<0 aktuell|1 kommend>&searchMode=false`
- `workgroupId` ohne Wert (Prototype serialisiert `null` so); für Kategorien ohne Klasse auch `schoolclassId` ohne Wert
- Personendetails: `select_person(<id>)` setzt die Person in der Session, danach `show_reiter.php` / `show_person_details.php` (`pageRequest, personCategory, searchMode`)

## Dokumenten-API (JSON, `apiBasePath` = `/escola/api/`)
Gefunden im Frontend-Bundle (Komponente `escola-docs-folder`):
| Zweck | Aufruf |
|---|---|
| Root lesen | `GET docs/root/{rootType}/{rootSubtype}/{foreignId}` → `{id, rootFolderId}` |
| Ordner lesen | `GET docs/root/{…}/folders/{folderId}` → `{id, name, parentFolderId, path[], folders[], files[], authorizationState, isReachableForGuardians, isReachableForStudents, accessLevel, …}` |
| Zuletzt geänderte Dateien | `GET docs/root/{…}/recent-files?page=n[&search=…]` |
| Datei-Download-URL | `docs/root/{…}/folder-files/{fileId}` (+ `/json-web-token` für signierten Link) |
| Schreibend (nicht verwenden) | `POST …/folders`, `PATCH …/folders/{id}`, `DELETE …/folders/{id}`, `POST …/folders/{id}/files` |
- Globale SuS-Vorlage: `rootType=global, rootSubtype=students, foreignId=null` → Root 1, Folder 63
- Pro Schüler:in vermutlich eigener Root mit `foreignId=<personId>` – rootType/rootSubtype noch zu bestätigen, sobald SuS existieren
- Dokumenten-Sets (Alternative): `GET docs/set/{setType}/{foreignId}/sets/{setId}`, Download `…/files/{fileId}/download`

## Nächste Schritte
- Klären, wo die SuS mit Dokumenten tatsächlich liegen (anderes System/Instanz? Import ausstehend?)
- Sobald 1 SuS mit Dokumenten existiert: Netzwerkaufrufe des Reiters „Dokumente“ mitschneiden → rootType/foreignId bestätigen → Export (Baum + Download) in escola-api ergänzen
