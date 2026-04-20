"""ET-77 / REV-03: launch-traction metrics — public + admin split.

Two endpoints share one compute path:

* ``GET /v1/metrics/launch`` — public, trust-signal counts only
  (``stars_total``, ``citations_mentioned``). Safe for the landing-page
  widget (ET-78). Intentionally excludes funnel/conversion metrics that
  would broadcast launch weakness externally.

* ``GET /v1/metrics/launch/admin`` — Bearer-gated, full aggregate payload.
  Requires ``Authorization: Bearer <LAUNCH_METRICS_ADMIN_TOKEN>``; a
  missing or mismatched token returns 401. If the env var is unset,
  the endpoint fails closed — no caller can authenticate.

Full admin fields
-----------------
- ``stars_total``                   GitHub stargazers (5-min cache).
- ``citations_mentioned``           Row count in ``citation_mentions`` or 0.
- ``keys_issued``                   Total ApiKey rows.
- ``api_calls_served``              Total ApiCallLog rows.
- ``signup_conversion_pct``         Users / unique visitors, or ``null``.
- ``api_activation_pct``            Users w/ >=1 API call / total users.
- ``enterprise_form_views``         GET hits on ``/enterprise*``.
- ``traffic_sources``               {host: count} from ApiCallLog.referrer.
- ``signup_to_first_call_seconds``  Median activation latency (ET-79).
"""
from __future__ import annotations

import hmac
import os
import time
from typing import Any
from urllib.parse import urlparse

import httpx
from fastapi import APIRouter, Header, HTTPException
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from src.shared.models import ApiCallLog, ApiKey


# ------ GitHub stars (5-min cache) ------------------------------------------------

GITHUB_OWNER = "emissions-audit"
GITHUB_REPO = "emissions-tracker"
_GITHUB_URL = f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}"
_GITHUB_TTL = 300  # 5 minutes

_STARS_CACHE: dict[str, Any] = {"value": None, "fetched_at": 0.0}


async def _fetch_stars() -> int | None:
    """Fetch stargazer count from GitHub. Returns ``None`` if no token configured
    or on any HTTP error (public-safe fallback).
    """
    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        return None

    now = time.monotonic()
    if _STARS_CACHE["value"] is not None and (now - _STARS_CACHE["fetched_at"]) < _GITHUB_TTL:
        return _STARS_CACHE["value"]  # type: ignore[return-value]

    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {token}",
    }
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(_GITHUB_URL, headers=headers)
            resp.raise_for_status()
            stars = int(resp.json().get("stargazers_count", 0))
    except (httpx.HTTPError, ValueError, KeyError):
        return None

    _STARS_CACHE["value"] = stars
    _STARS_CACHE["fetched_at"] = now
    return stars


# ------ Response cache (60s, full payload) ----------------------------------------

_CACHE_TTL = 60  # seconds
_CACHE: dict[str, Any] = {"data": None, "fetched_at": 0.0}


def _cached_payload() -> dict | None:
    now = time.monotonic()
    data = _CACHE["data"]
    if data is not None and (now - _CACHE["fetched_at"]) < _CACHE_TTL:
        return data  # type: ignore[return-value]
    return None


def _store_cache(payload: dict) -> None:
    _CACHE["data"] = payload
    _CACHE["fetched_at"] = time.monotonic()


# ------ Admin auth ----------------------------------------------------------------

PUBLIC_FIELDS = ("stars_total", "citations_mentioned")


def _require_admin(authorization: str | None) -> None:
    """Enforce Bearer auth against ``LAUNCH_METRICS_ADMIN_TOKEN``.

    Fails closed if the env var is unset — no caller can authenticate.
    Uses ``hmac.compare_digest`` for constant-time comparison.
    """
    expected = os.environ.get("LAUNCH_METRICS_ADMIN_TOKEN", "")
    if not expected:
        raise HTTPException(status_code=401, detail="admin metrics not configured")
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="missing bearer token")
    provided = authorization[len("Bearer "):]
    if not hmac.compare_digest(provided, expected):
        raise HTTPException(status_code=401, detail="invalid bearer token")


# ------ Helpers -------------------------------------------------------------------


def _referrer_host(referrer: str | None) -> str | None:
    if not referrer:
        return None
    try:
        host = urlparse(referrer).hostname
    except ValueError:
        return None
    return host or None


async def _count_citations(db: AsyncSession) -> int:
    """Return row count of ``citation_mentions`` if the table exists, else 0."""
    try:
        result = await db.execute(text("SELECT COUNT(*) FROM citation_mentions"))
        return int(result.scalar() or 0)
    except Exception:
        return 0


# ------ Compute (full payload) ----------------------------------------------------


