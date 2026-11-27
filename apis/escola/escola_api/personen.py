"""Parser für die Personenverwaltung (Schüler:innen, Lehrpersonen, weitere Personen).

Escola liefert pro Person mehrere "Reiter" (Abschnitte) als HTML. Im Bearbeitungsmodus
enthält jedes Feld einen Aufruf wie

    save_field('<feld verschlüsselt>', '<interner Name>', '<person verschlüsselt>', <id>, <zusatz>)
    saveDateField('<feld verschlüsselt>', '<interner Name>', <zusatz>)
    save_field_radio('<feld>', '<interner Name>', '<person>', <id>, <zusatz>, <wert>)

Die verschlüsselten Schlüssel gelten nur in der aktuellen Sitzung. Sie werden hier
ausgelesen und intern für das Schreiben verwendet, aber nie nach aussen gegeben.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from bs4 import BeautifulSoup

# Abschnitte mit Formularfeldern (weitere Reiter sind reine Anzeigen/Aktionen)
DATEN_ABSCHNITTE = ["name", "login", "personalien", "privat", "geschaeft",
                    "additional_fields_1", "additional_fields_2", "health"]

ABSCHNITT_TITEL = {
    "name": "Name", "login": "Login & Einstellungen", "personalien": "Personalien",
    "privat": "Privat", "geschaeft": "Schule / Geschäft", "additional_fields_1": "Weitere Infos",
    "additional_fields_2": "BISTA", "health": "Gesundheit & Ernährung",
}

# Personenkategorien der Personenverwaltung (Auswahl "p_rubrik")
KATEGORIEN = {
    "allActive": "alle aktiven Personen", "allInactive": "alle inaktiven Personen",
    "schueler": "Schüler:innen (Klassen)", "lehrperson": "Lehrpersonen",
    "schulleitung": "Schulleiter:innen", "admin": "Administrator:innen",
    "superadmin": "Superadministrator:innen", "eltern": "Eltern/Bezugspersonen (Klassen)",
    "guardians-all": "Eltern/Bezugspersonen (alle)", "doctor": "Ärztinnen & Ärzte",
    "dentist": "Zahnärztinnen & Zahnärzte", "gruppe_12": "Geschäftsleitung", "gruppe_2": "Schulbehörde",
    "gruppe_3": "Schulbehörden-Mitglieder", "gruppe_4": "Schulverwaltung", "gruppe_5": "Klassenassistenz",
    "gruppe_6": "Hausdienst", "gruppe_7": "Berufswahlcoach", "gruppe_8": "Praktikant/in",
    "gruppe_9": "Schulsozialarbeit (SSA)", "gruppe_10": "Di Medio", "gruppe_13": "RPK",
    "students-without-schoolclass": "Schüler:innen (ohne Klasse)",
    "future-students": "Zukünftige Schüler:innen (ohne Klasse)",
    "former-students": "Ehemalige Schüler:innen (ohne Klasse)",
}

# Felder, deren Wert nicht ausgegeben wird (nur ob gesetzt) – amtliche Nummern, Bankdaten
SENSIBEL = {"ahv", "iban", "swift", "bic"}
SENSIBEL_LABEL = re.compile(r"AHV|IBAN|BIC|SWIFT", re.I)

# Felder, die über die API nie geschrieben werden
SCHREIBSCHUTZ = {"ahv", "iban", "swift", "bic", "austritt", "departure_timestamp",
                 "departure_municipality_name"}
SCHREIBSCHUTZ_LABEL = re.compile(r"AHV|IBAN|BIC|SWIFT|Austritt|Wegzug|Passwort|Benutzername", re.I)
SCHREIBSCHUTZ_ABSCHNITTE = {"login"}

_SAVE = re.compile(r"save_field\('([^']+)','([^']+)','([^']+)',\s*(\d+)\s*(?:,\s*'?([^',)]*)'?)?")
_DATE = re.compile(r"saveDateField\('([^']+)','([^']+)',\s*'?(\d*)'?\)")
_RADIO = re.compile(r"save_field_radio\('([^']+)','([^']+)','([^']+)',\s*(\d+)\s*,\s*'?(\d*)'?\s*,\s*'?([^',)]*)'?")
_PERSON_DATE = re.compile(r"type:\s*7[^}]*?person:\s*'([^']+)'")


def _soup(h: str) -> BeautifulSoup:
    return BeautifulSoup(h, "lxml")


def _clean(s: str | None) -> str:
    return re.sub(r"\s+", " ", (s or "").replace("\xa0", " ")).strip()


@dataclass
class Feld:
    name: str                 # interner Escola-Name, z. B. 'natel', 'geburtstag'
    label: str
    typ: str                  # text | zahl | mehrzeilig | auswahl | auswahlknopf | checkbox | datum
    abschnitt: str
    wert: object = None       # Rohwert (Option-Wert bei Auswahl)
    text: str | None = None   # angezeigter Text bei Auswahl/Auswahlknopf
    optionen: list[dict] = field(default_factory=list)
    # intern (nur zum Schreiben)
    _feld: str = ""
    _person: str = ""
    _zusatz: str = ""

    def oeffentlich(self, mit_optionen: bool = False, sensibel_zeigen: bool = False) -> dict:
        d = {"name": self.name, "label": self.label, "typ": self.typ, "abschnitt": self.abschnitt,
             "wert": self.wert}
        if self.text is not None:
            d["text"] = self.text
        if self.ist_sensibel() and not sensibel_zeigen:
            d["wert"] = "***" if self.wert else ""
            d.pop("text", None)
        d["schreibbar"] = self.ist_schreibbar()
        if mit_optionen and self.optionen:
            d["optionen"] = self.optionen
        return d

    def ist_sensibel(self) -> bool:
        return self.name in SENSIBEL or bool(SENSIBEL_LABEL.search(self.label))

    def ist_schreibbar(self) -> bool:
        return not (self.name in SCHREIBSCHUTZ or self.abschnitt in SCHREIBSCHUTZ_ABSCHNITTE
                    or SCHREIBSCHUTZ_LABEL.search(self.label))


def parse_reiter(html: str) -> list[str]:
    """Abschnittsnamen aus `show_reiter.php`."""
    return [li["id"][3:] for li in _soup(html).select("li[id^=li_]")]


def bearbeitungsmodus_an(html: str) -> bool | None:
    cb = _soup(html).select_one("#edit_mode")
    return None if cb is None else cb.has_attr("checked")


def parse_abschnitt(html: str, abschnitt: str) -> list[Feld]:
    """Alle Felder eines Abschnitts (im Bearbeitungsmodus geladen)."""
    s = _soup(html)
    m = _PERSON_DATE.search(html)
    person_datum = m.group(1) if m else ""
    felder: dict[str, Feld] = {}
    reihenfolge: list[str] = []

    def add(f: Feld):
        if f.name not in felder:
            felder[f.name] = f
            reihenfolge.append(f.name)
        return felder[f.name]

    for tr in s.select("tr"):
        if tr.find("tr"):
            continue
        tds = tr.find_all("td", recursive=False)
        label = _clean(tds[0].get_text()) if tds else ""
        label = re.sub(r"(Dieser Wert|«c/o»).*$", "", label).strip()
        for el in tr.select("input, select, textarea"):
            h = el.get("onchange") or el.get("onblur") or el.get("onclick") or ""
            if (md := _DATE.search(h)):
                enc, name, zusatz = md.groups()
                f = add(Feld(name, label, "datum", abschnitt, _feld=enc, _person=person_datum, _zusatz=zusatz))
                part = el.get("id", "").rsplit("_", 1)[-1]
                parts = f.__dict__.setdefault("_teile", {})
                parts[part] = (el.get("value") or "").strip()
                if all(parts.get(k) for k in ("dd", "mm", "yyyy")):
                    f.wert = f"{parts['dd'].zfill(2)}.{parts['mm'].zfill(2)}.{parts['yyyy']}"
                elif f.wert is None:
                    f.wert = ""
                continue
            if (mr := _RADIO.search(h)):
                enc, name, penc, _pid, zusatz, wert = mr.groups()
                lab = s.find("label", attrs={"for": el.get("id")})
                txt = _clean(lab.get_text()) if lab else wert
                f = add(Feld(name, label, "auswahlknopf", abschnitt, _feld=enc, _person=penc, _zusatz=zusatz or ""))
                f.optionen.append({"wert": el.get("value", wert), "text": txt})
                if el.has_attr("checked"):
                    f.wert, f.text = el.get("value", wert), txt
                continue
            if (ms := _SAVE.search(h)):
                enc, name, penc, _pid, zusatz = ms.groups()
                zusatz = zusatz or ""
                if el.name == "select":
                    opts = [{"wert": o.get("value", ""), "text": _clean(o.get_text())} for o in el.select("option")]
                    sel = el.select_one("option[selected]") or (el.select("option")[0] if el.select("option") else None)
                    f = add(Feld(name, label, "auswahl", abschnitt, wert=sel.get("value") if sel else None,
                                 text=_clean(sel.get_text()) if sel else None, optionen=opts,
                                 _feld=enc, _person=penc, _zusatz=zusatz))
                elif el.name == "textarea":
                    add(Feld(name, label, "mehrzeilig", abschnitt, wert=el.get_text(), _feld=enc, _person=penc, _zusatz=zusatz))
                elif el.get("type") == "checkbox":
                    add(Feld(name, label, "checkbox", abschnitt, wert=el.has_attr("checked"), _feld=enc, _person=penc, _zusatz=zusatz))
                else:
                    typ = "zahl" if el.get("type") == "number" else "text"
                    add(Feld(name, label, typ, abschnitt, wert=el.get("value", ""), _feld=enc, _person=penc, _zusatz=zusatz))
    for f in felder.values():
        f.__dict__.pop("_teile", None)
    return [felder[n] for n in reihenfolge]


def parse_personenliste(html: str) -> list[dict]:
    out = []
    for li in _soup(html).select("li[id^=li_]"):
        pid = li["id"][3:]
        if not pid.isdigit():
            continue
        n = li.select_one(f"#name_person_{pid}")
        v = li.select_one(f"#vorname_person_{pid}")
        out.append({"id": int(pid), "nachname": _clean(n.get_text() if n else ""), "vorname": _clean(v.get_text() if v else "")})
    return out


# ------------------------------------------------------------------ Schreiben
_DATUM_RE = [re.compile(r"^(\d{1,2})\.(\d{1,2})\.(\d{4})$"), re.compile(r"^(\d{4})-(\d{2})-(\d{2})$")]


class FeldFehler(ValueError):
    pass


def schreib_payload(f: Feld, wert, freigabe: bool = False) -> dict:
    """POST-Parameter für `inc/ajax/persons/ajax_functions_persons.php`.
    freigabe=True nur für gezielt freigegebene Abläufe (z. B. Austritt)."""
    if not freigabe and not f.ist_schreibbar():
        raise FeldFehler(f"Feld '{f.name}' ({f.label}) ist schreibgeschützt")
    if f.typ == "datum":
        s = "" if wert in (None, "") else str(wert).strip()
        if s == "":
            dd = mm = yyyy = ""
        else:
            m = _DATUM_RE[0].match(s)
            if m:
                dd, mm, yyyy = m.group(1).zfill(2), m.group(2).zfill(2), m.group(3)
            elif (m := _DATUM_RE[1].match(s)):
                yyyy, mm, dd = m.groups()
            else:
                raise FeldFehler(f"Datum für '{f.name}' muss TT.MM.JJJJ oder JJJJ-MM-TT sein")
        return {"type": 7, "dd": dd, "mm": mm, "yyyy": yyyy, "person": f._person, "feld": f._feld, "additionalField": f._zusatz}
    if f.typ in ("auswahl", "auswahlknopf"):
        s = str(wert).strip()
        hit = [o for o in f.optionen if o["wert"] == s] or [o for o in f.optionen if o["text"].lower() == s.lower()] \
            or [o for o in f.optionen if o["text"].lower().startswith(s.lower())]
        if len(hit) != 1:
            moegl = ", ".join(f"{o['wert']}={o['text']}" for o in f.optionen[:15])
            raise FeldFehler(f"Wert '{wert}' für '{f.name}' nicht eindeutig/ungültig. Möglich: {moegl}{' …' if len(f.optionen) > 15 else ''}")
        w = hit[0]["wert"]
        if f.typ == "auswahlknopf":
            return {"type": 2, "feld": f._feld, "wert": w, "person_encrypted": f._person, "additional_field": f._zusatz}
        return {"type": 2, "feld": f._feld, "wert": w, "person_encrypted": f._person, "additional_field": f._zusatz, "prev": f.wert or ""}
    if f.typ == "checkbox":
        w = "1" if wert in (True, 1, "1", "true", "ja") else ""
        return {"type": 2, "feld": f._feld, "wert": w, "person_encrypted": f._person, "additional_field": f._zusatz, "prev": "1" if f.wert else ""}
    s = "" if wert is None else str(wert)
    if f.name in ("name", "vorname") and not s.strip():
        raise FeldFehler("Name und Vorname dürfen nicht leer sein")
    if f.typ == "zahl" and s and not re.fullmatch(r"-?\d+", s):
        raise FeldFehler(f"'{f.name}' erwartet eine Zahl")
    return {"type": 2, "feld": f._feld, "wert": s, "person_encrypted": f._person, "additional_field": f._zusatz, "prev": f.wert or ""}


# ------------------------------------------------------------------ AHV-Nummer und Schulmail
def ahv_pruefen(wert: str) -> str:
    """AHV-Nummer prüfen wie das Escola-Formular (13 Ziffern, beginnt mit 756, EAN-13-Prüfziffer).
    Gibt die Schreibweise 756.xxxx.xxxx.xx zurück."""
    ziffern = re.sub(r"[\s.]", "", str(wert or ""))
    if not re.fullmatch(r"\d{13}", ziffern) or not ziffern.startswith("756"):
        raise FeldFehler("AHV-Nummer: 13 Ziffern, beginnend mit 756 (z. B. 756.1234.5678.97)")
    summe = sum(int(z) * (3 if i % 2 else 1) for i, z in enumerate(ziffern[:12]))
    if (10 - summe % 10) % 10 != int(ziffern[12]):
        raise FeldFehler("AHV-Nummer: Prüfziffer stimmt nicht")
    return f"{ziffern[:3]}.{ziffern[3:7]}.{ziffern[7:11]}.{ziffern[11:]}"


def ahv_normal(wert: str) -> str:
    return re.sub(r"\D", "", str(wert or ""))


_ZUSAETZE = {"von", "vom", "van", "der", "den", "de", "di", "da", "del", "della", "dos", "du", "la", "le", "zu", "zum", "zur", "al", "el", "ten", "ter"}
_ERSATZ = {"ä": "ae", "ö": "oe", "ü": "ue", "ß": "ss", "æ": "ae", "œ": "oe", "ø": "o", "å": "a"}


def _mail_teil(name: str) -> str:
    import unicodedata
    teile = [t for t in re.split(r"[\s\-]+", name.strip().lower()) if t]
    # Namenszusätze gehören zum Namen: „von Arx“ -> vonarx, „de la Cruz“ -> delacruz
    i = 0
    while i < len(teile) - 1 and teile[i] in _ZUSAETZE:
        i += 1
    erster = "".join(teile[:i + 1])
    erster = "".join(_ERSATZ.get(c, c) for c in erster)
    erster = unicodedata.normalize("NFKD", erster).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]", "", erster)


def schulmail(vorname: str, nachname: str, domain: str = "sekbuelach.ch") -> str:
    """vorname.nachname@domain – Umlaute ä→ae usw., Akzente weg, bei Doppelnamen nur der erste Teil."""
    v, n = _mail_teil(vorname), _mail_teil(nachname)
    if not v or not n:
        raise FeldFehler("Schulmail: Vor- und Nachname nötig")
    return f"{v}.{n}@{domain}"


# ------------------------------------------------------------------ Zeugnis-Archiv
_ZEUGNIS_ERSTELLT = re.compile(r"erstellt am (\d{1,2})\.(\d{1,2})\.(\d{4}) um (\d{1,2}):(\d{2})(?: von (.+))?")
_DOWNLOAD = re.compile(r"/api/0/de/MediaServer/Download/([A-Za-z0-9_-]+)/([^\"'\s]*)")


def parse_zeugnis_archiv(html: str) -> list[dict]:
    """Personenverwaltung → «Zeugnis-/Formular-Archiv» (active_section=certificates).

    Aufbau (aufgezeichnet 26.11.2026): je Schuljahr ein Block `archiveSchoolYear_<Jahr>`, darin je Zeugnis ein
    Stern (`color-blue` = definitive, ausgedruckte Version), Vorschau, Download-Link
    `/api/0/de/MediaServer/Download/<token>/<Dateiname>` und «erstellt am TT.MM.JJJJ um HH:MM von …»."""
    soup = _soup(html)
    out = []
    for block in soup.select("div[id^=archiveSchoolYear_]"):
        jahr = block["id"].rsplit("_", 1)[-1]
        stern = None
        for el in block.descendants:
            if getattr(el, "name", None) != "a":
                continue
            klassen = el.get("class") or []
            if "fav-icon" in klassen:
                stern = "color-blue" in klassen
                continue
            m = _DOWNLOAD.search(el.get("href") or "")
            if not m:
                continue
            info = el.find_next_sibling("span")
            e = _ZEUGNIS_ERSTELLT.search(_clean(info.get_text()) if info else "")
            out.append({
                "id": m.group(1), "titel": _clean(el.get_text()),
                "schuljahr": f"{jahr}/{(int(jahr) + 1) % 100:02d}" if jahr.isdigit() else jahr,
                "definitiv": bool(stern),
                "erstellt": (f"{e.group(3)}-{int(e.group(2)):02d}-{int(e.group(1)):02d}T{int(e.group(4)):02d}:{e.group(5)}"
                             if e else None),
                "erstellt_von": _clean(e.group(6)) if e and e.group(6) else None,
                "datei": m.group(2).rstrip("."), "url": m.group(0),
            })
            stern = None
    return out


# ---------------------------------------------------------------- Escola-App und Logins (L12, #4)
def parse_app_status(html: str) -> dict:
    """Reiter „Escola App“ (Abschnitt `mobile`). Escola zeigt ein Symbol: `text-danger` + „App nicht aktiviert.“
    bzw. `text-success` (aus dem Escola-Skript `enableDisableMobile`). Aktiviert heisst: die Person darf die App
    nutzen – nicht, dass sie sie schon installiert hat (dafür Logins/Geräte). Live geprüft 28.11.2026 nur der
    Zustand „nicht aktiviert“ (niemand hatte die App aktiviert)."""
    box = _soup(html).select_one("#mobile")
    if box is None:
        return {"app_aktiviert": None, "app_schaltbar": False}
    icon = box.select_one("i.text-success, i.text-danger")
    txt = _clean(box.get_text(" "))
    if icon is not None:
        aktiv = "text-success" in (icon.get("class") or [])
    else:
        aktiv = None if not txt else "nicht aktiviert" not in txt
    return {"app_aktiviert": aktiv, "app_schaltbar": box.select_one("button") is not None}


def parse_aktivitaet(html: str) -> dict:
    """Reiter „Aktivität“: Anzahl Logins und letzter Login (Web und App)."""
    werte = {}
    for tr in _soup(html).select("table.niceTableNarrow tr"):
        tds = tr.find_all("td", recursive=False)
        if len(tds) >= 2:
            werte[_clean(tds[0].get_text())] = _clean(tds[1].get_text(" "))
    n = werte.get("Anzahl Logins", "")
    letzt = werte.get("letzter Login", "")
    return {"anzahl_logins": int(n) if n.isdigit() else None,
            "letzter_login": None if (not letzt or "noch nie" in letzt) else letzt}
