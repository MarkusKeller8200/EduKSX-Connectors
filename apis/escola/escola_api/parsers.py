"""HTML-Parser für die Escola-Antworten (sekbuelach.ch).

Escola liefert fast ausschliesslich HTML-Fragmente. Jede Funktion hier nimmt
rohes HTML entgegen und gibt einfache Python-Datenstrukturen (dicts) zurück.
Die Funktionen sind ohne Netzwerk testbar (siehe tests/).
"""
from __future__ import annotations

import html as _html
import re

from bs4 import BeautifulSoup

TAG_CODES = {"A": "Montag", "B": "Dienstag", "C": "Mittwoch", "D": "Donnerstag", "E": "Freitag"}


def _soup(html: str) -> BeautifulSoup:
    return BeautifulSoup(html, "lxml")


def _clean(s: str | None) -> str:
    return re.sub(r"\s+", " ", (s or "").replace("\xa0", " ")).strip()


def schulhaus_aus_gruppe(label: str) -> str:
    """'Klassen Hinterbirch' -> 'Hinterbirch', 'Arbeitsgruppen Mettmenriet' -> 'Mettmenriet'."""
    return _clean(re.sub(r"^(Klassen|Arbeitsgruppen)\s+", "", label or ""))


# --------------------------------------------------------------------------- Klassen
def parse_klassen(page_html: str) -> list[dict]:
    """Klassen und Arbeitsgruppen aus dem Auswahlfeld der Stundenplan-Seite
    (`GET admin.php?page_request=6`)."""
    out: list[dict] = []
    sel = _soup(page_html).select_one("#unifiedClassOrWorkgroupChooser")
    if sel is None:
        return out
    for opt in sel.select("option"):
        m = re.search(r"(klassen_id|workgroup_id)=(\d+)", opt.get("value", ""))
        if not m:
            continue
        text = _clean(opt.get_text())
        name, _, rest = text.partition(" - ")
        bezeichnung, _, klp = rest.partition(" – ")
        grp = opt.find_parent("optgroup")
        label = grp.get("label", "") if grp else ""
        out.append({
            "id": int(m.group(2)),
            "typ": "Klasse" if m.group(1) == "klassen_id" else "Arbeitsgruppe",
            "name": name.strip(),
            "bezeichnung": bezeichnung.strip(),
            "klassenlehrperson": klp.strip(),
            "schulhaus": schulhaus_aus_gruppe(label),
        })
    return out


# --------------------------------------------------------------------------- Lehrpersonen
def parse_lehrpersonen(html: str) -> list[dict]:
    """Personenliste aus `inc/ajax/persons/show_persons_of_group.php`."""
    out = []
    for li in _soup(html).select("li[id^=li_]"):
        pid = li["id"][3:]
        if not pid.isdigit():
            continue
        nach = li.select_one(f"#name_person_{pid}")
        vor = li.select_one(f"#vorname_person_{pid}")
        out.append({
            "id": int(pid),
            "nachname": _clean(nach.get_text() if nach else ""),
            "vorname": _clean(vor.get_text() if vor else ""),
        })
    return out


def lp_kuerzel(nachname: str, vorname: str) -> str:
    """Kürzel wie im Stundenplan: 2 Buchstaben Nachname + 2 Vorname (Akzente entfernt)."""
    import unicodedata

    def strip_acc(s: str) -> str:
        # Umlaute behalten (z. B. 'ÖbKa', 'WäLi'), nur andere Akzente entfernen (Félix -> Fe)
        keep = {"ä", "ö", "ü", "Ä", "Ö", "Ü"}
        return "".join(
            c if c in keep else unicodedata.normalize("NFD", c)[0] for c in s
        )

    return strip_acc(nachname.strip()[:2]) + strip_acc(vorname.strip()[:2])


# --------------------------------------------------------------------------- Bearbeitungsansicht (Fächer, Räume)
_ROOM_RE = re.compile(r"^(.*?)\s*\[([^\]]+)\]$")


