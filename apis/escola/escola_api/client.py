"""Lesender Client für Escola (sekbuelach.ch).

Authentifizierung: Escola nutzt ein PHP-Session-Cookie, kein API-Token. Der Client
übernimmt das Cookie einer bestehenden Browser-Anmeldung (Header `Cookie`).

WICHTIG: Escola merkt sich die "aktive Klasse" in der Session. Deshalb laufen alle
Aufrufe strikt nacheinander (Lock) – nie parallel mit derselben Session.
"""
from __future__ import annotations

import re
import threading
import time
from dataclasses import dataclass, field

import httpx

from . import parsers as P

TT = "inc/ajax/timetable/ajax_functions_timetable.php"


class KonfliktFehler(RuntimeError):
    """Daten passen nicht (z. B. AHV/E-Mail schon vergeben). `personen` nennt die Betroffenen."""
    def __init__(self, meldung: str, personen: list | None = None):
        super().__init__(meldung)
        self.personen = personen or []


class SessionAbgelaufen(RuntimeError):
    """Escola hat auf die Login-Seite umgeleitet – Cookie erneuern."""


@dataclass
class EscolaConfig:
    base_url: str = "https://www.sekbuelach.ch/"
    cookie: str = ""  # kompletter Cookie-Header aus dem Browser, z. B. "PHPSESSID=…"
    # Escola-Schuleinheiten (schoolUnitId) -> Schulhausname
    schuleinheiten: dict[int, str] = field(default_factory=lambda: {1: "Hinterbirch", 2: "Mettmenriet"})
    timeout: float = 30.0
    cache_sekunden: int = 600


