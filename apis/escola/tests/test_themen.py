"""Jeder Endpunkt gehört zu genau einem Thema; Reihenfolge der Themen steht in OpenAPI (Doku auf GitHub Pages)."""
from escola_api import themen
from escola_api.app import create_app


def test_alle_endpunkte_haben_ein_thema():
    app = create_app()
    assert themen.anwenden(app) == []
    o = app.openapi()
    assert [t["name"] for t in o["tags"]] == [t for t, _ in themen.THEMEN]
    benutzt = {op["tags"][0] for ms in o["paths"].values() for op in ms.values()}
    assert benutzt == {t for t, _ in themen.THEMEN}, "Thema ohne Endpunkt oder Endpunkt mit fremdem Tag"
    assert all(len(op["tags"]) == 1 for ms in o["paths"].values() for op in ms.values())


def test_keine_veraltete_zuordnung():
    app = create_app()
    da = {(m, r.path) for r in app.routes if getattr(r, "include_in_schema", False) for m in getattr(r, "methods", set())}
    assert set(themen.ZUORDNUNG) <= da, sorted(set(themen.ZUORDNUNG) - da)
