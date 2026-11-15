"""Escola-API lokal starten (wird von start-escola.bat / start-escola.command aufgerufen).

- Beim ersten Start: .env aus .env.example anlegen und zwei Fragen stellen (Schreiben erlauben?, Port).
  Dabei wird ein zufälliger API-Key erzeugt und angezeigt.
- Danach: Werte aus .env laden, API starten, Login und Testseite im Browser öffnen.
Zugangsdaten zu Escola werden hier NICHT gespeichert – die Anmeldung läuft über /login (mit 2FA).
"""
from __future__ import annotations

import os
import secrets
import sys
import threading
import time
import webbrowser
from pathlib import Path

HIER = Path(__file__).resolve().parent
ENV = HIER / ".env"
VORLAGE = HIER / ".env.example"


def frage(text: str, standard: str) -> str:
    try:
        antwort = input(f"{text} [{standard}]: ").strip()
    except EOFError:
        antwort = ""
    return antwort or standard


def env_setzen(zeilen: list[str], name: str, wert: str) -> list[str]:
    neu, gesetzt = [], False
    for z in zeilen:
        if z.split("=", 1)[0].strip() == name and not z.lstrip().startswith("#"):
            neu.append(f"{name}={wert}")
            gesetzt = True
        else:
            neu.append(z)
    if not gesetzt:
        neu.append(f"{name}={wert}")
    return neu


def einrichten() -> None:
    print("\nErster Start – lokale Einstellungen anlegen (.env)\n")
    zeilen = VORLAGE.read_text(encoding="utf-8").splitlines()
    schreiben = frage("Schreiben in Escola erlauben (für die Testseite nötig)? j/n", "j").lower().startswith("j")
    port = frage("Port", "8080")
    key = secrets.token_urlsafe(18)
    zeilen = env_setzen(zeilen, "ESCOLA_SCHREIBEN", "1" if schreiben else "0")
    zeilen = env_setzen(zeilen, "ESCOLA_API_KEY", key)
    zeilen = env_setzen(zeilen, "ESCOLA_PORT", port)
    ENV.write_text("\n".join(zeilen) + "\n", encoding="utf-8")
    print(f"\n.env angelegt. Dein API-Key (auch in .env): {key}")
    print("Den Key auf der Login- bzw. Testseite oben eintragen.\n")


def env_laden() -> None:
    for z in ENV.read_text(encoding="utf-8").splitlines():
        z = z.strip()
        if not z or z.startswith("#") or "=" not in z:
            continue
        k, v = z.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def main() -> None:
    if not ENV.exists():
        einrichten()
    env_laden()
    port = int(os.environ.get("ESCOLA_PORT", "8080"))
    basis = f"http://127.0.0.1:{port}"
    print(f"Escola-API startet auf {basis}")
    print(f"  Anmelden:  {basis}/login")
    print(f"  Testseite: {basis}/testseite")
    print(f"  API-Doku:  {basis}/docs")
    print(f"  Schreiben: {'erlaubt' if os.environ.get('ESCOLA_SCHREIBEN') == '1' else 'aus (nur lesen)'}")
    print("Beenden mit Ctrl+C.\n")
    if "--ohne-browser" not in sys.argv:
        def oeffnen():
            time.sleep(2.5)
            webbrowser.open(basis + "/login")
            webbrowser.open(basis + "/testseite")
        threading.Thread(target=oeffnen, daemon=True).start()
    sys.path.insert(0, str(HIER))
    import uvicorn
    uvicorn.run("escola_api.app:app", host="127.0.0.1", port=port, log_level="info")


if __name__ == "__main__":
    main()
