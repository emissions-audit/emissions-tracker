from src.shared import corrections as corrections_module


def test_emission_response_has_no_provenance_without_correction(client):
    corrections_module.clear_cache()
    corrections_module._cache = []
    resp = client.get("/v1/companies/00000000-0000-0000-0000-000000000001/emissions?year=2023&scope=1")
    assert resp.status_code == 200
    items = resp.json()["items"]
    assert len(items) == 1
    assert items[0].get("provenance") is None
    assert items[0]["value_mt_co2e"] == 68_000_000


def test_correction_overrides_value_and_adds_provenance(client):
    corrections_module._cache = [
        {
            "company_ticker": "SHEL",
            "year": 2023,
            "scope": "1",
            "field": "value_mt_co2e",
            "old_value": 68_000_000,
            "new_value": 70_500_000,
            "source_url": "https://example.org/shell-2023-restatement",
            "contributor": "@alice",
            "accepted_date": "2026-04-15",
        }
    ]
    try:
        resp = client.get(
            "/v1/companies/00000000-0000-0000-0000-000000000001/emissions?year=2023&scope=1"
        )
        assert resp.status_code == 200
        items = resp.json()["items"]
        assert len(items) == 1
        row = items[0]
        assert row["value_mt_co2e"] == 70_500_000
        prov = row.get("provenance")
        assert prov is not None
        assert prov["contributors"] == ["@alice"]
        assert len(prov["corrections"]) == 1
        c = prov["corrections"][0]
        assert c["field"] == "value_mt_co2e"
        assert c["old_value"] == 68_000_000
        assert c["new_value"] == 70_500_000
        assert c["contributor"] == "@alice"
        assert c["accepted_date"] == "2026-04-15"
    finally:
        corrections_module.clear_cache()


def test_correction_flows_through_list_and_compare_routes(client):
    corrections_module._cache = [
        {
            "company_ticker": "XOM",
            "year": 2023,
            "scope": "1",
            "field": "value_mt_co2e",
            "old_value": 112_000_000,
            "new_value": 120_000_000,
            "source_url": "https://example.org/xom-2023-restatement",
            "contributor": "@bob",
            "accepted_date": "2026-04-15",
        }
    ]
    try:
        list_resp = client.get("/v1/emissions?year=2023&scope=1&sort=value_mt_co2e&order=desc")
        assert list_resp.status_code == 200
        items = list_resp.json()["items"]
        xom_rows = [i for i in items if i["value_mt_co2e"] == 120_000_000]
        assert len(xom_rows) == 1
        assert xom_rows[0]["provenance"]["contributors"] == ["@bob"]

        shell = "00000000-0000-0000-0000-000000000001"
        exxon = "00000000-0000-0000-0000-000000000002"
        cmp_resp = client.get(
            f"/v1/emissions/compare?companies={shell},{exxon}&scopes=1&years=2023"
        )
        assert cmp_resp.status_code == 200
        cmp_rows = cmp_resp.json()
        xom_cmp = [r for r in cmp_rows if r["company_name"] == "ExxonMobil"]
        assert len(xom_cmp) == 1
        assert xom_cmp[0]["value_mt_co2e"] == 120_000_000
    finally:
        corrections_module.clear_cache()


def test_build_provenance_returns_none_without_match():
    result = corrections_module.build_provenance("NOPE", 2023, "1", corrections=[])
    assert result is None


def test_apply_value_returns_original_without_match():
    result = corrections_module.apply_value(
        "value_mt_co2e", 100.0, "NOPE", 2023, "1", corrections=[]
    )
    assert result == 100.0