def parse_faecher(edit_html: str) -> list[dict]:
    """Fachauswahl `select#tt_select_*` aus der Bearbeitungsansicht einer Zelle."""
    out, seen = [], set()
    for opt in _soup(edit_html).select("select[id^=tt_select_] option"):
        v = opt.get("value", "")
        if not v.isdigit() or v in ("0", "99999") or v in seen:
            continue
        seen.add(v)
        text = _clean(opt.get_text())
        m = re.match(r"^(.*)\(([^)]+)\)$", text)
        out.append({
            "id": int(v),
            "kuerzel": m.group(2).strip() if m else "",
            "name_kurz": (m.group(1) if m else text).strip(),
        })
    return out


def parse_raeume(edit_html: str) -> list[dict]:
    """Raumauswahl `select#room_id_*` aus der Bearbeitungsansicht einer Zelle."""
    out, seen = [], set()
    sel = _soup(edit_html).select_one("select[id^=room_id_]")
    if sel is None:
        return out
    for opt in sel.select("option"):
        v = opt.get("value", "")
        if not v.isdigit() or v == "0" or v in seen:
            continue
        seen.add(v)
        text = _clean(opt.get_text())
        m = _ROOM_RE.match(text)
        name = m.group(1) if m else text
        parts = [p.strip() for p in name.split(" - ")]
        grp = opt.find_parent("optgroup")
        gruppe = _clean(grp.get("label", "")) if grp else ""
        out.append({
            "id": int(v),
            "kuerzel": m.group(2).strip() if m else "",
            "name": name,
            "geschoss": parts[0] if parts else "",
            "nummer": parts[1] if len(parts) > 1 else "",
            "bezeichnung": " - ".join(parts[2:]),
            "gruppe": gruppe,  # z. B. 'Hibi - Trakt A'
        })
    return out


def parse_eintrag_details(edit_html: str) -> list[dict]:
    """Exakte IDs aller Einträge einer Zelle aus der Bearbeitungsansicht (type=1):
    Eintrags-ID, Fach-ID, Raum-IDs (1–3), Lehrpersonen-IDs – plus was wählbar ist.

    Lehrpersonen: Hat nur EINE Lehrperson das Fach in der Klasse, zeigt Escola nur ihren Namen
    (automatisch eingetragen, kein Schalter; ID aus `lp_warn_<eintrag>_<person>`). Haben mehrere das
    Fach, gibt es Schalter `teacher_<eintrag>_<person>` (checked = eingetragen). Live geprüft 15.11.2026."""
    s = _soup(edit_html)
    out = []
    for sel in s.select("select[id^=tt_select_]"):
        rid = sel["id"][len("tt_select_"):]
        if not rid.isdigit():
            continue  # 'new_…' = noch kein Eintrag
        gewaehlte = sel.select("option[selected]")
        chosen = gewaehlte[-1] if gewaehlte else None
        raeume, slots = [], []
        for prefix in ("room_id_", "room_2_id_", "room_3_id_"):
            rs = s.select_one(f"#{prefix}{rid}")
            o = rs.select_one("option[selected]") if rs else None
            wert = int(o["value"]) if o and o.get("value", "0").isdigit() and o["value"] != "0" else None
            slots.append(wert)
            if wert:
                raeume.append(wert)
        rs1 = s.select_one(f"#room_id_{rid}")
        raeume_waehlbar = sorted({int(o["value"]) for o in rs1.select("option") if o.get("value", "").isdigit()
                                  and o["value"] != "0"}) if rs1 else []
        lp_liste = []
        for cb in s.select(f"input[id^=teacher_{rid}_]"):
            lp_liste.append({"id": int(cb["id"].rsplit("_", 1)[1]), "gewaehlt": cb.has_attr("checked"), "schaltbar": True})
        bekannt = {x["id"] for x in lp_liste}
        for w in s.select(f"span[id^=lp_warn_{rid}_]"):
            pid = int(w["id"].rsplit("_", 1)[1])
            if pid not in bekannt:
                lp_liste.append({"id": pid, "gewaehlt": True, "schaltbar": False})
        for x in lp_liste:
            row = s.select_one(f"#teacher_{rid}_{x['id']}") or s.select_one(f"#lp_warn_{rid}_{x['id']}")
            n = row.find_parent(class_="tt-edit__row") if row else None
            name = n.select_one(".tt-edit__lp-name") if n else None
            x["name"] = name.get_text(strip=True) if name else None
        out.append({
            "eintrag_id": int(rid),
            "fach_id": int(chosen["value"]) if chosen and chosen.get("value", "").isdigit() and chosen["value"] != "0" else None,
            "faecher_waehlbar": [int(o["value"]) for o in sel.select("option") if o.get("value", "").isdigit()
                                 and o["value"] not in ("0", "99999")],
            "raum_ids": raeume,
            "raum_slots": slots,
            "raeume_waehlbar": raeume_waehlbar,
            "lehrperson_ids": [x["id"] for x in lp_liste if x["gewaehlt"]],
            "lehrpersonen": lp_liste,
        })
    return out


