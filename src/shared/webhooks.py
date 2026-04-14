from __future__ import annotations

import hashlib
import hmac
import logging
import uuid
from datetime import datetime, timezone

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.shared.models import Webhook, WebhookDelivery

logger = logging.getLogger(__name__)

MAX_RETRIES = 3
TIMEOUT_SECONDS = 10


def sign_payload(secret: str, body: bytes) -> str:
    return hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


async def deliver(webhook: Webhook, event: str, data: dict, session: AsyncSession) -> bool:
    import json

    payload = {
        "event": event,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "data": data,
    }
    body = json.dumps(payload).encode()
    signature = sign_payload(webhook.secret, body)
    headers = {
        "Content-Type": "application/json",
        "X-Webhook-Signature": signature,
        "X-Webhook-Event": event,
        "X-Webhook-ID": str(uuid.uuid4()),
    }

    delivery = WebhookDelivery(
        webhook_id=webhook.id,
        event=event,
        payload=payload,
        attempts=0,
        success=False,
    )

    async with httpx.AsyncClient(timeout=TIMEOUT_SECONDS) as client:
        for attempt in range(1, MAX_RETRIES + 1):
            delivery.attempts = attempt
            try:
                resp = await client.post(str(webhook.url), content=body, headers=headers)
                delivery.status_code = resp.status_code
                if resp.status_code < 400:
                    delivery.success = True
                    break
            except httpx.HTTPError:
                logger.warning("Webhook delivery attempt %d failed for %s", attempt, webhook.url)

    session.add(delivery)
    await session.commit()
    return delivery.success


async def fire_event(event: str, data: dict, session: AsyncSession) -> int:
    result = await session.execute(
        select(Webhook).where(Webhook.active.is_(True))
    )
    webhooks = result.scalars().all()

    delivered = 0
    for wh in webhooks:
        if event in (wh.events or []):
            ok = await deliver(wh, event, data, session)
            if ok:
                delivered += 1
    return delivered


def fire_event_sync(event: str, data: dict, sync_session) -> int:
    """Fire webhook event from a synchronous pipeline context."""
    from sqlalchemy import select as sa_select

    webhooks = sync_session.execute(
        sa_select(Webhook).where(Webhook.active.is_(True))
    ).scalars().all()

    if not webhooks:
        return 0

    import asyncio

    async def _deliver_all():
        count = 0
        for wh in webhooks:
            if event not in (wh.events or []):
                continue
            import json as _json

            payload = {
                "event": event,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "data": data,
            }
            body = _json.dumps(payload).encode()
            signature = sign_payload(wh.secret, body)
            headers = {
                "Content-Type": "application/json",
                "X-Webhook-Signature": signature,
                "X-Webhook-Event": event,
                "X-Webhook-ID": str(uuid.uuid4()),
            }

            delivery = WebhookDelivery(
                webhook_id=wh.id, event=event, payload=payload, attempts=0, success=False,
            )

            async with httpx.AsyncClient(timeout=TIMEOUT_SECONDS) as client:
                for attempt in range(1, MAX_RETRIES + 1):
                    delivery.attempts = attempt
                    try:
                        resp = await client.post(str(wh.url), content=body, headers=headers)
                        delivery.status_code = resp.status_code
                        if resp.status_code < 400:
                            delivery.success = True
                            break
                    except httpx.HTTPError:
                        logger.warning(
                            "Webhook delivery attempt %d failed for %s", attempt, wh.url
                        )

            sync_session.add(delivery)
            if delivery.success:
                count += 1
        sync_session.commit()
        return count

    return asyncio.run(_deliver_all())
