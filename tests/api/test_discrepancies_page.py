def test_discrepancies_page_returns_html(client):
    resp = client.get("/discrepancies")
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]


def test_discrepancies_page_contains_company_names(client):
    resp = client.get("/discrepancies")
    html = resp.text
    assert "ExxonMobil" in html
    assert "Shell" in html


def test_discrepancies_page_contains_hero_text(client):
    resp = client.get("/discrepancies")
    html = resp.text
    assert "cross-validate" in html.lower() or "discrepanc" in html.lower()


def test_discrepancies_page_has_csv_download_link(client):
    resp = client.get("/discrepancies")
    html = resp.text
    assert "/v1/discrepancies.csv" in html