class EscolaClient:
    def __init__(self, cfg: EscolaConfig, transport: httpx.BaseTransport | None = None):
        self.cfg = cfg
        self._lock = threading.RLock()
        self._cache: dict[str, tuple[float, object]] = {}
        # Zähler aller Anfragen an Escola (für Fortschrittsanzeige: GET /fortschritt)
        self.zaehler = 0
        self.zuletzt = ""
        self._http = httpx.Client(
            event_hooks={"request": [self._zaehlen]},
            base_url=cfg.base_url,
            # Mit ESCOLA_COOKIE: fester Cookie-Header. Ohne: Cookies aus dem Login (/auth/login)
            # landen im Cookie-Speicher dieses Clients – nur im Arbeitsspeicher, nie auf Disk.
            headers={k: v for k, v in {
                "Cookie": cfg.cookie,
                "User-Agent": "escola-api/1.1",
                "X-Requested-With": "XMLHttpRequest",
                # Escola prüft bei login.php (und evtl. weiteren POSTs) den Referer ("Referrer check failed")
                "Referer": cfg.base_url.rstrip("/") + "/admin.php",
                "Origin": cfg.base_url.rstrip("/").split("/", 3)[0] + "//" + cfg.base_url.split("/")[2] if "://" in cfg.base_url else None,
            }.items() if v},
            timeout=cfg.timeout,
            follow_redirects=False,
            transport=transport,
        )

    # ------------------------------------------------------------------ HTTP
    def _zaehlen(self, req: httpx.Request) -> None:
        self.zaehler += 1
        self.zuletzt = req.url.path.rsplit("/", 1)[-1]

    def _check(self, r: httpx.Response) -> str:
        loc = r.headers.get("location", "")
        if r.status_code in (301, 302, 303) and "login" in loc.lower():
            raise SessionAbgelaufen("Escola-Session abgelaufen (Umleitung auf Login)")
        r.raise_for_status()
        text = r.text
        if "<title>Escola - Login</title>" in text:
            raise SessionAbgelaufen("Escola-Session abgelaufen (Login-Seite erhalten)")
        return text

    def _get(self, url: str) -> str:
        return self._check(self._http.get(url))

    def _post(self, url: str, data: dict) -> str:
        return self._check(self._http.post(url, data={k: str(v) for k, v in data.items()}))

    def _cached(self, key: str, fn, refresh: bool = False):
        now = time.time()
        if not refresh and key in self._cache and now - self._cache[key][0] < self.cfg.cache_sekunden:
            return self._cache[key][1]
        val = fn()
        self._cache[key] = (now, val)
        return val

    # ------------------------------------------------------------------ Bausteine
    def _aktivieren(self, k: dict) -> None:
        param = "klassen_id" if k["typ"] == "Klasse" else "workgroup_id"
        self._get(f"admin.php?page_request=6&{param}={k['id']}")

    def _stundenplan_html(self, k: dict) -> str:
        self._aktivieren(k)
        return self._post("inc/ajax/timetable/application_class.php", {"mode": 0})

    def _zelle_ansehen(self, k: dict, tag: str, lektion_id: int) -> str:
        """Bearbeitungsansicht öffnen und sofort wieder schliessen (ändert keine Daten)."""
        cell = {
            "classOrWorkgroupId": k["id"], "schoolYear": 0, "semester": 1,
            "dayCode": tag, "lessonId": lektion_id, "classOrWorkgroupMode": "class",
        }
        try:
            return self._post(TT, {**cell, "type": 1})
        finally:
            self._post(TT, {**cell, "type": 3})

    def status(self) -> dict:
        with self._lock:
            html = self._get("admin.php?page_request=6")
            return {"angemeldet": True, "klassen_im_menue": len(P.parse_klassen(html))}

    # ------------------------------------------------------------------ Stammdaten
    def klassen(self, refresh: bool = False) -> list[dict]:
        def load():
            with self._lock:
                return P.parse_klassen(self._get("admin.php?page_request=6"))
        return self._cached("klassen", load, refresh)

    def _klassen_nur(self, refresh=False) -> list[dict]:
        return [k for k in self.klassen(refresh) if k["typ"] == "Klasse"]

    def lehrpersonen(self, refresh: bool = False) -> list[dict]:
        def load():
            res: dict[int, dict] = {}
            with self._lock:
                for unit, schulhaus in self.cfg.schuleinheiten.items():
                    html = self._post("inc/ajax/persons/show_persons_of_group.php", {
                        "pageRequest": 154, "personCategory": "lehrperson",
                        "schoolclassId": "null", "workgroupId": "null",
                        "schoolUnitId": unit, "schoolYear": 0, "searchMode": 0,
                    })
                    if len(html) < 100:  # "Es ist ein Fehler aufgetreten."
                        continue
                    for p in P.parse_lehrpersonen(html):
                        e = res.setdefault(p["id"], {**p, "kuerzel": P.lp_kuerzel(p["nachname"], p["vorname"]), "schulhaeuser": []})
                        if schulhaus not in e["schulhaeuser"]:
                            e["schulhaeuser"].append(schulhaus)
            return sorted(res.values(), key=lambda x: (x["nachname"], x["vorname"]))
        return self._cached("lehrpersonen", load, refresh)

    def raster(self, refresh: bool = False) -> dict[str, dict]:
        """Tage + Lektionen je Schulhaus (die Schulhäuser haben eigene Lektions-IDs/Zeiten)."""
        def load():
            out: dict[str, dict] = {}
            with self._lock:
                for k in self._klassen_nur(refresh):
                    sh = k["schulhaus"]
                    if sh in out or not k["name"]:
                        continue
                    out[sh] = {"schulhaus": sh, "referenzklasse": k["name"], **P.parse_raster(self._stundenplan_html(k))}
            return out
        return self._cached("raster", load, refresh)

    def _alle_stundenplaene(self, refresh: bool = False) -> list[tuple[dict, list[dict]]]:
        def load():
            res = []
            with self._lock:
                for k in self._klassen_nur(refresh):
                    res.append((k, P.parse_stundenplan(self._stundenplan_html(k))))
            return res
        return self._cached("stundenplaene", load, refresh)

    def faecher(self, refresh: bool = False) -> list[dict]:
        """Fächer aus der Fachauswahl. Escola zeigt dort nur Fächer, die der Klasse
        zugeteilt sind – darum wird je Schulhaus die erste Klasse mit Fächern genommen."""
        def load():
            res: dict[int, dict] = {}
            with self._lock:
                for sh in sorted({k["schulhaus"] for k in self._klassen_nur(refresh)}):
                    for k in [x for x in self._klassen_nur(refresh) if x["schulhaus"] == sh and x["name"]]:
                        lekt = self.raster(refresh).get(sh, {}).get("lektionen", [])
                        if not lekt:
                            break
                        f = P.parse_faecher(self._zelle_ansehen(k, "A", lekt[0]["id"]))
                        if f:
                            for x in f:
                                res.setdefault(x["id"], {**x, "schulhaeuser": []})["schulhaeuser"].append(sh)
                            break
            # volle Namen aus den Stundenplan-Tooltips ergänzen (Auswahl zeigt gekürzte Namen)
            voll = {e["fach_kuerzel"]: e["fach"] for _, es in self._alle_stundenplaene(refresh) for e in es}
            for x in res.values():
                x["name"] = voll.get(x["kuerzel"], x["name_kurz"])
            return sorted(res.values(), key=lambda x: x["name"])
        return self._cached("faecher", load, refresh)

    # ------------------------------------------------------------------ Modul Ressourcen
    RV = "inc/ajax/raumverwaltung/"

    def ressourcen(self, refresh: bool = False) -> list[dict]:
        """Alle Ressourcen aus dem Modul Ressourcen (beide Schulhäuser, mit Kategorie und Zeitprofil).
        Die IDs sind dieselben wie die Raum-IDs im Stundenplan."""
        def load():
            with self._lock:
                return P.parse_ressourcen(self._post(self.RV + "rooms.php", {}))
        return self._cached("ressourcen", load, refresh)

    def zeiteinteilung(self, refresh: bool = False) -> list[dict]:
        """Zeiteinteilungs-Profile des Moduls Ressourcen (z. B. „HIBI – Lektionen“) mit allen Zeiten."""
        def load():
            with self._lock:
                start = self._post(self.RV + "stundeneinteilung.php", {})
                profile, gewaehlt = P.parse_zeitprofile(start)
                out = []
                try:
                    for p in profile:
                        html = start if p["id"] == gewaehlt else \
                            self._post(self.RV + "stundeneinteilung.php", {"mode": 0, "selectedProfile": p["id"]})
                        out.append({**p, "zeiten": P.parse_zeiten(html)})
                finally:
                    if gewaehlt is not None and len(profile) > 1:  # Auswahl wie vorher
                        self._post(self.RV + "stundeneinteilung.php", {"mode": 0, "selectedProfile": gewaehlt})
                return out
        return self._cached("zeiteinteilung", load, refresh)

    def raeume(self, refresh: bool = False) -> dict[str, list[dict]]:
        """Räume je Schulhaus – aus dem Modul Ressourcen (vollständig für beide Schulhäuser).
        Fallback, falls das Modul nicht erreichbar ist: Raumauswahl eines Stundenplan-Eintrags."""
        try:
            res = self.ressourcen(refresh)
        except (httpx.HTTPError, SessionAbgelaufen) as e:
            if isinstance(e, SessionAbgelaufen):
                raise
            res = []
        if res:
            out: dict[str, list[dict]] = {}
            for r in res:
                if r.get("kategorie_typ", "Räume") not in ("Räume", ""):
                    continue
                out.setdefault(r["schulhaus"] or "unbekannt", []).append(
                    {k: r[k] for k in ("id", "kuerzel", "name", "geschoss", "nummer", "bezeichnung")}
                    | {"gruppe": r["kategorie"], "schulhaus": r["schulhaus"]})
            return out
        return self._raeume_aus_stundenplan(refresh)

    def _raeume_aus_stundenplan(self, refresh: bool = False) -> dict[str, list[dict]]:
        def load():
            out: dict[str, list[dict]] = {}
            with self._lock:
                for k, eintraege in self._alle_stundenplaene(refresh):
                    sh = k["schulhaus"]
                    if sh in out or not eintraege:
                        continue
                    e = eintraege[0]
                    r = P.parse_raeume(self._zelle_ansehen(k, e["tag_code"], e["lektion_id"]))
                    if r:
                        out[sh] = [{**x, "schulhaus": sh} for x in r]
            for sh in {k["schulhaus"] for k in self._klassen_nur(refresh)}:
                out.setdefault(sh, [])  # leer = noch kein Eintrag in diesem Schulhaus
            return out
        return self._cached("raeume_stundenplan", load, refresh)

    # ------------------------------------------------------------------ Einträge
    def eintraege(self, refresh: bool = False, genau: bool = False) -> list[dict]:
        """Alle Stundenplan-Einträge als flache Tabelle (eine Zeile pro Eintrag) inkl. IDs.

        genau=False: IDs werden über Kürzel/Namen aus den Stammdaten zugeordnet (schnell).
        genau=True:  zusätzlich pro belegter Zelle die Bearbeitungsansicht lesen –
                     liefert Escola-Eintrags-ID und exakte Fach-/Raum-/LP-IDs (langsamer).
        """
        raster = self.raster(refresh)
        faecher = {f["kuerzel"]: f["id"] for f in self.faecher(refresh)}
        lp_by_name: dict[str, list[int]] = {}
        for p in self.lehrpersonen(refresh):
            lp_by_name.setdefault(f"{p['nachname']} {p['vorname']}", []).append(p["id"])
        raeume = self.raeume(refresh)

        rows = []
        with self._lock:
            for k, es in self._alle_stundenplaene(refresh):
                sh = k["schulhaus"]
                lekt = {l["id"]: l for l in raster.get(sh, {}).get("lektionen", [])}
                rooms = raeume.get(sh, [])
                details_cache: dict[tuple, list[dict]] = {}
                pos_in_cell: dict[tuple, int] = {}
                for e in es:
                    key = (e["tag_code"], e["lektion_id"])
                    idx = pos_in_cell[key] = pos_in_cell.get(key, -1) + 1
                    l = lekt.get(e["lektion_id"], {})
                    # Räume: Name + Kürzel gemeinsam eindeutig (Kürzel allein nicht, z. B. A105)
                    raum_ids = []
                    for i, rn in enumerate(e["raeume"]):
                        rk = e["raeume_kuerzel"][i] if i < len(e["raeume_kuerzel"]) else ""
                        hit = [r["id"] for r in rooms if r["name"] == rn and (not rk or r["kuerzel"] == rk)]
                        raum_ids.append(hit[0] if len(hit) == 1 else None)
                    lp_ids = [(lp_by_name.get(n) or [None])[0] if len(lp_by_name.get(n, [])) <= 1 else None for n in e["lehrpersonen"]]
                    row = {
                        "klasse_id": k["id"], "klasse": k["name"], "schulhaus": sh,
                        "tag_code": e["tag_code"], "tag": P.TAG_CODES.get(e["tag_code"], e["tag_code"]),
                        "lektion_id": e["lektion_id"], "lektion_nr": l.get("nr"),
                        "von": l.get("von"), "bis": l.get("bis"),
                        "eintrag_id": None,
                        "fach_id": faecher.get(e["fach_kuerzel"]), "fach_kuerzel": e["fach_kuerzel"], "fach": e["fach"],
                        "lehrperson_ids": lp_ids, "lehrpersonen": e["lehrpersonen"], "lehrpersonen_kuerzel": e["lehrpersonen_kuerzel"],
                        "raum_ids": raum_ids, "raeume": e["raeume"], "raeume_kuerzel": e["raeume_kuerzel"],
                        "zusatz": e["zusatz"],
                    }
                    if genau:
                        if key not in details_cache:
                            details_cache[key] = P.parse_eintrag_details(self._zelle_ansehen(k, *key))
                        d = details_cache[key]
                        if idx < len(d):
                            row["eintrag_id"] = d[idx]["eintrag_id"]
                            row["fach_id"] = d[idx]["fach_id"]
                            row["raum_ids"] = d[idx]["raum_ids"]
                            row["lehrperson_ids"] = d[idx]["lehrperson_ids"]
                    rows.append(row)
        return rows

    # ------------------------------------------------------------------ Personen
    PERS = "inc/ajax/persons/"

    _NEU_LADEN = ("Bitte laden Sie die Seite neu", "Ungültige Anfrage oder fehlende Eingaben")

    def _raw(self, url: str, body: str, _wiederholt: bool = False) -> str:
        """POST mit exakt vorgegebenem Body (Escola erwartet z. B. `workgroupId` ohne Wert).
        Personen-Aufrufe: meldet Escola „Bitte laden Sie die Seite neu“ (Personen-Sitzung verloren,
        beobachtet 15.11.2026), wird die Personenverwaltung neu geöffnet und einmal wiederholt."""
        r = self._http.post(url, content=body.encode(),
                            headers={"Content-Type": "application/x-www-form-urlencoded; charset=UTF-8"})
        text = self._check(r)
        if not _wiederholt and url.startswith(self.PERS) and len(text) < 300 and any(m in text for m in self._NEU_LADEN):
            self._personen_kontext()
            if "show_person_details.php" in url and getattr(self, "_aktive_person", None):
                self._raw(self.PERS + "show_reiter.php", self._aktive_person, _wiederholt=True)
            return self._raw(url, body, _wiederholt=True)
        if "show_reiter.php" in url:
            self._aktive_person = body
        return text

    def _personen_kontext(self) -> None:
        """Personenverwaltung so öffnen, wie es die Escola-Seite beim Laden tut."""
        self._get("admin.php?page_request=154")
        self._http.post("inc/ajax/persons/personManagement.php?pageRequest=154", content=b"",
                        headers={"Content-Type": "application/x-www-form-urlencoded; charset=UTF-8"})
        unit = next(iter(self.cfg.schuleinheiten), 1)
        self._raw(self.PERS + "show_persons_of_group.php",
                  f"pageRequest=154&personCategory=allActive&schoolclassId&workgroupId&schoolUnitId={unit}"
                  "&schoolYear=0&searchMode=false", _wiederholt=True)

    def _unit_id(self, schulhaus: str) -> int | None:
        return next((u for u, n in self.cfg.schuleinheiten.items() if n == schulhaus), None)

    def kategorien(self, refresh: bool = False) -> dict[str, str]:
        """Rollen und Ansichten live aus Escola (Auswahl „p_rubrik“ der Personenverwaltung) – inkl.
        selbst angelegter Rollen wie „_neu“ (Kennung gruppe_<n>). Fallback: feste Liste."""
        from . import personen as PP

        def load():
            try:
                with self._lock:
                    html = self._raw(self.PERS + "personManagement.php",
                                     "pageRequest=154&personCategory=allActive&schoolclassId&workgroupId&schoolUnitId=1&schoolYear=0")
            except httpx.HTTPStatusError:
                return dict(PP.KATEGORIEN)
            from bs4 import BeautifulSoup
            opts = {o.get("value"): " ".join(o.get_text().split())
                    for o in BeautifulSoup(html, "lxml").select("select#p_rubrik option") if o.get("value")}
            return opts or dict(PP.KATEGORIEN)
        return self._cached("kategorien", load, refresh)

    def personen(self, kategorie: str = "allActive", refresh: bool = False) -> list[dict]:
        """Personenliste einer Kategorie (siehe personen.KATEGORIEN), über alle Schulhäuser."""
        from . import personen as PP
        if kategorie not in PP.KATEGORIEN and kategorie not in self.kategorien():
            raise ValueError(f"Unbekannte Rolle '{kategorie}'")
        if kategorie == "schueler":
            return self.schueler(refresh)

        def liste(unit):
            q = (f"pageRequest=154&personCategory={kategorie}&schoolclassId&workgroupId"
                 f"&schoolUnitId={unit}&schoolYear=0&searchMode=false")
            html = self._raw(self.PERS + "show_persons_of_group.php", q)
            # Inaktive zeigt Escola erst nach dem Schalter „inaktive Personen anzeigen“ (type=85, Umschalter).
            if kategorie == "allInactive" and 'id="showHideInactivePersonsSwitch"' in html \
                    and not re.search(r'id="showHideInactivePersonsSwitch"[^>]*checked', html):
                self._raw("inc/ajax/ajax_functions.php", "type=85")
                try:
                    html = self._raw(self.PERS + "show_persons_of_group.php", q)
                finally:
                    self._raw("inc/ajax/ajax_functions.php", "type=85")  # Anzeige wie vorher
            return html

        def load():
            res: dict[int, dict] = {}
            with self._lock:
                for unit, sh in self.cfg.schuleinheiten.items():
                    html = liste(unit)
                    for p in PP.parse_personenliste(html):
                        e = res.setdefault(p["id"], {**p, "kategorie": kategorie, "schulhaeuser": []})
                        if sh not in e["schulhaeuser"]:
                            e["schulhaeuser"].append(sh)
            return sorted(res.values(), key=lambda x: (x["nachname"], x["vorname"]))
        return self._cached(f"personen:{kategorie}", load, refresh)

    def schueler(self, refresh: bool = False, schuljahr: int = 0) -> list[dict]:
        """Alle Schüler:innen aller Klassen (schuljahr 0 = aktuelles, 1 = kommendes)."""
        from . import personen as PP

        def load():
            out = []
            with self._lock:
                for k in self._klassen_nur(refresh):
                    unit = self._unit_id(k["schulhaus"]) or 1
                    html = self._raw(self.PERS + "show_persons_of_group.php",
                                     f"pageRequest=154&personCategory=schueler&schoolclassId={k['id']}&workgroupId"
                                     f"&schoolUnitId={unit}&schoolYear={schuljahr}&searchMode=false")
                    for p in PP.parse_personenliste(html):
                        out.append({**p, "klasse_id": k["id"], "klasse": k["name"], "schulhaus": k["schulhaus"]})
            return out
        return self._cached(f"schueler:{schuljahr}", load, refresh)

    def _person_laden(self, pid: int, kategorie: str, abschnitte: list[str] | None, gesundheit: bool):
        """Person in der Session wählen und alle Datenabschnitte im Bearbeitungsmodus lesen."""
        from . import personen as PP
        cat = kategorie if kategorie in ("schueler", "allInactive") else "allActive"
        reiter = self._raw(self.PERS + "show_reiter.php", f"active_person={pid}&pageRequest=154&personCategory={cat}&searchMode=false")
        vorhanden = PP.parse_reiter(reiter)
        if not vorhanden:
            raise KeyError(f"Person {pid} nicht gefunden oder nicht sichtbar")
        wanted = [a for a in PP.DATEN_ABSCHNITTE if a in vorhanden and (abschnitte is None or a in abschnitte)
                  and (a != "health" or gesundheit)]
        detail = lambda a: self._raw(self.PERS + "show_person_details.php",
                                     f"active_section={a}&pageRequest=154&personCategory={cat}&searchMode=false")
        erstes = detail(wanted[0] if wanted else "name")
        war_an = PP.bearbeitungsmodus_an(erstes)
        if war_an is False:  # Felder gibt es nur im Bearbeitungsmodus
            self._raw(self.PERS + "ajax_functions_persons.php", "type=1&edit_mode=1")
        try:
            felder = []
            for i, a in enumerate(wanted):
                html = erstes if (i == 0 and war_an) else detail(a)
                felder += PP.parse_abschnitt(html, a)
        finally:
            if war_an is False:
                self._raw(self.PERS + "ajax_functions_persons.php", "type=1&edit_mode=0")
        return vorhanden, felder, war_an

    def person(self, pid: int, kategorie: str = "allActive", abschnitte: list[str] | None = None,
               mit_optionen: bool = False, gesundheit: bool = False, sensibel_zeigen: bool = False) -> dict:
        """Alle Felder einer Person, gruppiert nach Abschnitt, plus flaches Dict `felder`."""
        from . import personen as PP
        with self._lock:
            vorhanden, felder, _ = self._person_laden(pid, kategorie, abschnitte, gesundheit)
        abschn: dict[str, list] = {}
        for f in felder:
            abschn.setdefault(f.abschnitt, []).append(f.oeffentlich(mit_optionen, sensibel_zeigen))
        flach = {}
        for f in felder:
            o = f.oeffentlich(False, sensibel_zeigen)
            flach[f.name] = o.get("text", o["wert"]) if f.typ in ("auswahl", "auswahlknopf") else o["wert"]
        return {"id": pid, "kategorie": kategorie, "reiter": vorhanden,
                "abschnitte": {a: {"titel": PP.ABSCHNITT_TITEL.get(a, a), "felder": v} for a, v in abschn.items()},
                "felder": flach}

    def person_schreiben(self, pid: int, werte: dict, kategorie: str = "allActive",
                         probelauf: bool = False, gesundheit: bool = False) -> dict:
        """Felder einer Person ändern. `werte` = {interner Feldname: neuer Wert}.
        Bricht ohne Änderung ab, wenn ein Feld unbekannt, gesperrt oder ungültig ist."""
        from . import personen as PP
        with self._lock:
            _, felder, war_an = self._person_laden(pid, kategorie, None, gesundheit)
            by_name = {f.name: f for f in felder}
            plan, fehler = [], []
            for name, wert in werte.items():
                f = by_name.get(name)
                if f is None:
                    fehler.append({"feld": name, "fehler": "unbekanntes Feld"})
                    continue
                try:
                    plan.append((f, wert, PP.schreib_payload(f, wert)))
                except PP.FeldFehler as e:
                    fehler.append({"feld": name, "fehler": str(e)})
            if fehler:
                return {"id": pid, "geschrieben": False, "fehler": fehler}
            aenderungen = [{"feld": f.name, "label": f.label, "alt": (f.text if f.text is not None else f.wert)
                            if not f.ist_sensibel() else "***", "neu": wert} for f, wert, _ in plan]
            if probelauf:
                return {"id": pid, "geschrieben": False, "probelauf": True, "aenderungen": aenderungen}
            # Bearbeitungsmodus für das Speichern sicherstellen
            if war_an is False:
                self._raw(self.PERS + "ajax_functions_persons.php", "type=1&edit_mode=1")
            try:
                for f, _, payload in plan:
                    self._post(self.PERS + "ajax_functions_persons.php", payload)
            finally:
                if war_an is False:
                    self._raw(self.PERS + "ajax_functions_persons.php", "type=1&edit_mode=0")
            # Kontrolle: neu lesen
            _, neu, _ = self._person_laden(pid, kategorie, sorted({f.abschnitt for f, _, _ in plan}), gesundheit)
            neu_by = {f.name: f for f in neu}
            for a in aenderungen:
                nf = neu_by.get(a["feld"])
                a["jetzt"] = None if nf is None else (nf.text if nf.text is not None else nf.wert)
            self._cache.pop(f"personen:{kategorie}", None)
            return {"id": pid, "geschrieben": True, "aenderungen": aenderungen}

    # ------------------------------------------------------------------ Anlegen & Klassen-Transfer
    def _neue_person_rpc(self, methode: str, kategorie: str, klasse_id, unit: int, struct: dict):
        payload = {"parameters": {"newPersonStruct": struct},
                   "rpcContext": {"personCategoryGroup": kategorie, "schoolclassId": klasse_id, "schoolUnitId": unit}}
        r = self._http.post(f"rpc/collections/CaptureNewPersonAdmin/{methode}.php", json=payload)
        self._check(r)
        return r.json()

    def person_anlegen(self, nachname: str, vorname: str, geschlecht: str, kategorie: str,
                       schulhaus: str, klasse_id: int | None = None, trotz_duplikat: bool = False) -> dict:
        """Neue Person wie mit „Neue Person“ in der Escola-Personenverwaltung."""
        from . import personen as PP
        if (kategorie not in PP.KATEGORIEN and kategorie not in self.kategorien()) \
                or kategorie in ("allActive", "allInactive", "guardians-all", "eltern", "former-students"):
            raise ValueError(f"Mit '{kategorie}' kann keine Person angelegt werden (Ansicht, keine Rolle)")
        if kategorie == "schueler" and not klasse_id:
            raise ValueError("Für 'schueler' ist klasse_id nötig (ohne Klasse: 'students-without-schoolclass')")
        if geschlecht not in ("w", "m", "d"):
            raise ValueError("geschlecht muss w, m oder d sein")
        if not nachname.strip() or not vorname.strip():
            raise ValueError("Nachname und Vorname sind Pflicht")
        unit = self._unit_id(schulhaus)
        if unit is None:
            raise ValueError(f"Unbekanntes Schulhaus '{schulhaus}'")
        struct = {"id": -1, "firstName": vorname.strip(), "lastName": nachname.strip(), "gender": geschlecht}
        kl = klasse_id if kategorie == "schueler" else None
        with self._lock:
            dup = self._neue_person_rpc("checkForDuplicatePersonsRpc", kategorie, kl, unit, struct)
            dups = [{"id": d.get("id"), "name": d.get("displayName"), "rollen": d.get("listOfAllRoles"), "aktiv": d.get("active")}
                    for d in ((dup or {}).get("duplicatePersonStructs") or [])] if isinstance(dup, dict) else []
            if dups and not trotz_duplikat:
                return {"angelegt": False, "grund": "moegliche_duplikate", "duplikate": dups}
            res = self._neue_person_rpc("captureNewPersonRpc", kategorie, kl, unit, struct)
        if not (isinstance(res, list) and res and isinstance(res[0], int)):
            raise RuntimeError(f"Escola hat keine neue Personen-ID geliefert: {str(res)[:200]}")
        for k in list(self._cache):
            if k.startswith(("personen:", "schueler", "lehrpersonen")):
                self._cache.pop(k, None)
        return {"angelegt": True, "id": res[0], "duplikate_ignoriert": dups}

    def schueler_ohne_klasse(self, refresh: bool = False) -> list[dict]:
        from . import personen as PP

        def load():
            out = []
            with self._lock:
                for unit, sh in self.cfg.schuleinheiten.items():
                    for cat, status in (("students-without-schoolclass", "ohne Klasse"), ("future-students", "zukünftig")):
                        html = self._raw(self.PERS + "show_persons_of_group.php",
                                         f"pageRequest=154&personCategory={cat}&schoolclassId&workgroupId"
                                         f"&schoolUnitId={unit}&schoolYear=0&searchMode=false")
                        out += [{**p, "klasse_id": None, "klasse": None, "schulhaus": sh, "status": status}
                                for p in PP.parse_personenliste(html)]
            return out
        return self._cached("schueler:ohne_klasse", load, refresh)

    def _transfer_formular(self, pid: int, schuljahr: int) -> list[dict]:
        """Transfer-Formular öffnen (mode=13) und die dort angebotenen Klassen lesen."""
        from bs4 import BeautifulSoup
        self._raw(self.PERS + "show_reiter.php", f"active_person={pid}&pageRequest=154&personCategory=schueler&searchMode=false")
        form = self._post(self.PERS + "personManagement.php",
                          {"mode": 13, "transferSchoolyear": schuljahr, "pageRequest": 154, "activePersonId": pid})
        sel = BeautifulSoup(form, "lxml").select_one("select[name=klassen_id_transfer]")
        if sel is None:
            raise RuntimeError("Escola hat kein Transfer-Formular geliefert (Person ohne SuS-Rolle?)")
        return [{"id": int(o["value"]), "name": " ".join(o.get_text().split())}
                for o in sel.select("option") if o.get("value", "").isdigit()]

    def transfer_klassen(self, pid: int, schuljahr: int = 0) -> list[dict]:
        """Klassen, in die diese:r Schüler:in transferiert werden kann. Fürs kommende Schuljahr mit
        den künftigen Namen (z. B. 92 = „zukünftige H_A2a“); abschliessende Klassen fehlen dort."""
        if schuljahr not in (0, 1):
            raise ValueError("schuljahr muss 0 oder 1 sein")
        with self._lock:
            return self._transfer_formular(pid, schuljahr)

    def schueler_transfer(self, pid: int, klasse_id: int, stichtag: str | None = None, schuljahr: int = 0) -> dict:
        """SuS in eine Klasse transferieren (Escola-Aktion „SuS in eine Klasse transferieren“).
        Für Einteilung (ohne Klasse -> Klasse) und Umteilung (Klasse A -> B).
        schuljahr 0: aktuelles SJ, ab `stichtag` (JJJJ-MM-TT). schuljahr 1: kommendes SJ (ohne Stichtag)."""
        import re as _re
        from bs4 import BeautifulSoup
        if schuljahr not in (0, 1):
            raise ValueError("schuljahr muss 0 oder 1 sein")
        if schuljahr == 0 and not _re.fullmatch(r"\d{4}-\d{2}-\d{2}", stichtag or ""):
            raise ValueError("stichtag muss JJJJ-MM-TT sein")
        with self._lock:
            optionen = self._transfer_formular(pid, schuljahr)
            if klasse_id not in {o["id"] for o in optionen}:
                raise ValueError(f"Klasse {klasse_id} ist für diesen Transfer nicht wählbar "
                                 f"(aktuelle Klasse oder im {'kommenden' if schuljahr else 'aktuellen'} Schuljahr nicht vorhanden). "
                                 f"Möglich: {', '.join(str(o['id']) + '=' + o['name'] for o in optionen[:12])} …")
            daten = {"klassen_id_transfer": klasse_id, "Submit": "Transfer ausführen", "mode": 14,
                     "pageRequest": 154, "activePersonId": pid, "transferSchoolyear": schuljahr}
            if schuljahr == 0:
                daten["transferDate"] = stichtag
            res = self._post(self.PERS + "personManagement.php", daten)
        self._schueler_cache_leeren()
        ok = BeautifulSoup(res, "lxml").select_one(".alert-success")
        if ok is None:
            err = BeautifulSoup(res, "lxml").select_one(".alert")
            raise RuntimeError("Transfer fehlgeschlagen: " + (err.get_text(" ", strip=True)[:300] if err else "unbekannte Antwort"))
        txt = ok.get_text(" ", strip=True).replace("VORGANG WIDERRUFEN", "").strip()
        return {"transferiert": True, "id": pid, "klasse_id": klasse_id, "stichtag": stichtag if schuljahr == 0 else None,
                "schuljahr": schuljahr, "meldung": txt}

    def _schueler_cache_leeren(self):
        for k in list(self._cache):
            if k.startswith(("schueler", "personen:")):
                self._cache.pop(k, None)

    def schueler_klasse_finden(self, pid: int, schuljahr: int = 0) -> int | None:
        for s in self.schueler(True, schuljahr):
            if s["id"] == pid:
                return s["klasse_id"]
        return None

    def schueler_aus_klasse_entfernen(self, pid: int, klasse_id: int | None = None, schuljahr: int = 0) -> dict:
        """Klassenzuteilung entfernen (Escola-Aktion „SuS von der Klasse entfernen“, aktuelles bzw.
        kommendes SJ). Die Person bleibt erhalten und steht danach unter „ohne Klasse“."""
        import re as _re
        from bs4 import BeautifulSoup
        if schuljahr not in (0, 1):
            raise ValueError("schuljahr muss 0 oder 1 sein")
        if klasse_id is None:
            klasse_id = self.schueler_klasse_finden(pid, schuljahr)
            if klasse_id is None:
                raise ValueError(f"Person {pid} ist im {'kommenden' if schuljahr else 'aktuellen'} Schuljahr keiner Klasse zugeteilt")
        k = next((x for x in self._klassen_nur() if x["id"] == klasse_id), None)
        if k is None:
            raise ValueError(f"Unbekannte Klasse {klasse_id}")
        unit = self._unit_id(k["schulhaus"]) or 1
        action = 1008 if schuljahr == 0 else 1009  # bewusst nur diese beiden Aktionen
        ctx = f"pageRequest=154&personCategory=schueler&schoolUnitId={unit}&schoolYear={schuljahr}&schoolclassId={klasse_id}&workgroupId"
        with self._lock:
            frage = self._raw(self.PERS + "personManagement.php", f"mode=17&action={action}&element_string=:{int(pid)}:&{ctx}")
            m = _re.search(r"personManagementGotoMode\(29,\s*\{\s*isInNextSchoolyear:\s*(\d+),\s*schoolclassId:\s*(\d+),\s*schoolYear:\s*(\d+)", frage)
            if "wirklich die Klassenzuteilung entfernen" not in frage or not m or int(m.group(2)) != klasse_id:
                raise RuntimeError("Escola hat die Rückfrage zum Entfernen nicht gezeigt (Person nicht in dieser Klasse?)")
            res = self._raw(self.PERS + "personManagement.php",
                            f"mode=29&isInNextSchoolyear={m.group(1)}&schoolclassId={m.group(2)}&schoolYear={m.group(3)}"
                            f"&pageRequest=154&personCategory=schueler&schoolUnitId={unit}&workgroupId")
        self._schueler_cache_leeren()
        txt = " ".join(BeautifulSoup(res, "lxml").get_text(" ").split()).replace("VORGANG WIDERRUFEN", "").strip()
        if "Klassenzuordnungen wurden angepasst" not in txt:
            raise RuntimeError(f"Entfernen fehlgeschlagen: {txt[:200]}")
        return {"entfernt": True, "id": pid, "klasse_id": klasse_id, "schuljahr": schuljahr,
                "meldung": "Die Klassenzuordnungen wurden angepasst."}

    # ------------------------------------------------------------------ Schullaufbahn / Klassenbeginn (L19)
    # Escola teilt bei Import und Transfer immer ab heute ein; ein vergangenes Datum lehnt der Transfer
    # auch serverseitig ab (live geprüft 24.11.2026). Der Beginn lässt sich nur in der Schullaufbahn
    # ändern (Dialog „Klassen bearbeiten“ → „Von: Schuljahresbeginn“). Das Schuljahr läuft fix 1.8.–31.7.
    SC = "rpc/collections/SchoolCareer/"
    SC_KLASSE = "studentGroupsSchoolclass"

    def _sc_rpc(self, methode: str, params: dict):
        import json as _json
        r = self._http.post(self.SC + methode + ".php", content=_json.dumps(
            {"parameters": params, "rpcContext": {}}).encode(), headers={"Content-Type": "application/json"})
        text = self._check(r)
        if not text.strip():
            return None  # updateEntry antwortet leer
        try:
            data = _json.loads(text)
        except ValueError:
            raise RuntimeError(f"Escola-Fehler bei {methode}: {text[:150]}")
        if isinstance(data, dict) and "messageForUser" in data:
            raise RuntimeError(data["messageForUser"])
        return data

    @staticmethod
    def _sj_start(heute=None) -> int:
        import datetime as _dt
        d = heute or _dt.date.today()
        return d.year if d.month >= 8 else d.year - 1

    def schullaufbahn(self, pid: int) -> list[dict]:
        """Einträge der Schullaufbahn (Klassen je Schuljahr) mit Von/Bis und Edit-ID."""
        with self._lock:
            data = self._sc_rpc("getSchoolCareer", {"personId": int(pid), "modulesFilter": None})
        out = []
        for sj in (data or {}).get("timeline", []):
            for e in sj.get("entries", []):
                out.append({"schuljahr": sj.get("schoolyear"), "schuljahr_text": sj.get("schoolyearLabel"),
                            "modul": e.get("module"), "titel": e.get("title"), "von": e.get("dateFrom"),
                            "bis": e.get("dateTo"), "edit_id": e.get("editId"),
                            "felder": {f.get("title"): f.get("content") for f in e.get("fields", [])}})
        return out

    def _eintrittsdatum(self, pid: int) -> str | None:
        """Eintrittsdatum (Personalien) als JJJJ-MM-TT oder None."""
        import re as _re
        p = self.person(pid, "schueler", ["personalien"])
        m = _re.fullmatch(r"(\d{1,2})\.(\d{1,2})\.(\d{4})", str(p["felder"].get("eintritt") or "").strip())
        return f"{m.group(3)}-{int(m.group(2)):02d}-{int(m.group(1)):02d}" if m else None

    def klassenbeginn_setzen(self, pid: int, ab: str = "schuljahresbeginn", schuljahr: int | None = None,
                             edit_id: str | None = None, probelauf: bool = False) -> dict:
        """Beginn der Klassenzuteilung in der Schullaufbahn setzen.
        `ab`: „schuljahresbeginn“ (1.8.), „eintritt“ (später von 1.8. und Eintrittsdatum) oder JJJJ-MM-TT.
        Nur wenn die Person im Schuljahr genau einen Klasseneintrag hat (sonst `edit_id` angeben)."""
        import re as _re
        sj = schuljahr if schuljahr is not None else self._sj_start()
        sj_von, sj_bis = f"{sj}-08-01", f"{sj + 1}-07-31"
        if ab == "schuljahresbeginn":
            ziel = sj_von
        elif ab == "eintritt":
            e = self._eintrittsdatum(pid)
            ziel = max(sj_von, e) if e else sj_von
        elif _re.fullmatch(r"\d{4}-\d{2}-\d{2}", ab or ""):
            ziel = ab
        else:
            raise ValueError("ab: schuljahresbeginn, eintritt oder JJJJ-MM-TT")
        if not (sj_von <= ziel <= sj_bis):
            raise ValueError(f"{ziel} liegt nicht im Schuljahr {sj}/{str(sj + 1)[2:]} ({sj_von} bis {sj_bis})")
        eintraege = [e for e in self.schullaufbahn(pid) if e["modul"] == self.SC_KLASSE and e["schuljahr"] == sj]
        if edit_id is not None:
            eintraege = [e for e in eintraege if str(e["edit_id"]) == str(edit_id)]
        if not eintraege:
            raise ValueError(f"Person {pid} hat im Schuljahr {sj} keinen Klasseneintrag in der Schullaufbahn")
        if len(eintraege) > 1:
            raise KonfliktFehler(f"Person {pid} hat im Schuljahr {sj} mehrere Klasseneinträge – `edit_id` angeben",
                                 [{"edit_id": e["edit_id"], "klasse": e["titel"], "von": e["von"], "bis": e["bis"]}
                                  for e in eintraege])
        e = eintraege[0]
        if ziel > e["bis"]:
            raise ValueError(f"Beginn {ziel} liegt nach dem Ende des Eintrags ({e['bis']})")
        res = {"id": pid, "schuljahr": sj, "klasse": e["titel"], "von_alt": e["von"], "von_neu": ziel,
               "bis": e["bis"], "geaendert": False, "probelauf": probelauf}
        if e["von"] == ziel:
            return {**res, "meldung": "Beginn stimmt bereits"}
        if probelauf:
            return res
        with self._lock:
            felder = self._sc_rpc("getEntryEditFields", {"personId": int(pid), "module": self.SC_KLASSE,
                                                         "editId": str(e["edit_id"]), "schoolyear": sj, "draft": []})
            werte = [{"type": f["type"], "value": f.get("value")} for f in felder or []
                     if f.get("type") in ("schoolclass", "levelYear")]
            if not any(w["type"] == "schoolclass" and w["value"] for w in werte):
                raise RuntimeError("Escola hat keine Klasse im Bearbeitungsformular geliefert")
            self._sc_rpc("updateEntry", {"personId": int(pid), "module": self.SC_KLASSE, "editId": str(e["edit_id"]),
                                         "schoolyear": sj, "dateFrom": ziel, "dateTo": e["bis"], "values": werte})
        neu = [x for x in self.schullaufbahn(pid) if x["modul"] == self.SC_KLASSE and x["schuljahr"] == sj
               and x["titel"] == e["titel"]]
        if not any(x["von"] == ziel for x in neu):
            raise RuntimeError(f"Escola hat den Beginn nicht übernommen (jetzt: {[x['von'] for x in neu]})")
        return {**res, "geaendert": True}

    def klasse_klassenbeginn(self, klasse_id: int, ab: str = "eintritt", probelauf: bool = False) -> dict:
        """Klassenbeginn für alle SuS einer Klasse setzen (z. B. nach dem Import der Klasse).
        Fehler einzelner SuS brechen nicht ab, sie stehen in der Liste."""
        sus = [s for s in self.schueler(True) if s["klasse_id"] == klasse_id]
        ergebnisse = []
        for s in sus:
            try:
                r = self.klassenbeginn_setzen(s["id"], ab, probelauf=probelauf)
                ergebnisse.append({**r, "name": f"{s['nachname']} {s['vorname']}", "fehler": None})
            except (ValueError, RuntimeError, KonfliktFehler) as ex:
                ergebnisse.append({"id": s["id"], "name": f"{s['nachname']} {s['vorname']}", "fehler": str(ex)})
        return {"klasse_id": klasse_id, "ab": ab, "probelauf": probelauf, "anzahl": len(sus),
                "geaendert": sum(1 for r in ergebnisse if r.get("geaendert")),
                "fehler": sum(1 for r in ergebnisse if r.get("fehler")), "schueler": ergebnisse}

    # ------------------------------------------------------------------ Rollen
    # Rollen-IDs, die am 14.11.2026 im System waren – alles andere gilt als „neu“
    STANDARD_ROLLEN = {2, 3, 5, 6, 12, 13, 14, 15, 16, 17, 18, 21, 24, 25, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35, 36, 39, 40}
    # Zuordnen erlaubt: diese eingebauten Rollen + alle eigenen Rollen (Escola-Typ „gruppe“).
    # Alle übrigen eingebauten Rollen (Admin, Superadmin, Ärzt:innen, SuS, Eltern …) sind nur lesbar.
    FREIGEGEBENE_EINGEBAUTE_ROLLEN = {13, 16, 14, 17}  # Lehrpersonen / Schulleitung je Schulhaus

    def _zuordenbar(self) -> set[int]:
        return self.FREIGEGEBENE_EINGEBAUTE_ROLLEN | {r["id"] for r in self.rollen() if r["personengruppe"]}

    def rollen(self, refresh: bool = False) -> list[dict]:
        """Alle Escola-Rollen (Rollen-Konfiguration) mit ID, Name, Typ und Schulhaus."""
        def load():
            with self._lock:
                r = self._http.post("rpc/collections/RoleAssignmentConfigurationAdmin/getAllPlainRoles.php",
                                    json={"parameters": {}, "rpcContext": {}})
                self._check(r)
                data = r.json()
            return [{"id": x.get("id"), "name": x.get("name"), "typ": x.get("groupType"),
                     "schulhaus": x.get("schoolUnitName") or None, "personengruppe": bool(x.get("isDynamicRoleGroup")),
                     "neu": x.get("id") not in self.STANDARD_ROLLEN,
                     "zuordenbar": bool(x.get("isDynamicRoleGroup")) or x.get("id") in self.FREIGEGEBENE_EINGEBAUTE_ROLLEN}
                    for x in (data if isinstance(data, list) else [])]
        return self._cached("rollen", load, refresh)

    def _person_rollen_html(self, pid: int) -> str:
        """Reiter „Rollen“ – die Rollen-Schalter zeigt Escola NUR im Bearbeitungsmodus (live geprüft 15.11.2026)."""
        from . import personen as PP
        r = self._raw(self.PERS + "show_reiter.php", f"active_person={pid}&pageRequest=154&personCategory=allActive&searchMode=false")
        if "rollen" not in PP.parse_reiter(r):
            raise KeyError(f"Person {pid} nicht gefunden")
        q = "active_section=rollen&pageRequest=154&personCategory=allActive&searchMode=false"
        html = self._raw(self.PERS + "show_person_details.php", q)
        if PP.bearbeitungsmodus_an(html) is False:
            self._raw(self.PERS + "ajax_functions_persons.php", "type=1&edit_mode=1")
            self._rollen_edit_an = True
            html = self._raw(self.PERS + "show_person_details.php", q)
        return html

    def _rollen_edit_aus(self) -> None:
        if getattr(self, "_rollen_edit_an", False):
            self._rollen_edit_an = False
            self._raw(self.PERS + "ajax_functions_persons.php", "type=1&edit_mode=0")

    @staticmethod
    def _parse_person_rollen(html: str) -> list[dict]:
        from bs4 import BeautifulSoup
        s = BeautifulSoup(html, "lxml")
        out = []
        for cb in s.select("input[id^=role_]"):
            rid = cb["id"][5:]
            if not rid.isdigit():
                continue
            lab = s.find("label", attrs={"for": cb["id"]})
            name = " ".join((lab.get_text() if lab else (cb.parent.get_text() if cb.parent else "")).split())
            name = name.split(" (die ")[0].split(" (diese ")[0]
            out.append({"id": int(rid), "name": name, "zugewiesen": cb.has_attr("checked"),
                        "aenderbar": not cb.has_attr("disabled")})
        return out

    def person_rollen(self, pid: int) -> list[dict]:
        with self._lock:
            try:
                return self._parse_person_rollen(self._person_rollen_html(pid))
            finally:
                self._rollen_edit_aus()

    def person_rollen_setzen(self, pid: int, hinzufuegen: list[int], entfernen: list[int], probelauf: bool = False) -> dict:
        """Rollen einer Person hinzufügen/entfernen. Alles oder nichts: ungültige IDs brechen vorher ab."""
        if set(hinzufuegen) & set(entfernen):
            raise ValueError("Eine Rolle kann nicht gleichzeitig hinzugefügt und entfernt werden")
        erlaubt = self._zuordenbar()
        with self._lock:
          try:
            vorher = {r["id"]: r for r in self._parse_person_rollen(self._person_rollen_html(pid))}
            fehler = []
            for rid in [*hinzufuegen, *entfernen]:
                if rid not in erlaubt:
                    fehler.append({"rolle": rid, "fehler": "eingebaute Rolle – über die API nicht zuordenbar"})
                elif rid not in vorher:
                    fehler.append({"rolle": rid, "fehler": "unbekannte Rolle"})
                elif not vorher[rid]["aenderbar"]:
                    fehler.append({"rolle": rid, "fehler": f"in Escola nicht änderbar ({vorher[rid]['name']})"})
            if fehler:
                return {"id": pid, "geaendert": False, "fehler": fehler}
            plan = [(rid, 1) for rid in hinzufuegen if not vorher[rid]["zugewiesen"]] + \
                   [(rid, 0) for rid in entfernen if vorher[rid]["zugewiesen"]]
            if probelauf or not plan:
                return {"id": pid, "geaendert": False, "probelauf": probelauf,
                        "aenderungen": [{"rolle": r, "name": vorher[r]["name"], "neu": bool(v)} for r, v in plan]}
            for rid, val in plan:
                self._raw(self.PERS + "ajax_functions_persons.php", f"type=24&role={rid}&new_value={val}&label=")
            nachher = self._parse_person_rollen(self._person_rollen_html(pid))
          finally:
            self._rollen_edit_aus()
        for k in list(self._cache):
            if k.startswith(("personen:", "lehrpersonen")):
                self._cache.pop(k, None)
        return {"id": pid, "geaendert": True,
                "aenderungen": [{"rolle": r, "name": vorher[r]["name"], "neu": bool(v)} for r, v in plan],
                "rollen": [r for r in nachher if r["zugewiesen"]]}

    # ------------------------------------------------------------------ Aktivieren / Deaktivieren
    # Escola-Sammelaktionen (personManagement.php mode=17). Bewusst NUR diese zwei – über denselben
    # Aufruf laufen auch „definitiv löschen“ (4) u. a., die hier nie ausgelöst werden.
    # (Weitere erlaubte Sammelaktionen: 1008/1009 „SuS von der Klasse entfernen“, siehe oben.)
    _STATUS_AKTIONEN = {False: (1, "allActive", "deaktivieren", "deaktiviert"),
                        True: (2, "allInactive", "aktivieren", "aktiviert")}

    def person_aktiv_setzen(self, pid: int, aktiv: bool) -> dict:
        """Person deaktivieren (aktiv=False) oder wieder aktivieren (aktiv=True).
        Ablauf wie in Escola: Aktion wählen -> Rückfrage -> „JA, durchführen“ (mode=36)."""
        from bs4 import BeautifulSoup
        action, cat, verb, partizip = self._STATUS_AKTIONEN[bool(aktiv)]
        ctx = f"pageRequest=154&personCategory={cat}&schoolUnitId=1&schoolYear=0&schoolclassId&workgroupId"
        txt = lambda h: " ".join(BeautifulSoup(h, "lxml").get_text(" ").split())
        with self._lock:
            frage = self._raw(self.PERS + "personManagement.php", f"mode=17&action={action}&element_string=:{int(pid)}:&{ctx}")
            if f"wirklich {verb}" not in txt(frage) or "personManagementGotoMode(36" not in frage:
                raise RuntimeError(f"Escola hat die Rückfrage zum {verb.capitalize()} nicht gezeigt: {txt(frage)[:200]}")
            res = self._raw(self.PERS + "personManagement.php", f"mode=36&{ctx}")
        meldung = txt(res).replace("VORGANG WIDERRUFEN", "").strip()
        if f"erfolgreich {partizip}" not in meldung:
            raise RuntimeError(f"{verb.capitalize()} fehlgeschlagen: {meldung[:200]}")
        for k in list(self._cache):
            if k.startswith(("personen:", "lehrpersonen", "schueler")):
                self._cache.pop(k, None)
        return {"id": pid, "aktiv": bool(aktiv), "meldung": meldung[:200]}

    # ------------------------------------------------------------------ Austritt
    AUSTRITT_FELDER = ("austritt", "departure_timestamp", "departure_municipality_name")

    def schueler_austritt(self, pid: int, datum: str, wegzugsdatum: str | None = None,
                          wegzugsgemeinde: str | None = None, sofort_deaktivieren: bool = False) -> dict:
        return self.person_austritt(pid, datum, wegzugsdatum, wegzugsgemeinde, sofort_deaktivieren, "schueler")

    def person_austritt(self, pid: int, datum: str, wegzugsdatum: str | None = None,
                        wegzugsgemeinde: str | None = None, sofort_deaktivieren: bool = False,
                        kategorie: str = "allActive", rollen_ausgetreten: bool = False) -> dict:
        """Austritt erfassen: Austrittsdatum (+ optional Wegzugsdatum/-gemeinde) setzen.
        Escola deaktiviert die Person dann selbst (nicht sofort beim Speichern – laut Test am
        14.11.2026 auch nicht bei Austritt am selben Tag). Mit sofort_deaktivieren=True zusätzlich sofort."""
        from . import personen as PP
        werte = {"austritt": datum}
        if wegzugsdatum is not None:
            werte["departure_timestamp"] = wegzugsdatum
        if wegzugsgemeinde is not None:
            werte["departure_municipality_name"] = wegzugsgemeinde
        with self._lock:
            _, felder, war_an = self._person_laden(pid, kategorie, ["personalien"], False)
            by = {f.name: f for f in felder}
            plan = []
            for name, wert in werte.items():
                f = by.get(name)
                if f is None:
                    raise ValueError(f"Feld '{name}' bei Person {pid} nicht gefunden")
                try:  # nur für diese drei Felder und nur in diesem Ablauf freigegeben
                    plan.append((f, PP.schreib_payload(f, wert, freigabe=name in self.AUSTRITT_FELDER)))
                except PP.FeldFehler as e:
                    raise ValueError(str(e))
            if war_an is False:
                self._raw(self.PERS + "ajax_functions_persons.php", "type=1&edit_mode=1")
            try:
                for _, payload in plan:
                    self._post(self.PERS + "ajax_functions_persons.php", payload)
            finally:
                if war_an is False:
                    self._raw(self.PERS + "ajax_functions_persons.php", "type=1&edit_mode=0")
            _, neu, _ = self._person_laden(pid, kategorie, ["personalien"], False)
        jetzt = {f.name: f.wert for f in neu if f.name in self.AUSTRITT_FELDER}
        res = {"id": pid, "austritt": jetzt.get("austritt"), "wegzugsdatum": jetzt.get("departure_timestamp"),
               "wegzugsgemeinde": jetzt.get("departure_municipality_name"), "deaktiviert": False}
        if rollen_ausgetreten:  # vor dem Deaktivieren (Rollen-Reiter nur bei aktiven Personen sicher lesbar)
            res["rollen"] = self.rollen_ausgetreten(pid)
        if sofort_deaktivieren:
            res["deaktiviert"] = not self.person_aktiv_setzen(pid, False)["aktiv"]
        self._schueler_cache_leeren()
        return res

    # ------------------------------------------------------------------ Arbeitsgruppen
    WG = "inc/ajax/workgroups/"

    def arbeitsgruppen(self, schuljahr: int = 0, refresh: bool = False) -> list[dict]:
        """Alle Arbeitsgruppen mit ID, Name, Schulhaus und Anzahl zugeteilter Schüler:innen."""
        def load():
            res: dict[int, dict] = {}
            with self._lock:
                for unit in self.cfg.schuleinheiten:
                    r = self._post(self.WG + "ajax_functions_workgroups.php",
                                   {"type": 7, "labels": "", "label_filter_type": "", "schul_id": unit,
                                    "schul_year": schuljahr, "manual": 1, "filter": 1, "noLabels": 1})
                    import json as _json
                    try:
                        data = _json.loads(r)
                    except ValueError:
                        continue
                    for w in data if isinstance(data, list) else []:
                        if isinstance(w, dict) and w.get("id"):
                            res[w["id"]] = {"id": w["id"], "name": w.get("name"), "schulhaus": w.get("schoolName"),
                                            "anzahl_schueler": w.get("count")}
            return sorted(res.values(), key=lambda x: (x["schulhaus"] or "", x["name"] or ""))
        return self._cached(f"arbeitsgruppen:{schuljahr}", load, refresh)

    def schueler_arbeitsgruppen(self, pid: int, schuljahr: int = 0) -> list[dict]:
        import json as _json
        with self._lock:
            r = self._post(self.WG + "assignments.php", {"mode": 2, "student_id": pid, "schoolYear": schuljahr, "updateStudent": 0})
        ids = [w.get("workgroup_id") for w in (_json.loads(r).get("workgroups") or []) if w.get("workgroup_id")]
        namen = {w["id"]: w for w in self.arbeitsgruppen(schuljahr)}
        return [namen.get(int(i), {"id": int(i), "name": None, "schulhaus": None}) for i in ids]

    def schueler_arbeitsgruppe_setzen(self, pid: int, wg_id: int, dabei: bool, schuljahr: int = 0) -> dict:
        """Schüler:in einer Arbeitsgruppe zuteilen (dabei=True) bzw. daraus entfernen (dabei=False)."""
        if schuljahr not in (0, 1):
            raise ValueError("schuljahr muss 0 oder 1 sein")
        if wg_id not in {w["id"] for w in self.arbeitsgruppen(schuljahr, refresh=True)}:
            raise ValueError(f"Unbekannte Arbeitsgruppe {wg_id}")
        vorher = {w["id"] for w in self.schueler_arbeitsgruppen(pid, schuljahr)}
        with self._lock:
            if dabei and wg_id not in vorher:
                # Escola speichert „angezeigte“ Gruppen: nur die betroffene Gruppe anzeigen -> andere bleiben unberührt
                self._raw(self.WG + "assignments.php",
                          f"mode=3&student_id={int(pid)}&schoolYear={schuljahr}&workgroups%5B%5D={int(wg_id)}"
                          f"&allDisplayedWorkgroups%5B%5D={int(wg_id)}")
            elif not dabei and wg_id in vorher:
                self._post(self.WG + "ajax_functions_workgroups.php",
                           {"type": 9, "workgroupId": wg_id, "studentId": pid, "schoolYear": schuljahr})
        nachher = self.schueler_arbeitsgruppen(pid, schuljahr)
        ok = (wg_id in {w["id"] for w in nachher}) == dabei
        self._cache.pop(f"arbeitsgruppen:{schuljahr}", None)
        if not ok:
            raise RuntimeError("Escola hat die Arbeitsgruppen-Zuteilung nicht übernommen")
        return {"id": pid, "schuljahr": schuljahr, "arbeitsgruppen": nachher,
                "geaendert": (wg_id in vorher) != dabei}

    # ------------------------------------------------------------------ Fächer-Zuteilung Lehrpersonen
    LP = "inc/ajax/lehrpersonen/"
    # Rechte-Spalte -> Escola-Modus in lehrpersonen_faecher.php (alle per Lehrperson + aktive Klasse)
    RECHTE_MODI = {"klr": 3, "fp": 16, "spm": 22, "abs": 23}
    VORLAGEN = ("klassenlehrperson", "fachlehrperson", "sopae")

    @staticmethod
    def _ziel(klasse_id: int | None, arbeitsgruppe_id: int | None) -> dict:
        if bool(klasse_id) == bool(arbeitsgruppe_id):
            raise ValueError("Genau eines angeben: klasse_id oder arbeitsgruppe_id")
        return ({"typ": "Klasse", "id": int(klasse_id)} if klasse_id
                else {"typ": "Arbeitsgruppe", "id": int(arbeitsgruppe_id)})

    @staticmethod
    def _ziel_params(ziel: dict, sj: int) -> dict:
        k = ziel["typ"] == "Klasse"
        return {"class_id": ziel["id"] if k else 0, "workgroup_id": 0 if k else ziel["id"], "schoolYear": sj}

    def _schuljahr_zurueck(self) -> None:
        # Die Matrix mit school_year=1 stellt die GANZE Escola-Sitzung aufs kommende SJ um
        # (auch die Stundenplan-Anzeige, live beobachtet 15.11.2026) -> immer zurückstellen.
        self._post(self.LP + "lehrpersonen_faecher.php", {"mode": 0, "school_year": 0})

    def _matrix(self, ziel: dict, sj: int = 0) -> list[dict]:
        if sj not in (0, 1):
            raise ValueError("schuljahr muss 0 oder 1 sein")
        self._aktivieren(ziel)
        try:
            html = self._post(self.LP + "lehrpersonen_faecher.php", {"mode": 0, "school_year": sj})
        finally:
            if sj:
                self._schuljahr_zurueck()
        if ziel["typ"] == "Klasse":
            return P.parse_lehrpersonen_faecher(html)
        return P.parse_arbeitsgruppe_faecher(html)

    @staticmethod
    def _art(r: dict) -> str:
        if r["klr"]:
            return "Klassenlehrperson"
        return "SoPä" if r["spm"] else "Fachlehrperson"

    @classmethod
    def _gruppieren(cls, zeilen: list[dict]) -> list[dict]:
        lps: dict[int, dict] = {}
        for z in zeilen:
            lp = lps.setdefault(z["lehrperson_id"], {
                "id": z["lehrperson_id"], "name": z["lehrperson"], "faecher": [],
                **{k: z[k] for k in ("klr", "fp", "spm", "abs")},
                "klassenlehrperson": z["klr_automatisch"],
                "automatisch": [k for k in ("spm", "abs") if z[k + "_automatisch"]]})
            lp["faecher"].append({"assign_id": z["assign_id"], "id": z["fach_id"], "name": z["fach"],
                                  "kurz": z["fach_kurz"], "gesundheit": z["gesundheit"]})
        for lp in lps.values():
            lp["art"] = cls._art(lp)
        return sorted(lps.values(), key=lambda x: x["name"] or "")

    def _kopf(self, ziel: dict, sj: int) -> dict:
        k = "klasse_id" if ziel["typ"] == "Klasse" else "arbeitsgruppe_id"
        return {k: ziel["id"], "schuljahr": sj}

    def klasse_lehrpersonen(self, klasse_id: int | None = None, schuljahr: int = 0,
                            arbeitsgruppe_id: int | None = None) -> dict:
        """Alle Lehrpersonen einer Klasse/Arbeitsgruppe mit Fächern und Rechten."""
        ziel = self._ziel(klasse_id, arbeitsgruppe_id)
        with self._lock:
            zeilen = self._matrix(ziel, schuljahr)
        return {**self._kopf(ziel, schuljahr), "lehrpersonen": self._gruppieren(zeilen), "zuteilungen": zeilen}

    def _lehrperson_oeffnen(self, lp_id: int, ziel: dict, sj: int) -> str:
        """„Fächer anzeigen“ – setzt in Escola die aktive Lehrperson für das nachfolgende Zuteilen."""
        return self._post(self.LP + "zeige_faecher.php", {"type": 1, "lehrperson": lp_id, "fach_id": 0,
                                                          **self._ziel_params(ziel, sj)})

    def lehrperson_faecher(self, lp_id: int, klasse_id: int | None = None, schuljahr: int = 0,
                           arbeitsgruppe_id: int | None = None) -> dict:
        """Eine Lehrperson in einer Klasse/Arbeitsgruppe: alle Fächer (zugeteilt ja/nein) und Rechte."""
        ziel = self._ziel(klasse_id, arbeitsgruppe_id)
        with self._lock:
            zeilen = self._matrix(ziel, schuljahr)
            auswahl = P.parse_faecher_auswahl(self._lehrperson_oeffnen(int(lp_id), ziel, schuljahr))
        eigene = [z for z in zeilen if z["lehrperson_id"] == int(lp_id)]
        hat = {z["fach_id"] for z in eigene}
        for f in auswahl:
            f["zugeteilt"] = f["id"] in hat
        lp = (self._gruppieren(eigene) or [{"id": int(lp_id), "name": None, "faecher": [], "klr": False, "fp": False,
                                            "klassenlehrperson": False,
                                            "spm": False, "abs": False, "automatisch": [], "art": None}])[0]
        return {**self._kopf(ziel, schuljahr), **lp, "faecher_der_klasse": auswahl}

    def lehrperson_faecher_setzen(self, lp_id: int, klasse_id: int | None = None, faecher_hinzu: list[int] | None = None,
                                  faecher_weg: list[int] | None = None, rechte: dict | None = None,
                                  vorlage: str | None = None, faecher: list[int] | None = None,
                                  probelauf: bool = False, schuljahr: int = 0,
                                  arbeitsgruppe_id: int | None = None) -> dict:
        """Fächer zuteilen/entfernen und Rechte setzen.

        Regeln (Sekundarschule Bülach):
        - KLR setzt Escola SpM, Abs und Gesundheit automatisch.
        - Abs gibt es nur für die ganze Klasse -> für Nicht-Klassenlehrpersonen nicht setzbar.
        - Gesundheit wird nicht über die API gesetzt (folgt KLR).
        - Arbeitsgruppen: nur Fächer (keine KLR/FP/SpM; Abs nicht vorgesehen).
        - Kommendes Schuljahr: nur Fächer (Rechte dort noch nicht live geprüft).
        Vorlagen: klassenlehrperson (KLR), fachlehrperson (nur Fächer, keine Rechte),
        sopae (alle Fächer + SpM + FP)."""
        lp_id = int(lp_id)
        ziel = self._ziel(klasse_id, arbeitsgruppe_id)
        ist_ag = ziel["typ"] == "Arbeitsgruppe"
        hinzu, weg = set(faecher_hinzu or []), set(faecher_weg or [])
        soll = {k: bool(v) for k, v in (rechte or {}).items() if v is not None}
        if set(soll) - set(self.RECHTE_MODI):
            raise ValueError(f"Unbekannte Rechte: {sorted(set(soll) - set(self.RECHTE_MODI))} "
                             "(erlaubt: klr, fp, spm, abs; Gesundheit ist nur lesbar)")
        if soll and ist_ag:
            raise ValueError("Bei Arbeitsgruppen setzt die API keine Rechte (nur Fächer)")
        aktuell = self.lehrperson_faecher(lp_id, klasse_id, schuljahr, arbeitsgruppe_id)
        alle = {f["id"] for f in aktuell["faecher_der_klasse"]}
        hat = {f["id"] for f in aktuell["faecher"]}
        if vorlage:
            if vorlage not in self.VORLAGEN:
                raise ValueError(f"Unbekannte Vorlage {vorlage!r} (erlaubt: {', '.join(self.VORLAGEN)})")
            if ist_ag and vorlage == "klassenlehrperson":
                raise ValueError("Arbeitsgruppen haben keine Klassenlehrperson")
            if vorlage == "sopae":
                hinzu |= alle - hat
                soll = {} if ist_ag else {"klr": False, "spm": True, "fp": True, "abs": False}
            elif vorlage == "fachlehrperson":
                if faecher is None and not (hat | hinzu) - weg:
                    raise ValueError("Vorlage fachlehrperson braucht mindestens ein Fach (faecher)")
                soll = {} if ist_ag else {"klr": False, "spm": False, "fp": False, "abs": False}
            else:
                soll = {**soll, "klr": True}
        if faecher is not None:  # Soll-Liste – auch ohne Vorlage
            hinzu |= set(faecher) - hat
            weg |= hat - set(faecher)
        unbekannt = (hinzu | weg) - alle
        if unbekannt:
            raise ValueError(f"Fächer gibt es hier nicht: {sorted(unbekannt)}")
        if hinzu & weg:
            raise ValueError(f"Fächer gleichzeitig hinzufügen und entfernen: {sorted(hinzu & weg)}")
        hinzu, weg = hinzu - hat, weg & hat
        endfaecher = (hat | hinzu) - weg
        if aktuell.get("klassenlehrperson"):
            if soll.get("klr") is False:
                raise ValueError("Die Person ist Klassenlehrperson dieser Klasse; KLR hängt daran. "
                                 "Zuerst über PUT /klassen/{id}/klassenlehrpersonen austragen.")
            soll.pop("klr", None)
        klr_end = soll.get("klr", aktuell["klr"])
        if soll.get("abs") and not klr_end:
            raise ValueError("Abs (Klassenlehrpersonen-Rechte in den Absenzen) gilt für die ganze Klasse und ist nur "
                             "für Klassenlehrpersonen vorgesehen. Fachlehrpersonen sehen die Absenzen ihrer Lektionen.")
        if klr_end:
            soll.pop("spm", None); soll.pop("abs", None)  # setzt Escola selbst
        if soll and not endfaecher:
            raise ValueError("Rechte gibt es nur zusammen mit mindestens einem Fach in der Klasse")
        if endfaecher and not ist_ag:  # Abs bei Nicht-KLR immer aus (Regel: Absenzen nur in den eigenen Fächern)
            if not klr_end and aktuell["abs"] and "abs" not in aktuell["automatisch"]:
                soll.setdefault("abs", False)
        rechte_aend = {k: v for k, v in soll.items() if v != aktuell[k]}
        if rechte_aend and schuljahr:
            raise ValueError("Rechte fürs kommende Schuljahr setzt die API noch nicht (nur Fächer); "
                             "Rechte nach dem Schuljahreswechsel setzen")
        reihenfolge = sorted(rechte_aend, key=lambda k: (k != "klr", k))
        plan = {"lehrperson_id": lp_id, **self._kopf(ziel, schuljahr), "faecher_hinzu": sorted(hinzu),
                "faecher_weg": sorted(weg), "rechte": {k: rechte_aend[k] for k in reihenfolge}}
        if probelauf:
            return {"probelauf": True, **plan, "vorher": aktuell}
        assign = {f["id"]: f["assign_id"] for f in aktuell["faecher"]}
        with self._lock:
            self._aktivieren(ziel)
            try:
                for fid in sorted(hinzu):
                    # Escola teilt der zuletzt mit „Fächer anzeigen“ geöffneten Lehrperson zu (live geprüft)
                    self._lehrperson_oeffnen(lp_id, ziel, schuljahr)
                    self._post(self.LP + "ajax_functions_lehrpersonen.php",
                               {"type": 1, "fach_id": fid, "wert": 1, **self._ziel_params(ziel, schuljahr)})
                if endfaecher:
                    for k in reihenfolge:
                        d = {"mode": self.RECHTE_MODI[k], "lehrer_id": lp_id, "new_value": int(rechte_aend[k])}
                        if k == "klr":
                            d["allowed"] = 1
                        self._post(self.LP + "lehrpersonen_faecher.php", d)
                if weg:
                    # Zuteilungsnummern gelten nur im aktiven Kontext (Klasse bzw. Arbeitsgruppe) -> neu aktivieren
                    self._aktivieren(ziel)
                    for fid in sorted(weg):
                        self._post(self.LP + "lehrpersonen_faecher.php", {"mode": 2, "assignment": assign[fid]})
            finally:
                if schuljahr:
                    self._schuljahr_zurueck()
        self._cache.clear()  # Stundenplan-/Lehrpersonen-Caches hängen davon ab
        nachher = self.lehrperson_faecher(lp_id, klasse_id, schuljahr, arbeitsgruppe_id)
        fehler = []
        if {f["id"] for f in nachher["faecher"]} != endfaecher:
            fehler.append("Fächer")
        if endfaecher:
            fehler += [k for k, v in rechte_aend.items() if nachher[k] != v]
        if fehler:
            raise RuntimeError(f"Escola hat nicht alles übernommen: {', '.join(fehler)}")
        return {**plan, "nachher": nachher}

    # ------------------------------------------------------------------ Klassenlehrpersonen (Einstellungen → Klassen)
    def _klassen_formular(self, klasse_id: int):
        # mode=903/902 funktionieren nur im Kontext „Einstellungen → Klassen“ (sub_k=10), live geprüft
        self._get("admin.php?page_request=6&sub_k=10")
        return P.klassen_formular(self._get(f"admin.php?page_request=6&mode=903&id={int(klasse_id)}"))

    def _klp_antwort(self, klasse_id: int, info: dict) -> dict:
        n = info["waehlbar"]
        f = lambda ids: [{"slot": "ABC"[i], "id": pid, "name": n.get(pid)} for i, pid in enumerate(ids)]
        return {"klasse_id": int(klasse_id), "name": info["name"], "name_kommend": info["name_kommend"],
                "aktuell": f(info["klassenlehrpersonen"]["aktuell"]),
                "kommend": f(info["klassenlehrpersonen"]["kommend"]),
                "wird_archiviert": info["wird_archiviert"]}

    def klassenlehrpersonen(self, klasse_id: int, waehlbar: bool = False) -> dict:
        """Klassenlehrpersonen A/B/C einer Klasse, aktuelles und kommendes Schuljahr."""
        with self._lock:
            _, info = self._klassen_formular(klasse_id)
        res = self._klp_antwort(klasse_id, info)
        if waehlbar:
            res["waehlbar"] = [{"id": k, "name": v} for k, v in info["waehlbar"].items()]
        return res

    def klassenlehrpersonen_setzen(self, klasse_id: int, aktuell: list[int] | None = None,
                                   kommend: list[int] | None = None, probelauf: bool = False) -> dict:
        """Klassenlehrpersonen setzen (Liste = Soll für Slot A, B, C; [] = keine). None = unverändert.
        Escola gibt Klassenlehrpersonen automatisch die KLR-Rechte der Klasse."""
        soll = {k: v for k, v in (("aktuell", aktuell), ("kommend", kommend)) if v is not None}
        if not soll:
            raise ValueError("aktuell und/oder kommend angeben")
        with self._lock:
            felder, info = self._klassen_formular(klasse_id)
            for k, ids in soll.items():
                ids = [int(i) for i in ids]
                if len(ids) > 3:
                    raise ValueError("Höchstens 3 Klassenlehrpersonen (A, B, C)")
                if len(set(ids)) != len(ids):
                    raise ValueError(f"Doppelte Person in {k}")
                fremd = [i for i in ids if i not in info["waehlbar"]]
                if fremd:
                    raise ValueError(f"Nicht als Klassenlehrperson wählbar: {fremd}")
                if k == "kommend" and info["wird_archiviert"]:
                    raise ValueError("Klasse wird beim Schuljahreswechsel archiviert – kein kommendes Schuljahr")
                soll[k] = ids
            neu = {n: str(ids[i]) if i < len(ids) else "0"
                   for k, ids in soll.items() for i, n in enumerate(P.KLP_FELDER[k])}
            alt = {n: v for n, v in felder if n in neu}
            aend = {n: (alt.get(n), v) for n, v in neu.items() if alt.get(n) != v}
            vorher = self._klp_antwort(klasse_id, info)
            if probelauf or not aend:
                return {"probelauf": probelauf, "geaendert": bool(aend), "vorher": vorher,
                        "soll": {k: v for k, v in soll.items()}}
            daten = [(n, neu.get(n, v)) for n, v in felder] + [("submit", "Abschicken")]
            from urllib.parse import urlencode
            r = self._http.post(f"admin.php?page_request=6&mode=902&id={int(klasse_id)}", content=urlencode(daten).encode(),
                                headers={"Content-Type": "application/x-www-form-urlencoded; charset=UTF-8"})
            if r.is_redirect:
                if "login" in r.headers.get("location", "").lower():
                    raise SessionAbgelaufen("Escola-Session abgelaufen (Umleitung auf Login)")
            else:
                self._check(r)
            felder2, info2 = self._klassen_formular(klasse_id)
        self._cache.clear()
        andere_alt = [(n, v) for n, v in felder if n not in neu]
        andere_neu = [(n, v) for n, v in felder2 if n not in neu]
        if andere_alt != andere_neu:
            raise RuntimeError("Escola hat andere Klassen-Einstellungen verändert – bitte in Escola prüfen")
        if any(info2["klassenlehrpersonen"][k] != v for k, v in soll.items()):
            raise RuntimeError("Escola hat die Klassenlehrpersonen nicht übernommen")
        return {"geaendert": True, "vorher": vorher, "nachher": self._klp_antwort(klasse_id, info2)}

    # ------------------------------------------------------------------ AHV, Schulmail, Mitarbeitende
    SCHULMAIL_DOMAIN = "sekbuelach.ch"

    def personen_index(self, refresh: bool = False) -> dict:
        """AHV-Nummer und E-Mail aller aktiven und inaktiven Personen (für die Prüfung auf Doppelte).
        Liest jede Person einzeln (Reiter Personalien + Geschäft) – dauert, wird zwischengespeichert."""
        from . import personen as PP

        def load():
            eintraege, fehler = [], []
            for kat in ("allActive", "allInactive"):
                for p in self.personen(kat, refresh=True):
                    try:
                        with self._lock:
                            _, felder, _ = self._person_laden(p["id"], kat, ["personalien", "geschaeft"], False)
                    except Exception:  # Person nicht lesbar -> melden, nicht abbrechen
                        fehler.append(p["id"])
                        continue
                    w = {f.name: f.wert for f in felder}
                    eintraege.append({"id": p["id"], "name": f'{p["nachname"]} {p["vorname"]}'.strip(),
                                      "aktiv": kat == "allActive", "ahv": PP.ahv_normal(w.get("ahv")),
                                      "email": (w.get("email") or "").strip().lower()})
            return {"personen": eintraege, "nicht_gelesen": fehler, "stand": time.strftime("%Y-%m-%d %H:%M")}
        return self._cached("personen_index", load, refresh)

    def personen_suchen(self, ahv: str | None = None, email: str | None = None, refresh: bool = False) -> dict:
        """Personen mit dieser AHV-Nummer bzw. E-Mail (aktiv und inaktiv). AHV wird nicht zurückgegeben."""
        from . import personen as PP
        if not ahv and not email:
            raise ValueError("ahv oder email angeben")
        idx = self.personen_index(refresh)
        a = PP.ahv_normal(ahv) if ahv else None
        e = email.strip().lower() if email else None
        treffer = [{k: p[k] for k in ("id", "name", "aktiv")} for p in idx["personen"]
                   if (a and p["ahv"] == a) or (e and p["email"] == e)]
        return {"treffer": treffer, "index_stand": idx["stand"], "nicht_gelesen": idx["nicht_gelesen"]}

    def _feld_freigegeben_schreiben(self, pid: int, kategorie: str, name: str, wert: str) -> str | None:
        """Ein einzelnes, sonst gesperrtes Feld gezielt schreiben (nur aus geprüften Abläufen)."""
        from . import personen as PP
        with self._lock:
            _, felder, war_an = self._person_laden(pid, kategorie, None, False)
            f = {x.name: x for x in felder}.get(name)
            if f is None:
                raise ValueError(f"Feld '{name}' bei Person {pid} nicht gefunden")
            payload = PP.schreib_payload(f, wert, freigabe=True)
            if war_an is False:
                self._raw(self.PERS + "ajax_functions_persons.php", "type=1&edit_mode=1")
            try:
                self._post(self.PERS + "ajax_functions_persons.php", payload)
            finally:
                if war_an is False:
                    self._raw(self.PERS + "ajax_functions_persons.php", "type=1&edit_mode=0")
            _, neu, _ = self._person_laden(pid, kategorie, [f.abschnitt], False)
        return {x.name: x.wert for x in neu}.get(name)

    def ahv_setzen(self, pid: int, ahv: str, ueberschreiben: bool = False, kategorie: str = "allActive",
                   probelauf: bool = False) -> dict:
        """AHV-Nummer setzen: Format + Prüfziffer, darf keiner anderen Person gehören."""
        from . import personen as PP
        try:
            schoen = PP.ahv_pruefen(ahv)
        except PP.FeldFehler as e:
            raise ValueError(str(e))
        with self._lock:
            _, felder, _ = self._person_laden(pid, kategorie, ["personalien"], False)
        alt = PP.ahv_normal({f.name: f.wert for f in felder}.get("ahv"))
        if alt == PP.ahv_normal(schoen):
            return {"id": pid, "geaendert": False, "ahv": "gesetzt (unverändert)"}
        if alt and not ueberschreiben:
            raise KonfliktFehler("Die Person hat schon eine andere AHV-Nummer (ueberschreiben=true zum Ersetzen)")
        andere = [t for t in self.personen_suchen(ahv=schoen, refresh=True)["treffer"] if t["id"] != pid]
        if andere:
            raise KonfliktFehler("AHV-Nummer gehört schon einer anderen Person", andere)
        if probelauf:
            return {"id": pid, "probelauf": True, "geaendert": True}
        jetzt = self._feld_freigegeben_schreiben(pid, kategorie, "ahv", schoen)
        self._cache.pop("personen_index", None)
        if PP.ahv_normal(jetzt) != PP.ahv_normal(schoen):
            raise RuntimeError("Escola hat die AHV-Nummer nicht übernommen")
        return {"id": pid, "geaendert": True, "ahv": "gesetzt"}

    def schulmail_setzen(self, pid: int, vorname: str | None = None, nachname: str | None = None,
                         kategorie: str = "allActive", probelauf: bool = False) -> dict:
        """Schulmail vorname.nachname@sekbuelach.ch bilden, auf Doppelte prüfen und als E-Mail (Geschäft) setzen."""
        from . import personen as PP
        if not vorname or not nachname:
            with self._lock:
                _, felder, _ = self._person_laden(pid, kategorie, ["name"], False)
            w = {f.name: f.wert for f in felder}
            vorname, nachname = vorname or w.get("vorname"), nachname or w.get("name")
        try:
            adresse = PP.schulmail(vorname or "", nachname or "", self.SCHULMAIL_DOMAIN)
        except PP.FeldFehler as e:
            raise ValueError(str(e))
        andere = [t for t in self.personen_suchen(email=adresse, refresh=True)["treffer"] if t["id"] != pid]
        if andere:
            raise KonfliktFehler(f"{adresse} ist schon vergeben – bitte von Hand lösen", andere)
        if probelauf:
            return {"id": pid, "probelauf": True, "email": adresse}
        jetzt = self._feld_freigegeben_schreiben(pid, kategorie, "email", adresse)
        self._cache.pop("personen_index", None)
        if (jetzt or "").lower() != adresse:
            raise RuntimeError("Escola hat die E-Mail nicht übernommen")
        return {"id": pid, "email": adresse}

    def mitarbeiter_einstellen(self, nachname: str, vorname: str, geschlecht: str, schulhaus: str,
                               rolle: str, rollen_ids: list[int] | None = None, ahv: str | None = None,
                               felder: dict | None = None, schulmail: bool = True,
                               trotz_duplikat: bool = False, probelauf: bool = False) -> dict:
        """WF-01: anlegen, Rollen, Personendaten, AHV, Schulmail – mit Prüfungen VOR dem Anlegen."""
        from . import personen as PP
        schritte: list[dict] = []
        # 1. Prüfen, bevor etwas angelegt wird
        try:
            ahv_schoen = PP.ahv_pruefen(ahv) if ahv else None
            adresse = PP.schulmail(vorname, nachname, self.SCHULMAIL_DOMAIN) if schulmail else None
        except PP.FeldFehler as e:
            raise ValueError(str(e))
        rollen_ids = list(rollen_ids or [])
        if rollen_ids:
            zuordenbar = {r["id"] for r in self.rollen(refresh=True) if r.get("zuordenbar")}
            fremd = [r for r in rollen_ids if r not in zuordenbar]
            if fremd:
                raise ValueError(f"Rollen nicht zuordenbar: {fremd}")
        if ahv_schoen:
            t = self.personen_suchen(ahv=ahv_schoen, refresh=True)["treffer"]
            if t:
                raise KonfliktFehler("AHV-Nummer gehört schon einer Person (evtl. ehemalige:r Mitarbeiter:in – reaktivieren?)", t)
        if adresse:
            t = self.personen_suchen(email=adresse)["treffer"]
            if t:
                raise KonfliktFehler(f"{adresse} ist schon vergeben – bitte von Hand lösen", t)
        plan = {"nachname": nachname, "vorname": vorname, "schulhaus": schulhaus, "rolle": rolle,
                "rollen_ids": rollen_ids, "ahv": bool(ahv_schoen), "schulmail": adresse,
                "felder": sorted((felder or {}).keys())}
        if probelauf:
            return {"probelauf": True, "plan": plan}
        # 2. Anlegen
        neu = self.person_anlegen(nachname, vorname, geschlecht, rolle, schulhaus, None, trotz_duplikat)
        if not neu.get("angelegt"):
            raise KonfliktFehler("Escola meldet mögliche Duplikate", neu.get("duplikate"))
        pid = neu["id"]
        schritte.append({"schritt": "angelegt", "ok": True, "id": pid})
        # 3.–6. Weitere Schritte; bei Fehlern weitermachen und melden (Person existiert bereits)
        def schritt(name, fn):
            try:
                schritte.append({"schritt": name, "ok": True, "ergebnis": fn()})
            except Exception as e:
                schritte.append({"schritt": name, "ok": False, "fehler": str(e)})
        if rollen_ids:
            def r():
                res = self.person_rollen_setzen(pid, rollen_ids, [])
                if res.get("fehler"):
                    raise ValueError(res["fehler"])
                return [x.get("name") for x in res.get("rollen", [])]
            schritt("rollen", r)
        if felder:
            def f():
                r = self.person_schreiben(pid, felder)
                if not r.get("geschrieben"):
                    raise ValueError(r.get("fehler"))
                return [a["feld"] for a in r["aenderungen"]]
            schritt("felder", f)
        if ahv_schoen:
            schritt("ahv", lambda: self.ahv_setzen(pid, ahv_schoen)["ahv"])
        if adresse:
            schritt("schulmail", lambda: self.schulmail_setzen(pid, vorname, nachname)["email"])
        return {"id": pid, "vollstaendig": all(s["ok"] for s in schritte), "schritte": schritte}

    def lehrperson_einsatz(self, lp_id: int) -> dict:
        """Wo ist eine Lehrperson eingesetzt? Klassenlehrperson-Plätze, Fach-Zuteilungen, Stundenplan."""
        lp_id = int(lp_id)
        klassen = [k for k in self.klassen(refresh=True) if k.get("typ") == "Klasse"]
        klp, faecher = [], []
        for k in klassen:
            try:
                r = self.klassenlehrpersonen(k["id"])
            except ValueError:
                continue
            for sj in ("aktuell", "kommend"):
                for x in r[sj]:
                    if x["id"] == lp_id:
                        klp.append({"klasse_id": k["id"], "klasse": r["name"], "schuljahr": sj, "slot": x["slot"]})
            z = self.klasse_lehrpersonen(k["id"])
            for lp in z["lehrpersonen"]:
                if lp["id"] == lp_id:
                    faecher.append({"klasse_id": k["id"], "klasse": k.get("name"),
                                    "faecher": [f["id"] for f in lp["faecher"]],
                                    **{x: lp[x] for x in ("klr", "fp", "spm", "abs", "art")}})
        stunden = [e for e in self.eintraege(refresh=True)
                   if lp_id in (e.get("lehrperson_ids") or [])]
        return {"id": lp_id, "klassenlehrperson": klp, "fach_zuteilungen": faecher,
                "stundenplan_eintraege": len(stunden), "stundenplan": stunden}

    # ------------------------------------------------------------------ Stundenplan schreiben
    TAGE = ("A", "B", "C", "D", "E")

    def _zelle_param(self, klasse_id: int, tag: str, lektion_id: int) -> dict:
        if tag not in self.TAGE:
            raise ValueError("tag muss A–E sein (A = Montag)")
        return {"classOrWorkgroupId": int(klasse_id), "schoolYear": 0, "semester": 1, "dayCode": tag,
                "lessonId": int(lektion_id), "classOrWorkgroupMode": "class"}

    def _zelle_lesen(self, cell: dict) -> list[dict]:
        html = self._post(TT, {**cell, "type": 1})
        if "invalid input" in html:
            raise ValueError("Tag oder Lektion gibt es in diesem Stundenplan nicht")
        return P.parse_eintrag_details(html)

    def stundenplan_zelle(self, klasse_id: int, tag: str, lektion_id: int) -> dict:
        """Alle Einträge einer Zelle mit IDs und dem, was wählbar ist (ändert nichts)."""
        cell = self._zelle_param(klasse_id, tag, lektion_id)
        with self._lock:
            self._aktivieren({"typ": "Klasse", "id": int(klasse_id)})
            try:
                eintraege = self._zelle_lesen(cell)
            finally:
                self._post(TT, {**cell, "type": 3})
        return {"klasse_id": int(klasse_id), "tag": tag, "lektion_id": int(lektion_id), "eintraege": eintraege}

    def _eintrag_setzen(self, cell: dict, e: dict, fach_id, raum_ids, lehrperson_ids) -> list[str]:
        """Fach, Räume und Lehrpersonen eines Eintrags auf Soll bringen. Gibt Hinweise zurück."""
        hinweise = []
        rid = e["eintrag_id"]
        if fach_id is not None and fach_id != e["fach_id"]:
            if fach_id not in e["faecher_waehlbar"]:
                raise ValueError(f"Fach {fach_id} ist dieser Klasse nicht zugeteilt (zuerst Fächer-Zuteilung)")
            self._post(TT, {**cell, "type": 1, "new_entry": 1, "id": rid, "courseId": fach_id})
            e = next(x for x in self._zelle_lesen(cell) if x["eintrag_id"] == rid)
        if raum_ids is not None:
            if len(raum_ids) > 3:
                raise ValueError("Höchstens 3 Räume pro Eintrag")
            fremd = [r for r in raum_ids if r not in e["raeume_waehlbar"]]
            if fremd:
                raise ValueError(f"Räume nicht wählbar (anderes Schulhaus?): {fremd}")
            for i in range(3):
                soll = raum_ids[i] if i < len(raum_ids) else None
                if soll != e["raum_slots"][i]:
                    self._post(TT, {"type": 18, "roomId": soll or 0, "timetableRowId": rid, "roomType": i + 1})
        if lehrperson_ids is not None:
            soll = set(int(x) for x in lehrperson_ids)
            lps = {x["id"]: x for x in e["lehrpersonen"]}
            fremd = soll - set(lps)
            if fremd:
                raise ValueError(f"Lehrpersonen haben dieses Fach in der Klasse nicht: {sorted(fremd)} "
                                 "(zuerst Fächer-Zuteilung)")
            for pid, x in lps.items():
                if (pid in soll) != x["gewaehlt"]:
                    if not x["schaltbar"]:
                        hinweise.append(f"Lehrperson {pid} ist automatisch eingetragen (einzige mit diesem Fach) – "
                                        "ändern über die Fächer-Zuteilung")
                        continue
                    self._post(TT, {"timetableRowId": rid, "teacherId": pid, "type": 2})  # Umschalter
        return hinweise

    def stundenplan_schreiben(self, klasse_id: int, tag: str, lektion_id: int, eintrag_id: int | None = None,
                              fach_id: int | None = None, raum_ids: list[int] | None = None,
                              lehrperson_ids: list[int] | None = None, loeschen: bool = False,
                              probelauf: bool = False) -> dict:
        """Eintrag anlegen (eintrag_id=None), ändern oder löschen. Gilt fürs aktuelle Schuljahr."""
        cell = self._zelle_param(klasse_id, tag, lektion_id)
        if eintrag_id is None and (loeschen or fach_id is None):
            raise ValueError("Neuer Eintrag braucht fach_id")
        with self._lock:
            self._schuljahr_sicher(klasse_id)
            self._aktivieren({"typ": "Klasse", "id": int(klasse_id)})
            hinweise: list[str] = []
            erlaubt = self._faecher_klasse(klasse_id) if eintrag_id is None and not loeschen else set()
            try:
                vorher = self._zelle_lesen(cell)
                if eintrag_id is not None and eintrag_id not in {e["eintrag_id"] for e in vorher}:
                    raise ValueError(f"Eintrag {eintrag_id} gibt es in dieser Zelle nicht")
                if probelauf:
                    return {"probelauf": True, "vorher": vorher}
                if loeschen:
                    self._post(TT, {**cell, "type": 1, "deleteEntry": int(eintrag_id)})
                    rid = None
                else:
                    if eintrag_id is None:
                        if fach_id not in erlaubt:
                            raise ValueError(f"Fach {fach_id} ist dieser Klasse nicht zugeteilt (zuerst Fächer-Zuteilung)")
                        if vorher:  # belegte Zelle: Escola legt sofort einen leeren Eintrag an
                            html = self._post(TT, {**cell, "type": 1, "addCourseField": 1, "entryType": 0})
                            neu = {e["eintrag_id"] for e in P.parse_eintrag_details(html)} - {e["eintrag_id"] for e in vorher}
                        else:
                            html = self._post(TT, {**cell, "type": 1, "new_entry": 1, "id": f"new_{int(lektion_id)}_{tag}",
                                                   "courseId": fach_id})
                            neu = {e["eintrag_id"] for e in P.parse_eintrag_details(html)}
                        if len(neu) != 1:
                            raise RuntimeError("Escola hat keinen neuen Eintrag angelegt")
                        rid = neu.pop()
                    else:
                        rid = int(eintrag_id)
                    e = next(x for x in self._zelle_lesen(cell) if x["eintrag_id"] == rid)
                    hinweise = self._eintrag_setzen(cell, e, fach_id, raum_ids, lehrperson_ids)
                nachher = self._zelle_lesen(cell)
            finally:
                self._post(TT, {**cell, "type": 3})
        self._cache.clear()
        if loeschen and int(eintrag_id) in {e["eintrag_id"] for e in nachher}:
            raise RuntimeError("Escola hat den Eintrag nicht gelöscht")
        eintrag = next((x for x in nachher if x["eintrag_id"] == rid), None) if rid else None
        if eintrag is not None:
            fehler = []
            if fach_id is not None and eintrag["fach_id"] != fach_id:
                fehler.append("Fach")
            if raum_ids is not None and eintrag["raum_ids"] != list(raum_ids):
                fehler.append("Räume")
            if fehler:
                raise RuntimeError(f"Escola hat nicht alles übernommen: {', '.join(fehler)}")
        return {"klasse_id": int(klasse_id), "tag": tag, "lektion_id": int(lektion_id),
                "eintrag": eintrag, "geloescht": bool(loeschen), "hinweise": hinweise, "zelle": nachher}

    # ------------------------------------------------------------------ Stundenplan-Abgleich (L14, Issue #6)
    def _belegte_zellen(self, klasse_id: int) -> set[tuple[str, int]]:
        k = next((x for x in self._klassen_nur() if x["id"] == int(klasse_id)), None)
        if k is None:
            raise KeyError(f"Klasse {klasse_id} nicht gefunden")
        with self._lock:
            return {(e["tag_code"], int(e["lektion_id"])) for e in P.parse_stundenplan(self._stundenplan_html(k))}

    def stundenplan_abgleich(self, klasse_id: int, soll: list[dict], loeschen: bool = False,
                             probelauf: bool = True) -> dict:
        """Soll-Stundenplan einer Klasse (z. B. aus dem Stundenplaner-Export, von IDA/CONNECT ins neutrale Format
        gebracht) gegen Escola abgleichen. `soll`: [{tag, lektion_id, fach_id, raum_ids?, lehrperson_ids?}].
        Pro Zelle werden Einträge über das Fach zugeordnet; fehlende werden angelegt, abweichende Räume/Lehrpersonen
        geändert, überzählige nur mit `loeschen=True` gelöscht (sonst als `bleibt` gemeldet).
        Mit Fehlern (z. B. Fach der Klasse nicht zugeteilt) wird nichts geschrieben."""
        fehler, plan = [], {"neu": [], "aendern": [], "loeschen": [], "bleibt": [], "unveraendert": 0}
        zellen: dict[tuple[str, int], list[dict]] = {}
        for i, e in enumerate(soll):
            tag, lid = str(e.get("tag", "")).upper(), e.get("lektion_id")
            if tag not in self.TAGE or not isinstance(lid, int) or not isinstance(e.get("fach_id"), int):
                fehler.append({"zeile": i, "fehler": "tag (A–E), lektion_id und fach_id sind Pflicht"})
                continue
            zellen.setdefault((tag, lid), []).append({**e, "tag": tag, "zeile": i})
        erlaubt = self._faecher_klasse(klasse_id)
        for (tag, lid), es in zellen.items():
            for e in es:
                if e["fach_id"] not in erlaubt:
                    fehler.append({"zeile": e["zeile"], "fehler": f"Fach {e['fach_id']} ist der Klasse nicht zugeteilt (zuerst Fächer-Zuteilung)"})
        alle = set(zellen) | self._belegte_zellen(klasse_id)
        for tag, lid in sorted(alle):
            ist = list(self.stundenplan_zelle(klasse_id, tag, lid)["eintraege"])
            for e in zellen.get((tag, lid), []):
                treffer = next((x for x in ist if x.get("fach_id") == e["fach_id"]), None)
                ziel = {"tag": tag, "lektion_id": lid, "fach_id": e["fach_id"],
                        "raum_ids": e.get("raum_ids"), "lehrperson_ids": e.get("lehrperson_ids")}
                if treffer is None:
                    plan["neu"].append(ziel)
                    continue
                ist.remove(treffer)
                diff = {}
                if e.get("raum_ids") is not None and sorted(e["raum_ids"]) != sorted(treffer.get("raum_ids") or []):
                    diff["raum_ids"] = e["raum_ids"]
                lp_ist = sorted(treffer.get("lehrperson_ids") or [])
                if e.get("lehrperson_ids") is not None and sorted(e["lehrperson_ids"]) != lp_ist:
                    diff["lehrperson_ids"] = e["lehrperson_ids"]
                if diff:
                    plan["aendern"].append({"tag": tag, "lektion_id": lid, "eintrag_id": treffer["eintrag_id"],
                                            "fach_id": e["fach_id"], **diff})
                else:
                    plan["unveraendert"] += 1
            for rest in ist:
                eintrag = {"tag": tag, "lektion_id": lid, "eintrag_id": rest["eintrag_id"], "fach_id": rest.get("fach_id")}
                plan["loeschen" if loeschen else "bleibt"].append(eintrag)
        res = {"klasse_id": int(klasse_id), "probelauf": probelauf or bool(fehler), "plan": plan, "fehler": fehler}
        if probelauf or fehler:
            return res
        schritte = []
        for x in plan["neu"]:
            try:
                self.stundenplan_schreiben(klasse_id, x["tag"], x["lektion_id"], None, x["fach_id"], x["raum_ids"], x["lehrperson_ids"])
                schritte.append({**x, "aktion": "neu", "ok": True})
            except (ValueError, RuntimeError) as err:
                schritte.append({**x, "aktion": "neu", "ok": False, "fehler": str(err)})
        for x in plan["aendern"]:
            try:
                self.stundenplan_schreiben(klasse_id, x["tag"], x["lektion_id"], x["eintrag_id"], None,
                                           x.get("raum_ids"), x.get("lehrperson_ids"))
                schritte.append({**x, "aktion": "aendern", "ok": True})
            except (ValueError, RuntimeError) as err:
                schritte.append({**x, "aktion": "aendern", "ok": False, "fehler": str(err)})
        for x in plan["loeschen"]:
            try:
                self.stundenplan_schreiben(klasse_id, x["tag"], x["lektion_id"], x["eintrag_id"], loeschen=True)
                schritte.append({**x, "aktion": "loeschen", "ok": True})
            except (ValueError, RuntimeError) as err:
                schritte.append({**x, "aktion": "loeschen", "ok": False, "fehler": str(err)})
        self._cache.pop("stundenplaene", None)
        return {**res, "schritte": schritte, "vollstaendig": all(x["ok"] for x in schritte)}

    # ------------------------------------------------------------------ Felder pro Klasse (L16, Issue #8)
    def klasse_felder(self, klasse_id: int, felder: list[str], abschnitte: list[str] | None = None,
                      nur_leer: bool = False, schuljahr: int = 0) -> list[dict]:
        """Ausgewählte Felder aller Schüler:innen einer Klasse lesen, z. B. ein benutzerdefiniertes Feld
        „Kontrolle Zahnarzt“. `nur_leer=True` liefert nur die, bei denen mindestens ein Feld leer ist
        (Liste der offenen). Liest jede Person einzeln – mit `abschnitte` auf die nötigen Reiter begrenzen."""
        if not felder:
            raise ValueError("Mindestens ein Feld angeben")
        kinder = [x for x in self.schueler(schuljahr=schuljahr) if x.get("klasse_id") == int(klasse_id)]
        out = []
        for k in kinder:
            try:
                p = self.person(k["id"], "schueler", abschnitte)
                werte = {f: p.get("felder", {}).get(f) for f in felder}
                unbekannt = [f for f in felder if f not in p.get("felder", {})]
                row = {"schueler_id": k["id"], "nachname": k.get("nachname"), "vorname": k.get("vorname"), **werte,
                       "unbekannte_felder": ", ".join(unbekannt)}
            except (KeyError, ValueError, RuntimeError) as err:
                row = {"schueler_id": k["id"], "nachname": k.get("nachname"), "vorname": k.get("vorname"),
                       **{f: None for f in felder}, "unbekannte_felder": "", "fehler": str(err)}
            if not nur_leer or any(row.get(f) in (None, "") for f in felder):
                out.append(row)
        return out

    def _faecher_klasse(self, klasse_id: int) -> set[int]:
        return {z["fach_id"] for z in self._matrix({"typ": "Klasse", "id": int(klasse_id)}, 0)}

    def _schuljahr_sicher(self, klasse_id: int) -> None:
        """Sitzung sicher aufs aktuelle Schuljahr stellen (falls zuvor die Matrix mit school_year=1 lief)."""
        self._aktivieren({"typ": "Klasse", "id": int(klasse_id)})
        self._schuljahr_zurueck()

    def lehrperson_ersetzen(self, alt_id: int, neu_id: int, klassen_ids: list[int] | None = None,
                            klassenlehrperson: bool = True, probelauf: bool = False) -> dict:
        """Nachfolge (WF-04/06): in den Klassen der bisherigen Lehrperson dieselben Fächer der neuen geben,
        Stundenplan-Einträge übernehmen, Klassenlehrperson-Platz tauschen, bisherige austragen.
        Aktuelles Schuljahr; Rechte FP/SpM werden übernommen, KLR folgt dem Klassenlehrperson-Platz."""
        alt_id, neu_id = int(alt_id), int(neu_id)
        if alt_id == neu_id:
            raise ValueError("alt und neu sind dieselbe Person")
        einsatz = self.lehrperson_einsatz(alt_id)
        klassen = {z["klasse_id"]: z for z in einsatz["fach_zuteilungen"]}
        klp = [x for x in einsatz["klassenlehrperson"] if x["schuljahr"] == "aktuell"]
        if klassen_ids is not None:
            klassen = {k: v for k, v in klassen.items() if k in set(klassen_ids)}
            klp = [x for x in klp if x["klasse_id"] in set(klassen_ids)]
        stunden = [e for e in einsatz["stundenplan"] if e.get("klasse_id") in klassen]
        plan = {"alt": alt_id, "neu": neu_id,
                "klassen": [{"klasse_id": k, "faecher": v["faecher"], "fp": v["fp"], "spm": v["spm"] and not v["klr"]}
                            for k, v in klassen.items()],
                "klassenlehrperson_plaetze": klp if klassenlehrperson else [],
                "stundenplan_eintraege": len(stunden)}
        if probelauf:
            return {"probelauf": True, **plan}
        bericht = []

        def schritt(name, fn):
            try:
                bericht.append({"schritt": name, "ok": True, "ergebnis": fn()})
            except Exception as ex:
                bericht.append({"schritt": name, "ok": False, "fehler": str(ex)})

        for k in plan["klassen"]:  # 1. neue Lehrperson bekommt die Fächer (+ FP/SpM)
            rechte = {"fp": True} if k["fp"] else {}
            if k["spm"]:
                rechte["spm"] = True
            schritt(f"faecher_neu_{k['klasse_id']}", lambda k=k, r=rechte: self.lehrperson_faecher_setzen(
                neu_id, k["klasse_id"], faecher_hinzu=k["faecher"], rechte=r or None)["faecher_hinzu"])
        if klassenlehrperson:  # 2. Klassenlehrperson-Platz tauschen (gleiche Position)
            for x in klp:
                def tauschen(x=x):
                    aktuell = [p["id"] for p in self.klassenlehrpersonen(x["klasse_id"])["aktuell"]]
                    return self.klassenlehrpersonen_setzen(
                        x["klasse_id"], aktuell=[neu_id if p == alt_id else p for p in aktuell])["nachher"]["aktuell"]
                schritt(f"klassenlehrperson_{x['klasse_id']}", tauschen)
        for e in stunden:  # 3. Einträge mit Schaltern: neue Lehrperson einschalten
            def eintrag(e=e):
                z = self.stundenplan_zelle(e["klasse_id"], e["tag_code"], e["lektion_id"])
                for x in z["eintraege"]:
                    ids = {p["id"]: p for p in x["lehrpersonen"]}
                    if alt_id in ids and ids[alt_id]["gewaehlt"] and neu_id in ids and ids[neu_id]["schaltbar"] \
                            and not ids[neu_id]["gewaehlt"]:
                        soll = [p for p in x["lehrperson_ids"] if p != alt_id] + [neu_id]
                        self.stundenplan_schreiben(e["klasse_id"], e["tag_code"], e["lektion_id"], x["eintrag_id"],
                                                   lehrperson_ids=soll)
                return "ok"
            schritt(f"stunde_{e['klasse_id']}_{e['tag_code']}{e['lektion_id']}", eintrag)
        for k in plan["klassen"]:  # 4. bisherige Lehrperson austragen
            schritt(f"faecher_alt_{k['klasse_id']}", lambda k=k: self.lehrperson_faecher_setzen(
                alt_id, k["klasse_id"], faecher=[])["faecher_weg"])
        return {**plan, "vollstaendig": all(b["ok"] for b in bericht), "schritte": bericht}

    # ------------------------------------------------------------------ Austritt: Rolle „Ausgetreten“ (F-03)
    ROLLE_AUSGETRETEN = "Ausgetreten"

    def rolle_ausgetreten(self) -> dict:
        r = [x for x in self.rollen(refresh=True) if (x["name"] or "").strip().lower() == self.ROLLE_AUSGETRETEN.lower()]
        if not r:
            raise KonfliktFehler(f"Rolle „{self.ROLLE_AUSGETRETEN}“ fehlt – bitte in Escola unter Personen → "
                                 "Personengruppen anlegen und danach erneut ausführen")
        if not r[0]["zuordenbar"]:
            raise KonfliktFehler(f"Rolle „{self.ROLLE_AUSGETRETEN}“ ist keine eigene Rolle (Personengruppe)")
        return r[0]

    def rollen_ausgetreten(self, pid: int, probelauf: bool = False) -> dict:
        """Alle zuordenbaren Rollen der Person entfernen und die Rolle „Ausgetreten“ setzen.
        Eingebaute, nicht zuordenbare Rollen (z. B. Admin) bleiben und werden gemeldet."""
        ziel = self.rolle_ausgetreten()
        erlaubt = self._zuordenbar()
        jetzt = [r for r in self.person_rollen(pid) if r["zugewiesen"]]
        weg = [r["id"] for r in jetzt if r["id"] != ziel["id"] and r["id"] in erlaubt and r["aenderbar"]]
        bleiben = [r["name"] for r in jetzt if r["id"] != ziel["id"] and r["id"] not in weg]
        res = self.person_rollen_setzen(pid, [ziel["id"]], weg, probelauf)
        if res.get("fehler"):
            raise ValueError(res["fehler"])
        return {**res, "rolle_ausgetreten": ziel["id"], "nicht_entfernt": bleiben}

    # ------------------------------------------------------------------ Bezugspersonen / Eltern (L4)
    REF = "rpc/collections/PersonReferenceAdministrationAdmin/"
    SORGERECHT = {"sorgeberechtigt": "legal_guardian", "informationsberechtigt": "entitled_to_information",
                  "keine": "no_rights"}
    _SORGERECHT_RUECK = {v: k for k, v in SORGERECHT.items()}

    def _ref_rpc(self, methode: str, params: dict, andere_person: int):
        """RPC der Escola-Komponente „Bezugspersonen & Institutionen“ (rpcContext.otherPersonId = Bezugsperson-Kontext)."""
        import json as _json
        r = self._http.post(self.REF + methode + ".php", content=_json.dumps(
            {"parameters": params, "rpcContext": {"otherPersonId": int(andere_person)}}).encode(),
            headers={"Content-Type": "application/json"})
        text = self._check(r)
        try:
            data = _json.loads(text)
        except ValueError:
            raise RuntimeError(f"Escola-Fehler bei {methode}: {text[:150]}")
        if isinstance(data, dict) and data.get("__type") not in (None, "Ok") and "messageForUser" in data:
            raise RuntimeError(data["messageForUser"])
        return data

    def _funktionen(self) -> dict[int, str]:
        def load():
            with self._lock:
                cfg = self._ref_rpc("getConfigRpc", {}, 0)
            return {x["functionId"]: x["name"] for x in cfg["descOfRelStruct"]["guardianDescriptionOfRelationshipStructs"]}
        return self._cached("bezug_funktionen", load)

    def _funktion_id(self, funktion, geschlecht: str | None = None) -> int:
        f = self._funktionen()
        if funktion is None:
            return 1 if geschlecht == "w" else 2  # wie Escola: w -> Mutter, sonst Vater
        if isinstance(funktion, int) or str(funktion).isdigit():
            if int(funktion) not in f:
                raise ValueError(f"Unbekannte Funktion {funktion} (erlaubt: {f})")
            return int(funktion)
        treffer = [i for i, n in f.items() if n.lower() == str(funktion).strip().lower()]
        if not treffer:
            raise ValueError(f"Unbekannte Funktion „{funktion}“ (erlaubt: {', '.join(f.values())})")
        return treffer[0]

    def _sorgerecht(self, wert: str) -> str:
        if wert in self.SORGERECHT:
            return self.SORGERECHT[wert]
        if wert in self._SORGERECHT_RUECK:
            return wert
        raise ValueError("sorgerecht: sorgeberechtigt, informationsberechtigt oder keine")

    @classmethod
    def _bezug(cls, x: dict, seite: str) -> dict:
        rel = x.get("relationship") or {}
        p = x.get("guardian") if seite == "kind" else x.get("student")
        return {"beziehung_id": rel.get("id"), "person_id": (p or {}).get("id"), "name": (p or {}).get("displayName"),
                "aktiv": (p or {}).get("isActive"), "funktion_id": rel.get("descriptionOfRelationshipKey"),
                "funktion": rel.get("descriptionOfRelationship"),
                "sorgerecht": cls._SORGERECHT_RUECK.get(rel.get("custodianType"), rel.get("custodianType")),
                "abholberechtigt": rel.get("entitledToPickUp"),
                **({"gleiche_adresse": x.get("studentHasSameAddressAsGuardian"),
                    "rollen": (p or {}).get("schoolclassAndSchoolOrRolesString")} if seite == "kind"
                   else {"klasse": (p or {}).get("className")})}

    def bezugspersonen(self, schueler_id: int) -> list[dict]:
        """Eltern/Bezugspersonen einer Schülerin / eines Schülers."""
        with self._lock:
            data = self._ref_rpc("getGuardianReferenceStructsRpc", {}, schueler_id)
        return [self._bezug(x, "kind") for x in data or []]

    # ------------------------------------------------------------------ Schuljahr vorbereiten (WF-11 ff.)
    def klassenlisten(self, schuljahr: int = 0, schulhaus: str | None = None, refresh: bool = False) -> list[dict]:
        """Eine Zeile pro Schüler:in mit Klasse, Schulhaus und Klassenlehrperson(en) – für ICT
        (Zugänge Entra/Apple School Manager), Drucklisten und Abgleich nach der Einteilung (WF-13, WF-17)."""
        klp = {k["id"]: k.get("klassenlehrperson", "") for k in self.klassen(refresh)}
        rows = [s for s in self.schueler(refresh, schuljahr=schuljahr) if not schulhaus or s.get("schulhaus") == schulhaus]
        return sorted(({"schulhaus": s.get("schulhaus"), "klasse_id": s.get("klasse_id"), "klasse": s.get("klasse"),
                        "klassenlehrperson": klp.get(s.get("klasse_id"), ""), "schueler_id": s.get("id"),
                        "nachname": s.get("nachname"), "vorname": s.get("vorname")} for s in rows),
                      key=lambda r: (r["schulhaus"] or "", r["klasse"] or "", r["nachname"] or "", r["vorname"] or ""))

    def eltern_der_klasse(self, klasse_id: int, schuljahr: int = 0) -> list[dict]:
        """Alle Bezugspersonen der Schüler:innen einer Klasse, eine Zeile pro Kind und Bezugsperson –
        Grundlage für App-Onboarding, Zuteilungsbrief und Nachfassen (WF-14, WF-15). Kinder ohne
        Bezugsperson erscheinen mit leeren Feldern, damit Lücken auffallen."""
        kinder = [s for s in self.schueler(schuljahr=schuljahr) if s.get("klasse_id") == int(klasse_id)]
        out = []
        for k in kinder:
            bez = self.bezugspersonen(k["id"])
            for b in bez or [{}]:
                out.append({"schueler_id": k["id"], "schueler": f"{k.get('nachname', '')} {k.get('vorname', '')}".strip(),
                            "bezugsperson_id": b.get("person_id"), "bezugsperson": b.get("name"),
                            "funktion": b.get("funktion"), "sorgerecht": b.get("sorgerecht"),
                            "aktiv": b.get("aktiv"), "gleiche_adresse": b.get("gleiche_adresse")})
        return out

    def import_pruefen(self, personen: list[dict]) -> list[dict]:
        """Vorprüfung einer Importliste mit der Escola-Duplikatprüfung („Neue Person“), ohne etwas anzulegen.
        Jede Zeile: nachname, vorname, geschlecht (w/m/d), art (schueler|eltern), schulhaus. (WF-11)"""
        out = []
        for i, p in enumerate(personen):
            nn, vn, g = str(p.get("nachname", "")).strip(), str(p.get("vorname", "")).strip(), p.get("geschlecht")
            art = p.get("art", "schueler")
            fehler = [t for t, ok in (("nachname fehlt", nn), ("vorname fehlt", vn),
                                       ("geschlecht w/m/d", g in ("w", "m", "d")),
                                       ("art schueler/eltern", art in ("schueler", "eltern"))) if not ok]
            unit = self._unit_id(p["schulhaus"]) if p.get("schulhaus") else next(iter(self.cfg.schuleinheiten), 1)
            if p.get("schulhaus") and unit is None:
                fehler.append(f"unbekanntes Schulhaus '{p['schulhaus']}'")
            if fehler:
                out.append({"zeile": i, "nachname": nn, "vorname": vn, "status": "fehler", "fehler": fehler, "duplikate": []})
                continue
            kat = "students-without-schoolclass" if art == "schueler" else "eltern"
            struct = {"id": -1, "firstName": vn, "lastName": nn, "gender": g}
            with self._lock:
                dup = self._neue_person_rpc("checkForDuplicatePersonsRpc", kat, None, unit, struct)
            dups = [{"id": d.get("id"), "name": d.get("displayName"), "rollen": d.get("listOfAllRoles"), "aktiv": d.get("active")}
                    for d in ((dup or {}).get("duplicatePersonStructs") or [])] if isinstance(dup, dict) else []
            out.append({"zeile": i, "nachname": nn, "vorname": vn, "art": art,
                        "status": "moegliche_duplikate" if dups else "neu", "fehler": [], "duplikate": dups})
        return out

    def kinder(self, bezugsperson_id: int) -> list[dict]:
        """Alle Kinder, mit denen eine Bezugsperson verknüpft ist."""
        with self._lock:
            data = self._ref_rpc("getGuardianReferenceStructsAtGuardianSideRpc", {}, bezugsperson_id)
        return [self._bezug(x, "eltern") for x in data or []]

    def bezugsperson_verknuepfen(self, schueler_id: int, person_id: int, funktion=None, sorgerecht: str = "sorgeberechtigt",
                                 abholberechtigt: bool = True) -> dict:
        """Bestehende Person als Bezugsperson verknüpfen (z. B. Elternteil von Geschwistern, F-06)."""
        if any(b["person_id"] == int(person_id) for b in self.bezugspersonen(schueler_id)):
            raise KonfliktFehler("Diese Person ist schon Bezugsperson")
        with self._lock:
            ctx = self._ref_rpc("getContextPersonRpc", {}, person_id)
        struct = {"id": -1, "childId": int(schueler_id), "guardianId": int(person_id),
                  "descriptionOfRelationshipKey": self._funktion_id(funktion, ctx.get("gender")),
                  "descriptionOfRelationship": "", "custodianType": self._sorgerecht(sorgerecht),
                  "entitledToPickUp": bool(abholberechtigt)}
        with self._lock:
            self._ref_rpc("createGuardianRelationshipRpc", {"guardRelStruct": struct, "sideOfRel": "Student"}, schueler_id)
        neu = [b for b in self.bezugspersonen(schueler_id) if b["person_id"] == int(person_id)]
        if not neu:
            raise RuntimeError("Escola hat die Verknüpfung nicht angelegt")
        return neu[0]

    def bezugsperson_anlegen(self, schueler_id: int, nachname: str, vorname: str, geschlecht: str, funktion=None,
                             sorgerecht: str = "sorgeberechtigt", abholberechtigt: bool = True,
                             trotz_duplikat: bool = False) -> dict:
        """Neue Bezugsperson anlegen und verknüpfen. Vorher Escola-Duplikatprüfung: gibt es die Person schon
        (z. B. Elternteil von Geschwistern), kommt 409 mit Liste -> bestehende verknüpfen (F-06)."""
        if geschlecht not in ("w", "m", "d"):
            raise ValueError("geschlecht muss w, m oder d sein")
        kind = next((x for x in self.schueler(True) if x.get("id") == int(schueler_id)), {})
        kl, sh = kind.get("klasse_id"), kind.get("schulhaus")
        unit = (self._unit_id(sh) if sh else None) or next(iter(self.cfg.schuleinheiten), 1)
        struct = {"id": -1, "firstName": vorname.strip(), "lastName": nachname.strip(), "gender": geschlecht}
        with self._lock:
            dup = self._neue_person_rpc("checkForDuplicatePersonsRpc", "eltern", kl, unit, struct)
        dups = [{"id": d.get("id"), "name": d.get("displayName"), "rollen": d.get("listOfAllRoles"), "aktiv": d.get("active")}
                for d in ((dup or {}).get("duplicatePersonStructs") or [])] if isinstance(dup, dict) else []
        if dups and not trotz_duplikat:
            raise KonfliktFehler("Mögliche Duplikate – bestehende Person verknüpfen (POST …/bezugspersonen mit person_id) "
                                 "oder trotz_duplikat=true", dups)
        vorher = {b["person_id"] for b in self.bezugspersonen(schueler_id)}
        rel = {"id": -1, "childId": int(schueler_id), "guardianId": None,
               "descriptionOfRelationshipKey": self._funktion_id(funktion, geschlecht), "descriptionOfRelationship": "",
               "custodianType": self._sorgerecht(sorgerecht), "entitledToPickUp": bool(abholberechtigt)}
        with self._lock:
            self._ref_rpc("createNewPersonAndRelationshipRpc",
                          {"newGuardAndRelStruct": {"newPerson": struct, "guardianRelationship": rel}, "sideOfRel": "Student"},
                          schueler_id)
        neu = [b for b in self.bezugspersonen(schueler_id) if b["person_id"] not in vorher]
        if len(neu) != 1:
            raise RuntimeError("Escola hat die Bezugsperson nicht angelegt")
        self._cache.pop("personen_index", None)
        return {**neu[0], "angelegt": True, "duplikate_ignoriert": dups}

    def sorgerecht_setzen(self, schueler_id: int, beziehung_id: int, sorgerecht: str) -> dict:
        if not any(b["beziehung_id"] == int(beziehung_id) for b in self.bezugspersonen(schueler_id)):
            raise ValueError(f"Beziehung {beziehung_id} gehört nicht zu Schüler:in {schueler_id}")
        with self._lock:
            self._ref_rpc("editCustodianTypeRpc", {"relationshipId": int(beziehung_id),
                                                   "newCustodianType": self._sorgerecht(sorgerecht),
                                                   "typeOfRelationship": "guardian_relationship", "sideOfRel": "Student"},
                          schueler_id)
        b = next(b for b in self.bezugspersonen(schueler_id) if b["beziehung_id"] == int(beziehung_id))
        if b["sorgerecht"] != (sorgerecht if sorgerecht in self.SORGERECHT else self._SORGERECHT_RUECK[sorgerecht]):
            raise RuntimeError("Escola hat das Sorgerecht nicht übernommen")
        return b

    def bezugsperson_entfernen(self, schueler_id: int, beziehung_id: int, deaktivieren: bool = False) -> dict:
        """Nur die Verknüpfung löschen (Person bleibt) – mit deaktivieren=True wird die Bezugsperson zusätzlich
        deaktiviert (Escola-Option „Beziehung löschen und Bezugsperson deaktivieren“)."""
        if not any(b["beziehung_id"] == int(beziehung_id) for b in self.bezugspersonen(schueler_id)):
            raise ValueError(f"Beziehung {beziehung_id} gehört nicht zu Schüler:in {schueler_id}")
        opt = "delete_relationship_deactivate_guardian" if deaktivieren else "delete_only_relationship"
        with self._lock:
            self._ref_rpc("deleteGuardianRelationshipRpc", {"id": int(beziehung_id), "deleteOption": opt,
                                                            "sideOfRel": "Student"}, schueler_id)
        if any(b["beziehung_id"] == int(beziehung_id) for b in self.bezugspersonen(schueler_id)):
            raise RuntimeError("Escola hat die Verknüpfung nicht gelöscht")
        return {"schueler_id": int(schueler_id), "beziehung_id": int(beziehung_id), "entfernt": True,
                "bezugsperson_deaktiviert": deaktivieren}

    def eltern_ohne_weitere_kinder(self, schueler_id: int, deaktivieren: bool = False) -> dict:
        """F-07: Bezugspersonen, die ausser diesem Kind keine aktiven Kinder an der Schule haben und sonst keine
        Rolle (nur „Eltern/Bezugspersonen“). Mit deaktivieren=True werden sie deaktiviert."""
        ergebnis = []
        for b in self.bezugspersonen(schueler_id):
            andere = [k for k in self.kinder(b["person_id"]) if k["person_id"] != int(schueler_id) and k["aktiv"]]
            rollen = [r.strip() for r in (b.get("rollen") or "").split(",") if r.strip()]
            nur_eltern = all(r.startswith("Eltern") for r in rollen)
            e = {"person_id": b["person_id"], "name": b["name"], "aktiv": b["aktiv"],
                 "weitere_kinder": [k["name"] for k in andere], "andere_rollen": [r for r in rollen if not r.startswith("Eltern")]}
            e["deaktivieren"] = bool(b["aktiv"] and not andere and nur_eltern)
            if deaktivieren and e["deaktivieren"]:
                e["deaktiviert"] = not self.person_aktiv_setzen(b["person_id"], False)["aktiv"]
            ergebnis.append(e)
        return {"schueler_id": int(schueler_id), "bezugspersonen": ergebnis}

    def close(self):
        self._http.close()