# --------------------------------------------------------------------------- Modul Ressourcen
_PROFIL_SCHULHAUS = {"HIBI": "Hinterbirch", "METTMI": "Mettmenriet"}


def _schulhaus_aus_text(*texte: str) -> str | None:
    for t in texte:
        u = (t or "").upper()
        for k, v in _PROFIL_SCHULHAUS.items():
            if u.startswith(k):
                return v
    return None


def parse_ressourcen(html: str) -> list[dict]:
    """Ressourcenliste aus dem Modul Ressourcen (`inc/ajax/raumverwaltung/rooms.php`)."""
    s = _soup(html)
    out = []
    for head in s.select("tr.head_2"):
        name_el = head.select_one(".bigger-font-size")
        if not name_el:
            continue
        kat = _clean(name_el.get_text())
        typ_el = name_el.find_next_sibling("span")
        kat_typ = _clean(typ_el.get_text()).strip("()") if typ_el else ""
        row = head.find_next_sibling("tr")
        ul = row.select_one("ul[id^=rooms_]") if row else None
        if ul is None:
            continue
        kat_id = int(ul["id"].split("_", 1)[1])
        for li in ul.select("li[id^=item_]"):
            rid = li["id"].split("_", 1)[1]
            if not rid.isdigit():
                continue
            tds = li.select("td")
            text = _clean(tds[0].get_text()) if tds else ""
            m = _ROOM_RE.match(text)
            name = m.group(1) if m else text
            parts = [p.strip() for p in name.split(" - ")]
            profil = _clean(tds[1].get_text()) if len(tds) > 1 else ""
            cb = li.select_one("input[type=checkbox]")
            out.append({
                "id": int(rid), "kuerzel": m.group(2).strip() if m else "", "name": name,
                "geschoss": parts[0] if len(parts) > 2 else "", "nummer": parts[1] if len(parts) > 2 else "",
                "bezeichnung": " - ".join(parts[2:]) if len(parts) > 2 else (parts[-1] if parts else ""),
                "kategorie_id": kat_id, "kategorie": kat, "kategorie_typ": kat_typ,
                "zeitprofil": profil, "reservierbar": bool(cb and cb.has_attr("checked")),
                "schulhaus": _schulhaus_aus_text(profil, kat),
            })
    return out


def parse_zeitprofile(html: str) -> tuple[list[dict], int | None]:
    """Zeiteinteilungs-Profile aus `stundeneinteilung.php` + aktuell gewähltes Profil."""
    sel = _soup(html).select_one("select#profileChooser")
    if sel is None:
        return [], None
    profile = [{"id": int(o["value"]), "name": _clean(o.get_text()),
                "schulhaus": _schulhaus_aus_text(_clean(o.get_text()))} for o in sel.select("option") if o.get("value", "").isdigit()]
    chosen = sel.select_one("option[selected]")
    return profile, int(chosen["value"]) if chosen and chosen.get("value", "").isdigit() else None


