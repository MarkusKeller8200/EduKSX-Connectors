# Escola – Felder einer Schülerin / eines Schülers

Erhoben am 14.11.2026 an der Testperson **„SuS SuS“** (Datenbank-ID 650, Klasse H_A1a, Hinterbirch).
Status: ✅ mit Testwert befüllt und nachgeprüft · ⏭️ bewusst nicht befüllt · ➖ schon vorhanden / Standard belassen

## Reiter „Name“
| Feld | interner Name | Typ | Testwert | Status |
|---|---|---|---|---|
| Name | `name` | Text | sus | ➖ |
| Vorname | `vorname` | Text | sus | ➖ |
| Schüler:innen-Nummer | `student_number` | Zahl | 999650 | ✅ |
| Titel | `titel` | Text | Test | ✅ |
| alternativer Name (optional) | `alternative_last_name` | Text | Testname | ✅ |
| alternativer Vorname (optional) | `alternative_first_name` | Text | Testvorname | ✅ |
| Geschlecht | – | Auswahl (weiblich/männlich) | weiblich | ➖ |
| Abkürzung | `abbr` | Text | SuSu | ✅ |
| Portrait | – | Datei-Upload | – | ⏭️ |

## Reiter „Login & Einstellungen“
| Feld | Typ | Status |
|---|---|---|
| Benutzername | Text (sus.sus) | ⏭️ Login nicht verändert |
| Passwort (2×) | Passwort | ⏭️ |
| Haupt-E-Mail-Adresse | Auswahl | ⏭️ |
| Benachrichtigung | Checkbox (ja) | ⏭️ |
| Nachrichten: Zielsprache Übersetzungen | Auswahl (145 Sprachen) | ⏭️ |
| Kontaktmöglichkeit | Checkbox (ja) | ⏭️ |
| Person kann den Benutzernamen ändern | Checkbox (ja) | ⏭️ |
| Person kann das Passwort ändern | Checkbox (ja) | ⏭️ |

## Reiter „Passkeys“
Keine Eingabefelder (Verwaltung von Passkeys der Person) – ⏭️

## Reiter „Personalien“
| Feld | interner Name | Typ | Testwert | Status |
|---|---|---|---|---|
| Geburtsdatum | `geburtstag` | Datum | 01.01.2013 | ✅ |
| Beruf | `beruf` | Text | Schüler:in (Test) | ✅ |
| Nationalität | `nationality_id` | Auswahl (203 Länder) + Freitext „anderes Land“ | Schweiz | ✅ |
| Heimatort | `heimatort` | Text | Bülach | ✅ |
| Geburtsort | `place_of_birth` | Text | Bülach | ✅ |
| Umgangssprache | `colloquial_language_id` | Auswahl (92 Sprachen) + Freitext | Deutsch | ✅ |
| Erstsprache (Muttersprache) | `mothertongue_id` | Auswahl (92 Sprachen) + Freitext | Deutsch | ✅ |
| weitere Sprachen | `other_languages` | Text | Englisch | ✅ |
| Aufenthaltsbewilligung | `residence_permit` | Auswahl (18 Arten) | Schweizer Bürger:in | ✅ |
| Aufenthaltsbewilligung gültig von / bis | – | Datum | – | ⏭️ (bei CH-Bürger:in nicht nötig) |
| Religion | `religion` | Text | Test | ✅ |
| Konfession | `konfession` | Text | Test | ✅ |
| AHV-Nummer | `ahv` | Text | – | ⏭️ amtliche Nummer |
| Eintrittsdatum | `eintritt` | Datum | 18.08.2025 | ✅ |
| Eintrittsdatum Kindergarten | `entry_date_kindergarden` | Datum | 21.08.2017 | ✅ |
| Eintrittsdatum 1. Klasse | `entry_date_first_class` | Datum | 19.08.2019 | ✅ |
| Eintrittsdatum Oberstufe | `entry_date_secondary_school` | Datum | 18.08.2025 | ✅ |
| Austrittsdatum | `austritt` | Datum | – | ⏭️ könnte die Person austreten lassen |
| IBAN | – | Text | – | ⏭️ Bankdaten |
| BIC/SWIFT | – | Text | – | ⏭️ Bankdaten |
| Wegzugsdatum | `departure_timestamp` | Datum | – | ⏭️ wie Austritt |
| Name Wegzugsgemeinde | – | Text | – | ⏭️ |
| Zuzugsdatum | `arrival_timestamp` | Datum | 01.07.2020 | ✅ |
| Name Zuzugsgemeinde | `arrival_municipality_name` | Text | Winterthur | ✅ |
| Fremd-ID | `foreign_id` | Text | TEST-650 | ✅ |

## Reiter „Bezugspersonen & Institutionen“
Keine direkten Felder. Hier werden Eltern/Bezugspersonen und Institutionen **als eigene Personen verknüpft**, je mit „sorgeberechtigt“ / „informationsberechtigt“ (`saveGuardianSettings.php`). – ⏭️ (bräuchte eigene Test-Elternpersonen)

