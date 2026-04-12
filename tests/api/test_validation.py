import pytest


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


def test_discrepancy_response_has_ticker(client):
    resp = client.get("/v1/discrepancies")
    data = resp.json()
    assert data["total"] >= 1
    item = data["items"][0]
    assert "ticker" in item
    assert item["ticker"] == "XOM"


def test_discrepancy_response_has_sources(client):
    resp = client.get("/v1/discrepancies")
    data = resp.json()
    item = data["items"][0]
    assert "sources" in item
    assert len(item["sources"]) == 2
    source_types = {s["source_type"] for s in item["sources"]}
    assert source_types == {"regulatory", "satellite"}


def test_discrepancy_response_has_delta(client):
    resp = client.get("/v1/discrepancies")
    data = resp.json()
    item = data["items"][0]
    assert "delta_mt_co2e" in item
    assert item["delta_mt_co2e"] == pytest.approx(56_000_000.0)


def test_discrepancy_source_has_filing_url(client):
    resp = client.get("/v1/discrepancies")
    data = resp.json()
    item = data["items"][0]
    regulatory = [s for s in item["sources"] if s["source_type"] == "regulatory"][0]
    satellite = [s for s in item["sources"] if s["source_type"] == "satellite"][0]
    assert "filing_url" in regulatory
    assert "filing_url" in satellite
    assert satellite["filing_url"] is None


def test_discrepancies_filter_by_ticker(client):
    resp = client.get("/v1/discrepancies?ticker=SHEL")
    data = resp.json()
    assert data["total"] == 1
    assert data["items"][0]["ticker"] == "SHEL"


def test_discrepancies_filter_by_company_name(client):
    resp = client.get("/v1/discrepancies?company=Exxon")
    data = resp.json()
    assert data["total"] == 1
    assert data["items"][0]["company_name"] == "ExxonMobil"


def test_discrepancies_filter_by_min_delta(client):
    resp = client.get("/v1/discrepancies?min_delta=10000000")
    data = resp.json()
    assert data["total"] == 1
    assert data["items"][0]["ticker"] == "XOM"


def test_discrepancies_sort_by_ticker(client):
    resp = client.get("/v1/discrepancies?sort=ticker")
    data = resp.json()
    assert data["total"] == 2
    tickers = [item["ticker"] for item in data["items"]]
    assert tickers == ["SHEL", "XOM"]


def test_discrepancies_sort_by_delta(client):
    resp = client.get("/v1/discrepancies?sort=delta")
    data = resp.json()
    assert data["total"] == 2
    assert data["items"][0]["ticker"] == "XOM"
    assert data["items"][1]["ticker"] == "SHEL"


def test_discrepancies_csv_returns_csv(client):
    resp = client.get("/v1/discrepancies.csv")
    assert resp.status_code == 200
    assert "text/csv" in resp.headers["content-type"]
    assert "attachment" in resp.headers.get("content-disposition", "")


def test_discrepancies_csv_has_expected_columns(client):
    resp = client.get("/v1/discrepancies.csv")
    lines = resp.text.strip().split("\n")
    header = lines[0]
    assert "company_name" in header
    assert "ticker" in header
    assert "spread_pct" in header
    assert "delta_mt_co2e" in header
    assert len(lines) >= 3  # header + 2 data rows


def test_discrepancies_csv_sorted_by_spread(client):
    resp = client.get("/v1/discrepancies.csv")
    lines = resp.text.strip().split("\n")
    data_rows = lines[1:]
    spreads = []
    for row in data_rows:
        cols = row.split(",")
        spreads.append(float(cols[5]))
    assert spreads == sorted(spreads, reverse=True)


def test_company_validation_entries_have_provenance(client):
    resp = client.get("/v1/companies/00000000-0000-0000-0000-000000000001/validation")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    entries = data[0]["entries"]
    assert len(entries) == 2
    for entry in entries:
        assert "filing_url" in entry
