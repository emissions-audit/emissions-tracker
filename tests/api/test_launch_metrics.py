"""Tests for ET-77: /v1/metrics/launch — public + admin split (REV-03).

The endpoint is partitioned to avoid broadcasting funnel-weakness signals
publicly at launch:

* ``GET /v1/metrics/launch`` — public, trust-signal counts only
  (``stars_total``, ``citations_mentioned``).
* ``GET /v1/metrics/launch/admin`` — Bearer-gated, full aggregate payload
  including conversion rates, activation %, traffic sources, and
  funnel timing. Gate token comes from ``LAUNCH_METRICS_ADMIN_TOKEN``.
"""
from __future__ import annotations

import hashlib
import uuid

import pytest
from fastapi.testclient import TestClient

from src.api.main import create_app
from src.api.routes import launch_metrics as launch_metrics_mod
from src.shared.models import ApiCallLog, ApiKey


PUBLIC_KEYS = {
    "stars_total",
    "citations_mentioned",
}

ADMIN_KEYS = {
    "stars_total",
    "citations_mentioned",
    "keys_issued",
    "api_calls_served",
    "signup_conversion_pct",
    "api_activation_pct",
    "enterprise_form_views",
    "traffic_sources",
    "signup_to_first_call_seconds",
}

ADMIN_ONLY_KEYS = ADMIN_KEYS - PUBLIC_KEYS

ADMIN_TOKEN = "test-admin-token-xyz"


@pytest.fixture(autouse=True)
def _clear_cache():
    """Reset the 60s response cache between tests so each test sees fresh data."""
    launch_metrics_mod._CACHE["data"] = None
    launch_metrics_mod._CACHE["fetched_at"] = 0.0
    yield
    launch_metrics_mod._CACHE["data"] = None
    launch_metrics_mod._CACHE["fetched_at"] = 0.0


@pytest.fixture
def _no_github(monkeypatch):
    """Force stars_total to None by returning None from the fetcher."""
    async def _none_fetch():
        return None
    monkeypatch.setattr(launch_metrics_mod, "_fetch_stars", _none_fetch)


@pytest.fixture
def _admin_token(monkeypatch):
    """Configure LAUNCH_METRICS_ADMIN_TOKEN for admin-endpoint tests."""
    monkeypatch.setenv("LAUNCH_METRICS_ADMIN_TOKEN", ADMIN_TOKEN)


def _admin_headers(token: str = ADMIN_TOKEN) -> dict:
    return {"Authorization": f"Bearer {token}"}


# =========================================================================
# Public endpoint: /v1/metrics/launch
# =========================================================================


def test_public_returns_200(db_session, _no_github):
    app = create_app(db_session_override=db_session)
    client = TestClient(app)
    resp = client.get("/v1/metrics/launch")
    assert resp.status_code == 200


def test_public_has_only_public_keys(db_session, _no_github):
    app = create_app(db_session_override=db_session)
    client = TestClient(app)
    resp = client.get("/v1/metrics/launch")
    data = resp.json()
    assert set(data.keys()) == PUBLIC_KEYS


def test_public_does_not_leak_admin_fields(db_session, _no_github):
    """Regression guard: funnel-weakness signals (keys, conversion, activation,
    traffic sources, timing) MUST NOT appear on the public endpoint (REV-03).
    """
    app = create_app(db_session_override=db_session)
    client = TestClient(app)
    resp = client.get("/v1/metrics/launch")
    data = resp.json()
    for leaked in ADMIN_ONLY_KEYS:
        assert leaked not in data, f"admin field leaked on public endpoint: {leaked}"


def test_public_empty_db_shape(db_session, _no_github):
    app = create_app(db_session_override=db_session)
    client = TestClient(app)
    resp = client.get("/v1/metrics/launch")
    data = resp.json()
    assert data["citations_mentioned"] == 0
    assert data["stars_total"] is None


def test_public_response_is_cached(db_session, _no_github):
    """Two calls within the 60s TTL should return the same payload even if
    underlying data changes."""
    app = create_app(db_session_override=db_session)
    client = TestClient(app)

    resp1 = client.get("/v1/metrics/launch")
    data1 = resp1.json()
    assert data1["citations_mentioned"] == 0

    resp2 = client.get("/v1/metrics/launch")
    data2 = resp2.json()
    assert data2 == data1


