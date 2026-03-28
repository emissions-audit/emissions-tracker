def test_company_filings(client):
    resp = client.get("/v1/companies/00000000-0000-0000-0000-000000000001/filings")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    assert data["items"][0]["filing_type"] == "10k_xbrl"
