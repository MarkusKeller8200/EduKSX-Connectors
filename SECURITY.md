# Sicherheit

## Unterstützte Versionen

Sicherheitskorrekturen gibt es für die jeweils **neueste Version** bzw. den aktuellen Stand auf `main`.

## Sicherheitslücke melden

Bitte **kein Issue** für Sicherheitslücken anlegen – auch nicht in einem privaten Repository: Issues sehen alle
Mitwirkenden, und Benachrichtigungen gehen per E-Mail hinaus.

1. Melden: direkt an den Eigentümer dieses Repositorys (E-Mail oder Teams).
2. Beschreiben: betroffene Version, Schritte zum Nachstellen, mögliche Auswirkung. Keine Zugangsdaten und keine
   echten Personendaten mitschicken.

Private Sicherheitsmeldungen über GitHub («Report a vulnerability») gibt es nur bei öffentlichen Repositorys.

## Was dich erwartet

- Eingangsbestätigung innerhalb von **5 Arbeitstagen**.
- Einschätzung und, wenn bestätigt, Korrektur in der nächsten Version – je nach Schwere als Bugfix-Version. Danach
  Eintrag im CHANGELOG unter «Behoben» (ohne Angriffsdetails), auf Wunsch mit Nennung der meldenden Person.
- Wird die Meldung abgelehnt (z. B. kein Sicherheitsproblem oder ausserhalb des Projekts), gibt es eine Begründung.

## Grundsätze

- Personendaten nur so weit wie nötig bearbeiten (Datensparsamkeit); Testdaten immer erfunden
- Personendaten nach IDG (Kanton Zürich) bearbeiten (Zweckbindung, Verhältnismässigkeit, Informationssicherheit)
- Schutzbedarf «vertraulich»: Daten verschlüsselt speichern und übertragen, Zugriffe protokollieren
- Keine echten Daten in Tests, Issues, Protokollen und Bildschirmfotos
- Zugangsdaten, Tokens und Schlüssel nie im Repository; nur verschlüsselt bzw. im Schlüsselbund speichern
- Anmeldung über Microsoft Entra ID; Rechte über Gruppen, nicht über einzelne Konten
