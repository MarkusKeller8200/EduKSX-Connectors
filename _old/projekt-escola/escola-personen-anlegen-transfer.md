# Escola – Personen anlegen & SuS einer Klasse zuordnen

Ermittelt am 14.11.2026 (Analyse Frontend, Mitschnitt eines Transfers durch den Admin, Live-Test im Testsystem).
Umgesetzt in der Escola-API v1.3: `POST /schueler`, `POST /personen`, `POST /schueler/{id}/klasse`, `GET /schueler?ohne_klasse=true`.

## Neue Person anlegen ✅ live getestet
Escola-Komponente `escola-capture-new-person` (Button „Neue Person“ in der Personenverwaltung).

`POST rpc/collections/CaptureNewPersonAdmin/<methode>.php` (JSON)
```json
{
  "parameters": {"newPersonStruct": {"id": -1, "firstName": "…", "lastName": "…", "gender": "w|m|d"}},
  "rpcContext": {"personCategoryGroup": "students-without-schoolclass", "schoolclassId": null, "schoolUnitId": 1}
}
```
- `checkForDuplicatePersonsRpc` → `null` (keine Duplikate) oder
  `{"duplicatePersonStructs": [{"id", "displayName", "gender", "listOfAllRoles", "personPictureUrl", "active"}]}`
- `captureNewPersonRpc` → `[<neue ID>, ""]` (Test: `[652,""]`)
- `personCategoryGroup` bestimmt die Rolle: `schueler` (+ `schoolclassId`), `students-without-schoolclass`, `future-students`, `lehrperson`, `gruppe_4` (Schulverwaltung) …
- `schoolUnitId`: 1 = Hinterbirch, 2 = Mettmenriet

## SuS in eine Klasse transferieren ✅ mitgeschnitten + live getestet
1. Person wählen: `POST inc/ajax/persons/show_reiter.php` `active_person=<id>`
2. Formular öffnen: `POST inc/ajax/persons/personManagement.php` `mode=13&transferSchoolyear=0&pageRequest=154&activePersonId=<id>`
   → HTML mit Klassenauswahl (`klassen_id_transfer`)
3. Transfer: `POST inc/ajax/persons/personManagement.php`
   `klassen_id_transfer=<klasse>&transferDate=JJJJ-MM-TT&Submit=Transfer ausführen&mode=14&pageRequest=154&activePersonId=<id>&transferSchoolyear=0|1`
   → `<div class="alert alert-success">… wurde ab <Datum> in die Klasse … transferiert.`
4. Widerrufen (Link in der Erfolgsmeldung): `personManagementGotoMode(16, {transferSchoolyear, transferDate})` → `mode=16` (nicht getestet)

- Mehrfachauswahl in der Liste läuft über `mode=17&action=1006|1007&element_string=:<id>:<id>:` (nicht getestet).

## Testdaten im Testsystem (14.11.2026)
- 650 „SuS SuS“ (H_A1a, alle Felder mit Testwerten)
- 651 „SUS OHNE KLASSE“ → vom Admin nach H_A1a transferiert
- 652 „Test Anlegen“ → per API-Aufruf ohne Klasse angelegt, dann nach TEST_A1a (120) transferiert

## Hinweis
Gleiche Datei `personManagement.php` führt mit anderen `mode`/`action`-Werten auch Deaktivieren/Löschen aus → nur die oben dokumentierten Werte verwenden.