def parse_zeiten(html: str) -> list[dict]:
    out = []
    for tr in _soup(html).select("tr"):
        sp = tr.select_one("td span")
        m = re.search(r"edit_time\((\d+)\)", str(tr))
        if not (sp and m):
            continue
        von, _, bis = _clean(sp.get_text()).partition(" - ")
        out.append({"id": int(m.group(1)), "nr": len(out) + 1, "von": von.strip(), "bis": bis.strip()})
    return out


# --------------------------------------------------------------------------- Stundenplan (Anzeige)
def parse_raster(tt_html: str) -> dict:
    """Tage und Lektionen (mit Escola-ID und Zeiten) aus `application_class.php` mode=0."""
    s = _soup(tt_html)
    lektionen = []
    for tr in s.select("tr"):
        t = tr.select_one(".timetable-lessons")
        c = tr.select_one("[id^=content_]")
        if not (t and c):
            continue
        _, _, lid = c["id"].split("_", 2)
        zeiten = [_clean(n.get_text()) for n in t.select("nobr")]
        lektionen.append({
            "id": int(lid),
            "nr": len(lektionen) + 1,
            "von": zeiten[0] if zeiten else "",
            "bis": zeiten[1] if len(zeiten) > 1 else "",
        })
    codes = []
    for c in s.select("[id^=content_]"):
        code = c["id"].split("_")[1]
        if code not in codes:
            codes.append(code)
    tage = [{"code": c, "nr": i + 1, "name": TAG_CODES.get(c, c)} for i, c in enumerate(codes)]
    return {"tage": tage, "lektionen": lektionen}


def _split_tooltip(title: str) -> tuple[str, list[str], list[str]]:
    """Tooltip '<b>Fach</b><br>LP1<br />LP2<br /><i>Raum1/Raum2</i>' -> (Fach, [LP], [Räume])."""
    raw = _html.unescape(title or "")
    t = _soup(raw)
    b = t.find("b")
    i = t.find("i")
    fach = _clean(b.get_text()) if b else ""
    raum_txt = _clean(i.get_text()) if i else ""
    if b:
        b.decompose()
    if i:
        i.decompose()
    for br in t.find_all("br"):
        br.replace_with("\n")
    lps = [_clean(x) for x in t.get_text().split("\n") if _clean(x)]
    raeume = [r.strip() for r in raum_txt.split("/") if r.strip()] if raum_txt else []
    return fach, lps, raeume


def parse_stundenplan(tt_html: str) -> list[dict]:
    """Alle Einträge aus der Stundenplan-Ansicht (`application_class.php` mode=0).
    Enthält Namen/Kürzel, aber keine IDs von LP/Räumen (die werden später gemappt)."""
    s = _soup(tt_html)
    out = []
    for cell in s.select("[id^=content_]"):
        _, tag, lid = cell["id"].split("_", 2)
        for td in cell.select("table.stundenplan_innen td"):
            a = td.select_one("a.tipped")
            if a is None:
                continue
            fach, lps, raeume = _split_tooltip(a.get("title", ""))
            divs = [_clean(d.get_text()) for d in td.find_all("div", recursive=False)]
            kurz = td.select_one(".timetable-course-name")
            lp_k = divs[0] if divs else ""
            raum_k = divs[1] if len(divs) > 1 else ""
            out.append({
                "tag_code": tag,
                "lektion_id": int(lid),
                "fach_kuerzel": _clean(kurz.get_text()) if kurz else "",
                "fach": fach,
                "lehrpersonen": lps,
                "lehrpersonen_kuerzel": [x for x in lp_k.split("/") if x],
                "raeume": raeume,
                "raeume_kuerzel": [x for x in raum_k.split("/") if x],
                "zusatz": " | ".join(divs[2:]),
            })
    return out


