"""Tests for ET-79: first-call instrumentation middleware.

Phase 2 Task 2.3 — track time-to-first-API-call per user (ApiKey holder).

On the first authenticated request with a given key, the middleware stamps
``ApiKey.first_api_call_at = utcnow()``. Subsequent requests must not update
the column. Unauthenticated requests are ignored.

This is an onboarding-funnel signal feeding ``GET /v1/metrics/launch``
(``signup_to_first_call_seconds``).
"""
from __future__ import annotations

import hashlib
import uuid
from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from src.api.main import create_app
from src.api.routes import launch_metrics as launch_metrics_mod
from src.shared.models import ApiKey


@pytest.fixture(autouse=True)
def _clear_launch_cache():
    launch_metrics_mod._CACHE["data"] = None
    launch_metrics_mod._CACHE["fetched_at"] = 0.0
    yield
    launch_metrics_mod._CACHE["data"] = None
    launch_metrics_mod._CACHE["fetched_at"] = 0.0


def _make_key(db_session, raw: str = "test-et79-key") -> tuple[str, uuid.UUID]:
    """Insert an ApiKey with first_api_call_at=None; return (raw_key, id)."""
    key_id = uuid.uuid4()
    key_hash = hashlib.sha256(raw.encode()).hexdigest()
    db_session._session.add(
        ApiKey(
            id=key_id,
            key_hash=key_hash,
            email="user@example.com",
            tier="free",
            rate_limit=1000,
            first_api_call_at=None,
        )
    )
    db_session._session.commit()
    return raw, key_id


def _fetch_key(db_session, key_id: uuid.UUID) -> ApiKey:
    db_session._session.expire_all()
    return db_session._session.get(ApiKey, key_id)


def test_first_authenticated_call_stamps_first_api_call_at(db_session):
    raw, key_id = _make_key(db_session)
    app = create_app(db_session_override=db_session)
    client = TestClient(app)

    # Sanity: starts as None
    assert _fetch_key(db_session, key_id).first_api_call_at is None

    before = datetime.utcnow()
    resp = client.get("/v1/companies", headers={"X-API-Key": raw})
    after = datetime.utcnow()
    assert resp.status_code == 200

    stamped = _fetch_key(db_session, key_id).first_api_call_at
    assert stamped is not None, "first_api_call_at should be set after first call"
    # Allow a small skew window
    assert (before - timedelta(seconds=5)) <= stamped <= (after + timedelta(seconds=5))


def test_second_authenticated_call_does_not_update_first_api_call_at(db_session):
    """The stamp is idempotent — only the first call writes."""
    raw, key_id = _make_key(db_session)
    app = create_app(db_session_override=db_session)
    client = TestClient(app)

    r1 = client.get("/v1/companies", headers={"X-API-Key": raw})
    assert r1.status_code == 200
    first_stamp = _fetch_key(db_session, key_id).first_api_call_at
    assert first_stamp is not None

    # Second call — must not change the stamp
    r2 = client.get("/v1/companies", headers={"X-API-Key": raw})
    assert r2.status_code == 200
    second_stamp = _fetch_key(db_session, key_id).first_api_call_at
    assert second_stamp == first_stamp, "second call must not overwrite first_api_call_at"


def test_unauthenticated_call_does_not_touch_any_key(db_session):
    _, key_id = _make_key(db_session)
    app = create_app(db_session_override=db_session)
    client = TestClient(app)

    resp = client.get("/v1/companies")  # no X-API-Key header
    assert resp.status_code == 200
    assert _fetch_key(db_session, key_id).first_api_call_at is None


def test_invalid_key_does_not_stamp(db_session):
    _, key_id = _make_key(db_session)
    app = create_app(db_session_override=db_session)
    client = TestClient(app)

    resp = client.get("/v1/companies", headers={"X-API-Key": "not-a-real-key"})
    assert resp.status_code == 401
    assert _fetch_key(db_session, key_id).first_api_call_at is None
