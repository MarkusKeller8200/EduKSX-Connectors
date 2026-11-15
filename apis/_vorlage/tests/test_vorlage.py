from fastapi.testclient import TestClient

from vorlage_api.app import app


def test_status():
    assert TestClient(app).get("/status").json()["ok"] is True
