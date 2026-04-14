from __future__ import annotations

import secrets
import uuid

from fastapi import APIRouter, HTTPException, Request
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from src.shared.models import Webhook
from src.shared.schemas import (
    PaginatedResponse,
    WebhookCreate,
    WebhookResponse,
    WEBHOOK_EVENTS,
)


def build_router(get_db) -> APIRouter:
    r = APIRouter(prefix="/v1/webhooks", tags=["webhooks"])

    def _require_key(request: Request) -> uuid.UUID:
        key_id = getattr(request.state, "api_key_id", None)
        if key_id is None:
            raise HTTPException(status_code=401, detail="API key required for webhook management")
        return key_id

    @r.get("", response_model=PaginatedResponse)
    async def list_webhooks(request: Request, db: AsyncSession = get_db):
        key_id = _require_key(request)
        stmt = select(Webhook).where(Webhook.api_key_id == key_id)
        total = (await db.execute(select(func.count()).select_from(stmt.subquery()))).scalar() or 0
        items = (await db.execute(stmt)).scalars().all()
        return PaginatedResponse(
            items=[WebhookResponse.model_validate(w) for w in items],
            total=total,
            limit=total,
            offset=0,
        )

    @r.post("", response_model=WebhookResponse, status_code=201)
    async def create_webhook(body: WebhookCreate, request: Request, db: AsyncSession = get_db):
        key_id = _require_key(request)
        invalid = [e for e in body.events if e not in WEBHOOK_EVENTS]
        if invalid:
            raise HTTPException(
                status_code=422,
                detail=f"Invalid events: {invalid}. Valid: {WEBHOOK_EVENTS}",
            )
        webhook = Webhook(
            api_key_id=key_id,
            url=body.url,
            events=body.events,
            secret=secrets.token_hex(32),
            active=True,
        )
        db.add(webhook)
        await db.commit()
        await db.refresh(webhook)
        return WebhookResponse.model_validate(webhook)

    @r.get("/{webhook_id}", response_model=WebhookResponse)
    async def get_webhook(webhook_id: uuid.UUID, request: Request, db: AsyncSession = get_db):
        key_id = _require_key(request)
        result = await db.execute(
            select(Webhook).where(Webhook.id == webhook_id, Webhook.api_key_id == key_id)
        )
        webhook = result.scalars().first()
        if not webhook:
            raise HTTPException(status_code=404, detail="Webhook not found")
        return WebhookResponse.model_validate(webhook)

    @r.delete("/{webhook_id}", status_code=204)
    async def delete_webhook(webhook_id: uuid.UUID, request: Request, db: AsyncSession = get_db):
        key_id = _require_key(request)
        result = await db.execute(
            select(Webhook).where(Webhook.id == webhook_id, Webhook.api_key_id == key_id)
        )
        webhook = result.scalars().first()
        if not webhook:
            raise HTTPException(status_code=404, detail="Webhook not found")
        await db.delete(webhook)
        await db.commit()

    @r.patch("/{webhook_id}/deactivate", response_model=WebhookResponse)
    async def deactivate_webhook(
        webhook_id: uuid.UUID, request: Request, db: AsyncSession = get_db
    ):
        key_id = _require_key(request)
        result = await db.execute(
            select(Webhook).where(Webhook.id == webhook_id, Webhook.api_key_id == key_id)
        )
        webhook = result.scalars().first()
        if not webhook:
            raise HTTPException(status_code=404, detail="Webhook not found")
        webhook.active = False
        await db.commit()
        await db.refresh(webhook)
        return WebhookResponse.model_validate(webhook)

    @r.patch("/{webhook_id}/activate", response_model=WebhookResponse)
    async def activate_webhook(
        webhook_id: uuid.UUID, request: Request, db: AsyncSession = get_db
    ):
        key_id = _require_key(request)
        result = await db.execute(
            select(Webhook).where(Webhook.id == webhook_id, Webhook.api_key_id == key_id)
        )
        webhook = result.scalars().first()
        if not webhook:
            raise HTTPException(status_code=404, detail="Webhook not found")
        webhook.active = True
        await db.commit()
        await db.refresh(webhook)
        return WebhookResponse.model_validate(webhook)

    return r
