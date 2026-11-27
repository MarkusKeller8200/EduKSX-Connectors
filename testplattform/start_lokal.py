"""Testplattform lokal starten – mit allen APIs (#50). Aufgerufen von start-testplattform.bat / .command.

    python3 start_lokal.py                 alle APIs aus apis/ und die Plattform starten, Browser öffnen
    python3 start_lokal.py --nur-plattform nur die Plattform (APIs selbst starten)
    python3 start_lokal.py --ohne-browser

- Eine Python-Umgebung für alles (testplattform/.venv): Pakete aller APIs werden installiert, wenn sich eine
  requirements.txt geändert hat.
- Fehlt apis/<name>/.env, wird sie aus .env.example angelegt: zufälliger API-Key, Schreiben AUS (<NAME>_SCHREIBEN=0).
- Läuft eine API schon (Port belegt), wird sie nicht doppelt gestartet.
- Alles lauscht nur auf 127.0.0.1. Ctrl+C beendet Plattform und APIs.
API-Keys und Zugangsdaten bleiben auf diesem Rechner (apis/<name>/.env, nie im Repo).
"""
from __future__ import annotations

import hashlib
import json
import os
import secrets
import socket
import subprocess
import sys
import threading
import time
import webbrowser
from pathlib import Path

HIER = Path(__file__).resolve().parent
REPO = HIER.parent


def env_lesen(datei: Path) -> dict[str, str]:
    werte: dict[str, str] = {}
    if datei.exists():
        for z in datei.read_text(encoding="utf-8").splitlines():
            z = z.strip()
            if z and not z.startswith("#") and "=" in z:
                k, v = z.split("=", 1)
                werte[k.strip()] = v.strip().strip('"').strip("'")
    return werte


def env_setzen(zeilen: list[str], name: str, wert: str) -> list[str]:
    neu, gesetzt = [], False
    for z in zeilen:
        if not z.lstrip().startswith("#") and z.split("=", 1)[0].strip() == name:
            neu.append(f"{name}={wert}")
            gesetzt = True
        else:
            neu.append(z)
    return neu if gesetzt else neu + [f"{name}={wert}"]


def apis(vorlage: bool = False) -> list[tuple[Path, dict]]:
    aus = []
    for datei in sorted((REPO / "apis").glob("*/api.json")):
        info = json.loads(datei.read_text(encoding="utf-8"))
        if str(info.get("name", "")).startswith("_") and not vorlage:
            continue
        aus.append((datei.parent, info))
    return aus


def env_anlegen(ordner: Path, praefix: str) -> bool:
    """apis/<name>/.env aus .env.example anlegen (API-Key zufällig, Schreiben aus). True = neu angelegt."""
    ziel = ordner / ".env"
    if ziel.exists():
        return False
    vorlage = ordner / ".env.example"
    zeilen = vorlage.read_text(encoding="utf-8").splitlines() if vorlage.exists() else []
    zeilen = env_setzen(zeilen, praefix + "API_KEY", secrets.token_urlsafe(18))
    zeilen = env_setzen(zeilen, praefix + "SCHREIBEN", "0")
    ziel.write_text("\n".join(zeilen) + "\n", encoding="utf-8")
    return True


def pakete_installieren(liste: list[Path]) -> None:
    dateien = [p / "requirements.txt" for p in liste if (p / "requirements.txt").exists()] + [HIER / "requirements.txt"]
    stand = hashlib.sha256(b"".join(d.read_bytes() for d in dateien)).hexdigest()
    marke = Path(sys.prefix) / ".eduksx-pakete"
    if marke.exists() and marke.read_text().strip() == stand:
        return
    print("Installiere Pakete aller APIs (einmalig bzw. nach Änderungen) …")
    befehl = [sys.executable, "-m", "pip", "install", "-q"]
    for d in dateien:
        befehl += ["-r", str(d)]
    subprocess.run(befehl, check=True)
    try:
        marke.write_text(stand)
    except OSError:
        pass  # z. B. System-Python ohne Schreibrecht – dann beim nächsten Mal erneut prüfen


def port_belegt(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.3)
        return s.connect_ex(("127.0.0.1", port)) == 0


def weiterleiten(name: str, strom) -> None:
    for zeile in iter(strom.readline, ""):
        print(f"[{name}] {zeile.rstrip()}", flush=True)


def api_starten(ordner: Path, info: dict) -> subprocess.Popen | None:
    name = str(info.get("name", ordner.name))
    praefix = name.lstrip("_").upper() + "_"
    if env_anlegen(ordner, praefix):
        print(f"  {name}: apis/{ordner.name}/.env angelegt (neuer API-Key, Schreiben aus – {praefix}SCHREIBEN=1 zum Schreiben)")
    werte = env_lesen(ordner / ".env")
    port = int(os.environ.get(praefix + "PORT") or werte.get(praefix + "PORT") or (info.get("plugin") or {}).get("port", 8080))
    if port_belegt(port):
        print(f"  {name}: Port {port} belegt – läuft schon, wird nicht neu gestartet")
        return None
    env = {**werte, **os.environ}  # Umgebung geht vor .env
    env.setdefault("PYTHONUNBUFFERED", "1")
    paket = f"{name.lstrip('_')}_api"
    p = subprocess.Popen([sys.executable, "-m", "uvicorn", f"{paket}.app:app", "--host", "127.0.0.1", "--port", str(port)],
                         cwd=ordner, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                         encoding="utf-8", errors="replace")
    threading.Thread(target=weiterleiten, args=(name, p.stdout), daemon=True).start()
    print(f"  {name}: startet auf http://127.0.0.1:{port} (Schreiben {'erlaubt' if werte.get(praefix + 'SCHREIBEN') == '1' else 'aus'})")
    return p


def main() -> None:
    for k, v in env_lesen(HIER / ".env").items():
        os.environ.setdefault(k, v)
    port = int(os.environ.get("TESTPLATTFORM_PORT", "8090"))
    basis = f"http://127.0.0.1:{port}"
    liste = apis(os.environ.get("TESTPLATTFORM_VORLAGE", "0") == "1")
    prozesse: list[subprocess.Popen] = []

    if "--nur-plattform" not in sys.argv:
        pakete_installieren([o for o, _ in liste])
        print("APIs:")
        for ordner, info in liste:
            p = api_starten(ordner, info)
            if p:
                prozesse.append(p)
        time.sleep(1.5)

    sys.path.insert(0, str(HIER))
    from testplattform.app import plugins_aus_repo

    print(f"\nTestplattform startet auf {basis}")
    for p in plugins_aus_repo():
        print(f"  {p.titel:<15} {p.version:<8} {p.base_url:<26} API-Key {'hinterlegt' if p.api_key else 'fehlt'}")
    print("Beenden mit Ctrl+C (beendet auch die gestarteten APIs).\n")
    if "--ohne-browser" not in sys.argv:
        threading.Thread(target=lambda: (time.sleep(2), webbrowser.open(basis)), daemon=True).start()
    import uvicorn
    try:
        uvicorn.run("testplattform.app:app", host="127.0.0.1", port=port, log_level="info")
    finally:
        for p in prozesse:
            p.terminate()
        for p in prozesse:
            try:
                p.wait(timeout=5)
            except subprocess.TimeoutExpired:
                p.kill()


if __name__ == "__main__":
    main()
