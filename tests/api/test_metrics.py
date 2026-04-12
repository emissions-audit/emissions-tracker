from fastapi.testclient import TestClient

from src.api.main import create_app


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
    for key in ("uptime_seconds", "started_at", "version", "coverage", "database"):
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
