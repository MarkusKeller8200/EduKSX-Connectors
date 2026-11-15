import httpx

from escola_api.client import EscolaClient, EscolaConfig


def test_zaehler_zaehlt_jede_escola_anfrage():
    c = EscolaClient(EscolaConfig(cookie="x"), transport=httpx.MockTransport(lambda r: httpx.Response(200, text="ok")))
    assert c.zaehler == 0
    c._http.get("admin.php?page_request=6")
    c._http.post("inc/ajax/persons/show_persons_of_group.php", content=b"")
    assert c.zaehler == 2 and c.zuletzt == "show_persons_of_group.php"
