def test_company_validation(client):
    resp = client.get("/v1/companies/00000000-0000-0000-0000-000000000001/validation")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["flag"] == "yellow"
    assert data[0]["source_count"] == 2
    assert len(data[0]["entries"]) == 2


def test_list_discrepancies(client):
    resp = client.get("/v1/discrepancies")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] >= 1


def test_list_discrepancies_filter_flag(client):
    resp = client.get("/v1/discrepancies?flag=yellow")
    assert resp.status_code == 200
    data = resp.json()
    assert all(item["flag"] == "yellow" for item in data["items"])


def test_top_discrepancies(client):
    resp = client.get("/v1/discrepancies/top")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) >= 1
    if len(data) > 1:
        assert data[0]["spread_pct"] >= data[1]["spread_pct"]
