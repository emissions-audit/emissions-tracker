def test_company_emissions(client):
    resp = client.get("/v1/companies/00000000-0000-0000-0000-000000000001/emissions")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 3  # scope 1 2023, scope 2 2023, scope 1 2022


def test_company_emissions_filter_year(client):
    resp = client.get("/v1/companies/00000000-0000-0000-0000-000000000001/emissions?year=2023")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 2


def test_cross_company_emissions(client):
    resp = client.get("/v1/emissions?year=2023&scope=1")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 2  # Shell and Exxon scope 1 2023


def test_cross_company_emissions_sorted(client):
    resp = client.get("/v1/emissions?year=2023&scope=1&sort=value_t_co2e&order=desc")
    assert resp.status_code == 200
    items = resp.json()["items"]
    assert items[0]["value_t_co2e"] >= items[1]["value_t_co2e"]


def test_compare_emissions(client):
    shell = "00000000-0000-0000-0000-000000000001"
    exxon = "00000000-0000-0000-0000-000000000002"
    resp = client.get(f"/v1/emissions/compare?companies={shell},{exxon}&scopes=1&years=2023")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 2