## Reiter „Privat“
| Feld | interner Name | Typ | Testwert | Status |
|---|---|---|---|---|
| Adresse wie | `same_address_as` | Auswahl (eigene Adresse / Adresse einer Bezugsperson) | Eigene Adresse | ➖ |
| Strasse, Nr. | `strasse` | Text | Teststrasse 1 | ✅ |
| PLZ & Wohnort | `private_town_id` | Auswahl (4114 Orte) + Freitext PLZ/Ort | 8180 Bülach – ZH | ✅ |
| Politische Gemeinde | `private_civil_commune_federal_statistical_office_code` | Auswahl (2117 Gemeinden) | Bülach – ZH | ✅ |
| Land | `private_country_id` | Auswahl + Freitext | Schweiz | ✅ |
| c/o-Adresszusatz | `care_of` | Text | Test | ✅ |
| Telefon 1 | `telefon` | Text | 044 000 00 01 | ✅ |
| Telefon 2 | `telefon_2` | Text | 044 000 00 02 | ✅ |
| Telefon mobil | `natel` | Text | 079 000 00 01 | ✅ |
| E-Mail (privat) | `email_privat` | Text | sus.sus@example.com | ✅ |
| Homepage | `website` | Text | https://example.com | ✅ |
| Notfall-Telefon: Nummer / Person | `emergency_phone`, `emergency_phone_person` | Text | 079 000 00 02 / Test Notfallkontakt | ✅ |
| Notfall-Telefon 2: Nummer / Person | `emergency_phone_2`, `emergency_phone_2_person` | Text | 079 000 00 03 / Test Notfallkontakt 2 | ✅ |
| **Zukünftige Adresse** (Klassenzuteilung): Strasse | `class_allocation_future_address_street` | Text | Teststrasse | ✅ |
| … Hausnummer | `class_allocation_future_address_house_number` | Text | 2 | ✅ |
| … PLZ & Ort | `class_allocation_future_address_commune_id` | Auswahl + Freitext | 8180 Bülach – ZH | ✅ |
| … Land | `class_allocation_future_address_country_id` | Auswahl + Freitext | Schweiz | ✅ |
| … c/o-Adresszusatz | `class_allocation_future_address_care_of` | Text | Test | ✅ |

## Reiter „Schule“
| Feld | interner Name | Typ | Testwert | Status |
|---|---|---|---|---|
| E-Mail (Schule) | `email` | Text | sus.sus@example.com | ✅ |
| Homepage | `website_g` | Text | https://example.com | ✅ |

## Reiter „Geschwister“
Anzeige der verknüpften Geschwister (0) – keine Felder.

## Reiter „Rollen“
27 Rollen-Checkboxen (Schüler:innen ✔, Eltern, Ärzt:innen, Lehrpersonen/Schulleitung/Admin/Klassenassistenz/Hausdienst/Berufswahlcoach/Praktikant/SSA je Hinterbirch und Mettmenriet, Superadmin, Geschäftsleitung, Schulbehörde, Schulbehörden-Mitglieder, Schulverwaltung, Di Medio, RPK). – ⏭️ Berechtigungen nicht verändert

## Reiter „Export“
Keine Felder (Export-/Sync-Status).

## Reiter „BISTA“ (Bildungsstatistik)
| Feld | Typ | Testwert | Status |
|---|---|---|---|
| Schulort Vorjahr | Auswahlknopf (4 Werte) | Kanton ZH/TG/GL/GR | ✅ |
| Lehrplanstatus | Auswahlknopf (10/20/30) | Unterricht nach Regellehrplan | ✅ |
| Integrierte Sonderschulung | Auswahlknopf (0–3) | kein Sonderschulstatus | ✅ |
| abweichende Schulgemeinde (Sgem) | Auswahl (214) | Standard-Wert | ➖ |
| Bista-Code SA/Schulart | Auswahl (26) | Standard-Wert | ➖ |

## Reiter „Weitere Infos“, „Escola App“, „Dokumente“
Für dieses Admin-Konto ohne Eingabefelder. „Dokumente“ wird leer geliefert, die Dokumenten-API antwortet mit 403 (keine Berechtigung).

## Technik (Speichern)
- Bearbeitungsmodus: `POST inc/ajax/persons/ajax_functions_persons.php` `type=1, edit_mode=1`
- Person wählen: `POST inc/ajax/persons/show_reiter.php` `active_person=<id>`; Reiter: `show_person_details.php` `active_section=<name|login|personalien|eltern|privat|geschaeft|rollen|sync|additional_fields_1|additional_fields_2|documents|mobile>`
- Text/Auswahl: `ajax_functions_persons.php` `type=2, feld=<verschlüsselter Feldschlüssel>, wert, person_encrypted, additional_field, prev`
- Datum: `type=7, dd, mm, yyyy, person=<verschlüsselt>, feld=<verschlüsselt>, additionalField`
- Auswahlknopf: `type=2, wert=<Schlüssel>`
- Feld- und Personenschlüssel (`V2$…`) sind verschlüsselt und pro Sitzung neu → immer aus dem HTML des Reiters lesen (`onchange="save_field('<feld>','<intern>','<person>',<id>,<add>)"`).