# =========================================================================
# Admin endpoint: /v1/metrics/launch/admin
# =========================================================================


def test_admin_requires_bearer_token(db_session, _no_github, _admin_token):
    app = create_app(db_session_override=db_session)
    client = TestClient(app)
    resp = client.get("/v1/metrics/launch/admin")
    assert resp.status_code == 401


def test_admin_rejects_wrong_token(db_session, _no_github, _admin_token):
    app = create_app(db_session_override=db_session)
    client = TestClient(app)
    resp = client.get(
        "/v1/metrics/launch/admin",
        headers=_admin_headers("not-the-right-token"),
    )
    assert resp.status_code == 401


def test_admin_rejects_non_bearer_scheme(db_session, _no_github, _admin_token):
    app = create_app(db_session_override=db_session)
    client = TestClient(app)
    resp = client.get(
        "/v1/metrics/launch/admin",
        headers={"Authorization": f"Basic {ADMIN_TOKEN}"},
    )
    assert resp.status_code == 401


def test_admin_returns_401_when_env_var_unset(db_session, _no_github, monkeypatch):
    """If LAUNCH_METRICS_ADMIN_TOKEN is not configured, admin is effectively
    closed — no caller can authenticate, and the endpoint MUST NOT fall open.
    """
    monkeypatch.delenv("LAUNCH_METRICS_ADMIN_TOKEN", raising=False)
    app = create_app(db_session_override=db_session)
    client = TestClient(app)
    resp = client.get(
        "/v1/metrics/launch/admin",
        headers=_admin_headers("anything"),
    )
    assert resp.status_code == 401


def test_admin_returns_full_payload(db_session, _no_github, _admin_token):
    app = create_app(db_session_override=db_session)
    client = TestClient(app)
    resp = client.get("/v1/metrics/launch/admin", headers=_admin_headers())
    assert resp.status_code == 200
    data = resp.json()
    assert set(data.keys()) == ADMIN_KEYS


def test_admin_empty_db_shape(db_session, _no_github, _admin_token):
    app = create_app(db_session_override=db_session)
    client = TestClient(app)
    resp = client.get("/v1/metrics/launch/admin", headers=_admin_headers())
    data = resp.json()

    assert data["keys_issued"] == 0
    assert data["api_calls_served"] == 0
    assert data["enterprise_form_views"] == 0
    assert data["citations_mentioned"] == 0
    assert data["api_activation_pct"] is None
    assert data["signup_conversion_pct"] is None
    assert data["stars_total"] is None
    assert data["traffic_sources"] in ([], {})
    assert data["signup_to_first_call_seconds"] is None


def test_admin_keys_issued_counts_api_keys(db_session, _no_github, _admin_token):
    for i in range(3):
        db_session._session.add(ApiKey(
            id=uuid.uuid4(),
            key_hash=hashlib.sha256(f"k{i}".encode()).hexdigest(),
            email=f"u{i}@example.com",
            tier="free",
            rate_limit=100,
        ))
    db_session._session.commit()

    app = create_app(db_session_override=db_session)
    client = TestClient(app)
    resp = client.get("/v1/metrics/launch/admin", headers=_admin_headers())
    data = resp.json()
    assert data["keys_issued"] == 3


def test_admin_api_calls_served_counts_logs(db_session, _no_github, _admin_token):
    for _ in range(5):
        db_session._session.add(ApiCallLog(
            id=uuid.uuid4(),
            endpoint="/v1/companies",
            method="GET",
            status_code=200,
            response_time_ms=7.0,
        ))
    db_session._session.commit()

    app = create_app(db_session_override=db_session)
    client = TestClient(app)
    resp = client.get("/v1/metrics/launch/admin", headers=_admin_headers())
    data = resp.json()
    assert data["api_calls_served"] == 5


def test_admin_enterprise_form_views(db_session, _no_github, _admin_token):
    for _ in range(4):
        db_session._session.add(ApiCallLog(
            id=uuid.uuid4(),
            endpoint="/enterprise",
            method="GET",
            status_code=200,
            response_time_ms=10.0,
        ))
    db_session._session.add(ApiCallLog(
        id=uuid.uuid4(),
        endpoint="/enterprise",
        method="POST",
        status_code=201,
        response_time_ms=20.0,
    ))
    db_session._session.add(ApiCallLog(
        id=uuid.uuid4(),
        endpoint="/v1/companies",
        method="GET",
        status_code=200,
        response_time_ms=5.0,
    ))
    db_session._session.commit()

    app = create_app(db_session_override=db_session)
    client = TestClient(app)
    resp = client.get("/v1/metrics/launch/admin", headers=_admin_headers())
    data = resp.json()
    assert data["enterprise_form_views"] == 4


