# Betrieb: die APIs in einer Webanwendung nutzen

## Kurz
Die APIs laufen **auf einem Server**, nicht im Browser. Eine Webanwendung (IDA, CONNECT, Testseite) ruft
sie dort per HTTP auf. Lokal als Python-Programm auf dem eigenen Rechner zu laufen ist nur eine
Möglichkeit für Entwicklung und Tests – nötig ist es nicht.

## Warum nicht direkt im Browser?
Eine reine Browser-Anwendung kann Escola nicht selbst ansprechen:
- Escola erlaubt keine Aufrufe von fremden Webseiten (keine CORS-Freigabe); der Browser blockiert sie.
- Die Escola-Anmeldung ist ein Sitzungs-Cookie (HttpOnly), das eine fremde Seite weder lesen noch setzen kann.
- Zugangsdaten, AHV-Prüfung, Schreibschutz und Kontrolle nach dem Schreiben gehören auf einen Server,
  nicht in Code, den jeder Browser herunterlädt.

Darum braucht es immer ein **Backend** zwischen Webanwendung und Escola – genau das ist die Escola-API.

## Varianten

| Variante | Wie | Passt für |
|---|---|---|
| A – eigener Dienst (empfohlen) | API als Docker-Container bzw. `uvicorn` auf einem Schulserver oder einer Cloud-Instanz in der Schweiz; Webanwendung ruft `https://escola-api.…/…` auf | IDA, CONNECT, mehrere Anwendungen gleichzeitig |
| B – im Backend der Webanwendung | Das Backend der Webanwendung (z. B. Python) bindet das Paket `escola_api` direkt ein oder leitet Aufrufe durch | eine einzelne Anwendung mit Python-Backend |
| C – Neubau in der Sprache der Webanwendung | Logik nach Node/TypeScript o. ä. übertragen (es sind reine HTTP-Aufrufe an Escola) | nur wenn Python im Betrieb nicht möglich ist – hoher Aufwand, die Tests müssten mitwandern |

## Was beim Betrieb gilt
- Nur intern bzw. hinter HTTPS und Zugangsschutz betreiben; `ESCOLA_API_KEY` setzen.
- Die Webanwendung ruft die API **von ihrem Server aus** auf (der API-Key gehört nicht in den Browser),
  oder die API liegt unter derselben Adresse wie die Webanwendung hinter einem Reverse Proxy mit Anmeldung.
- Pro Escola-Sitzung laufen Aufrufe nacheinander. Für gleichzeitige Nutzung mehrere Sitzungen (Anmeldungen).
- Personendaten: Standort Schweiz, Protokolle ohne Personendaten, Zugriff nur für berechtigte Mitarbeitende.

## Testseite
Die Testseite (`/testseite`) wird von der API selbst ausgeliefert. Sie läuft also überall dort, wo die API
läuft – lokal unter `http://127.0.0.1:8080/testseite` oder auf dem Server unter dessen Adresse.
