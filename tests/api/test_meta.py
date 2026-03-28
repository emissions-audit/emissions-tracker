def test_stats(client):
    resp = client.get("/v1/stats")
    assert resp.status_code == 200
    data = resp.json()
    assert data["company_count"] == 2
    assert data["emission_count"] == 4
    assert data["year_range"]["min"] == 2022
    assert data["year_range"]["max"] == 2023


def test_meta_sectors(client):
    resp = client.get("/v1/meta/sectors")
    assert resp.status_code == 200
    data = resp.json()
    assert "energy" in [s["sector"] for s in data]


def test_meta_methodology(client):
    resp = client.get("/v1/meta/methodology")
    assert resp.status_code == 200
    data = resp.json()
    assert "normalization" in data
    assert "sources" in data