def test_admin_api_activation_pct(db_session, _no_github, _admin_token):
    keys = []
    for i in range(3):
        full_hash = hashlib.sha256(f"key-{i}".encode()).hexdigest()
        keys.append(full_hash)
        db_session._session.add(ApiKey(
            id=uuid.uuid4(),
            key_hash=full_hash,
            email=f"u{i}@example.com",
            tier="free",
            rate_limit=100,
        ))

    for key_hash in keys[:2]:
        db_session._session.add(ApiCallLog(
            id=uuid.uuid4(),
            endpoint="/v1/emissions",
            method="GET",
            status_code=200,
            response_time_ms=15.0,
            api_key_hash=key_hash[:16],
        ))
    db_session._session.commit()

    app = create_app(db_session_override=db_session)
    client = TestClient(app)
    resp = client.get("/v1/metrics/launch/admin", headers=_admin_headers())
    data = resp.json()
    assert data["api_activation_pct"] is not None
    assert 66.0 < data["api_activation_pct"] < 67.0


def test_admin_traffic_sources_grouped_by_host(db_session, _no_github, _admin_token):
    referrers = [
        "https://google.com/search?q=co2",
        "https://google.com/",
        "https://news.ycombinator.com/",
        None,
    ]
    for ref in referrers:
        db_session._session.add(ApiCallLog(
            id=uuid.uuid4(),
            endpoint="/v1/companies",
            method="GET",
            status_code=200,
            response_time_ms=10.0,
            referrer=ref,
        ))
    db_session._session.commit()

    app = create_app(db_session_override=db_session)
    client = TestClient(app)
    resp = client.get("/v1/metrics/launch/admin", headers=_admin_headers())
    data = resp.json()

    sources = data["traffic_sources"]
    if isinstance(sources, dict):
        assert sources.get("google.com") == 2
        assert sources.get("news.ycombinator.com") == 1
    else:
        lookup = {row["host"]: row["count"] for row in sources}
        assert lookup.get("google.com") == 2
        assert lookup.get("news.ycombinator.com") == 1


def test_admin_signup_to_first_call_seconds_median(db_session, _no_github, _admin_token):
    from datetime import datetime, timedelta

    t0 = datetime(2026, 4, 1, 12, 0, 0)
    latencies = [10, 60, 300]
    for i, secs in enumerate(latencies):
        db_session._session.add(ApiKey(
            id=uuid.uuid4(),
            key_hash=hashlib.sha256(f"m{i}".encode()).hexdigest(),
            email=f"m{i}@example.com",
            tier="free",
            rate_limit=100,
            created_at=t0,
            first_api_call_at=t0 + timedelta(seconds=secs),
        ))
    db_session._session.add(ApiKey(
        id=uuid.uuid4(),
        key_hash=hashlib.sha256(b"unactivated").hexdigest(),
        email="skip@example.com",
        tier="free",
        rate_limit=100,
        created_at=t0,
        first_api_call_at=None,
    ))
    db_session._session.commit()

    app = create_app(db_session_override=db_session)
    client = TestClient(app)
    resp = client.get("/v1/metrics/launch/admin", headers=_admin_headers())
    data = resp.json()
    assert data["signup_to_first_call_seconds"] == 60.0


def test_admin_response_is_cached(db_session, _no_github, _admin_token):
    app = create_app(db_session_override=db_session)
    client = TestClient(app)

    resp1 = client.get("/v1/metrics/launch/admin", headers=_admin_headers())
    data1 = resp1.json()
    assert data1["keys_issued"] == 0

    db_session._session.add(ApiKey(
        id=uuid.uuid4(),
        key_hash=hashlib.sha256(b"late").hexdigest(),
        email="late@example.com",
        tier="free",
        rate_limit=100,
    ))
    db_session._session.commit()

    resp2 = client.get("/v1/metrics/launch/admin", headers=_admin_headers())
    data2 = resp2.json()
    assert data2["keys_issued"] == 0
