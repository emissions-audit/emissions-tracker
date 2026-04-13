from __future__ import annotations

import time

import httpx
from fastapi import APIRouter

GITHUB_OWNER = "emissions-audit"
GITHUB_REPO = "emissions-tracker"
GITHUB_API_URL = f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}"

CACHE_TTL_SECONDS = 300  # 5 minutes

_cache: dict[str, object] = {"data": None, "fetched_at": 0.0}


async def _fetch_github_stats() -> dict:
    now = time.monotonic()
    if _cache["data"] is not None and (now - _cache["fetched_at"]) < CACHE_TTL_SECONDS:
        return _cache["data"]

    headers = {"Accept": "application/vnd.github+json"}
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(GITHUB_API_URL, headers=headers)
        resp.raise_for_status()
        data = resp.json()

        # Contributors count requires a separate request (paginated).
        # Use the per_page=1 trick with the Link header to get total count.
        contributors_count = 0
        try:
            contrib_resp = await client.get(
                f"{GITHUB_API_URL}/contributors",
                headers=headers,
                params={"per_page": 1, "anon": "true"},
            )
            contrib_resp.raise_for_status()
            link_header = contrib_resp.headers.get("link", "")
            if 'rel="last"' in link_header:
                # Extract page number from last link
                last_part = [p for p in link_header.split(",") if 'rel="last"' in p][0]
                page_num = last_part.split("page=")[-1].split(">")[0]
                contributors_count = int(page_num)
            else:
                # Single page — count items directly
                contributors_count = len(contrib_resp.json())
        except Exception:
            contributors_count = 0

    result = {
        "stars": data.get("stargazers_count", 0),
        "forks": data.get("forks_count", 0),
        "open_issues": data.get("open_issues_count", 0),
        "contributors": contributors_count,
    }
    _cache["data"] = result
    _cache["fetched_at"] = now
    return result


def build_router(get_db) -> APIRouter:
    router = APIRouter(tags=["project"])

    @router.get("/v1/project-stats")
    async def project_stats():
        try:
            data = await _fetch_github_stats()
        except httpx.HTTPError:
            return {
                "stars": None,
                "forks": None,
                "open_issues": None,
                "contributors": None,
                "error": "Failed to fetch GitHub stats",
            }
        return data

    return router