# ---------------------------------------------------------------- Fächer-Zuteilung (Klasse ↔ Lehrperson)
# Spalten der Escola-Matrix (Klassenverwaltung → Lehrpersonen), in dieser Reihenfolge.
# KLR/FP/SpM/Abs gelten pro Lehrperson und Klasse, Gesundheit pro Fach-Zuteilung.
RECHTE_SPALTEN = (("klr", "edit-admin-rights"), ("fp", "edit-sne-rights"), ("spm", "edit-measures-rights"),
                  ("abs", "edit-absences-rights"), ("gesundheit", "edit-access-to-health-data"))


def parse_lehrpersonen_faecher(html: str) -> list[dict]:
    """Matrix `lehrpersonen_faecher.php mode=0` -> eine Zeile pro Fach-Zuteilung."""
    s = BeautifulSoup(html, "lxml")
    out = []
    for cb in s.select("input.teacher-course-assignment-cb"):
        tr = cb.find_parent("tr")
        assign_id = int(cb["id"].rsplit("_", 1)[1])
        name = tr.select_one("span.shrink-0")
        fach_tr = tr.find_parent("table").find_parent("tr")
        fach = fach_tr.find("strong") if fach_tr else None
        lp_id = fach_id = None
        m = re.search(r"edit_assignment\((\d+)\s*,\s*(\d+)\)", str(tr))
        if m:
            lp_id, fach_id = int(m.group(1)), int(m.group(2))
        rechte = {}
        for key, prefix in RECHTE_SPALTEN:
            i = tr.select_one(f'input[id^="{prefix}"]')
            rechte[key] = bool(i is not None and i.has_attr("checked"))
            rechte[key + "_automatisch"] = bool(i is not None and i.has_attr("disabled"))
        fname = re.sub(r"\s+", " ", fach.get_text(" ", strip=True)) if fach else None
        kurz = re.search(r"\(([^)]+)\)\s*$", fname or "")
        out.append({"assign_id": assign_id, "fach_id": fach_id,
                    "fach": re.sub(r"\s*\([^)]+\)\s*$", "", fname or "") or None,
                    "fach_kurz": kurz.group(1) if kurz else None,
                    "lehrperson_id": lp_id, "lehrperson": name.get_text(strip=True) if name else None, **rechte})
    return out


def parse_faecher_auswahl(html: str) -> list[dict]:
    """`zeige_faecher.php type=1` -> alle Fächer der Klasse mit Häkchen, ob die Lehrperson sie hat."""
    s = BeautifulSoup(html, "lxml")
    out = []
    for i in s.select('input[id^="fach_"]'):
        lab = i.find_parent("label")
        txt = re.sub(r"\s+", " ", lab.get_text(" ", strip=True)) if lab else ""
        kurz = re.search(r"\(([^)]+)\)\s*$", txt)
        out.append({"id": int(i["id"].split("_", 1)[1]), "name": re.sub(r"\s*\([^)]+\)\s*$", "", txt),
                    "kurz": kurz.group(1) if kurz else None, "zugeteilt": i.has_attr("checked")})
    return out


# ---------------------------------------------------------------- Klassen-Einstellungen (Klassenlehrpersonen)
KLP_FELDER = {"aktuell": ("klassenlehrer_id", "klassenlehrer_id_2", "klassenlehrer_id_3"),
              "kommend": ("klassenlehrer_id_plan", "klassenlehrer_id_2_plan", "klassenlehrer_id_3_plan")}


def _gewaehlt(sel) -> str:
    """Escola markiert immer „(keine)“ UND die echte Person als selected -> letzte gewinnt (wie der Browser)."""
    opts = sel.find_all("option")
    sel_opts = [o for o in opts if o.has_attr("selected")]
    o = sel_opts[-1] if sel_opts else (opts[0] if opts else None)
    return (o.get("value", o.get_text(strip=True)) if o else "")


