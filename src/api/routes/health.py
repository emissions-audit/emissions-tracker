from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session


def build_router(get_db) -> APIRouter:
    router = APIRouter(tags=["health"])

    @router.get("/health")
    def health():
        return {"status": "healthy", "version": "0.1.0"}

    @router.get("/ready")
    def ready(db: Session = get_db):
        try:
            db.execute(text("SELECT 1"))
            return {"status": "ready", "database": "connected"}
        except Exception:
            return {"status": "degraded", "database": "disconnected"}

    return router
