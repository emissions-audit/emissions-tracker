from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


def build_router(get_db) -> APIRouter:
    router = APIRouter(tags=["health"])

    @router.get("/health")
    def health():
        return {"status": "healthy", "version": "0.1.0"}

    @router.get("/ready")
    async def ready(db: AsyncSession = get_db):
        try:
            await db.execute(text("SELECT 1"))
            return {"status": "ready", "database": "connected"}
        except Exception:
            return {"status": "degraded", "database": "disconnected"}

    return router