def klassen_formular(html: str) -> tuple[list[tuple[str, str]], dict]:
    """Formular `mode=903` -> (Felder genau wie der Browser sie sendet, Infos).

    Gibt alle Werte in Formular-Reihenfolge zurück, damit beim Speichern (mode=902) nur geändert wird,
    was man ändern will."""
    s = BeautifulSoup(html, "lxml")
    form = s.select_one('form[action*="mode=902"]')
    if form is None:
        raise ValueError("Klassen-Formular nicht gefunden")
    felder: list[tuple[str, str]] = []
    for e in form.find_all(["input", "select", "textarea"]):
        name = e.get("name")
        if not name or e.has_attr("disabled"):
            continue
        if e.name == "select":
            felder.append((name, _gewaehlt(e)))
        elif e.name == "textarea":
            felder.append((name, e.get_text()))
        else:
            t = (e.get("type") or "text").lower()
            if t in ("submit", "button", "image", "reset", "file"):
                continue
            if t in ("checkbox", "radio") and not e.has_attr("checked"):
                continue
            felder.append((name, e.get("value", "on")))
    lps = {}
    sel = form.find("select", attrs={"name": "klassenlehrer_id"})
    for o in sel.find_all("option") if sel else []:
        if o.get("value", "0") != "0":
            lps[int(o["value"])] = o.get_text(strip=True)
    werte = dict(felder)
    klp = {k: [int(werte[n]) for n in namen if werte.get(n, "0") not in ("", "0")] for k, namen in KLP_FELDER.items()}
    return felder, {"name": werte.get("name"), "name_kommend": werte.get("name_plan"), "klassenlehrpersonen": klp,
                    "waehlbar": lps,
                    "wird_archiviert": "archive_at_next_schoolyear_change" in werte}


def parse_arbeitsgruppe_faecher(html: str) -> list[dict]:
    """Matrix `lehrpersonen_faecher.php mode=0` bei aktiver Arbeitsgruppe.
    Andere Form als bei Klassen: Spalten Fach | Lehrperson(en) | Gesundheit | Abs | Aktionen,
    mehrere Lehrpersonen eines Fachs stehen untereinander in derselben Zeile. Eigene Zuteilungsnummern."""
    s = BeautifulSoup(html, "lxml")
    out = []
    for tr in s.select("table.nice_table_narrow tr[valign=top]"):
        tds = tr.find_all("td", recursive=False)
        if len(tds) < 5:
            continue
        fname = re.sub(r"\s+", " ", tds[0].get_text(" ", strip=True))
        kurz = re.search(r"\(([^)]+)\)\s*$", fname)
        namen = [d.get_text(strip=True) for d in tds[1].select("div > div")] or [tds[1].get_text(strip=True)]
        gesundheit = [i.has_attr("checked") for i in tds[2].select("input")]
        abs_ = [i.has_attr("checked") for i in tds[3].select("input")]
        aktionen = [str(d) for d in tds[4].select("div > div")] or [str(tds[4])]
        for i, a in enumerate(aktionen):
            m = re.search(r"edit_assignment\((\d+)\s*,\s*(\d+)\)", a)
            d = re.search(r"delete_assignment\((\d+)\)", a)
            if not (m and d):
                continue
            out.append({"assign_id": int(d.group(1)), "fach_id": int(m.group(2)),
                        "fach": re.sub(r"\s*\([^)]+\)\s*$", "", fname) or None, "fach_kurz": kurz.group(1) if kurz else None,
                        "lehrperson_id": int(m.group(1)), "lehrperson": namen[i] if i < len(namen) else None,
                        "klr": False, "fp": False, "spm": False,
                        "abs": abs_[i] if i < len(abs_) else False,
                        "gesundheit": gesundheit[i] if i < len(gesundheit) else False,
                        **{k + "_automatisch": False for k in ("klr", "fp", "spm", "abs", "gesundheit")}})
    return out
