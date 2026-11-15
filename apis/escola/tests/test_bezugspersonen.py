"""Bezugspersonen (RPC PersonReferenceAdministrationAdmin) – Formen wie live am 15.11.2026 gelesen.
Dazu: Rollen nur im Bearbeitungsmodus, Selbstheilung der Personen-Sitzung."""
import json
from urllib.parse import parse_qs

import httpx
import pytest

from escola_api.client import EscolaClient, EscolaConfig, KonfliktFehler

FUNKTIONEN = [{"__type": "GuardianDescriptionOfRelationshipStruct", "name": n, "functionId": i}
              for i, n in [(1, "Mutter"), (2, "Vater"), (3, "Vormund"), (4, "andere Funktion")]]
RUECK = {"legal_guardian", "entitled_to_information", "no_rights"}


class Fake:
    def __init__(self):
        self.rel = {}          # id -> dict
        self.personen = {649: ("TEST TEST", "w", "Lehrpersonen (Hinterbirch)", True),
                         650: ("Testname Testvorname", "w", "Schüler:innen", True),
                         651: ("Geschwister Kind", "m", "Schüler:innen", True)}
        self.next_rel, self.next_person = 0, 900
        self.dup = []
        self.deaktiviert = []

    def ref_struct(self, r, seite):
        g, k = self.personen[r["guardianId"]], self.personen[r["childId"]]
        return {"__type": "GuardianReferenceStruct", "refId": r["id"],
                "guardian": {"id": r["guardianId"], "displayName": g[0], "gender": g[1],
                             "schoolclassAndSchoolOrRolesString": g[2], "isActive": g[3]},
                "student": {"id": r["childId"], "displayName": k[0], "className": "H_A1a", "isActive": k[3]},
                "relationship": {"__type": "GuardianRelationshipStruct", **{x: r[x] for x in
                                 ("id", "childId", "guardianId", "descriptionOfRelationshipKey", "custodianType",
                                  "entitledToPickUp")}, "descriptionOfRelationship": dict(
                                     (f["functionId"], f["name"]) for f in FUNKTIONEN)[r["descriptionOfRelationshipKey"]]},
                "studentHasSameAddressAsGuardian": True}

    def __call__(self, req):
        p = req.url.path
        if "PersonReferenceAdministrationAdmin" in p:
            m = p.rsplit("/", 1)[1][:-4]
            body = json.loads(req.content)
            par, other = body["parameters"], body["rpcContext"]["otherPersonId"]
            if m == "getConfigRpc":
                return httpx.Response(200, json={"descOfRelStruct": {"guardianDescriptionOfRelationshipStructs": FUNKTIONEN}})
            if m == "getContextPersonRpc":
                return httpx.Response(200, json={"id": other, "gender": self.personen[other][1]})
            if m == "getGuardianReferenceStructsRpc":
                return httpx.Response(200, json=[self.ref_struct(r, "k") for r in self.rel.values() if r["childId"] == other])
            if m == "getGuardianReferenceStructsAtGuardianSideRpc":
                return httpx.Response(200, json=[self.ref_struct(r, "g") for r in self.rel.values() if r["guardianId"] == other])
            if m == "createGuardianRelationshipRpc":
                s = par["guardRelStruct"]
                assert par["sideOfRel"] == "Student" and s["custodianType"] in RUECK and s["id"] == -1
                self.next_rel += 1
                self.rel[self.next_rel] = {**s, "id": self.next_rel}
                return httpx.Response(200, json={"__type": "Ok"})
            if m == "createNewPersonAndRelationshipRpc":
                s = par["newGuardAndRelStruct"]
                self.next_person += 1
                np = s["newPerson"]
                self.personen[self.next_person] = (f'{np["lastName"]} {np["firstName"]}', np["gender"], "Eltern/Bezugspersonen", True)
                self.next_rel += 1
                self.rel[self.next_rel] = {**s["guardianRelationship"], "id": self.next_rel, "guardianId": self.next_person}
                return httpx.Response(200, json={"__type": "Ok"})
            if m == "editCustodianTypeRpc":
                if par["typeOfRelationship"] != "guardian_relationship":  # wie Escola: sonst Fehler
                    return httpx.Response(200, text="Es ist ein Fehler aufgetreten.")
                self.rel[par["relationshipId"]]["custodianType"] = par["newCustodianType"]
                return httpx.Response(200, json={"__type": "Ok"})
            if m == "deleteGuardianRelationshipRpc":
                r = self.rel.pop(par["id"])
                if par["deleteOption"] == "delete_relationship_deactivate_guardian":
                    self.deaktiviert.append(r["guardianId"])
                return httpx.Response(200, json={"__type": "Ok"})
        if "CaptureNewPersonAdmin" in p:
            if not self.dup:
                return httpx.Response(200, text="null")
            return httpx.Response(200, json={"__type": "DuplicatePersonStructs", "duplicatePersonStructs": self.dup})
        raise AssertionError(f"unerwartet: {p}")


@pytest.fixture
def env(monkeypatch):
    fake = Fake()
    c = EscolaClient(EscolaConfig(base_url="https://x/"), transport=httpx.MockTransport(fake))
    monkeypatch.setattr(c, "schueler", lambda refresh=False, sj=0: [
        {"id": 650, "klasse_id": 92, "schulhaus": "Hinterbirch"}, {"id": 651, "klasse_id": 92, "schulhaus": "Hinterbirch"}])
    monkeypatch.setattr(c, "person_aktiv_setzen", lambda pid, a: fake.deaktiviert.append(pid) or {"aktiv": a})
    return c, fake