async def _compute_full_payload(db: AsyncSession) -> dict:
    """Compute every metric. Callers shape/filter the response.

    One DB pass per cache window, regardless of public vs admin traffic mix.
    """
    # Keys issued (proxy for "users")
    try:
        keys_issued = int((await db.execute(
            select(func.count(ApiKey.id))
        )).scalar() or 0)
    except Exception:
        keys_issued = 0

    # Total API calls served
    try:
        api_calls_served = int((await db.execute(
            select(func.count(ApiCallLog.id))
        )).scalar() or 0)
    except Exception:
        api_calls_served = 0

    # API activation: users with >=1 API call / total users
    activation_pct: float | None = None
    if keys_issued > 0:
        try:
            key_prefix = func.substr(ApiKey.key_hash, 1, 16)
            subq = (
                select(func.distinct(ApiCallLog.api_key_hash))
                .where(ApiCallLog.api_key_hash.isnot(None))
                .subquery()
            )
            activated = int((await db.execute(
                select(func.count(func.distinct(ApiKey.id)))
                .where(key_prefix.in_(select(subq)))
            )).scalar() or 0)
            activation_pct = round(100.0 * activated / keys_issued, 2)
        except Exception:
            activation_pct = None

    # Enterprise form views
    try:
        enterprise_form_views = int((await db.execute(
            select(func.count(ApiCallLog.id))
            .where(
                ApiCallLog.endpoint.like("/enterprise%"),
                ApiCallLog.method == "GET",
            )
        )).scalar() or 0)
    except Exception:
        enterprise_form_views = 0

    # Signup conversion: users / unique visitors
    signup_conversion_pct: float | None = None
    try:
        unique_visitors = int((await db.execute(
            select(func.count(func.distinct(ApiCallLog.client_ip)))
            .where(ApiCallLog.client_ip.isnot(None))
        )).scalar() or 0)
        if unique_visitors > 0:
            signup_conversion_pct = round(100.0 * keys_issued / unique_visitors, 2)
    except Exception:
        signup_conversion_pct = None

    # Traffic sources: group by referrer host
    traffic_sources: dict[str, int] = {}
    try:
        rows = (await db.execute(
            select(ApiCallLog.referrer, func.count(ApiCallLog.id))
            .where(
                ApiCallLog.referrer.isnot(None),
                ApiCallLog.referrer != "",
            )
            .group_by(ApiCallLog.referrer)
        )).all()
        for referrer, count in rows:
            host = _referrer_host(referrer)
            if not host:
                continue
            traffic_sources[host] = traffic_sources.get(host, 0) + int(count)
    except Exception:
        traffic_sources = {}

    # GitHub stars (cached)
    try:
        stars_total = await _fetch_stars()
    except Exception:
        stars_total = None

    # Citations (table may not exist yet)
    citations_mentioned = await _count_citations(db)

    # ET-79: median signup-to-first-call latency (seconds)
    signup_to_first_call_seconds: float | None = None
    try:
        rows = (await db.execute(
            select(ApiKey.created_at, ApiKey.first_api_call_at)
            .where(ApiKey.first_api_call_at.isnot(None))
        )).all()
        deltas = [
            (first - created).total_seconds()
            for created, first in rows
            if created is not None and first is not None
        ]
        if deltas:
            deltas.sort()
            n = len(deltas)
            mid = n // 2
            if n % 2 == 1:
                median = deltas[mid]
            else:
                median = (deltas[mid - 1] + deltas[mid]) / 2.0
            signup_to_first_call_seconds = round(median, 2)
    except Exception:
        signup_to_first_call_seconds = None

    return {
        "stars_total": stars_total,
        "citations_mentioned": citations_mentioned,
        "keys_issued": keys_issued,
        "api_calls_served": api_calls_served,
        "signup_conversion_pct": signup_conversion_pct,
        "api_activation_pct": activation_pct,
        "enterprise_form_views": enterprise_form_views,
        "traffic_sources": traffic_sources,
        "signup_to_first_call_seconds": signup_to_first_call_seconds,
    }


async def _get_or_compute(db: AsyncSession) -> dict:
    cached = _cached_payload()
    if cached is not None:
        return cached
    payload = await _compute_full_payload(db)
    _store_cache(payload)
    return payload


# ------ Router --------------------------------------------------------------------


def build_router(get_db) -> APIRouter:
    router = APIRouter(tags=["metrics"])

    @router.get("/v1/metrics/launch")
    async def launch_metrics_public(db: AsyncSession = get_db) -> dict:
        full = await _get_or_compute(db)
        return {k: full[k] for k in PUBLIC_FIELDS}

    @router.get("/v1/metrics/launch/admin")
    async def launch_metrics_admin(
        db: AsyncSession = get_db,
        authorization: str | None = Header(default=None),
    ) -> dict:
        _require_admin(authorization)
        return await _get_or_compute(db)

    return router
