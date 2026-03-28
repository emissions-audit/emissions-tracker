def test_company_pledges(client):
    resp = client.get("/v1/companies/00000000-0000-0000-0000-000000000001/pledges")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["pledge_type"] == "net_zero"
    assert data[0]["target_year"] == 2050


def test_pledge_tracker(client):
    resp = client.get("/v1/pledges/tracker")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) >= 1
    row = data[0]
    assert "company_name" in row
    assert "on_track" in row