def test_verknuepfen_sorgerecht_entfernen(env):
    c, fake = env
    b = c.bezugsperson_verknuepfen(650, 649, "andere Funktion", "informationsberechtigt", False)
    assert b["funktion"] == "andere Funktion" and b["sorgerecht"] == "informationsberechtigt" and b["gleiche_adresse"]
    with pytest.raises(KonfliktFehler, match="schon Bezugsperson"):
        c.bezugsperson_verknuepfen(650, 649)
    assert c.sorgerecht_setzen(650, b["beziehung_id"], "sorgeberechtigt")["sorgerecht"] == "sorgeberechtigt"
    assert c.kinder(649)[0]["person_id"] == 650
    c.bezugsperson_entfernen(650, b["beziehung_id"])
    assert c.bezugspersonen(650) == [] and not fake.deaktiviert


def test_anlegen_mit_duplikatpruefung_und_funktion_nach_geschlecht(env):
    c, fake = env
    fake.dup = [{"id": 777, "displayName": "Muster Anna", "listOfAllRoles": "Eltern", "active": True}]
    with pytest.raises(KonfliktFehler) as e:
        c.bezugsperson_anlegen(650, "Muster", "Anna", "w")
    assert e.value.personen[0]["id"] == 777 and not fake.rel
    fake.dup = []
    m = c.bezugsperson_anlegen(650, "Muster", "Anna", "w")
    v = c.bezugsperson_anlegen(650, "Muster", "Peter", "m", sorgerecht="informationsberechtigt")
    assert (m["funktion"], v["funktion"]) == ("Mutter", "Vater") and v["sorgerecht"] == "informationsberechtigt"
    with pytest.raises(ValueError, match="Unbekannte Funktion"):
        c.bezugsperson_anlegen(650, "X", "Y", "w", funktion="Tante")


def test_eltern_ohne_weitere_kinder(env):
    c, fake = env
    mutter = c.bezugsperson_anlegen(650, "Muster", "Anna", "w")["person_id"]
    vater = c.bezugsperson_anlegen(650, "Muster", "Peter", "m")["person_id"]
    c.bezugsperson_verknuepfen(651, vater)          # Vater hat noch ein Kind an der Schule
    c.bezugsperson_verknuepfen(650, 649)            # Lehrperson als Bezugsperson -> nie deaktivieren
    r = c.eltern_ohne_weitere_kinder(650)
    plan = {e["person_id"]: e["deaktivieren"] for e in r["bezugspersonen"]}
    assert plan == {mutter: True, vater: False, 649: False} and not fake.deaktiviert
    c.eltern_ohne_weitere_kinder(650, deaktivieren=True)
    assert fake.deaktiviert == [mutter]


# ---------------------------------------------------------------- Rollen & Personen-Sitzung
class RollenFake:
    def __init__(self, sitzung_ok=True):
        self.edit = False
        self.sitzung_ok = sitzung_ok
        self.calls = []

    def __call__(self, req):
        p = req.url.path
        f = {k: v[0] for k, v in parse_qs(req.content.decode(), keep_blank_values=True).items()}
        self.calls.append(p.rsplit("/", 1)[1])
        if req.method == "GET" or "personManagement" in p or "show_persons_of_group" in p:
            self.sitzung_ok = True
            return httpx.Response(200, text="<ul></ul>")
        if not self.sitzung_ok:
            return httpx.Response(200, text='<div class="alert alert-danger">Bitte laden Sie die Seite neu.</div>')
        if p.endswith("show_reiter.php"):
            return httpx.Response(200, text='<ul><li id="li_name">Name</li><li id="li_rollen">Rollen</li></ul>')
        if p.endswith("ajax_functions_persons.php") and f.get("type") == "1":
            self.edit = f["edit_mode"] == "1"
            return httpx.Response(200, text="")
        if p.endswith("show_person_details.php"):
            cb = '<input type="checkbox" id="edit_mode" %s>' % ("checked" if self.edit else "")
            rollen = ('<input id="role_13" type="checkbox" checked><label for="role_13">Lehrpersonen (Hinterbirch)</label>'
                      '<input id="role_25" type="checkbox"><label for="role_25">Hausdienst</label>') if self.edit else ""
            return httpx.Response(200, text=cb + rollen + "<div>" + "x" * 300 + "</div>")
        raise AssertionError(p)


def test_rollen_nur_im_bearbeitungsmodus_und_danach_wieder_aus():
    fake = RollenFake()
    c = EscolaClient(EscolaConfig(base_url="https://x/"), transport=httpx.MockTransport(fake))
    r = c.person_rollen(649)
    assert [x["id"] for x in r if x["zugewiesen"]] == [13] and len(r) == 2
    assert fake.edit is False


def test_selbstheilung_personen_sitzung():
    fake = RollenFake(sitzung_ok=False)
    c = EscolaClient(EscolaConfig(base_url="https://x/"), transport=httpx.MockTransport(fake))
    r = c.person_rollen(649)
    assert [x["id"] for x in r if x["zugewiesen"]] == [13]
    assert "personManagement.php" in fake.calls and fake.edit is False
