import uuid

from fastapi.testclient import TestClient

from src.api.main import create_app
from src.shared.models import ApiCallLog, EnterpriseInquiry


def test_metrics_returns_200(db_session):
    app = create_app(db_session_override=db_session)
    client = TestClient(app)
    resp = client.get("/v1/metrics")
    assert resp.status_code == 200


def test_metrics_has_expected_keys(db_session):
    app = create_app(db_session_override=db_session)
    client = TestClient(app)
    resp = client.get("/v1/metrics")
    data = resp.json()
    for key in ("uptime_seconds", "started_at", "version", "coverage", "enterprise", "database"):
        assert key in data


def test_metrics_uptime_is_non_negative_integer(db_session):
    app = create_app(db_session_override=db_session)
    client = TestClient(app)
    resp = client.get("/v1/metrics")
    data = resp.json()
    assert isinstance(data["uptime_seconds"], int)
    assert data["uptime_seconds"] >= 0


def test_metrics_version_is_expected(db_session):
    app = create_app(db_session_override=db_session)
    client = TestClient(app)
    resp = client.get("/v1/metrics")
    data = resp.json()
    assert data["version"] == "0.1.0"


def test_metrics_enterprise_empty(db_session):
    """Enterprise section returns zeros when no data exists."""
    app = create_app(db_session_override=db_session)
    client = TestClient(app)
    resp = client.get("/v1/metrics")
    data = resp.json()
    ent = data["enterprise"]
    assert ent["page_views"] == 0
    assert ent["submissions"] == 0
    assert ent["referrers"] == []


def test_metrics_enterprise_with_data(db_session):
    """Enterprise section counts page views, submissions, and referrers."""
    # Seed enterprise page views (GET /enterprise)
    for ref in ["https://google.com", "https://google.com", "https://linkedin.com"]:
        db_session._session.add(ApiCallLog(
            id=uuid.uuid4(),
            endpoint="/enterprise",
            method="GET",
            status_code=200,
            response_time_ms=50.0,
            referrer=ref,
        ))
    # A POST to /enterprise shouldn't count as page view
    db_session._session.add(ApiCallLog(
        id=uuid.uuid4(),
        endpoint="/enterprise",
        method="POST",
        status_code=201,
        response_time_ms=80.0,
    ))
    # A GET to a non-enterprise endpoint shouldn't count
    db_session._session.add(ApiCallLog(
        id=uuid.uuid4(),
        endpoint="/v1/emissions",
        method="GET",
        status_code=200,
        response_time_ms=30.0,
    ))
    # Seed enterprise inquiries
    db_session._session.add(EnterpriseInquiry(
        id=uuid.uuid4(),
        company_name="Acme Corp",
        email="cto@acme.com",
        use_case="Portfolio ESG reporting",
    ))
    db_session._session.add(EnterpriseInquiry(
        id=uuid.uuid4(),
        company_name="Globex Inc",
        email="data@globex.com",
    ))
    db_session._session.commit()

    app = create_app(db_session_override=db_session)
    client = TestClient(app)
    resp = client.get("/v1/metrics")
    data = resp.json()
    ent = data["enterprise"]

    assert ent["page_views"] == 3
    assert ent["submissions"] == 2
    assert len(ent["referrers"]) == 2
    # google.com appears twice, should be first
    assert ent["referrers"][0]["referrer"] == "https://google.com"
    assert ent["referrers"][0]["count"] == 2
    assert ent["referrers"][1]["referrer"] == "https://linkedin.com"
    assert ent["referrers"][1]["count"] == 1
