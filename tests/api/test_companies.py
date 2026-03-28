def test_list_companies(client):
    resp = client.get("/v1/companies")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 2
    assert len(data["items"]) == 2


def test_list_companies_filter_country(client):
    resp = client.get("/v1/companies?country=GB")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert data["items"][0]["name"] == "Shell plc"


def test_get_company(client):
    resp = client.get("/v1/companies/00000000-0000-0000-0000-000000000001")
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "Shell plc"


def test_get_company_not_found(client):
    resp = client.get("/v1/companies/00000000-0000-0000-0000-999999999999")
    assert resp.status_code == 404
