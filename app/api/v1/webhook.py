import json

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession
from svix.webhooks import Webhook, WebhookVerificationError

from app.config.database import get_db
from app.config.logging_config import logger
from app.config.settings import settings
from app.schemas.webhook import WebhookAckResponse
from app.services import venue as venue_service
from app.utils.errors import ValidationError

router = APIRouter(prefix="/webhooks", tags=["Webhooks"])


def verify_webhook(payload: bytes, headers: dict) -> dict:
    """Verify the Svix signature of a Clerk webhook delivery and return the
    decoded event. Fail-closed: any missing/invalid ``svix-*`` header raises,
    and the endpoint answers 400 (Clerk only retries non-2xx).

    The signature must be checked before the payload is trusted, so this is a
    plain function (patchable in tests), not a FastAPI dependency.
    """
    if not settings.clerk_webhook_secret:
        logger.warning("CLERK_WEBHOOK_SECRET not configured; rejecting webhook delivery")
        raise WebhookVerificationError
    Webhook(settings.clerk_webhook_secret).verify(payload, headers)
    return json.loads(payload)


@router.post("/clerk", response_model=WebhookAckResponse)
async def clerk_webhook(request: Request, db: AsyncSession = Depends(get_db)):
    """Receive Clerk user lifecycle events for venue accounts (one Clerk account per venue).

    ``user.created`` links the new account to a new, empty venue (counter token, no positions,
    no events, placeholder name: the venue sets its name through the Venue endpoints).
    ``user.deleted`` removes the venue only if it never had an event; venues with claim
    history are kept (and logged) until contact retention exists. Handlers are idempotent
    (Clerk redelivers), every verified event is answered 200 and unknown types are ignored.
    """
    payload = await request.body()
    try:
        event = verify_webhook(payload, dict(request.headers))
    except (WebhookVerificationError, ValueError):
        logger.error("Webhook rejected: invalid or missing Svix signature")
        raise ValidationError("Invalid webhook signature")

    event_type = event.get("type")
    data = event.get("data") or {}
    clerk_id = data.get("id")

    if not event_type or not clerk_id:
        logger.warning("Webhook ignored: missing type or data.id")
        return WebhookAckResponse()

    if event_type == "user.created":
        venue = await venue_service.create_venue_for_account(db, clerk_id)
        logger.info("Webhook user.created: clerk user %s linked to venue %s", clerk_id, venue.id)

    elif event_type == "user.deleted":
        venue = await venue_service.find_venue_by_clerk_id(db, clerk_id)
        if venue is None:
            logger.info("Webhook user.deleted for clerk user %s without a venue; ignoring", clerk_id)
        elif await venue_service.remove_venue_for_account(db, clerk_id):
            logger.info("Webhook user.deleted: removed venue %s of clerk user %s", venue.id, clerk_id)
        else:
            logger.warning(
                "Webhook user.deleted: venue %s of clerk user %s has events; kept (clean up manually)",
                venue.id,
                clerk_id,
            )

    else:
        logger.info("Webhook event %s ignored", event_type)

    return WebhookAckResponse()
