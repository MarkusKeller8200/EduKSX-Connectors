"""Testplattform lokal starten (wird von start-testplattform.bat / .command aufgerufen).

Liest testplattform/.env (falls vorhanden), startet die Plattform nur auf diesem Rechner (127.0.0.1) und öffnet
den Browser. API-Keys der APIs liest die Plattform aus der Umgebung bzw. aus apis/<name>/.env – sie bleiben auf
dem Rechner und gehen nie an den Browser.
"""
from __future__ import annotations

import os
import sys
import threading
import time
import webbrowser
from pathlib import Path

HIER = Path(__file__).resolve().parent


def env_laden(datei: Path) -> None:
    if not datei.exists():
        return
    for z in datei.read_text(encoding="utf-8").splitlines():
        z = z.strip()
        if z and not z.startswith("#") and "=" in z:
            k, v = z.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def main() -> None:
    env_laden(HIER / ".env")
    port = int(os.environ.get("TESTPLATTFORM_PORT", "8090"))
    basis = f"http://127.0.0.1:{port}"
    sys.path.insert(0, str(HIER))
    from testplattform.app import plugins_aus_repo

    print(f"Testplattform startet auf {basis}")
    for p in plugins_aus_repo():
        print(f"  {p.titel:<15} {p.version:<8} {p.base_url:<26} API-Key {'hinterlegt' if p.api_key else 'fehlt'}")
    print("Die APIs selbst separat starten (z. B. start-escola, uvicorn cmi_api.app:app --port 8082).")
    print("Beenden mit Ctrl+C.\n")
    if "--ohne-browser" not in sys.argv:
        threading.Thread(target=lambda: (time.sleep(2), webbrowser.open(basis)), daemon=True).start()
    import uvicorn
    uvicorn.run("testplattform.app:app", host="127.0.0.1", port=port, log_level="info")


if __name__ == "__main__":
    main()
