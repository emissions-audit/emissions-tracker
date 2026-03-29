import hashlib
import uuid

from fastapi.testclient import TestClient

from src.shared.models import ApiCallLog, ApiKey
from src.api.main import create_app


class TestAnalyticsMiddleware:
    def test_request_creates_log_entry(self, seeded_session):
        app = create_app(db_session_override=seeded_session)
        client = TestClient(app)

        client.get("/v1/companies")

        logs = seeded_session.query(ApiCallLog).all()
        assert len(logs) == 1
        assert logs[0].endpoint == "/v1/companies"
        assert logs[0].method == "GET"
        assert logs[0].status_code == 200
        assert logs[0].response_time_ms > 0
        assert logs[0].tier == "anonymous"

    def test_multiple_requests_create_multiple_logs(self, seeded_session):
        app = create_app(db_session_override=seeded_session)
        client = TestClient(app)

        client.get("/v1/companies")
        client.get("/v1/stats")
        client.get("/v1/meta/sectors")

        logs = seeded_session.query(ApiCallLog).all()
        assert len(logs) == 3
        endpoints = {log.endpoint for log in logs}
        assert "/v1/companies" in endpoints
        assert "/v1/stats" in endpoints
        assert "/v1/meta/sectors" in endpoints

    def test_logs_authenticated_request_tier(self, seeded_session):
        key = "test-analytics-key-123"
        key_hash = hashlib.sha256(key.encode()).hexdigest()
        seeded_session.add(ApiKey(
            id=uuid.uuid4(), key_hash=key_hash,
            email="test@example.com", tier="pro", rate_limit=1000,
        ))
        seeded_session.commit()

        app = create_app(db_session_override=seeded_session)
        client = TestClient(app)

        client.get("/v1/companies", headers={"X-API-Key": key})

        log = seeded_session.query(ApiCallLog).first()
        assert log.tier == "pro"
        assert log.api_key_hash == key_hash[:16]

    def test_skips_docs_and_openapi_paths(self, seeded_session):
        app = create_app(db_session_override=seeded_session)
        client = TestClient(app)

        client.get("/docs")
        client.get("/openapi.json")

        logs = seeded_session.query(ApiCallLog).all()
        assert len(logs) == 0


class TestAnalyticsSummaryEndpoint:
    def test_returns_summary(self, seeded_session):
        app = create_app(db_session_override=seeded_session)
        client = TestClient(app)

        # Generate some traffic first
        client.get("/v1/companies")
        client.get("/v1/companies")
        client.get("/v1/stats")

        r = client.get("/v1/analytics/summary")
        assert r.status_code == 200
        data = r.json()
        # 3 initial requests + the analytics/summary request itself = 4
        assert data["total_calls"] >= 3
        assert data["period_days"] == 30
        assert len(data["top_endpoints"]) > 0
        assert data["avg_response_time_ms"] > 0

    def test_custom_period(self, seeded_session):
        app = create_app(db_session_override=seeded_session)
        client = TestClient(app)

        client.get("/v1/companies")

        r = client.get("/v1/analytics/summary", params={"days": 7})
        assert r.status_code == 200
        assert r.json()["period_days"] == 7
